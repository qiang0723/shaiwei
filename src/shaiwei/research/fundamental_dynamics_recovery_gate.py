"""Run the F2-0R legal-unestimable-row recovery data gate."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pandas as pd

from shaiwei.config import PROJECT_ROOT
from shaiwei.ingest.catalog import load_latest_api
from shaiwei.ledger import sha256_file
from shaiwei.provenance import git_head
from shaiwei.research.fundamental_dynamics_contract import verify_predecessor_effect
from shaiwei.research.fundamental_dynamics_features import FEATURE_IDS
from shaiwei.research.fundamental_dynamics_gate import build_dynamics_panel
from shaiwei.research.fundamental_dynamics_recovery_contract import (
    GO_VERDICT,
    NO_GO_VERDICT,
    FundamentalDynamicsRecoveryProtocol,
    verify_predecessor_data,
)
from shaiwei.research.fundamental_pit_contract import (
    FundamentalPitError,
    canonical_json,
    sha256_json,
    verify_source_evidence,
)
from shaiwei.research.fundamental_pit_gate import _write_json_once, _write_parquet_once


def recovery_null_diagnostics(panel: pd.DataFrame) -> dict[str, int]:
    current_missing = panel["current_end_date"].isna()
    predecessor_missing = panel["predecessor_end_date"].isna()
    pair_absent = current_missing & predecessor_missing
    partial_pair = current_missing ^ predecessor_missing
    any_feature = panel[list(FEATURE_IDS)].notna().any(axis=1)
    return {
        "pair_absent_rows": int(pair_absent.sum()),
        "pair_absent_rows_with_nonnull_available_date": int(
            (pair_absent & panel["available_date"].notna()).sum()
        ),
        "pair_absent_rows_with_any_nonnull_feature": int((pair_absent & any_feature).sum()),
        "pair_present_rows_missing_end_date": int(partial_pair.sum()),
    }


def recovery_gate_results(
    protocol: FundamentalDynamicsRecoveryProtocol,
    diagnostics: dict[str, Any],
    *,
    panel_sha256: str,
) -> dict[str, bool]:
    gates = protocol.document["gates"]
    count_gate = gates["membership_count_each_formation"]
    coverage = diagnostics["coverage"]
    expected_panel = protocol.document["predecessor"]["feature_panel_sha256"]
    return {
        "predecessor_identity_preserved": True,
        "panel_identical_to_v1": panel_sha256 == expected_panel,
        "calendar_scope": diagnostics["open_day_first"] <= "20160104"
        and diagnostics["open_day_last"] == "20260731",
        "formation_count": diagnostics["quality_formation_count"]
        >= int(str(gates["formation_dates_after_quality_start"]).split("_")[-1]),
        "membership_count": diagnostics["membership_min"] >= int(count_gate["minimum"])
        and diagnostics["membership_max"] <= int(count_gate["maximum"]),
        "bse_absent": diagnostics["bse_rows"] == int(gates["bse_rows"]),
        "unique_keys": diagnostics["duplicate_feature_keys"] == int(gates["duplicate_feature_keys"]),
        "no_current_mixed_periods": diagnostics["current_mixed_component_period_rows"]
        == int(gates["current_mixed_component_period_rows"]),
        "no_predecessor_mixed_periods": diagnostics["predecessor_mixed_component_period_rows"]
        == int(gates["predecessor_mixed_component_period_rows"]),
        "only_consecutive_pairs": diagnostics["nonconsecutive_pair_rows"]
        == int(gates["nonconsecutive_pair_rows"]),
        "no_future_availability": diagnostics["future_availability_rows"]
        == int(gates["future_availability_rows"]),
        "unestimable_available_date_null": diagnostics[
            "pair_absent_rows_with_nonnull_available_date"
        ]
        == int(gates["pair_absent_rows_with_nonnull_available_date"]),
        "unestimable_features_all_null": diagnostics["pair_absent_rows_with_any_nonnull_feature"]
        == int(gates["pair_absent_rows_with_any_nonnull_feature"]),
        "no_partial_pairs": diagnostics["pair_present_rows_missing_end_date"]
        == int(gates["pair_present_rows_missing_end_date"]),
        "no_source_conflicts": diagnostics["source_identity_conflicts"]
        == int(gates["source_identity_conflicts"]),
        "aggregate_coverage": all(
            value["aggregate"] >= float(gates["feature_aggregate_coverage_minimum"])
            for value in coverage.values()
        ),
        "worst_formation_coverage": all(
            value["worst_formation"] >= float(gates["feature_worst_formation_coverage_minimum"])
            for value in coverage.values()
        ),
    }


def _code_identity(project_root: Path) -> str:
    files = {
        "v1_contract": "src/shaiwei/research/fundamental_dynamics_contract.py",
        "v1_pairing": "src/shaiwei/research/fundamental_dynamics_pairing.py",
        "v1_features": "src/shaiwei/research/fundamental_dynamics_features.py",
        "v1_gate": "src/shaiwei/research/fundamental_dynamics_gate.py",
        "recovery_contract": "src/shaiwei/research/fundamental_dynamics_recovery_contract.py",
        "recovery_gate": "src/shaiwei/research/fundamental_dynamics_recovery_gate.py",
    }
    return sha256_json({name: sha256_file(project_root / path) for name, path in files.items()})


def run(
    protocol: FundamentalDynamicsRecoveryProtocol,
    *,
    project_root: Path = PROJECT_ROOT,
    manifest_output: Path | None = None,
) -> dict[str, Any]:
    predecessor = verify_predecessor_data(protocol, project_root=project_root)
    f1_effect = verify_predecessor_effect(protocol, project_root=project_root)
    source_evidence = verify_source_evidence(protocol)
    frames = {source_api: load_latest_api(source_api) for source_api in protocol.required_apis}
    panel, diagnostics = build_dynamics_panel(protocol, frames)
    diagnostics.update(recovery_null_diagnostics(panel))
    feature_path = protocol.project_path("ignored_feature_panel", project_root=project_root)
    feature_sha = _write_parquet_once(feature_path, panel)
    gates = recovery_gate_results(protocol, diagnostics, panel_sha256=feature_sha)
    verdict = GO_VERDICT if all(gates.values()) else NO_GO_VERDICT
    input_identity = sha256_json(
        {
            "protocol_sha256": protocol.sha256,
            "predecessor": predecessor,
            "f1_effect": f1_effect,
            "sources": source_evidence,
        }
    )
    report = {
        "schema_version": "f2-csi800-fundamental-dynamics-recovery-report-v2",
        "protocol_id": protocol.document["protocol_id"],
        "protocol_sha256": protocol.sha256,
        "input_snapshot_sha256": input_identity,
        "code_snapshot_sha256": _code_identity(project_root),
        "code_git_head": git_head(),
        "result_blind_claim": False,
        "predecessor": predecessor,
        "f1_effect": f1_effect,
        "source_evidence": source_evidence,
        "diagnostics": diagnostics,
        "gates": gates,
        "feature_panel": {"row_count": len(panel), "sha256": feature_sha},
        "factor_results_inspected": False,
        "model_training_run": False,
        "backtest_run": False,
        "deepseek_calls": 0,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "verdict": verdict,
    }
    report_path = protocol.project_path("ignored_report", project_root=project_root)
    report_sha = _write_json_once(report_path, report)
    manifest = {
        "schema_version": "f2-csi800-fundamental-dynamics-recovery-manifest-v2",
        "protocol_id": protocol.document["protocol_id"],
        "protocol_sha256": protocol.sha256,
        "input_snapshot_sha256": input_identity,
        "code_snapshot_sha256": report["code_snapshot_sha256"],
        "code_git_head": report["code_git_head"],
        "result_blind_claim": False,
        "predecessor": predecessor,
        "f1_effect": f1_effect,
        "report": {"path": report_path.relative_to(project_root).as_posix(), "sha256": report_sha},
        "feature_panel": {
            "path": feature_path.relative_to(project_root).as_posix(),
            "row_count": len(panel),
            "sha256": feature_sha,
        },
        "diagnostic_counts": {
            key: diagnostics[key]
            for key in (
                "quality_no_consecutive_pair_rows",
                "quality_newer_unpaired_common_period_rows",
                "pair_absent_rows",
                "pair_absent_rows_with_nonnull_available_date",
                "pair_absent_rows_with_any_nonnull_feature",
                "pair_present_rows_missing_end_date",
                "nonconsecutive_pair_rows",
                "future_availability_rows",
            )
        },
        "gates": gates,
        "coverage": diagnostics["coverage"],
        "factor_results_inspected": False,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "verdict": verdict,
    }
    _write_json_once(
        manifest_output or protocol.project_path("tracked_manifest", project_root=project_root),
        manifest,
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=PROJECT_ROOT / "config/f2_csi800_fundamental_dynamics_recovery_v2.yaml",
    )
    parser.add_argument("--manifest-output", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        result = run(
            FundamentalDynamicsRecoveryProtocol.load(args.protocol),
            manifest_output=args.manifest_output,
        )
    except (FundamentalPitError, OSError, RuntimeError, TypeError, ValueError) as error:
        print(canonical_json({"status": "FAIL", "error_class": type(error).__name__, "message": str(error)}))
        return 2
    print(canonical_json(result))
    return 0 if result["verdict"] == GO_VERDICT else 3


if __name__ == "__main__":
    raise SystemExit(main())

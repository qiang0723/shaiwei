"""Build and judge the offline F2-0 CSI800 fundamental dynamics data gate."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pandas as pd

from shaiwei.config import PROJECT_ROOT
from shaiwei.ingest.catalog import load_latest_api
from shaiwei.ledger import sha256_file
from shaiwei.provenance import git_head
from shaiwei.research.fundamental_dynamics_contract import (
    GO_VERDICT,
    NO_GO_VERDICT,
    FundamentalDynamicsProtocol,
    verify_predecessor_effect,
)
from shaiwei.research.fundamental_dynamics_features import FEATURE_IDS, calculate_dynamics
from shaiwei.research.fundamental_dynamics_pairing import (
    common_periods,
    latest_consecutive_pairs,
    pair_diagnostics,
    statement_periods,
)
from shaiwei.research.fundamental_pit_contract import (
    FundamentalPitError,
    canonical_json,
    sha256_json,
    verify_source_evidence,
)
from shaiwei.research.fundamental_pit_gate import (
    STATEMENT_FIELDS,
    _canonical_statement,
    _formation_dates,
    _members,
    _open_days,
    _with_availability,
    _write_json_once,
    _write_parquet_once,
)


def _build_periods(
    members: pd.DataFrame,
    frames: dict[str, pd.DataFrame],
    availability_days: list[str],
) -> tuple[dict[str, pd.DataFrame], dict[str, int], int]:
    periods: dict[str, pd.DataFrame] = {}
    source_rows: dict[str, int] = {}
    conflict_count = 0
    for name in STATEMENT_FIELDS:
        statement, conflicts = _canonical_statement(
            name,
            [frames[f"tushare.{name}"], frames[f"tushare.{name}_vip"]],
        )
        source_rows[name] = len(statement)
        conflict_count += conflicts
        periods[name] = statement_periods(
            members,
            _with_availability(statement, availability_days),
            name,
        )
    return periods, source_rows, conflict_count


def _coverage(panel: pd.DataFrame, quality_start: str) -> dict[str, dict[str, float]]:
    quality = panel.loc[panel["formation_date"].ge(quality_start)]
    result = {}
    for feature_id in FEATURE_IDS:
        by_date = quality.groupby("formation_date")[feature_id].apply(
            lambda values: float(values.notna().mean())
        )
        result[feature_id] = {
            "aggregate": float(quality[feature_id].notna().mean()),
            "worst_formation": float(by_date.min()) if not by_date.empty else 0.0,
        }
    return result


def build_dynamics_panel(
    protocol: FundamentalDynamicsProtocol,
    frames: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    scope = protocol.document["scope"]
    start = str(scope["start_date"]).replace("-", "")
    quality_start = str(scope["quality_start_date"]).replace("-", "")
    end = str(scope["end_date"]).replace("-", "")
    availability_days = _open_days(frames["tushare.trade_cal"], "19000101", end)
    open_days = [day for day in availability_days if day >= start]
    formations = _formation_dates(open_days)
    members = _members(frames["tushare.index_weight"], formations, str(scope["official_index_code"]))
    if members.empty:
        raise FundamentalPitError("F2-0 has no CSI800 formation members")
    periods, source_rows, conflict_count = _build_periods(members, frames, availability_days)
    common = common_periods(periods)
    panel, newer_unpaired = latest_consecutive_pairs(members, common)
    availability_columns = [
        *[f"current_{name}_available_date" for name in STATEMENT_FIELDS],
        *[f"predecessor_{name}_available_date" for name in STATEMENT_FIELDS],
    ]
    normalized = panel[availability_columns].astype("string").fillna("")
    panel["available_date"] = normalized.max(axis=1).replace("", pd.NA).where(
        panel["current_end_date"].notna()
    )
    panel = calculate_dynamics(panel)
    quality = panel.loc[panel["formation_date"].ge(quality_start)]
    diagnostics = {
        "open_day_count": len(open_days),
        "open_day_first": open_days[0],
        "open_day_last": open_days[-1],
        "formation_count": len(formations),
        "quality_formation_count": int(quality["formation_date"].nunique()),
        "member_rows": len(panel),
        "membership_min": int(quality.groupby("formation_date")["ts_code"].nunique().min()),
        "membership_max": int(quality.groupby("formation_date")["ts_code"].nunique().max()),
        "security_count": int(panel["ts_code"].nunique()),
        "bse_rows": int(panel["ts_code"].astype(str).str.endswith(".BJ").sum()),
        "quality_no_consecutive_pair_rows": int(quality["current_end_date"].isna().sum()),
        "newer_unpaired_common_period_rows": int(newer_unpaired.sum()),
        "quality_newer_unpaired_common_period_rows": int(
            (newer_unpaired & panel["formation_date"].ge(quality_start)).sum()
        ),
        "source_identity_conflicts": conflict_count,
        "canonical_annual_rows": source_rows,
        "coverage": _coverage(panel, quality_start),
        **pair_diagnostics(panel),
    }
    keep = [
        "formation_date",
        "ts_code",
        "membership_snapshot_date",
        "current_end_date",
        "predecessor_end_date",
        "available_date",
        *FEATURE_IDS,
    ]
    result = panel.loc[:, keep].sort_values(["formation_date", "ts_code"]).reset_index(drop=True)
    return result, diagnostics


def gate_results(protocol: FundamentalDynamicsProtocol, diagnostics: dict[str, Any]) -> dict[str, bool]:
    gates = protocol.document["gates"]
    count_gate = gates["membership_count_each_formation"]
    coverage = diagnostics["coverage"]
    return {
        "predecessor_identity_preserved": True,
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
        "quality_pair_complete": diagnostics["quality_no_consecutive_pair_rows"]
        == int(gates["quality_no_consecutive_pair_rows"]),
        "no_future_availability": diagnostics["future_availability_rows"]
        == int(gates["future_availability_rows"]),
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
        "f1_contract": "src/shaiwei/research/fundamental_pit_contract.py",
        "f1_gate_helpers": "src/shaiwei/research/fundamental_pit_gate.py",
        "contract": "src/shaiwei/research/fundamental_dynamics_contract.py",
        "pairing": "src/shaiwei/research/fundamental_dynamics_pairing.py",
        "features": "src/shaiwei/research/fundamental_dynamics_features.py",
        "gate": "src/shaiwei/research/fundamental_dynamics_gate.py",
    }
    return sha256_json({name: sha256_file(project_root / path) for name, path in files.items()})


def run(
    protocol: FundamentalDynamicsProtocol,
    *,
    project_root: Path = PROJECT_ROOT,
    manifest_output: Path | None = None,
) -> dict[str, Any]:
    predecessor = verify_predecessor_effect(protocol, project_root=project_root)
    source_evidence = verify_source_evidence(protocol)
    frames = {source_api: load_latest_api(source_api) for source_api in protocol.required_apis}
    panel, diagnostics = build_dynamics_panel(protocol, frames)
    gates = gate_results(protocol, diagnostics)
    verdict = GO_VERDICT if all(gates.values()) else NO_GO_VERDICT
    input_identity = sha256_json(
        {"protocol_sha256": protocol.sha256, "predecessor": predecessor, "sources": source_evidence}
    )
    feature_path = protocol.project_path("ignored_feature_panel", project_root=project_root)
    feature_sha = _write_parquet_once(feature_path, panel)
    report = {
        "schema_version": "f2-csi800-fundamental-dynamics-report-v1",
        "protocol_id": protocol.document["protocol_id"],
        "protocol_sha256": protocol.sha256,
        "input_snapshot_sha256": input_identity,
        "code_snapshot_sha256": _code_identity(project_root),
        "code_git_head": git_head(),
        "predecessor": predecessor,
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
        "schema_version": "f2-csi800-fundamental-dynamics-manifest-v1",
        "protocol_id": protocol.document["protocol_id"],
        "protocol_sha256": protocol.sha256,
        "input_snapshot_sha256": input_identity,
        "code_snapshot_sha256": report["code_snapshot_sha256"],
        "code_git_head": report["code_git_head"],
        "predecessor": predecessor,
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
                "newer_unpaired_common_period_rows",
                "quality_newer_unpaired_common_period_rows",
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
        default=PROJECT_ROOT / "config/f2_csi800_fundamental_dynamics_v1.yaml",
    )
    parser.add_argument("--manifest-output", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        result = run(FundamentalDynamicsProtocol.load(args.protocol), manifest_output=args.manifest_output)
    except (FundamentalPitError, OSError, RuntimeError, TypeError, ValueError) as error:
        print(canonical_json({"status": "FAIL", "error_class": type(error).__name__, "message": str(error)}))
        return 2
    print(canonical_json(result))
    return 0 if result["verdict"] == GO_VERDICT else 3


if __name__ == "__main__":
    raise SystemExit(main())

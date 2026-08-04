"""Run the released M4-1 effect gate and one complete deterministic replay."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.star50_residual.compute import CANDIDATES
from shaiwei.research.star50_residual_effect.contract import (
    EffectProtocol,
    EffectRelease,
    ResidualEffectError,
    canonical_sha256,
    project_path,
    sha256_file,
    verify_pushed_clean_state,
)
from shaiwei.research.star50_residual_effect.data import (
    build_extended_features,
    build_labels,
    load_inputs,
    neutralize,
)
from shaiwei.research.star50_residual_effect.evidence import (
    append_ledgers,
    code_bundle_sha256,
    save_pass,
    write_json,
)
from shaiwei.research.star50_residual_effect.judge import safe_judge_candidates
from shaiwei.research.star50_residual_effect.metrics import (
    direction_evidence,
    evaluate_candidate,
)


def _load_p2_protocol(protocol: EffectProtocol) -> dict[str, Any]:
    path = project_path(protocol.document["upstream_contract"]["p2_correction_protocol_path"])
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ResidualEffectError("M4-1 corrected P2 execution contract is invalid")
    return document


def _prediction_concat(predictions: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frame = pd.concat(
        [predictions[name] for name in ("test_2023", "test_2024", "test_2025")],
        ignore_index=True,
    ).sort_values(["trade_date", "ts_code"])
    if frame.duplicated(["trade_date", "ts_code"]).any():
        raise ResidualEffectError("M4-1 OOS Alpha158 predictions overlap")
    return frame.reset_index(drop=True)


def _run_pass(
    protocol: EffectProtocol,
    *,
    pass_name: str,
    result_root: Path,
) -> dict[str, Any]:
    inputs = load_inputs(protocol)
    features = build_extended_features(inputs, protocol)
    labels = build_labels(inputs, protocol)
    core = neutralize(features, inputs.members, predictions=None)
    directions = direction_evidence(core, labels, protocol.document)
    passing = [name for name, value in directions.items() if value["direction_pass"]]
    positions = {day: index for index, day in enumerate(inputs.calendar)}
    estimable_labels = labels.loc[labels["label"].notna()]
    integrity = {
        "m4_discovery_artifact_exact": True,
        "feature_window_never_after_signal": bool(
            features["window_end"].astype(str).le(features["trade_date"].astype(str)).all()
        ),
        "feature_keys_are_signal_day_members": len(
            features.merge(
                inputs.members[["trade_date", "ts_code"]],
                on=["trade_date", "ts_code"],
                how="inner",
                validate="one_to_one",
            )
        )
        == len(features),
        "label_entry_is_t_plus_1": bool(
            all(
                positions[row.entry_date] == positions[row.trade_date] + 1
                for row in estimable_labels.itertuples(index=False)
            )
        ),
        "label_exit_is_t_plus_11": bool(
            all(
                positions[row.exit_date] == positions[row.trade_date] + 11
                for row in estimable_labels.itertuples(index=False)
            )
        ),
        "bse_absent": not inputs.members["ts_code"].str.endswith(".BJ").any()
        and not features["ts_code"].str.endswith(".BJ").any(),
    }
    if not all(integrity.values()):
        raise ResidualEffectError(f"M4-1 PIT/shift integrity failed: {integrity}")

    incremental = pd.DataFrame(columns=["trade_date", "ts_code", *CANDIDATES])
    pressure_panels: dict[str, pd.DataFrame] = {}
    if passing:
        incremental = neutralize(
            features,
            inputs.members,
            predictions=_prediction_concat(inputs.predictions),
        )
        pressure_purpose = {
            str(row["name"]): str(row["alpha158_input_purpose"])
            for row in protocol.document["evaluation"]["pressure_periods"]
        }
        for name, purpose in pressure_purpose.items():
            pressure_panels[name] = neutralize(
                features,
                inputs.members,
                predictions=inputs.predictions[purpose],
            )
    p2_protocol = _load_p2_protocol(protocol)
    baseline_cache: dict[str, Any] = {}
    results = [
        evaluate_candidate(
            candidate,
            incremental_panel=incremental,
            pressure_panels=pressure_panels,
            labels=labels,
            predictions=inputs.predictions,
            market=inputs.market,
            members=inputs.members,
            benchmark=inputs.benchmark,
            protocol=protocol.document,
            p2_protocol=p2_protocol,
            baseline_cache=baseline_cache,
            factor_library_root=PROJECT_ROOT / "data/research/factor_library",
        )
        for candidate in CANDIDATES
        if candidate in passing
    ]
    decisions = safe_judge_candidates(results, directions, protocol.document, integrity)
    saved = save_pass(
        result_root / pass_name,
        features=features,
        core=core,
        incremental=incremental,
        results=results,
    )
    stable_results = [
        {key: value for key, value in row.items() if key not in {"return_rows", "ic_rows"}}
        for row in results
    ]
    return {
        "input_counts": {
            "member_days": int(len(inputs.members)),
            "market_rows": int(len(inputs.market)),
            "benchmark_rows": int(len(inputs.benchmark)),
            "extended_feature_rows": int(len(features)),
            "label_rows": int(labels["label"].notna().sum()),
            "core_rows": int(len(core)),
            "incremental_rows": int(len(incremental)),
            "bse_rows": int(
                inputs.members["ts_code"].str.endswith(".BJ").sum()
                + features["ts_code"].str.endswith(".BJ").sum()
            ),
        },
        "directions": directions,
        "integrity": integrity,
        "results": stable_results,
        "decisions": decisions,
        "saved": saved,
        "canonical": canonical_sha256(
            {
                "input_counts": {
                    "members": int(len(inputs.members)),
                    "features": int(len(features)),
                    "labels": int(labels["label"].notna().sum()),
                    "core": int(len(core)),
                    "incremental": int(len(incremental)),
                },
                "directions": directions,
                "integrity": integrity,
                "results": stable_results,
                "decisions": decisions,
                "artifacts": saved["canonical"],
            }
        ),
    }


def _input_snapshot(protocol: EffectProtocol) -> str:
    upstream = protocol.verify_upstream()
    return canonical_sha256(
        {
            "protocol_sha256": protocol.sha256,
            "upstream": upstream,
            "predictions": protocol.document["upstream_contract"]["corrected_prediction_inputs"],
        }
    )


def _paths(protocol: EffectProtocol) -> tuple[Path, Path, Path, Path]:
    identity = protocol.document["identity"]
    return (
        project_path(identity["result_root"]),
        project_path(identity["effect_report"]),
        project_path(identity["run_ledger"]),
        project_path(identity["decision_ledger"]),
    )


def _manifest(
    report: dict[str, Any],
    report_path: Path,
    report_sha256: str,
    run_ledger: Path,
    decision_ledger: Path,
) -> dict[str, Any]:
    return {
        "schema_version": "m4-star50-residual-effect-manifest-v1",
        "protocol_id": report["protocol_id"],
        "protocol_sha256": report["protocol_sha256"],
        "execution_release_sha256": report["execution_release_sha256"],
        "implementation_git_head": report["implementation_git_head"],
        "code_bundle_sha256": report["code_bundle_sha256"],
        "input_snapshot_sha256": report["input_snapshot_sha256"],
        "effect_report": {
            "path": report_path.relative_to(PROJECT_ROOT).as_posix(),
            "sha256": report_sha256,
        },
        "artifact_hashes": report["artifact_hashes"],
        "direction_pass_count": report["direction_pass_count"],
        "adapted_gate_pass_count": report["adapted_gate_pass_count"],
        "candidates": report["candidates"],
        "formal_g1_v1_status": report["formal_g1_v1_status"],
        "formal_factor_library_insertions": 0,
        "determinism_pass": report["determinism_pass"],
        "verdict": report["verdict"],
        "strategy_effective": report["strategy_effective"],
        "production_authorization": "none",
        "ledgers": {
            "runs": {
                "path": run_ledger.relative_to(PROJECT_ROOT).as_posix(),
                "sha256": sha256_file(run_ledger),
            },
            "decisions": {
                "path": decision_ledger.relative_to(PROJECT_ROOT).as_posix(),
                "sha256": sha256_file(decision_ledger),
            },
        },
    }


def run(protocol_path: Path, release_path: Path) -> dict[str, Any]:
    protocol = EffectProtocol.load(protocol_path)
    bundle = code_bundle_sha256()
    release = EffectRelease.load(release_path, protocol, code_bundle_sha256=bundle)
    result_root, report_path, run_ledger, decision_ledger = _paths(protocol)
    if report_path.exists():
        verify_pushed_clean_state(release)
        protocol.verify_upstream()
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report_sha = sha256_file(report_path)
        append_ledgers(
            report,
            report_sha,
            run_path=run_ledger,
            decision_path=decision_ledger,
        )
        manifest = _manifest(report, report_path, report_sha, run_ledger, decision_ledger)
        write_json(manifest, result_root / "manifest.json")
        return report

    release_head = verify_pushed_clean_state(release)
    input_snapshot = _input_snapshot(protocol)
    started_at = datetime.now(timezone.utc).isoformat()
    first = _run_pass(protocol, pass_name="first_pass", result_root=result_root)
    protocol.verify_upstream()
    replay = _run_pass(protocol, pass_name="determinism_replay", result_root=result_root)
    protocol.verify_upstream()
    determinism = {
        "canonical_equal": first["canonical"] == replay["canonical"],
        "artifact_canonical_equal": first["saved"]["canonical"]
        == replay["saved"]["canonical"],
        "artifact_physical_sha256_equal": first["saved"]["physical"]
        == replay["saved"]["physical"],
    }
    determinism_pass = all(determinism.values())
    if not determinism_pass:
        raise ResidualEffectError("M4-1 deterministic replay differs")
    decisions = first["decisions"]
    pass_count = sum(row["adapted_gate_decision"] == "PASS" for row in decisions)
    verdict = (
        protocol.document["decision_contract"]["verdict_on_any_candidate_pass"]
        if pass_count
        else protocol.document["decision_contract"]["verdict_on_no_candidate_pass"]
    )
    strategy_effective = (
        protocol.document["decision_contract"]["strategy_effective_on_go"]
        if pass_count
        else protocol.document["decision_contract"]["strategy_effective_on_failure"]
    )
    finished_at = datetime.now(timezone.utc).isoformat()
    run_id = f"m4-star50-residual-effect-v1-{input_snapshot[:12]}-{bundle[:12]}"
    report: dict[str, Any] = {
        "schema_version": "m4-star50-residual-effect-report-v1",
        "protocol_id": protocol.document["protocol_id"],
        "research_family": protocol.document["identity"]["research_family"],
        "run_id": run_id,
        "protocol_sha256": protocol.sha256,
        "execution_release_sha256": release.sha256,
        "implementation_git_head": release.document["implementation_git_head"],
        "release_git_head": release_head,
        "code_bundle_sha256": bundle,
        "input_snapshot_sha256": input_snapshot,
        "run_started_at": started_at,
        "run_finished_at": finished_at,
        "input_counts": first["input_counts"],
        "direction_evidence": first["directions"],
        "integrity": first["integrity"],
        "direction_pass_count": sum(
            bool(row["direction_pass"]) for row in first["directions"].values()
        ),
        "adapted_gate_pass_count": int(pass_count),
        "candidates": decisions,
        "determinism": determinism,
        "determinism_pass": determinism_pass,
        "artifact_hashes": {
            "first_pass_canonical": first["saved"]["canonical"],
            "first_pass_physical": first["saved"]["physical"],
            "determinism_replay_canonical": replay["saved"]["canonical"],
            "determinism_replay_physical": replay["saved"]["physical"],
        },
        "formal_g1_v1_status": protocol.document["evaluation"]["formal_g1_v1_status"],
        "formal_g1_v1_reason": protocol.document["evaluation"]["formal_g1_v1_reason"],
        "formal_factor_library_insertions": 0,
        "model_training_run": False,
        "network_requests": 0,
        "api_key_read": False,
        "strategy_results_inspected": True,
        "verdict": verdict,
        "strategy_effective": strategy_effective,
        "production_authorization": "none",
    }
    report_sha, _ = write_json(report, report_path)
    append_ledgers(report, report_sha, run_path=run_ledger, decision_path=decision_ledger)
    manifest = _manifest(report, report_path, report_sha, run_ledger, decision_ledger)
    write_json(manifest, result_root / "manifest.json")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--execution-release", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = run(args.protocol, args.execution_release)
    except (OSError, ResidualEffectError, TypeError, ValueError) as error:
        print(json.dumps({"status": "FAIL", "error_class": type(error).__name__}, sort_keys=True))
        return 2
    print(
        json.dumps(
            {
                "status": "PASS",
                "run_id": report["run_id"],
                "direction_pass_count": report["direction_pass_count"],
                "adapted_gate_pass_count": report["adapted_gate_pass_count"],
                "formal_g1_v1_status": report["formal_g1_v1_status"],
                "verdict": report["verdict"],
                "strategy_effective": report["strategy_effective"],
                "production_authorization": "none",
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

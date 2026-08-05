"""Independent read-only audit of completed M4-1 evidence."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import pandas as pd

from shaiwei.research.star50_residual_effect.contract import (
    EffectProtocol,
    ResidualEffectError,
    project_path,
    sha256_file,
)
from shaiwei.research.star50_residual_effect.evidence import (
    build_manifest,
    expected_ledger_rows,
    frame_hash,
)


SORT_KEYS = {
    "extended_features": ["trade_date", "ts_code"],
    "core_residuals": ["trade_date", "ts_code"],
    "incremental_residuals": ["trade_date", "ts_code"],
    "daily_executions": ["candidate", "window", "scenario", "trade_date"],
    "daily_rank_ic": ["candidate", "window", "series_type", "trade_date"],
}


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _candidate_decision_matches(row: dict[str, Any]) -> bool:
    if not row["direction"]["direction_pass"]:
        expected = "REJECT_DIRECTION"
        failed = {"pre_registered_direction"}
    else:
        expected = "PASS" if all(row["gates"].values()) else "REJECT"
        failed = {name for name, passed in row["gates"].items() if not passed}
    recorded = row["failed_gates"]
    return (
        row["adapted_gate_decision"] == expected
        and len(recorded) == len(set(recorded))
        and set(recorded) == failed
    )


def audit(protocol_path: Path) -> dict[str, Any]:
    protocol = EffectProtocol.load(protocol_path)
    protocol.verify_upstream()
    identity = protocol.document["identity"]
    report_path = project_path(identity["effect_report"])
    if not report_path.is_file():
        raise ResidualEffectError("M4-1 effect report is absent")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("protocol_sha256") != protocol.sha256:
        raise ResidualEffectError("M4-1 report protocol binding differs")
    physical_checks: dict[str, bool] = {}
    canonical_checks: dict[str, bool] = {}
    for pass_name, physical_key, canonical_key in (
        ("first_pass", "first_pass_physical", "first_pass_canonical"),
        (
            "determinism_replay",
            "determinism_replay_physical",
            "determinism_replay_canonical",
        ),
    ):
        for artifact, expected in report["artifact_hashes"][physical_key].items():
            path = project_path(f"{identity['result_root']}/{pass_name}/{artifact}.parquet")
            physical_checks[f"{pass_name}/{artifact}"] = sha256_file(path) == expected
            frame = pd.read_parquet(path)
            canonical_checks[f"{pass_name}/{artifact}"] = (
                frame_hash(frame, SORT_KEYS[artifact])
                == report["artifact_hashes"][canonical_key][artifact]
            )
    decision_checks: dict[str, bool] = {}
    for row in report["candidates"]:
        decision_checks[row["candidate"]] = _candidate_decision_matches(row)
    pass_count = sum(row["adapted_gate_decision"] == "PASS" for row in report["candidates"])
    verdict_expected = (
        protocol.document["decision_contract"]["verdict_on_any_candidate_pass"]
        if pass_count
        else protocol.document["decision_contract"]["verdict_on_no_candidate_pass"]
    )
    run_rows = _read_rows(project_path(identity["run_ledger"]))
    decision_rows = _read_rows(project_path(identity["decision_ledger"]))
    report_sha = sha256_file(report_path)
    expected_run, expected_decisions = expected_ledger_rows(report, report_sha)
    run_ledger = project_path(identity["run_ledger"])
    decision_ledger = project_path(identity["decision_ledger"])
    manifest_path = project_path(f"{identity['result_root']}/manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_manifest = build_manifest(
        report,
        report_path,
        report_sha,
        run_ledger,
        decision_ledger,
    )
    checks = {
        "physical_artifacts": all(physical_checks.values()),
        "canonical_artifacts": all(canonical_checks.values()),
        "first_replay_physical_equal": report["artifact_hashes"]["first_pass_physical"]
        == report["artifact_hashes"]["determinism_replay_physical"],
        "first_replay_canonical_equal": report["artifact_hashes"]["first_pass_canonical"]
        == report["artifact_hashes"]["determinism_replay_canonical"],
        "candidate_decisions": all(decision_checks.values()),
        "pit_and_shift_integrity": all(report["integrity"].values()),
        "pass_count": pass_count == int(report["adapted_gate_pass_count"]),
        "verdict": report["verdict"] == verdict_expected,
        "formal_g1_not_claimed": report["formal_g1_v1_status"]
        == "NOT_RUN_UNIVERSE_WINDOW_DOMAIN_MISMATCH",
        "no_formal_insertions": report["formal_factor_library_insertions"] == 0,
        "run_ledger_one_row": len(run_rows) == 1,
        "decision_ledger_three_rows": len(decision_rows) == 3,
        "run_ledger_exact": run_rows == [expected_run],
        "decision_ledger_exact": sorted(decision_rows, key=lambda row: row["decision_id"])
        == sorted(expected_decisions, key=lambda row: row["decision_id"]),
        "manifest_exact": manifest == expected_manifest,
        "production_authorization_none": report["production_authorization"] == "none",
    }
    if not all(checks.values()):
        raise ResidualEffectError(f"M4-1 independent audit failed: {checks}")
    return {
        "schema_version": "m4-star50-residual-effect-independent-audit-v1",
        "report_sha256": report_sha,
        "manifest_sha256": sha256_file(manifest_path),
        "physical_checks": physical_checks,
        "canonical_checks": canonical_checks,
        "decision_checks": decision_checks,
        "checks": checks,
        "status": "PASS",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = audit(args.protocol)
    except (OSError, ResidualEffectError, TypeError, ValueError) as error:
        print(json.dumps({"status": "FAIL", "error_class": type(error).__name__}, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

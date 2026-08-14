"""Offline evaluator for the frozen host-transport H00906 recovery."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from shaiwei.research.trend_swing.benchmark_lineage import (
    DAILY_PATH,
    FACTSHEET_PATH,
    FIRST_HISTORY_PATH,
    MANIFEST_DRAFT_PATH,
    REPORT_PATH,
    SECOND_HISTORY_PATH,
    OUTPUT_ROOT,
    load_recovery,
)
from shaiwei.research.trend_swing.benchmark_lineage_evidence import evaluate_and_persist
from shaiwei.research.trend_swing.contract import sha256_file


def validate_output_preflight(
    raw_directory: Path,
    targets: tuple[Path, ...],
) -> dict[str, object]:
    load_recovery()
    resolved_root = OUTPUT_ROOT.resolve()
    resolved_raw = raw_directory.resolve()
    if raw_directory.is_symlink() or not raw_directory.is_dir():
        raise RuntimeError("H00906 raw output directory is absent or a symlink")
    if not resolved_raw.is_relative_to(resolved_root):
        raise RuntimeError("H00906 raw output directory escapes the frozen root")
    if not os.access(resolved_raw, os.W_OK):
        raise RuntimeError("H00906 raw output directory is not writable")
    if any(target.exists() or target.is_symlink() for target in targets):
        raise RuntimeError("H00906 host-transfer target already exists")
    return {
        "verdict": "PASS",
        "raw_directory": raw_directory.as_posix(),
        "target_count": len(targets),
        "all_targets_absent": True,
    }


def run_once() -> dict:
    recovery = load_recovery()
    raw_paths = (FACTSHEET_PATH, FIRST_HISTORY_PATH, SECOND_HISTORY_PATH)
    if not all(path.is_file() and not path.is_symlink() for path in raw_paths):
        raise RuntimeError("host-transferred H00906 evidence is incomplete")
    if any(path.exists() for path in (DAILY_PATH, REPORT_PATH, MANIFEST_DRAFT_PATH)):
        raise RuntimeError("H00906 recovery evaluation was already consumed")
    frozen = recovery["frozen_raw_inputs"]
    expected_hashes = (
        (FACTSHEET_PATH, frozen["factsheet_sha256"]),
        (FIRST_HISTORY_PATH, frozen["history_first_sha256"]),
        (SECOND_HISTORY_PATH, frozen["history_second_sha256"]),
    )
    if any(sha256_file(path) != expected for path, expected in expected_hashes):
        raise RuntimeError("H00906 frozen raw input identity differs")
    report = evaluate_and_persist(
        FACTSHEET_PATH.read_bytes(),
        FIRST_HISTORY_PATH.read_bytes(),
        SECOND_HISTORY_PATH.read_bytes(),
        raw_already_persisted=True,
        transport_recovery={
            "prior_failed_transport_attempt_count": 2,
            "prior_offline_evaluation_attempt_count": 2,
            "recovery_completed_response_count": 3,
            "secret_read_count": 0,
        },
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "evaluate"), nargs="?", default="evaluate")
    args = parser.parse_args(argv)
    if args.action == "preflight":
        report = validate_output_preflight(
            FACTSHEET_PATH.parent,
            (FACTSHEET_PATH, FIRST_HISTORY_PATH, SECOND_HISTORY_PATH),
        )
        print(json.dumps(report, sort_keys=True))
        return 0
    report = run_once()
    print(
        json.dumps(
            {
                "verdict": report["verdict"],
                "row_count": report["row_count"],
                "first_date": report["first_date"],
                "last_date": report["last_date"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

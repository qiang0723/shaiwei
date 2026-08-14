"""Offline evaluator for the frozen host-transport H00906 recovery."""

from __future__ import annotations

import json

from shaiwei.research.trend_swing.benchmark_lineage import (
    DAILY_PATH,
    FACTSHEET_PATH,
    FIRST_HISTORY_PATH,
    MANIFEST_DRAFT_PATH,
    REPORT_PATH,
    SECOND_HISTORY_PATH,
    load_recovery,
)
from shaiwei.research.trend_swing.benchmark_lineage_evidence import evaluate_and_persist


def run_once() -> dict:
    load_recovery()
    raw_paths = (FACTSHEET_PATH, FIRST_HISTORY_PATH, SECOND_HISTORY_PATH)
    if not all(path.is_file() and not path.is_symlink() for path in raw_paths):
        raise RuntimeError("host-transferred H00906 evidence is incomplete")
    if any(path.exists() for path in (DAILY_PATH, REPORT_PATH, MANIFEST_DRAFT_PATH)):
        raise RuntimeError("H00906 recovery evaluation was already consumed")
    report = evaluate_and_persist(
        FACTSHEET_PATH.read_bytes(),
        FIRST_HISTORY_PATH.read_bytes(),
        SECOND_HISTORY_PATH.read_bytes(),
        raw_already_persisted=True,
        transport_recovery={
            "prior_failed_transport_attempt_count": 1,
            "recovery_completed_response_count": 3,
            "secret_read_count": 0,
        },
    )
    return report


def main() -> int:
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

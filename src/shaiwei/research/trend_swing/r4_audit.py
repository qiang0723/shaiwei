"""Independent aggregate audit for the one-shot TS-1A-R4 profile."""

from __future__ import annotations

import json
from typing import Any

import duckdb
import pyarrow.parquet as pq

from shaiwei.research.trend_swing.contract import TrendSwingError, sha256_file, write_once_json
from shaiwei.research.trend_swing.r4_contract import (
    ADDENDUM_PATH,
    AUDIT_PATH,
    DAILY_PATH,
    EVENT_PATH,
    PROTOCOL_PATH,
    REPORT_PATH,
)


FORBIDDEN_COLUMNS = {
    "return_after_entry",
    "pnl",
    "win_rate",
    "excess_return",
    "mae",
    "mfe",
    "sharpe",
    "drawdown",
    "alpha158_score",
    "alpha158_rank",
}


def _report() -> dict[str, Any]:
    value = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TrendSwingError("TS R4 report must be a mapping")
    return value


def audit_once() -> dict[str, Any]:
    if AUDIT_PATH.exists():
        raise TrendSwingError("TS R4 audit already exists; rerun is forbidden")
    report = _report()
    connection = duckdb.connect(":memory:")
    try:
        status_rows = connection.execute(
            "SELECT event_status,count(*) FROM read_parquet(?) GROUP BY 1 ORDER BY 1",
            [str(EVENT_PATH)],
        ).fetchall()
        year_rows = connection.execute(
            """
            SELECT substr(trade_date,1,4),count(*) FROM read_parquet(?)
            WHERE event_status='LEGAL_ENTRY_EVENT' GROUP BY 1 ORDER BY 1
            """,
            [str(EVENT_PATH)],
        ).fetchall()
        total, days = connection.execute(
            """
            SELECT count(*),count(DISTINCT trade_date) FROM read_parquet(?)
            WHERE event_status='LEGAL_ENTRY_EVENT'
              AND trade_date BETWEEN '20190101' AND '20241231'
            """,
            [str(EVENT_PATH)],
        ).fetchone()
    finally:
        connection.close()
    status = {str(key): int(value) for key, value in status_rows}
    yearly = {str(key): int(value) for key, value in year_rows}
    event = report["event_evidence"]
    artifact = report["machine_artifacts"]
    checks = {
        "protocol_hash_matches": report["protocol_identity"]["protocol_sha256"]
        == sha256_file(PROTOCOL_PATH),
        "addendum_hash_matches": report["protocol_identity"][
            "operationalization_addendum_sha256"
        ]
        == sha256_file(ADDENDUM_PATH),
        "event_hash_matches": artifact["true_event_intermediate"]["sha256"]
        == sha256_file(EVENT_PATH),
        "daily_hash_matches": artifact["anonymous_daily"]["sha256"]
        == sha256_file(DAILY_PATH),
        "event_row_count_matches": artifact["true_event_intermediate"]["row_count"]
        == pq.read_metadata(EVENT_PATH).num_rows,
        "daily_row_count_matches": artifact["anonymous_daily"]["row_count"]
        == pq.read_metadata(DAILY_PATH).num_rows,
        "status_counts_match": status == event["confirmed_event_status_counts"],
        "year_counts_match": yearly == event["legal_entry_event_count_by_calendar_year"],
        "evaluability_counts_match": [int(total), int(days)]
        == [
            event["evaluability_2019_2024"]["true_legal_entry_event_count"],
            event["evaluability_2019_2024"]["distinct_true_legal_entry_day_count"],
        ],
        "no_forbidden_event_columns": not (
            FORBIDDEN_COLUMNS & set(pq.read_schema(EVENT_PATH).names)
        ),
        "anonymous_daily_has_no_security_identity": "ts_code"
        not in pq.read_schema(DAILY_PATH).names,
        "result_blind": report["authority"]["result_blind"] is True,
        "zero_effect_attempts": report["authority"]["strategy_effect_attempt_count"] == 0,
        "strategy_not_evaluated": report["strategy_effective"] == "NOT_EVALUATED",
        "production_authorization_none": report["production_authorization"] == "none",
    }
    if not all(checks.values()):
        raise TrendSwingError(f"TS R4 independent audit failed: {checks}")
    audit = {
        "schema_version": "ts-v3-pullback-state-independent-audit-r4-v1",
        "report_sha256": sha256_file(REPORT_PATH),
        "event_sha256": sha256_file(EVENT_PATH),
        "daily_sha256": sha256_file(DAILY_PATH),
        "recomputed_status_counts": status,
        "recomputed_year_counts": yearly,
        "recomputed_evaluability_2019_2024": {
            "true_legal_entry_event_count": int(total),
            "distinct_true_legal_entry_day_count": int(days),
        },
        "checks": checks,
        "verdict": "PASS",
    }
    write_once_json(AUDIT_PATH, audit)
    return audit

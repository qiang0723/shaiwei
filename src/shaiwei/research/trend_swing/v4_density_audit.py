"""Independent artifact-level audit for TS-v4B density preflight."""

from __future__ import annotations

import json
from typing import Any

import duckdb
import pyarrow.parquet as pq

from shaiwei.research.trend_swing.contract import (
    TrendSwingError,
    project_path,
    sha256_file,
    write_once_json,
)
from shaiwei.research.trend_swing.v4_density_contract import (
    AUDIT_PATH,
    DAILY_PATH,
    EVENT_PATH,
    REPORT_PATH,
    V4DensityRelease,
    V4DensityRecovery,
    runtime_code_identity,
    validate_bound_inputs,
)


FORBIDDEN_EVENT_COLUMNS = {
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
    "baseline_score",
}


def _report() -> dict[str, Any]:
    value = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TrendSwingError("TS v4B report must be a mapping")
    return value


def _recompute(
    connection: duckdb.DuckDBPyConnection,
    release: V4DensityRelease,
) -> tuple[list[dict[str, Any]], list[str], list[list[str]]]:
    alpha_path = project_path(release.inputs["alpha158_path"])
    connection.from_parquet(str(alpha_path), hive_partitioning=False).project(
        "CAST(ts_code AS VARCHAR) AS ts_code,CAST(trade_date AS VARCHAR) AS trade_date"
    ).create_view("alpha_raw")
    duplicates = int(
        connection.execute(
            """
            SELECT count(*) FROM (SELECT ts_code,trade_date,count(*) n FROM alpha_raw
              GROUP BY 1,2 HAVING n>1)
            """
        ).fetchone()[0]
    )
    connection.execute("CREATE TEMP TABLE alpha_keys AS SELECT DISTINCT * FROM alpha_raw")
    gate = release.document["density_gate"]
    evidence: list[dict[str, Any]] = []
    for arm_id, depth in release.arms:
        status_rows = connection.execute(
            "SELECT event_status,count(*) FROM read_parquet(?) WHERE arm_id=? GROUP BY 1 ORDER BY 1",
            [str(EVENT_PATH), arm_id],
        ).fetchall()
        year_rows = connection.execute(
            """
            SELECT CAST(substr(trade_date,1,4) AS INTEGER),count(*) FROM read_parquet(?)
            WHERE arm_id=? AND event_status='LEGAL_ENTRY_EVENT' GROUP BY 1 ORDER BY 1
            """,
            [str(EVENT_PATH), arm_id],
        ).fetchall()
        total, days, matched = connection.execute(
            """
            SELECT count(*),count(DISTINCT e.trade_date),count(a.ts_code)
            FROM read_parquet(?) e LEFT JOIN alpha_keys a USING(ts_code,trade_date)
            WHERE e.arm_id=? AND e.event_status='LEGAL_ENTRY_EVENT'
            """,
            [str(EVENT_PATH), arm_id],
        ).fetchone()
        total, days, matched = int(total), int(days), int(matched)
        yearly = {str(year): int(count) for year, count in year_rows}
        coverage = matched / total if total else None
        checks = {
            "legal_events_at_least_30": total >= gate["per_arm_minimum_legal_events"],
            "signal_days_at_least_20": days >= gate["per_arm_minimum_distinct_signal_days"],
            "each_required_year_at_least_5": all(
                yearly.get(str(year), 0) >= gate["per_arm_minimum_events_each_calendar_year"]
                for year in gate["required_calendar_years"]
            ),
            "alpha158_keys_unique": duplicates
            == gate["alpha158_duplicate_event_key_count_required"],
            "alpha158_event_key_coverage_complete": coverage
            == gate["alpha158_event_key_coverage_required"],
        }
        evidence.append(
            {
                "arm_id": arm_id,
                "pullback_depth_fraction": depth,
                "confirmed_event_status_counts": {
                    str(status): int(count) for status, count in status_rows
                },
                "legal_event_count": total,
                "distinct_signal_day_count": days,
                "legal_event_count_by_calendar_year": yearly,
                "alpha158_event_keys": {
                    "allowed_columns": ["ts_code", "trade_date"],
                    "global_duplicate_key_count": duplicates,
                    "matched_legal_event_key_count": matched,
                    "coverage": coverage,
                    "score_or_rank_read": False,
                },
                "density_gate_checks": checks,
                "pass": all(checks.values()),
            }
        )
    passing = [item["arm_id"] for item in evidence if item["pass"]]
    pairs = [list(pair) for pair in release.adjacent_pairs if all(x in passing for x in pair)]
    return evidence, passing, pairs


def audit_once() -> dict[str, Any]:
    if AUDIT_PATH.exists():
        raise TrendSwingError("TS v4B audit already exists; same-scope rerun is forbidden")
    release = V4DensityRelease.load()
    recovery = V4DensityRecovery.load(release)
    validate_bound_inputs(release)
    report = _report()
    identity = runtime_code_identity()
    connection = duckdb.connect(":memory:")
    try:
        evidence, passing, pairs = _recompute(connection, release)
    finally:
        connection.close()
    expected_verdict = release.document["density_gate"][
        "pass_verdict"
        if len(pairs) >= release.document["density_gate"]["minimum_passing_adjacent_pair_count"]
        else "failure_verdict"
    ]
    artifacts = report["machine_artifacts"]
    checks = {
        "release_hash_matches": report["release_identity"]["release_sha256"]
        == release.sha256,
        "recovery_hash_matches": report["release_identity"]["recovery_sha256"]
        == recovery.sha256,
        "runtime_git_head_matches": report["release_identity"]["git_head"]
        == identity["git_head"],
        "runtime_snapshot_matches": report["release_identity"]["code_snapshot_sha256"]
        == identity["code_snapshot_sha256"],
        "event_hash_matches": artifacts["arm_event_intermediate"]["sha256"]
        == sha256_file(EVENT_PATH),
        "daily_hash_matches": artifacts["anonymous_arm_daily"]["sha256"]
        == sha256_file(DAILY_PATH),
        "event_rows_match": artifacts["arm_event_intermediate"]["row_count"]
        == pq.read_metadata(EVENT_PATH).num_rows,
        "daily_rows_match": artifacts["anonymous_arm_daily"]["row_count"]
        == pq.read_metadata(DAILY_PATH).num_rows,
        "arm_evidence_matches": evidence == report["arm_evidence"],
        "passing_arms_match": passing == report["passing_arms"],
        "passing_pairs_match": pairs == report["passing_adjacent_pairs"],
        "verdict_matches": expected_verdict == report["verdict"],
        "no_forbidden_event_columns": not (
            FORBIDDEN_EVENT_COLUMNS & set(pq.read_schema(EVENT_PATH).names)
        ),
        "anonymous_daily_has_no_security_identity": "ts_code"
        not in pq.read_schema(DAILY_PATH).names,
        "result_blind": report["authority"]["result_blind"] is True,
        "zero_effect_attempts": report["authority"]["strategy_effect_attempt_count"] == 0,
        "strategy_not_evaluated": report["strategy_effective"] == "NOT_EVALUATED",
        "production_authorization_none": report["production_authorization"] == "none",
    }
    if not all(checks.values()):
        raise TrendSwingError(f"TS v4B independent audit failed: {checks}")
    audit = {
        "schema_version": "ts-v4-density-preflight-independent-audit-v1",
        "report_sha256": sha256_file(REPORT_PATH),
        "event_sha256": sha256_file(EVENT_PATH),
        "daily_sha256": sha256_file(DAILY_PATH),
        "recomputed_arm_evidence": evidence,
        "recomputed_passing_arms": passing,
        "recomputed_passing_adjacent_pairs": pairs,
        "checks": checks,
        "verdict": "PASS",
    }
    write_once_json(AUDIT_PATH, audit)
    return audit

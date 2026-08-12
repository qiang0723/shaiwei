"""Independent aggregate-only audit for the one-shot TS-1A-R2 profile."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb
import pyarrow.parquet as pq

from shaiwei.research.trend_swing.contract import (
    FORBIDDEN_RESULT_TERMS,
    TrendSwingError,
    canonical_sha256,
    sha256_file,
    write_once_json,
)
from shaiwei.research.trend_swing.recovery_candidate import CANDIDATE_EVENT_PATH
from shaiwei.research.trend_swing.recovery_contract import (
    AUDIT_PATH,
    DAILY_PROFILE_PATH,
    MANIFEST_PATH,
    PROFILE_PATH,
    RecoveryAddendum,
    RecoveryProtocol,
    RecoveryR2,
    RecoveryR2Addendum,
    RecoveryRelease,
)
from shaiwei.research.trend_swing.recovery_r3_contract import RecoveryR3


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TrendSwingError(f"TS recovery audit expected mapping: {path.name}")
    return value


def _keys(value: Any) -> set[str]:
    result: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            result.add(str(key).lower())
            result.update(_keys(child))
    elif isinstance(value, list):
        for child in value:
            result.update(_keys(child))
    return result


def _recompute_daily(path: Path) -> dict[str, int]:
    connection = duckdb.connect(":memory:")
    try:
        row = connection.execute(
            """
            SELECT count(*),sum(candidate_count),count(*) FILTER(WHERE candidate_count>0),
                   sum(candidate_next_open_executable_count)
            FROM read_parquet(?,hive_partitioning=false)
            """,
            [str(path)],
        ).fetchone()
    finally:
        connection.close()
    return {
        "trade_day_count": int(row[0]),
        "candidate_events": int(row[1] or 0),
        "days_with_candidates": int(row[2] or 0),
        "candidate_next_open_executable_events": int(row[3] or 0),
    }


def _recompute_candidate_intermediate(path: Path) -> dict[str, int]:
    connection = duckdb.connect(":memory:")
    try:
        row = connection.execute(
            """
            SELECT count(*),count(DISTINCT trade_date),
                   sum(next_open_executable::INTEGER)
            FROM read_parquet(?,hive_partitioning=false)
            """,
            [str(path)],
        ).fetchone()
    finally:
        connection.close()
    return {
        "candidate_events": int(row[0]),
        "days_with_candidates": int(row[1]),
        "candidate_next_open_executable_events": int(row[2] or 0),
    }


def audit_offline_once() -> dict[str, Any]:
    if AUDIT_PATH.exists():
        raise TrendSwingError("TS recovery independent audit already exists; rerun is forbidden")
    protocol = RecoveryProtocol.load()
    addendum = RecoveryAddendum.load(protocol)
    recovery_r2 = RecoveryR2.load(protocol, addendum)
    recovery_r2_addendum = RecoveryR2Addendum.load(recovery_r2)
    recovery_r3 = RecoveryR3.load(recovery_r2, recovery_r2_addendum)
    release = RecoveryRelease.load(
        protocol, addendum, recovery_r2, recovery_r2_addendum, recovery_r3
    )
    manifest = _load(MANIFEST_PATH)
    report = _load(PROFILE_PATH)
    daily = _recompute_daily(DAILY_PROFILE_PATH)
    candidate_counts = _recompute_candidate_intermediate(CANDIDATE_EVENT_PATH)
    funnel = report["anonymous_candidate_profile"]["funnel"]
    candidate_meta = report["machine_artifacts"]["candidate_event_intermediate"]
    candidate_schema = pq.read_schema(CANDIDATE_EVENT_PATH).names
    checks = {
        "protocol_hashes_match": report["protocol_identity"]
        == {
            "recovery_protocol_sha256": protocol.sha256,
            "operationalization_addendum_sha256": addendum.sha256,
            "recovery_r2_protocol_sha256": recovery_r2.sha256,
            "recovery_r2_addendum_sha256": recovery_r2_addendum.sha256,
            "recovery_r3_protocol_sha256": recovery_r3.sha256,
            "release_scope_sha256": release.scope_sha256,
        },
        "manifest_binding_matches": report["input_manifest_sha256"] == canonical_sha256(manifest),
        "manifest_file_hash_matches": report["input_manifest_file_sha256"]
        == sha256_file(MANIFEST_PATH),
        "daily_file_hash_matches": report["machine_artifacts"]["anonymous_daily_profile"]["sha256"]
        == sha256_file(DAILY_PROFILE_PATH),
        "daily_row_count_matches": report["machine_artifacts"]["anonymous_daily_profile"]["row_count"]
        == pq.read_metadata(DAILY_PROFILE_PATH).num_rows == daily["trade_day_count"],
        "candidate_count_recomputed": daily["candidate_events"] == funnel["candidate_events"],
        "candidate_days_recomputed": daily["days_with_candidates"] == funnel["days_with_candidates"],
        "candidate_intermediate_count_matches": pq.read_metadata(CANDIDATE_EVENT_PATH).num_rows
        == candidate_meta["row_count"] == funnel["candidate_events"],
        "candidate_intermediate_aggregates_match": candidate_counts
        == {
            "candidate_events": funnel["candidate_events"],
            "days_with_candidates": funnel["days_with_candidates"],
            "candidate_next_open_executable_events": funnel[
                "candidate_next_open_executable_events"
            ],
        },
        "candidate_intermediate_hash_matches": sha256_file(CANDIDATE_EVENT_PATH)
        == candidate_meta["sha256"],
        "candidate_intermediate_has_no_outcome": not {
            "return_after_entry", "win_rate", "pnl", "excess_return", "mae", "mfe",
            "sharpe", "drawdown",
        }.intersection(name.lower() for name in candidate_schema),
        "next_open_count_recomputed": daily["candidate_next_open_executable_events"]
        == funnel["candidate_next_open_executable_events"],
        "result_blind": report["authority"]["result_blind"] is True,
        "zero_effect_attempts": report["authority"]["strategy_effect_attempt_count"] == 0,
        "strategy_not_evaluated": report["strategy_effective"] == "NOT_EVALUATED",
        "production_authorization_none": report["production_authorization"] == "none",
        "no_forbidden_result_keys": not (_keys(report) & FORBIDDEN_RESULT_TERMS),
        "no_security_identity_in_daily_profile": pq.read_schema(DAILY_PROFILE_PATH).names
        == [
            "trade_date", "eligible_member_count", "market_pass_count", "sector_pass_count",
            "cap_pass_count", "weekly_amount_pass_count", "monthly_high_pass_count",
            "weekly_low_pass_count", "weekly_close_pass_count", "candidate_count",
            "candidate_daily_amount_bonus_count", "candidate_next_open_executable_count",
        ],
    }
    if not all(checks.values()):
        raise TrendSwingError(f"TS recovery independent audit failed: {checks}")
    audit = {
        "schema_version": "ts-v3-data-recovery-independent-audit-r2-v1",
        "report_sha256": sha256_file(PROFILE_PATH),
        "manifest_sha256": sha256_file(MANIFEST_PATH),
        "anonymous_daily_profile_sha256": sha256_file(DAILY_PROFILE_PATH),
        "recomputed_aggregates": daily,
        "recomputed_candidate_intermediate": candidate_counts,
        "checks": checks,
        "verdict": "PASS",
    }
    write_once_json(AUDIT_PATH, audit)
    return audit

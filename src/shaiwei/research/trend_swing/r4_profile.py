"""One-shot, aggregate-only TS-1A-R4 result-blind profile."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import duckdb
import pyarrow.parquet as pq

from shaiwei.config import PROJECT_ROOT
from shaiwei.provenance import code_snapshot_sha256, git_head
from shaiwei.research.trend_swing.contract import (
    ALPHA158_PATH,
    TrendSwingError,
    canonical_sha256,
    sha256_file,
    write_once_json,
)
from shaiwei.research.trend_swing.r4_contract import (
    AUDIT_PATH,
    DAILY_PATH,
    EVENT_PATH,
    R3_MANIFEST_PATH,
    R4_OUTPUT_DIR,
    REPORT_PATH,
    R4Addendum,
    R4Protocol,
    load_r3_manifest,
    validate_bound_inputs,
)
from shaiwei.research.trend_swing.r4_state import prepare_r4_state
from shaiwei.research.trend_swing.recovery_market import prepare_market_and_sector
from shaiwei.research.trend_swing.recovery_store import configure_store, prepare_core_tables


def benchmark_preflight(manifest: dict[str, Any]) -> dict[str, Any]:
    sources = manifest.get("sources", {})
    matches: list[dict[str, Any]] = []
    for source_api, source in sources.items():
        if "H00906" in str(source_api).upper():
            matches.append({"source_api": source_api, "artifact_count": 0})
        for artifact in source.get("artifacts", []):
            metadata = {
                "path": artifact.get("path"),
                "params": artifact.get("params"),
                "source_api": artifact.get("source_api"),
            }
            if "H00906" in json.dumps(metadata, ensure_ascii=False).upper():
                matches.append({"source_api": source_api, "artifact_count": 1})
    return {
        "logical_identifier": "CSI_H00906_TOTAL_RETURN",
        "search_scope": "R3_BOUND_INPUT_MANIFEST_METADATA_ONLY",
        "matching_metadata_count": len(matches),
        "bound": bool(matches),
        "price_index_substitution_used": False,
        "locally_derived_proxy_used": False,
        "verdict": "PASS" if matches else "BLOCKED_BENCHMARK_DATA",
    }


def _alpha_coverage(
    connection: duckdb.DuckDBPyConnection,
    alpha_path: Path,
) -> dict[str, Any]:
    path = alpha_path.resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()) or not path.is_file():
        raise TrendSwingError("TS R4 Alpha158 cache is absent or escapes project root")
    connection.from_parquet(str(path), hive_partitioning=False).project(
        "CAST(ts_code AS VARCHAR) AS ts_code,CAST(trade_date AS VARCHAR) AS trade_date"
    ).create_view("r4_alpha_keys_raw")
    duplicate = int(
        connection.execute(
            """
            SELECT count(*) FROM (
              SELECT ts_code,trade_date,count(*) AS n FROM r4_alpha_keys_raw
              GROUP BY 1,2 HAVING n>1
            )
            """
        ).fetchone()[0]
    )
    row = connection.execute(
        """
        SELECT count(*) AS denominator,count(a.ts_code) AS matched
        FROM r4_events e LEFT JOIN r4_alpha_keys_raw a USING(ts_code,trade_date)
        WHERE e.event_status='LEGAL_ENTRY_EVENT'
          AND e.trade_date BETWEEN '20190101' AND '20241231'
        """
    ).fetchone()
    denominator, matched = (int(value or 0) for value in row)
    coverage = matched / denominator if denominator else None
    return {
        "allowed_columns": ["ts_code", "trade_date"],
        "duplicate_key_count": duplicate,
        "true_event_count": denominator,
        "matched_true_event_key_count": matched,
        "event_key_coverage": coverage,
        "prediction_values_or_ranks_read": False,
        "pass": duplicate == 0 and denominator > 0 and coverage == 1.0,
    }


def _event_summary(connection: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    status_rows = connection.execute(
        "SELECT event_status,count(*) FROM r4_events GROUP BY 1 ORDER BY 1"
    ).fetchall()
    year_rows = connection.execute(
        """
        SELECT CAST(substr(trade_date,1,4) AS INTEGER) AS calendar_year,count(*) AS n
        FROM r4_events WHERE event_status='LEGAL_ENTRY_EVENT'
        GROUP BY 1 ORDER BY 1
        """
    ).fetchall()
    yearly = {str(year): int(count) for year, count in year_rows}
    row = connection.execute(
        """
        SELECT count(*) AS true_events,count(DISTINCT trade_date) AS true_event_days
        FROM r4_events WHERE event_status='LEGAL_ENTRY_EVENT'
          AND trade_date BETWEEN '20190101' AND '20241231'
        """
    ).fetchone()
    total, days = (int(value or 0) for value in row)
    required_years = tuple(range(2019, 2025))
    gate_checks = {
        "event_count_at_least_60": total >= 60,
        "event_days_at_least_40": days >= 40,
        "each_year_at_least_3": all(yearly.get(str(year), 0) >= 3 for year in required_years),
        "at_least_4_years_have_8": sum(
            yearly.get(str(year), 0) >= 8 for year in required_years
        )
        >= 4,
    }
    return {
        "confirmed_event_status_counts": {
            str(status): int(count) for status, count in status_rows
        },
        "legal_entry_event_count_by_calendar_year": yearly,
        "evaluability_2019_2024": {
            "true_legal_entry_event_count": total,
            "distinct_true_legal_entry_day_count": days,
            "checks": gate_checks,
            "pass": all(gate_checks.values()),
        },
    }


def _write_artifacts(connection: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    if EVENT_PATH.exists() or DAILY_PATH.exists():
        raise TrendSwingError("TS R4 profile artifacts already exist; rerun is forbidden")
    R4_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    connection.execute(
        """
        COPY (
          SELECT ts_code,trade_date,market_rank,plan_week,industry,segment,first_touch_date,
                 source_week,week_vwap,initial_structure_stop,confirmation_adj_factor,
                 next_trade_date,next_adjusted_open,next_adj_factor,next_volume_shares,
                 next_day_eligible,stop_distance,event_status
          FROM r4_events ORDER BY trade_date,ts_code
        ) TO ? (FORMAT PARQUET,COMPRESSION ZSTD)
        """,
        [str(EVENT_PATH)],
    )
    connection.execute(
        """
        COPY (
          SELECT d.trade_date,
                 count(DISTINCT c.ts_code) AS confirmed_event_count,
                 count(DISTINCT e.ts_code) FILTER(WHERE e.event_status='LEGAL_ENTRY_EVENT')
                   AS legal_entry_event_count
          FROM open_days d
          LEFT JOIN r4_confirmed_events c USING(trade_date)
          LEFT JOIN r4_events e USING(ts_code,trade_date)
          GROUP BY 1 ORDER BY 1
        ) TO ? (FORMAT PARQUET,COMPRESSION ZSTD)
        """,
        [str(DAILY_PATH)],
    )
    return {
        "true_event_intermediate": {
            "path": EVENT_PATH.relative_to(PROJECT_ROOT).as_posix(),
            "row_count": pq.read_metadata(EVENT_PATH).num_rows,
            "sha256": sha256_file(EVENT_PATH),
            "contains_security_identity": True,
            "contains_post_entry_outcome": False,
            "gitignored": True,
        },
        "anonymous_daily": {
            "path": DAILY_PATH.relative_to(PROJECT_ROOT).as_posix(),
            "row_count": pq.read_metadata(DAILY_PATH).num_rows,
            "sha256": sha256_file(DAILY_PATH),
            "contains_security_identity": False,
            "gitignored": True,
        },
    }


def run_profile_once() -> dict[str, Any]:
    if REPORT_PATH.exists() or AUDIT_PATH.exists():
        raise TrendSwingError("TS R4 report or audit already exists; rerun is forbidden")
    protocol = R4Protocol.load()
    addendum = R4Addendum.load(protocol)
    validate_bound_inputs(protocol)
    manifest = load_r3_manifest()
    connection = duckdb.connect(":memory:")
    try:
        configure_store(connection, R4_OUTPUT_DIR / "duckdb-tmp")
        prepare_core_tables(
            connection,
            manifest,
            start_date=protocol.start_date,
            end_date=protocol.end_date,
        )
        prepare_market_and_sector(connection)
        prepare_r4_state(connection)
        events = _event_summary(connection)
        alpha = _alpha_coverage(connection, ALPHA158_PATH)
        artifacts = _write_artifacts(connection)
    finally:
        connection.close()
    benchmark = benchmark_preflight(manifest)
    event_pass = events["evaluability_2019_2024"]["pass"] and alpha["pass"]
    event_verdict = (
        "GO_TRUE_EVENT_SAMPLE" if event_pass else "STOP_INSUFFICIENT_TRUE_EVENTS"
    )
    if not event_pass:
        overall = "STOP_INSUFFICIENT_TRUE_EVENTS"
    elif benchmark["verdict"] != "PASS":
        overall = "BLOCKED_BENCHMARK_DATA"
    else:
        overall = "GO_TS_V3_EFFECT_PROTOCOL_FREEZE"
    report = {
        "schema_version": "ts-v3-pullback-state-profile-r4-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "protocol_identity": {
            "protocol_sha256": protocol.sha256,
            "operationalization_addendum_sha256": addendum.sha256,
            "r3_manifest_file_sha256": sha256_file(R3_MANIFEST_PATH),
        },
        "code_identity": {
            "git_head": git_head(),
            "code_snapshot_sha256": code_snapshot_sha256(),
        },
        "authority": {
            "result_blind": True,
            "strategy_effect_attempt_count": 0,
            "post_entry_outcome_read": False,
            "alpha158_prediction_values_or_ranks_read": False,
            "network_or_secret_read": False,
            "production_authorization": "none",
        },
        "event_evidence": events,
        "alpha158_key_only": alpha,
        "benchmark_preflight": benchmark,
        "machine_artifacts": artifacts,
        "event_gate_verdict": event_verdict,
        "benchmark_gate_verdict": benchmark["verdict"],
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "verdict": overall,
    }
    report["canonical_payload_sha256"] = canonical_sha256(report)
    write_once_json(REPORT_PATH, report)
    return report

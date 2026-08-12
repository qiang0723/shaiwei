"""One-shot aggregate TS-v4B discovery density profile."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import pyarrow.parquet as pq

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.trend_swing.contract import (
    TrendSwingError,
    canonical_sha256,
    project_path,
    sha256_file,
    write_once_json,
)
from shaiwei.research.trend_swing.r4_contract import load_r3_manifest
from shaiwei.research.trend_swing.recovery_market import prepare_market_and_sector
from shaiwei.research.trend_swing.recovery_store import configure_store, prepare_core_tables
from shaiwei.research.trend_swing.v4_density_contract import (
    AUDIT_PATH,
    DAILY_PATH,
    EVENT_PATH,
    OUTPUT_DIR,
    REPORT_PATH,
    V4DensityRelease,
    V4DensityRecovery,
    runtime_code_identity,
    validate_bound_inputs,
)
from shaiwei.research.trend_swing.v4_density_state import prepare_v4_density_state


def mature_signal_end(
    connection: duckdb.DuckDBPyConnection,
    discovery_end: str,
    purge_count: int,
) -> str:
    row = connection.execute(
        """
        SELECT trade_date FROM open_days WHERE trade_date<=?
        ORDER BY trade_date DESC LIMIT 1 OFFSET ?
        """,
        [discovery_end, purge_count],
    ).fetchone()
    if row is None:
        raise TrendSwingError("TS v4B cannot determine the mature discovery signal end")
    return str(row[0])


def prepare_alpha_keys(
    connection: duckdb.DuckDBPyConnection,
    path: Path,
) -> int:
    resolved = project_path(path)
    if not resolved.is_file():
        raise TrendSwingError("TS v4B Alpha158 cache is absent")
    connection.from_parquet(str(resolved), hive_partitioning=False).project(
        "CAST(ts_code AS VARCHAR) AS ts_code,CAST(trade_date AS VARCHAR) AS trade_date"
    ).create_view("v4_alpha_keys_raw")
    duplicate = int(
        connection.execute(
            """
            SELECT count(*) FROM (
              SELECT ts_code,trade_date,count(*) AS n FROM v4_alpha_keys_raw
              GROUP BY 1,2 HAVING n>1
            )
            """
        ).fetchone()[0]
    )
    connection.execute(
        "CREATE TEMP TABLE v4_alpha_keys AS SELECT DISTINCT * FROM v4_alpha_keys_raw"
    )
    return duplicate


def _arm_evidence(
    connection: duckdb.DuckDBPyConnection,
    release: V4DensityRelease,
    start: str,
    end: str,
    duplicate_alpha_keys: int,
) -> list[dict[str, Any]]:
    gate = release.document["density_gate"]
    results: list[dict[str, Any]] = []
    for arm_id, depth in release.arms:
        status_rows = connection.execute(
            """
            SELECT event_status,count(*) FROM v4_events
            WHERE arm_id=? AND trade_date BETWEEN ? AND ? GROUP BY 1 ORDER BY 1
            """,
            [arm_id, start, end],
        ).fetchall()
        year_rows = connection.execute(
            """
            SELECT CAST(substr(trade_date,1,4) AS INTEGER),count(*) FROM v4_events
            WHERE arm_id=? AND event_status='LEGAL_ENTRY_EVENT'
              AND trade_date BETWEEN ? AND ? GROUP BY 1 ORDER BY 1
            """,
            [arm_id, start, end],
        ).fetchall()
        total, days, matched = connection.execute(
            """
            SELECT count(*),count(DISTINCT e.trade_date),count(a.ts_code)
            FROM v4_events e LEFT JOIN v4_alpha_keys a USING(ts_code,trade_date)
            WHERE e.arm_id=? AND e.event_status='LEGAL_ENTRY_EVENT'
              AND e.trade_date BETWEEN ? AND ?
            """,
            [arm_id, start, end],
        ).fetchone()
        total, days, matched = int(total), int(days), int(matched)
        yearly = {str(year): int(count) for year, count in year_rows}
        coverage = matched / total if total else None
        checks = {
            "legal_events_at_least_30": total >= gate["per_arm_minimum_legal_events"],
            "signal_days_at_least_20": days
            >= gate["per_arm_minimum_distinct_signal_days"],
            "each_required_year_at_least_5": all(
                yearly.get(str(year), 0) >= gate["per_arm_minimum_events_each_calendar_year"]
                for year in gate["required_calendar_years"]
            ),
            "alpha158_keys_unique": duplicate_alpha_keys
            == gate["alpha158_duplicate_event_key_count_required"],
            "alpha158_event_key_coverage_complete": coverage
            == gate["alpha158_event_key_coverage_required"],
        }
        results.append(
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
                    "global_duplicate_key_count": duplicate_alpha_keys,
                    "matched_legal_event_key_count": matched,
                    "coverage": coverage,
                    "score_or_rank_read": False,
                },
                "density_gate_checks": checks,
                "pass": all(checks.values()),
            }
        )
    return results


def _write_artifacts(
    connection: duckdb.DuckDBPyConnection,
    start: str,
    end: str,
) -> dict[str, Any]:
    if any(path.exists() for path in (EVENT_PATH, DAILY_PATH, REPORT_PATH, AUDIT_PATH)):
        raise TrendSwingError("TS v4B output already exists; same-scope rerun is forbidden")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    connection.sql(
        """
        SELECT arm_id,pullback_depth_fraction,ts_code,trade_date,market_rank,plan_week,
               industry,segment,first_touch_date,source_week,arm_pullback_line,week_vwap,
               initial_structure_stop,confirmation_adj_factor,next_trade_date,
               next_adjusted_open,next_adj_factor,next_volume_shares,next_day_eligible,
               stop_distance,event_status
        FROM v4_events WHERE trade_date BETWEEN ? AND ?
        ORDER BY arm_id,trade_date,ts_code
        """,
        params=[start, end],
    ).write_parquet(str(EVENT_PATH), compression="zstd")
    connection.sql(
        """
        SELECT a.arm_id,d.trade_date,
               count(e.ts_code) AS confirmed_event_count,
               count(e.ts_code) FILTER(WHERE e.event_status='LEGAL_ENTRY_EVENT')
                 AS legal_event_count
        FROM v4_arms a CROSS JOIN open_days d
        LEFT JOIN v4_events e ON e.arm_id=a.arm_id AND e.trade_date=d.trade_date
        WHERE d.trade_date BETWEEN ? AND ? GROUP BY 1,2 ORDER BY 1,2
        """,
        params=[start, end],
    ).write_parquet(str(DAILY_PATH), compression="zstd")
    return {
        "arm_event_intermediate": {
            "path": EVENT_PATH.relative_to(PROJECT_ROOT).as_posix(),
            "row_count": pq.read_metadata(EVENT_PATH).num_rows,
            "sha256": sha256_file(EVENT_PATH),
            "contains_security_identity": True,
            "contains_post_entry_outcome": False,
            "gitignored": True,
        },
        "anonymous_arm_daily": {
            "path": DAILY_PATH.relative_to(PROJECT_ROOT).as_posix(),
            "row_count": pq.read_metadata(DAILY_PATH).num_rows,
            "sha256": sha256_file(DAILY_PATH),
            "contains_security_identity": False,
            "gitignored": True,
        },
    }


def run_profile_once() -> dict[str, Any]:
    if any(path.exists() for path in (EVENT_PATH, DAILY_PATH, REPORT_PATH, AUDIT_PATH)):
        raise TrendSwingError("TS v4B profile or audit already exists; rerun is forbidden")
    release = V4DensityRelease.load()
    recovery = V4DensityRecovery.load(release)
    validate_bound_inputs(release)
    identity = runtime_code_identity()
    inputs = release.inputs
    manifest = load_r3_manifest(project_path(inputs["r3_manifest_path"]))
    connection = duckdb.connect(":memory:")
    try:
        configure_store(connection, OUTPUT_DIR / "duckdb-tmp")
        prepare_core_tables(
            connection,
            manifest,
            start_date=str(inputs["source_context_start"]),
            end_date=str(inputs["discovery_end"]),
        )
        prepare_market_and_sector(connection)
        prepare_v4_density_state(connection, release.arms)
        mature_end = mature_signal_end(
            connection,
            str(inputs["discovery_end"]),
            int(inputs["final_signal_date_purge_count"]),
        )
        duplicate_alpha = prepare_alpha_keys(connection, project_path(inputs["alpha158_path"]))
        arms = _arm_evidence(
            connection,
            release,
            str(inputs["discovery_start"]),
            mature_end,
            duplicate_alpha,
        )
        artifacts = _write_artifacts(
            connection, str(inputs["discovery_start"]), mature_end
        )
    finally:
        connection.close()
    passing = [item["arm_id"] for item in arms if item["pass"]]
    passing_pairs = [
        list(pair) for pair in release.adjacent_pairs if all(arm in passing for arm in pair)
    ]
    passed = len(passing_pairs) >= release.document["density_gate"][
        "minimum_passing_adjacent_pair_count"
    ]
    verdict = release.document["density_gate"][
        "pass_verdict" if passed else "failure_verdict"
    ]
    report = {
        "schema_version": "ts-v4-density-preflight-profile-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "release_identity": {
            "release_sha256": release.sha256,
            "recovery_sha256": recovery.sha256,
            **identity,
        },
        "profile_scope": {
            "source_context_start": inputs["source_context_start"],
            "discovery_start": inputs["discovery_start"],
            "discovery_end": inputs["discovery_end"],
            "purged_final_signal_day_count": inputs["final_signal_date_purge_count"],
            "mature_signal_end": mature_end,
        },
        "authority": {
            "result_blind": True,
            "proposed_strategy_attempt_count": 4,
            "density_profile_attempt_count": 1,
            "strategy_effect_attempt_count": 0,
            "post_entry_outcome_read": False,
            "alpha158_score_or_rank_read": False,
            "benchmark_value_read": False,
            "network_or_secret_read": False,
        },
        "arm_evidence": arms,
        "passing_arms": passing,
        "passing_adjacent_pairs": passing_pairs,
        "machine_artifacts": artifacts,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "verdict": verdict,
    }
    report["canonical_payload_sha256"] = canonical_sha256(report)
    write_once_json(REPORT_PATH, report)
    return report

"""Aggregate-only index, Alpha158-key, and gate evidence for TS recovery."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.trend_swing.contract import TrendSwingError
from shaiwei.research.trend_swing.recovery_store import quality_summary


REQUIRED_INDEX_RANGES = {
    "000906.SH": ("20160104", "20260811"),
    "399006.SZ": ("20160104", "20260811"),
    "000688.SH": ("20191231", "20260811"),
}


def index_completeness(connection: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    rows = []
    for code, (start, end) in REQUIRED_INDEX_RANGES.items():
        row = connection.execute(
            """
            WITH required AS (
              SELECT trade_date FROM open_days WHERE trade_date BETWEEN ? AND ?
            ), actual AS (
              SELECT trade_date,record_count,value_variant_count FROM index_keys
              WHERE ts_code=? AND trade_date BETWEEN ? AND ?
            )
            SELECT count(*) AS required_day_count,count(a.trade_date) AS observed_day_count,
                   sum((coalesce(a.record_count,0)>1)::INTEGER) AS duplicate_day_count,
                   sum((coalesce(a.value_variant_count,0)>1)::INTEGER) AS conflicting_day_count,
                   sum((a.trade_date IS NULL)::INTEGER) AS missing_day_count,
                   min(a.trade_date) AS first_observed_date,max(a.trade_date) AS last_observed_date
            FROM required r LEFT JOIN actual a USING(trade_date)
            """,
            [start, end, code, start, end],
        ).fetchone()
        names = [column[0] for column in connection.description]
        item = dict(zip(names, row, strict=True))
        for name in names[:5]:
            item[name] = int(item[name] or 0)
        item["ts_code"] = code
        item["required_start_date"] = start
        item["required_end_date"] = end
        item["pass"] = (
            item["observed_day_count"] == item["required_day_count"]
            and item["duplicate_day_count"] == 0
            and item["conflicting_day_count"] == 0
            and item["missing_day_count"] == 0
        )
        rows.append(item)
    return {"indexes": rows, "pass": all(row["pass"] for row in rows)}


def alpha158_key_coverage(
    connection: duckdb.DuckDBPyConnection,
    alpha_path: Path,
    *,
    root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    path = alpha_path.resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise TrendSwingError("TS recovery Alpha158 cache is absent or escapes project root")
    connection.from_parquet(
        str(path), hive_partitioning=False
    ).project(
        "CAST(ts_code AS VARCHAR) AS ts_code,CAST(trade_date AS VARCHAR) AS trade_date"
    ).create_view("alpha_keys_raw")
    duplicate = connection.execute(
        """
        SELECT count(*) FROM (
          SELECT ts_code,trade_date,count(*) AS n FROM alpha_keys_raw GROUP BY 1,2 HAVING n>1
        )
        """
    ).fetchone()[0]
    first_date, last_date = connection.execute(
        "SELECT min(trade_date),max(trade_date) FROM alpha_keys_raw"
    ).fetchone()
    row = connection.execute(
        """
        SELECT count(*) FILTER(WHERE c.trade_date BETWEEN ? AND ?) AS denominator,
               count(a.ts_code) FILTER(WHERE c.trade_date BETWEEN ? AND ?) AS matched,
               count(*) FILTER(WHERE c.trade_date<? OR c.trade_date>?) AS outside_cache
        FROM candidate_flags c LEFT JOIN alpha_keys_raw a USING(ts_code,trade_date)
        WHERE c.is_candidate
        """,
        [first_date, last_date, first_date, last_date, first_date, last_date],
    ).fetchone()
    denominator, matched, outside = (int(value or 0) for value in row)
    coverage = matched / denominator if denominator else None
    return {
        "cache_first_date": first_date,
        "cache_last_date": last_date,
        "duplicate_prediction_key_count": int(duplicate),
        "candidate_events_within_cache_span": denominator,
        "matched_candidate_event_keys": matched,
        "candidate_events_outside_cache_span": outside,
        "event_key_coverage": coverage,
        "prediction_values_read": False,
        "maturity_status": "FROZEN_OOS_CACHE_ONLY_NO_CURRENT_MODEL_BACKFILL",
        "pass": duplicate == 0 and denominator > 0 and coverage is not None and coverage >= 0.95,
    }


def data_gate_checks(
    quality: dict[str, Any],
    indexes: dict[str, Any],
    alpha: dict[str, Any],
) -> dict[str, bool]:
    return {
        "stock_bar_or_nontrading_coverage": quality["bar_or_nontrading_coverage"] >= 0.995,
        "market_cap_coverage": quality["market_cap_coverage_on_bars"] >= 0.995,
        "industry_coverage": quality["industry_coverage"] >= 0.99,
        "duplicate_keys_absent": quality["duplicate_key_days"] == 0,
        "conflicting_keys_absent": quality["conflicting_key_days"] == 0,
        "bse_absent": quality["bse_member_days"] == 0,
        "lifecycle_conflicts_absent": quality["lifecycle_conflict_days"] == 0,
        "future_lineage_absent": quality["eligible_before_list_days"] == 0,
        "members_on_or_after_delist_absent": quality["eligible_on_or_after_delist_days"] == 0,
        "unexplained_missing_bars_absent": quality["unexplained_missing_days"] == 0,
        "independent_trading_without_bar_absent": quality["status1_without_bar_days"] == 0,
        "official_index_history_complete": indexes["pass"],
        "alpha158_event_keys_sufficient": alpha["pass"],
    }


def evidence_summary(
    connection: duckdb.DuckDBPyConnection,
    alpha_path: Path,
) -> dict[str, Any]:
    quality = quality_summary(connection)
    indexes = index_completeness(connection)
    alpha = alpha158_key_coverage(connection, alpha_path)
    checks = data_gate_checks(quality, indexes, alpha)
    return {
        "universe_data_quality": quality,
        "official_index_completeness": indexes,
        "alpha158_key_coverage": alpha,
        "data_gate_checks": checks,
        "data_gate_pass": all(checks.values()),
    }

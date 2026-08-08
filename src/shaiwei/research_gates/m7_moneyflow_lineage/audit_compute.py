"""Independent DuckDB recomputation of the M7 lineage core."""

from __future__ import annotations

from typing import Any

import duckdb
import pandas as pd

from .contract import CATEGORIES, UNIVERSE_IDS, LineageError, LineageProtocol
from .reader import LineageInputs


CONFLICTS = (
    "CONFLICTING_INDEPENDENT_TRADE_STATUS",
    "CONFLICT_DAILY_PRESENT_INDEPENDENT_NONTRADING",
    "CONFLICT_DAILY_ABSENT_INDEPENDENT_TRADING",
    "CONFLICTING_PRIMARY_SUSPENSION_ROWS",
)
UNRESOLVED = (
    "PRIMARY_FULL_DAY_SUSPENSION_ONLY_UNRESOLVED",
    "INTRADAY_SUSPENSION_NOT_EXPLANATION",
    "UNRESOLVED_NO_TRADE_EVIDENCE",
)


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 12) if denominator else 0.0


def _gate(gate_id: str, passed: bool, observed: Any, threshold: Any) -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "status": "PASS" if passed else "FAIL",
        "observed": observed,
        "threshold": threshold,
    }


def _mapping(protocol: LineageProtocol, dates: tuple[str, ...]) -> pd.DataFrame:
    ordered = list(dates)
    if ordered != sorted(set(ordered)):
        raise LineageError("lineage audit official dates are duplicated or unordered")
    scope = protocol.document["scope"]
    rows = []
    for index, date in enumerate(ordered):
        if scope["feature_date_start"] <= date <= scope["feature_date_end"]:
            rows.append({"trade_date": date, "source_date": ordered[index - 1] if index else ""})
    return pd.DataFrame(rows)


def _scalar(connection: duckdb.DuckDBPyConnection, query: str, params: list[Any] | None = None) -> int:
    value = connection.execute(query, params or []).fetchone()[0]
    return int(value or 0)


def _prepare(connection: duckdb.DuckDBPyConnection, protocol: LineageProtocol, inputs: LineageInputs) -> None:
    for name, frame in (
        ("raw_membership", inputs.membership),
        ("raw_moneyflow", inputs.moneyflow_keys),
        ("raw_daily", inputs.daily_keys),
        ("raw_suspend", inputs.suspension),
        ("raw_independent", inputs.independent_status),
        ("date_map", _mapping(protocol, inputs.official_dates)),
        ("quarantine", pd.DataFrame({"source_date": sorted(inputs.quarantined_source_dates)})),
    ):
        connection.register(name, frame)
    scope = protocol.document["scope"]
    connection.execute(
        "CREATE TEMP TABLE membership AS SELECT * FROM raw_membership WHERE CAST(trade_date AS VARCHAR) BETWEEN ? AND ?",
        [scope["feature_date_start"], scope["feature_date_end"]],
    )
    connection.execute(
        "CREATE TEMP TABLE moneyflow AS SELECT * FROM raw_moneyflow WHERE CAST(trade_date AS VARCHAR) BETWEEN ? AND ?",
        [scope["source_date_start"], scope["source_date_end"]],
    )
    connection.execute(
        "CREATE TEMP TABLE moneyflow_keys AS SELECT DISTINCT CAST(ts_code AS VARCHAR) ts_code, CAST(trade_date AS VARCHAR) source_date FROM moneyflow"
    )
    connection.execute(
        "CREATE TEMP TABLE daily_keys AS SELECT DISTINCT CAST(ts_code AS VARCHAR) ts_code, CAST(trade_date AS VARCHAR) source_date FROM raw_daily"
    )
    connection.execute(
        "CREATE TEMP TABLE suspend_keys AS SELECT CAST(ts_code AS VARCHAR) ts_code, CAST(trade_date AS VARCHAR) source_date, max(CAST(primary_full_day AS INTEGER)) primary_full_day, max(CAST(primary_intraday AS INTEGER)) primary_intraday FROM raw_suspend GROUP BY 1,2"
    )
    connection.execute(
        "CREATE TEMP TABLE independent_keys AS SELECT CAST(ts_code AS VARCHAR) ts_code, CAST(trade_date AS VARCHAR) source_date, max(CAST(independent_nontrading AS INTEGER)) independent_nontrading, max(CAST(independent_trading AS INTEGER)) independent_trading FROM raw_independent GROUP BY 1,2"
    )
    connection.execute(
        """
        CREATE TEMP TABLE classified AS
        WITH joined AS (
          SELECT CAST(m.trade_date AS VARCHAR) trade_date,
                 CAST(m.universe_id AS VARCHAR) universe_id,
                 CAST(m.ts_code AS VARCHAR) ts_code,
                 CAST(dm.source_date AS VARCHAR) source_date,
                 q.source_date IS NOT NULL quarantined,
                 mf.ts_code IS NOT NULL moneyflow_present,
                 d.ts_code IS NOT NULL daily_present,
                 coalesce(s.primary_full_day,0) primary_full_day,
                 coalesce(s.primary_intraday,0) primary_intraday,
                 coalesce(i.independent_nontrading,0) independent_nontrading,
                 coalesce(i.independent_trading,0) independent_trading
          FROM membership m
          LEFT JOIN date_map dm ON CAST(m.trade_date AS VARCHAR)=CAST(dm.trade_date AS VARCHAR)
          LEFT JOIN quarantine q ON CAST(dm.source_date AS VARCHAR)=CAST(q.source_date AS VARCHAR)
          LEFT JOIN moneyflow_keys mf ON CAST(m.ts_code AS VARCHAR)=mf.ts_code AND CAST(dm.source_date AS VARCHAR)=mf.source_date
          LEFT JOIN daily_keys d ON CAST(m.ts_code AS VARCHAR)=d.ts_code AND CAST(dm.source_date AS VARCHAR)=d.source_date
          LEFT JOIN suspend_keys s ON CAST(m.ts_code AS VARCHAR)=s.ts_code AND CAST(dm.source_date AS VARCHAR)=s.source_date
          LEFT JOIN independent_keys i ON CAST(m.ts_code AS VARCHAR)=i.ts_code AND CAST(dm.source_date AS VARCHAR)=i.source_date
        )
        SELECT *, CASE
          WHEN quarantined THEN 'QUARANTINED_SOURCE_DATE'
          WHEN independent_nontrading=1 AND independent_trading=1 THEN 'CONFLICTING_INDEPENDENT_TRADE_STATUS'
          WHEN daily_present AND independent_nontrading=1 THEN 'CONFLICT_DAILY_PRESENT_INDEPENDENT_NONTRADING'
          WHEN daily_present THEN 'CONFIRMED_MONEYFLOW_GAP_DAILY_PRESENT'
          WHEN independent_trading=1 THEN 'CONFLICT_DAILY_ABSENT_INDEPENDENT_TRADING'
          WHEN independent_nontrading=1 THEN 'CONFIRMED_NONTRADING_INDEPENDENT'
          WHEN primary_full_day=1 AND primary_intraday=1 THEN 'CONFLICTING_PRIMARY_SUSPENSION_ROWS'
          WHEN primary_full_day=1 THEN 'PRIMARY_FULL_DAY_SUSPENSION_ONLY_UNRESOLVED'
          WHEN primary_intraday=1 THEN 'INTRADAY_SUSPENSION_NOT_EXPLANATION'
          ELSE 'UNRESOLVED_NO_TRADE_EVIDENCE' END category
        FROM joined WHERE NOT (moneyflow_present AND NOT quarantined)
        """
    )


def _diagnostics(connection: duckdb.DuckDBPyConnection) -> dict[str, int]:
    member_duplicate = _scalar(
        connection,
        "SELECT coalesce(sum(n),0) FROM (SELECT count(*) n FROM membership GROUP BY trade_date,universe_id,ts_code HAVING count(*)>1)",
    )
    moneyflow_duplicate = _scalar(
        connection,
        "SELECT coalesce(sum(n),0) FROM (SELECT count(*) n FROM moneyflow GROUP BY trade_date,ts_code HAVING count(*)>1)",
    )
    member_invalid = _scalar(
        connection,
        "SELECT count(*) FROM membership WHERE NOT regexp_full_match(coalesce(CAST(ts_code AS VARCHAR),''),'[0-9]{6}\\.SH')",
    )
    source_invalid = 0
    bse = 0
    for table in ("moneyflow", "raw_daily", "raw_suspend", "raw_independent"):
        source_invalid += _scalar(
            connection,
            f"SELECT count(*) FROM {table} WHERE NOT regexp_full_match(coalesce(CAST(ts_code AS VARCHAR),''),'[0-9]{{6}}\\.(SH|SZ)')",
        )
        bse += _scalar(
            connection,
            f"SELECT count(*) FROM {table} WHERE ends_with(coalesce(CAST(ts_code AS VARCHAR),''),'.BJ')",
        )
    bse += _scalar(
        connection,
        "SELECT count(*) FROM membership WHERE ends_with(coalesce(CAST(ts_code AS VARCHAR),''),'.BJ')",
    )
    invalid_status = (
        _scalar(
            connection, "SELECT coalesce(sum(CAST(invalid_status_rows AS BIGINT)),0) FROM raw_independent"
        )
        if "invalid_status_rows"
        in [row[0] for row in connection.execute("DESCRIBE raw_independent").fetchall()]
        else 0
    )
    return {
        "membership_duplicate_rows": member_duplicate,
        "moneyflow_duplicate_rows": moneyflow_duplicate,
        "membership_invalid_rows": member_invalid,
        "source_invalid_rows": source_invalid,
        "bse_rows": bse,
        "invalid_independent_status_rows": invalid_status,
    }


def recompute_lineage_core(protocol: LineageProtocol, inputs: LineageInputs) -> dict[str, Any]:
    connection = duckdb.connect(":memory:")
    try:
        _prepare(connection, protocol, inputs)
        diagnostics = _diagnostics(connection)
        membership_count = _scalar(connection, "SELECT count(*) FROM membership")
        missing_count = _scalar(connection, "SELECT count(*) FROM classified")
        missing_mapping = _scalar(
            connection,
            "SELECT count(*) FROM membership m LEFT JOIN date_map d ON CAST(m.trade_date AS VARCHAR)=CAST(d.trade_date AS VARCHAR) WHERE d.source_date IS NULL OR CAST(d.source_date AS VARCHAR)='' ",
        )
        raw_counts = dict(
            connection.execute("SELECT category,count(*) FROM classified GROUP BY category").fetchall()
        )
        counts = {category: int(raw_counts.get(category, 0)) for category in CATEGORIES}
        cells = []
        for universe in UNIVERSE_IDS:
            for segment in protocol.document["scope"]["complete_half_year_segments"]:
                rows = connection.execute(
                    "SELECT category,count(*) FROM classified WHERE universe_id=? AND trade_date BETWEEN ? AND ? GROUP BY category",
                    [universe, segment["start"], segment["end"]],
                ).fetchall()
                cell_counts = {category: 0 for category in CATEGORIES}
                cell_counts.update({str(category): int(count) for category, count in rows})
                total = sum(cell_counts.values())
                cells.append(
                    {
                        "universe_id": universe,
                        "segment": segment["name"],
                        "missing_row_count": total,
                        "category_counts": cell_counts,
                        "category_rates": {
                            category: _ratio(count, total) for category, count in cell_counts.items()
                        },
                    }
                )
    finally:
        connection.close()
    conflict_count = sum(counts[item] for item in CONFLICTS)
    unresolved_count = sum(counts[item] for item in UNRESOLVED)
    partition_delta = missing_count - sum(counts.values())
    invalid_keys = (
        diagnostics["membership_invalid_rows"]
        + diagnostics["source_invalid_rows"]
        + diagnostics["bse_rows"]
        + diagnostics["invalid_independent_status_rows"]
    )
    gates = [
        _gate(
            "input_key_rows_unique",
            diagnostics["membership_duplicate_rows"] + diagnostics["moneyflow_duplicate_rows"] == 0,
            diagnostics["membership_duplicate_rows"] + diagnostics["moneyflow_duplicate_rows"],
            0,
        ),
        _gate("key_domain_pass", invalid_keys == 0, invalid_keys, 0),
        _gate("pit_mapping_pass", missing_mapping == 0, missing_mapping, 0),
        _gate("missing_row_partition_pass", partition_delta == 0, partition_delta, 0),
        _gate("conflict_row_count_zero", conflict_count == 0, conflict_count, 0),
        _gate("unresolved_row_count_zero", unresolved_count == 0, unresolved_count, 0),
    ]
    decision = protocol.document["decision"]
    verdict = decision["go"] if all(item["status"] == "PASS" for item in gates) else decision["no_go"]
    return {
        "dataset_and_grain": {
            "grain": "feature_date_x_universe_id_x_ts_code",
            "membership_row_count": membership_count,
            "missing_row_count": missing_count,
            "universe_count": len(UNIVERSE_IDS),
            "half_year_segment_count": len(protocol.document["scope"]["complete_half_year_segments"]),
        },
        "lineage_partition": {
            "category_counts": counts,
            "category_rates_within_missing": {
                category: _ratio(count, missing_count) for category, count in counts.items()
            },
            "conflict_row_count": conflict_count,
            "unresolved_row_count": unresolved_count,
            "partition_delta": partition_delta,
            "cells": cells,
        },
        "validity": diagnostics,
        "gates": gates,
        "authority": {
            "adjusted_or_counterfactual_coverage_computed": False,
            "candidate_definition_count": 0,
            "effect_test_count": 0,
            "generation_attempt_increment": 0,
            "strategy_effective": "NOT_EVALUATED",
            "production_authorization": "none",
        },
        "verdict": verdict,
    }

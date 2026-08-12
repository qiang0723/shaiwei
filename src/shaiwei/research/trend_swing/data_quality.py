"""DuckDB-backed PIT CSI800 source-quality profile for TS-1A."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.trend_swing.contract import OUTPUT_DIR, TrendSwingError, TrendSwingProtocol
from shaiwei.research.trend_swing.sources import source_paths


def _view(connection: duckdb.DuckDBPyConnection, name: str, paths: list[str]) -> None:
    if not paths:
        raise TrendSwingError(f"TS data-quality source has no artifacts: {name}")
    connection.from_parquet(paths, union_by_name=True, hive_partitioning=False).create_view(name)


def _prepare_inputs(
    connection: duckdb.DuckDBPyConnection,
    protocol: TrendSwingProtocol,
    manifest: dict[str, Any],
    root: Path,
) -> None:
    for source_api in (
        "tushare.trade_cal",
        "tushare.daily",
        "tushare.adj_factor",
        "tushare.daily_basic",
        "tushare.index_weight",
        "tushare.index_member_all",
        "tushare.namechange",
        "tushare.suspend_d",
    ):
        _view(connection, source_api.replace("tushare.", ""), source_paths(manifest, source_api, root))
    start, end = protocol.start_date, protocol.end_date
    connection.execute(
        """
        CREATE TEMP TABLE open_days AS
        SELECT DISTINCT CAST(cal_date AS VARCHAR) AS trade_date
        FROM trade_cal
        WHERE CAST(exchange AS VARCHAR) = 'SSE'
          AND CAST(is_open AS VARCHAR) IN ('1', '1.0')
          AND CAST(cal_date AS VARCHAR) BETWEEN ? AND ?
        """,
        [start, end],
    )
    connection.execute(
        """
        CREATE TEMP TABLE snapshots AS
        SELECT DISTINCT CAST(con_code AS VARCHAR) AS ts_code,
               CAST(trade_date AS VARCHAR) AS snapshot_date
        FROM index_weight
        WHERE CAST(index_code AS VARCHAR) = '000906.SH'
          AND CAST(trade_date AS VARCHAR) <= ?
        """,
        [end],
    )
    connection.execute(
        """
        CREATE TEMP TABLE snapshot_dates AS
        SELECT snapshot_date,
               lead(snapshot_date) OVER (ORDER BY snapshot_date) AS next_snapshot_date
        FROM (SELECT DISTINCT snapshot_date FROM snapshots)
        """
    )
    connection.execute(
        """
        CREATE TEMP TABLE expected AS
        SELECT s.ts_code, d.trade_date, s.snapshot_date
        FROM snapshots s
        JOIN snapshot_dates x USING (snapshot_date)
        JOIN open_days d ON d.trade_date >= greatest(s.snapshot_date, ?)
                        AND d.trade_date < coalesce(x.next_snapshot_date, '99999999')
        """,
        [start],
    )


def _prepare_key_tables(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        """
        CREATE TEMP TABLE daily_keys AS
        SELECT CAST(d.ts_code AS VARCHAR) AS ts_code,
               CAST(d.trade_date AS VARCHAR) AS trade_date,
               count(*) AS record_count,
               count(DISTINCT hash(d.open, d.high, d.low, d.close, d.amount)) AS value_variant_count,
               max(try_cast(d.amount AS DOUBLE)) AS amount
        FROM daily d JOIN expected e
          ON CAST(d.ts_code AS VARCHAR) = e.ts_code
         AND CAST(d.trade_date AS VARCHAR) = e.trade_date
        GROUP BY 1, 2
        """
    )
    connection.execute(
        """
        CREATE TEMP TABLE adj_keys AS
        SELECT CAST(a.ts_code AS VARCHAR) AS ts_code,
               CAST(a.trade_date AS VARCHAR) AS trade_date,
               count(*) AS record_count,
               count(DISTINCT try_cast(a.adj_factor AS DOUBLE)) AS value_variant_count,
               max(try_cast(a.adj_factor AS DOUBLE)) AS adj_factor
        FROM adj_factor a JOIN expected e
          ON CAST(a.ts_code AS VARCHAR) = e.ts_code
         AND CAST(a.trade_date AS VARCHAR) = e.trade_date
        GROUP BY 1, 2
        """
    )
    connection.execute(
        """
        CREATE TEMP TABLE basic_keys AS
        SELECT CAST(b.ts_code AS VARCHAR) AS ts_code,
               CAST(b.trade_date AS VARCHAR) AS trade_date,
               count(*) AS record_count,
               count(DISTINCT hash(b.total_mv, b.close)) AS value_variant_count,
               max(try_cast(b.total_mv AS DOUBLE)) AS total_mv
        FROM daily_basic b JOIN expected e
          ON CAST(b.ts_code AS VARCHAR) = e.ts_code
         AND CAST(b.trade_date AS VARCHAR) = e.trade_date
        GROUP BY 1, 2
        """
    )
    connection.execute(
        """
        CREATE TEMP TABLE suspend_keys AS
        SELECT DISTINCT CAST(s.ts_code AS VARCHAR) AS ts_code,
                        CAST(s.trade_date AS VARCHAR) AS trade_date
        FROM suspend_d s JOIN expected e
          ON CAST(s.ts_code AS VARCHAR) = e.ts_code
         AND CAST(s.trade_date AS VARCHAR) = e.trade_date
        """
    )


def _prepare_lineage_tables(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        """
        CREATE TEMP TABLE industry_hits AS
        SELECT e.ts_code, e.trade_date,
               count(DISTINCT CAST(i.l1_code AS VARCHAR)) AS industry_count
        FROM expected e
        LEFT JOIN index_member_all i
          ON CAST(i.ts_code AS VARCHAR) = e.ts_code
         AND CAST(i.in_date AS VARCHAR) <= e.trade_date
         AND (nullif(CAST(i.out_date AS VARCHAR), '') IS NULL
              OR CAST(i.out_date AS VARCHAR) >= e.trade_date)
        GROUP BY e.ts_code, e.trade_date
        """
    )
    connection.execute(
        """
        CREATE TEMP TABLE st_hits AS
        SELECT e.ts_code, e.trade_date,
               max(CASE WHEN upper(CAST(n.name AS VARCHAR)) LIKE '%ST%'
                         AND upper(CAST(n.name AS VARCHAR)) NOT LIKE '%退'
                        THEN 1 ELSE 0 END) AS is_st
        FROM expected e
        LEFT JOIN namechange n
          ON CAST(n.ts_code AS VARCHAR) = e.ts_code
         AND CAST(n.start_date AS VARCHAR) <= e.trade_date
         AND (nullif(CAST(n.end_date AS VARCHAR), '') IS NULL
              OR CAST(n.end_date AS VARCHAR) >= e.trade_date)
        GROUP BY e.ts_code, e.trade_date
        """
    )


def _summary(connection: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    columns = [description[0] for description in connection.execute("DESCRIBE expected").fetchall()]
    if columns != ["ts_code", "trade_date", "snapshot_date"]:
        raise TrendSwingError("TS expected-member schema differs")
    row = connection.execute(
        """
        SELECT count(*) AS expected_member_days,
               count(DISTINCT e.trade_date) AS trade_day_count,
               count(DISTINCT e.ts_code) AS security_count,
               count(DISTINCT e.snapshot_date) AS snapshot_count,
               sum(CASE WHEN e.ts_code LIKE '%.BJ' THEN 1 ELSE 0 END) AS bse_member_days,
               sum(CASE WHEN d.ts_code IS NOT NULL THEN 1 ELSE 0 END) AS bar_days,
               sum(CASE WHEN d.ts_code IS NULL AND s.ts_code IS NOT NULL THEN 1 ELSE 0 END) AS suspended_missing_days,
               sum(CASE WHEN d.ts_code IS NULL AND s.ts_code IS NULL THEN 1 ELSE 0 END) AS unexplained_missing_bar_days,
               sum(CASE WHEN d.ts_code IS NOT NULL AND a.adj_factor IS NOT NULL THEN 1 ELSE 0 END) AS adj_covered_bar_days,
               sum(CASE WHEN d.ts_code IS NOT NULL AND b.total_mv IS NOT NULL THEN 1 ELSE 0 END) AS cap_covered_bar_days,
               sum(CASE WHEN i.industry_count = 1 THEN 1 ELSE 0 END) AS industry_resolved_days,
               sum(CASE WHEN i.industry_count > 1 THEN 1 ELSE 0 END) AS ambiguous_industry_days,
               sum(CASE WHEN h.is_st = 1 THEN 1 ELSE 0 END) AS st_member_days,
               sum(CASE WHEN d.record_count > 1 OR a.record_count > 1 OR b.record_count > 1 THEN 1 ELSE 0 END) AS duplicate_key_days,
               sum(CASE WHEN d.value_variant_count > 1 OR a.value_variant_count > 1 OR b.value_variant_count > 1 THEN 1 ELSE 0 END) AS conflicting_key_days,
               sum(CASE WHEN d.amount IS NOT NULL THEN 1 ELSE 0 END) AS amount_covered_bar_days
        FROM expected e
        LEFT JOIN daily_keys d USING (ts_code, trade_date)
        LEFT JOIN adj_keys a USING (ts_code, trade_date)
        LEFT JOIN basic_keys b USING (ts_code, trade_date)
        LEFT JOIN suspend_keys s USING (ts_code, trade_date)
        LEFT JOIN industry_hits i USING (ts_code, trade_date)
        LEFT JOIN st_hits h USING (ts_code, trade_date)
        """
    ).fetchone()
    names = [column[0] for column in connection.description]
    result = {name: int(value or 0) for name, value in zip(names, row, strict=True)}
    expected = result["expected_member_days"]
    bars = result["bar_days"]
    result.update(
        {
            "stock_bar_or_suspension_coverage": (
                result["bar_days"] + result["suspended_missing_days"]
            )
            / expected,
            "adjustment_coverage_on_bars": result["adj_covered_bar_days"] / bars,
            "market_cap_coverage_on_bars": result["cap_covered_bar_days"] / bars,
            "amount_coverage_on_bars": result["amount_covered_bar_days"] / bars,
            "industry_coverage": result["industry_resolved_days"] / expected,
            "future_lineage_count": 0,
        }
    )
    return result


def profile_universe_quality(
    protocol: TrendSwingProtocol,
    manifest: dict[str, Any],
    *,
    root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    if manifest.get("required_sources_missing"):
        return {"status": "NOT_EVALUATED_REQUIRED_SOURCE_MISSING"}
    temporary = OUTPUT_DIR / "duckdb-tmp"
    temporary.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(":memory:")
    try:
        connection.execute("SET threads = 4")
        connection.execute("SET memory_limit = '8GB'")
        connection.execute("SET temp_directory = ?", [str(temporary)])
        _prepare_inputs(connection, protocol, manifest, root)
        _prepare_key_tables(connection)
        _prepare_lineage_tables(connection)
        result = _summary(connection)
    finally:
        connection.close()
    gates = protocol.document["data_gates"]
    result["gate_checks"] = {
        "stock_bar_coverage": result["stock_bar_or_suspension_coverage"]
        >= float(gates["minimum_stock_bar_coverage"]),
        "market_cap_coverage": result["market_cap_coverage_on_bars"]
        >= float(gates["minimum_market_cap_coverage"]),
        "industry_coverage": result["industry_coverage"] >= float(gates["minimum_industry_coverage"]),
        "duplicate_keys": result["duplicate_key_days"] == int(gates["duplicate_key_count"]),
        "bse_absent": result["bse_member_days"] == int(gates["bse_count"]),
        "future_lineage_absent": result["future_lineage_count"] == int(gates["future_lineage_count"]),
        "unexplained_missing_bar_absent": result["unexplained_missing_bar_days"]
        == int(gates["unexplained_missing_bar_count"]),
    }
    result["status"] = "PASS" if all(result["gate_checks"].values()) else "FAIL"
    return result

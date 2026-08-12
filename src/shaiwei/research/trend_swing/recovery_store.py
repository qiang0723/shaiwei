"""DuckDB evidence store for the result-blind TS-1A-R1 recovery."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.trend_swing.contract import TrendSwingError
from shaiwei.research.trend_swing.sources import source_paths


CORE_SOURCES = (
    "tushare.trade_cal",
    "tushare.stock_basic",
    "tushare.daily",
    "tushare.adj_factor",
    "tushare.daily_basic",
    "tushare.index_weight",
    "tushare.index_daily",
    "tushare.index_member_all",
    "tushare.namechange",
    "tushare.suspend_d",
    "baostock.history_k_data_plus",
)


def _view(
    connection: duckdb.DuckDBPyConnection,
    name: str,
    manifest: dict[str, Any],
    source_api: str,
    root: Path,
) -> None:
    paths = source_paths(manifest, source_api, root)
    if not paths:
        raise TrendSwingError(f"TS recovery source has no immutable artifacts: {source_api}")
    connection.from_parquet(paths, union_by_name=True, hive_partitioning=False).create_view(name)


def configure_store(connection: duckdb.DuckDBPyConnection, temporary: Path) -> None:
    temporary.mkdir(parents=True, exist_ok=True)
    connection.execute("SET threads = 4")
    connection.execute("SET memory_limit = '8GB'")
    connection.execute("SET temp_directory = ?", [str(temporary)])


def prepare_core_tables(
    connection: duckdb.DuckDBPyConnection,
    manifest: dict[str, Any],
    *,
    start_date: str,
    end_date: str,
    root: Path = PROJECT_ROOT,
) -> None:
    names = {source: source.rsplit(".", 1)[-1] for source in CORE_SOURCES}
    names["baostock.history_k_data_plus"] = "baostock_status"
    for source_api, name in names.items():
        _view(connection, name, manifest, source_api, root)
    connection.execute(
        """
        CREATE TEMP TABLE open_days AS
        SELECT CAST(cal_date AS VARCHAR) AS trade_date,
               row_number() OVER (ORDER BY CAST(cal_date AS VARCHAR)) AS market_rank
        FROM (
          SELECT DISTINCT cal_date FROM trade_cal
          WHERE CAST(exchange AS VARCHAR) = 'SSE'
            AND CAST(is_open AS VARCHAR) IN ('1', '1.0')
            AND CAST(cal_date AS VARCHAR) BETWEEN ? AND ?
        )
        """,
        [start_date, end_date],
    )
    connection.execute(
        """
        CREATE TEMP TABLE lifecycle AS
        SELECT CAST(ts_code AS VARCHAR) AS ts_code,
               min(nullif(CAST(list_date AS VARCHAR), '')) AS list_date,
               nullif(max(nullif(CAST(delist_date AS VARCHAR), '')), '') AS delist_date,
               count(DISTINCT nullif(CAST(list_date AS VARCHAR), '')) AS list_variant_count,
               count(DISTINCT nullif(CAST(delist_date AS VARCHAR), '')) AS delist_variant_count
        FROM stock_basic
        GROUP BY 1
        """
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
        [end_date],
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
        CREATE TEMP TABLE expected_raw AS
        SELECT s.ts_code, d.trade_date, d.market_rank, s.snapshot_date,
               l.list_date, l.delist_date, l.list_variant_count, l.delist_variant_count
        FROM snapshots s
        JOIN snapshot_dates x USING (snapshot_date)
        JOIN open_days d ON d.trade_date >= greatest(s.snapshot_date, ?)
                        AND d.trade_date < coalesce(x.next_snapshot_date, '99999999')
        LEFT JOIN lifecycle l USING (ts_code)
        """,
        [start_date],
    )
    connection.execute(
        """
        CREATE TEMP TABLE expected AS
        SELECT * FROM expected_raw
        WHERE list_date IS NOT NULL
          AND list_date <= trade_date
          AND (delist_date IS NULL OR trade_date < delist_date)
        """
    )
    _prepare_market_keys(connection)
    _prepare_availability(connection)
    _prepare_lineage(connection)


def _prepare_market_keys(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        """
        CREATE TEMP TABLE daily_keys AS
        SELECT CAST(d.ts_code AS VARCHAR) AS ts_code,
               CAST(d.trade_date AS VARCHAR) AS trade_date,
               count(*) AS record_count,
               count(DISTINCT hash(d.open,d.high,d.low,d.close,d.pre_close,d.vol,d.amount))
                 AS value_variant_count,
               max(try_cast(d.open AS DOUBLE)) AS open,
               max(try_cast(d.high AS DOUBLE)) AS high,
               max(try_cast(d.low AS DOUBLE)) AS low,
               max(try_cast(d.close AS DOUBLE)) AS close,
               max(try_cast(d.vol AS DOUBLE)) AS vol,
               max(try_cast(d.amount AS DOUBLE)) AS amount
        FROM daily d JOIN expected e
          ON CAST(d.ts_code AS VARCHAR)=e.ts_code
         AND CAST(d.trade_date AS VARCHAR)=e.trade_date
        GROUP BY 1,2
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
          ON CAST(a.ts_code AS VARCHAR)=e.ts_code
         AND CAST(a.trade_date AS VARCHAR)=e.trade_date
        GROUP BY 1,2
        """
    )
    connection.execute(
        """
        CREATE TEMP TABLE basic_keys AS
        SELECT CAST(b.ts_code AS VARCHAR) AS ts_code,
               CAST(b.trade_date AS VARCHAR) AS trade_date,
               count(*) AS record_count,
               count(DISTINCT hash(b.total_mv,b.close)) AS value_variant_count,
               max(try_cast(b.total_mv AS DOUBLE)) AS total_mv
        FROM daily_basic b JOIN expected e
          ON CAST(b.ts_code AS VARCHAR)=e.ts_code
         AND CAST(b.trade_date AS VARCHAR)=e.trade_date
        GROUP BY 1,2
        """
    )


def _prepare_availability(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        """
        CREATE TEMP TABLE primary_suspension AS
        SELECT DISTINCT CAST(s.ts_code AS VARCHAR) AS ts_code,
                        CAST(s.trade_date AS VARCHAR) AS trade_date
        FROM suspend_d s JOIN expected e
          ON CAST(s.ts_code AS VARCHAR)=e.ts_code
         AND CAST(s.trade_date AS VARCHAR)=e.trade_date
        WHERE CAST(s.suspend_type AS VARCHAR)='S'
          AND coalesce(trim(CAST(s.suspend_timing AS VARCHAR)), '')=''
        """
    )
    connection.execute(
        """
        CREATE TEMP TABLE status_keys AS
        SELECT CAST(b.ts_code AS VARCHAR) AS ts_code,
               replace(CAST(b.trade_date AS VARCHAR), '-', '') AS trade_date,
               count(DISTINCT trim(CAST(b.trade_status AS VARCHAR))) AS status_variant_count,
               max(trim(CAST(b.trade_status AS VARCHAR))) AS trade_status
        FROM baostock_status b
        GROUP BY 1,2
        """
    )
    invalid = connection.execute(
        """
        SELECT count(*) FROM status_keys
        WHERE status_variant_count != 1 OR trade_status NOT IN ('0','1')
        """
    ).fetchone()[0]
    if invalid:
        raise TrendSwingError("TS recovery independent trade-status evidence conflicts")
    connection.execute(
        """
        CREATE TEMP TABLE availability AS
        SELECT e.ts_code,e.trade_date,
               d.ts_code IS NOT NULL AS has_bar,
               p.ts_code IS NOT NULL AS primary_suspended,
               coalesce(s.trade_status, '') AS independent_status,
               (p.ts_code IS NOT NULL AND coalesce(s.trade_status,'')!='1')
                 OR coalesce(s.trade_status,'')='0' AS confirmed_nontrading
        FROM expected e
        LEFT JOIN daily_keys d USING(ts_code,trade_date)
        LEFT JOIN primary_suspension p USING(ts_code,trade_date)
        LEFT JOIN status_keys s USING(ts_code,trade_date)
        """
    )


def _prepare_lineage(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        """
        CREATE TEMP TABLE industry_hits AS
        WITH hits AS (
          SELECT e.ts_code,e.trade_date,CAST(i.l1_code AS VARCHAR) AS l1_code,
                 CAST(i.in_date AS VARCHAR) AS in_date
          FROM expected e JOIN index_member_all i
            ON CAST(i.ts_code AS VARCHAR)=e.ts_code
           AND CAST(i.in_date AS VARCHAR)<=e.trade_date
           AND (nullif(CAST(i.out_date AS VARCHAR),'') IS NULL
                OR CAST(i.out_date AS VARCHAR)>=e.trade_date)
        ), latest AS (
          SELECT *,max(in_date) OVER(PARTITION BY ts_code,trade_date) AS latest_in FROM hits
        )
        SELECT ts_code,trade_date,count(DISTINCT l1_code) AS industry_count,
               min(l1_code) AS industry
        FROM latest WHERE in_date=latest_in GROUP BY 1,2
        """
    )
    connection.execute(
        """
        CREATE TEMP TABLE st_hits AS
        WITH hits AS (
          SELECT e.ts_code,e.trade_date,CAST(n.name AS VARCHAR) AS security_name,
                 CAST(n.start_date AS VARCHAR) AS start_date
          FROM expected e JOIN namechange n
            ON CAST(n.ts_code AS VARCHAR)=e.ts_code
           AND CAST(n.start_date AS VARCHAR)<=e.trade_date
           AND (nullif(CAST(n.end_date AS VARCHAR),'') IS NULL
                OR CAST(n.end_date AS VARCHAR)>=e.trade_date)
        ), latest AS (
          SELECT *,max(start_date) OVER(PARTITION BY ts_code,trade_date) AS latest_start FROM hits
        )
        SELECT ts_code,trade_date,
               max(CASE WHEN upper(security_name) LIKE '%ST%' THEN 1 ELSE 0 END) AS is_st
        FROM latest WHERE start_date=latest_start GROUP BY 1,2
        """
    )


def quality_summary(connection: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    row = connection.execute(
        """
        SELECT
          (SELECT count(*) FROM expected_raw) AS raw_member_days,
          (SELECT count(*) FROM expected) AS eligible_member_days,
          (SELECT count(*) FROM expected_raw WHERE delist_date IS NOT NULL
             AND trade_date>=delist_date) AS on_or_after_delist_days,
          (SELECT count(*) FROM expected_raw WHERE list_date IS NULL OR trade_date<list_date)
             AS before_or_missing_list_days,
          (SELECT count(*) FROM expected_raw WHERE list_variant_count!=1
             OR delist_variant_count>1) AS lifecycle_conflict_days,
          sum(has_bar::INTEGER) AS bar_days,
          sum((NOT has_bar AND confirmed_nontrading)::INTEGER) AS confirmed_nontrading_days,
          sum((NOT has_bar AND NOT confirmed_nontrading)::INTEGER) AS unexplained_missing_days,
          sum((NOT has_bar AND independent_status='1')::INTEGER) AS status1_without_bar_days,
          sum((has_bar AND confirmed_nontrading)::INTEGER) AS nontrading_with_bar_days,
          sum((has_bar AND primary_suspended AND independent_status!='1')::INTEGER)
             AS primary_suspension_with_bar_days,
          sum((e.ts_code LIKE '%.BJ')::INTEGER) AS bse_member_days,
          sum((d.record_count>1 OR a.record_count>1 OR b.record_count>1)::INTEGER)
             AS duplicate_key_days,
          sum((d.value_variant_count>1 OR a.value_variant_count>1
               OR b.value_variant_count>1)::INTEGER) AS conflicting_key_days,
          sum((d.ts_code IS NOT NULL AND a.adj_factor IS NOT NULL)::INTEGER)
             AS adjusted_bar_days,
          sum((d.ts_code IS NOT NULL AND b.total_mv IS NOT NULL)::INTEGER)
             AS cap_bar_days,
          sum((coalesce(i.industry_count,0)=1)::INTEGER) AS industry_resolved_days,
          sum((coalesce(i.industry_count,0)>1)::INTEGER) AS industry_ambiguous_days,
          sum((coalesce(s.is_st,0)=1)::INTEGER) AS st_member_days
        FROM expected e JOIN availability v USING(ts_code,trade_date)
        LEFT JOIN daily_keys d USING(ts_code,trade_date)
        LEFT JOIN adj_keys a USING(ts_code,trade_date)
        LEFT JOIN basic_keys b USING(ts_code,trade_date)
        LEFT JOIN industry_hits i USING(ts_code,trade_date)
        LEFT JOIN st_hits s USING(ts_code,trade_date)
        """
    ).fetchone()
    names = [column[0] for column in connection.description]
    result = {name: int(value or 0) for name, value in zip(names, row, strict=True)}
    result["eligible_on_or_after_delist_days"] = int(
        connection.execute(
            """
            SELECT count(*) FROM expected
            WHERE delist_date IS NOT NULL AND trade_date>=delist_date
            """
        ).fetchone()[0]
    )
    result["eligible_before_list_days"] = int(
        connection.execute(
            "SELECT count(*) FROM expected WHERE list_date IS NULL OR trade_date<list_date"
        ).fetchone()[0]
    )
    eligible = result["eligible_member_days"]
    bars = result["bar_days"]
    result.update(
        {
            "bar_or_nontrading_coverage": (
                result["bar_days"] + result["confirmed_nontrading_days"]
            )
            / eligible,
            "adjustment_coverage_on_bars": result["adjusted_bar_days"] / bars,
            "market_cap_coverage_on_bars": result["cap_bar_days"] / bars,
            "industry_coverage": result["industry_resolved_days"] / eligible,
        }
    )
    return result

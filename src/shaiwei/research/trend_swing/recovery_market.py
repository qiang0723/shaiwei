"""Result-blind market, segment, and PIT sector state construction."""

from __future__ import annotations

from typing import Any

import duckdb


INDEX_CODES = ("000906.SH", "399006.SZ", "000688.SH")


def prepare_index_state(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        """
        CREATE TEMP TABLE index_keys AS
        SELECT CAST(ts_code AS VARCHAR) AS ts_code,
               CAST(trade_date AS VARCHAR) AS trade_date,
               count(*) AS record_count,
               count(DISTINCT hash(open,high,low,close,pre_close)) AS value_variant_count,
               max(try_cast(open AS DOUBLE)) AS open,
               max(try_cast(high AS DOUBLE)) AS high,
               max(try_cast(low AS DOUBLE)) AS low,
               max(try_cast(close AS DOUBLE)) AS close
        FROM index_daily
        WHERE CAST(ts_code AS VARCHAR) IN ('000906.SH','399006.SZ','000688.SH')
          AND CAST(trade_date AS VARCHAR) BETWEEN '20160101' AND '20260811'
        GROUP BY 1,2
        """
    )
    connection.execute(
        """
        CREATE TEMP TABLE index_roll AS
        SELECT *,
               lag(close) OVER(PARTITION BY ts_code ORDER BY trade_date) AS prior_close,
               avg(close) OVER(PARTITION BY ts_code ORDER BY trade_date
                 ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS sma20,
               count(*) OVER(PARTITION BY ts_code ORDER BY trade_date
                 ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS sma20_count
        FROM index_keys
        """
    )
    connection.execute(
        """
        CREATE TEMP TABLE index_week AS
        WITH weekly AS (
          SELECT ts_code,
                 strftime(date_trunc('week',strptime(trade_date,'%Y%m%d'))
                   + INTERVAL 4 DAY,'%Y%m%d') AS week_end,
                 min(low) AS week_low
          FROM index_keys GROUP BY 1,2
        )
        SELECT *,lag(week_low) OVER(PARTITION BY ts_code ORDER BY week_end) AS prior_week_low
        FROM weekly
        """
    )
    connection.execute(
        """
        CREATE TEMP TABLE index_state AS
        SELECT b.*,
               b.close/b.prior_close-1.0 AS daily_return,
               w.week_end AS latest_complete_week,
               b.sma20_count=20 AND b.close>b.sma20 AS close_above_sma20,
               w.prior_week_low IS NOT NULL AND w.week_low>=w.prior_week_low
                 AS weekly_low_non_decreasing,
               b.sma20_count=20 AND b.close>b.sma20
                 AND w.prior_week_low IS NOT NULL AND w.week_low>=w.prior_week_low AS gate_pass
        FROM index_roll b
        ASOF LEFT JOIN index_week w
          ON b.ts_code=w.ts_code AND b.trade_date>w.week_end
        """
    )


def prepare_member_state(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        """
        CREATE TEMP TABLE all_price_bars AS
        WITH d AS (
          SELECT CAST(x.ts_code AS VARCHAR) AS ts_code,CAST(x.trade_date AS VARCHAR) AS trade_date,
                 count(*) AS n,count(DISTINCT hash(open,high,low,close,vol,amount)) AS variants,
                 max(try_cast(open AS DOUBLE)) AS open,max(try_cast(high AS DOUBLE)) AS high,
                 max(try_cast(low AS DOUBLE)) AS low,max(try_cast(close AS DOUBLE)) AS close,
                 max(try_cast(vol AS DOUBLE)) AS vol,max(try_cast(amount AS DOUBLE)) AS amount
          FROM daily x JOIN (SELECT DISTINCT ts_code FROM expected) u
            ON CAST(x.ts_code AS VARCHAR)=u.ts_code
          WHERE CAST(x.trade_date AS VARCHAR) BETWEEN '20160101' AND '20260811'
            AND CAST(x.ts_code AS VARCHAR) NOT LIKE '%.BJ' GROUP BY 1,2
        ), a AS (
          SELECT CAST(x.ts_code AS VARCHAR) AS ts_code,CAST(x.trade_date AS VARCHAR) AS trade_date,
                 count(*) AS n,count(DISTINCT try_cast(adj_factor AS DOUBLE)) AS variants,
                 max(try_cast(adj_factor AS DOUBLE)) AS adj_factor
          FROM adj_factor x JOIN (SELECT DISTINCT ts_code FROM expected) u
            ON CAST(x.ts_code AS VARCHAR)=u.ts_code
          WHERE CAST(x.trade_date AS VARCHAR) BETWEEN '20160101' AND '20260811'
            AND CAST(x.ts_code AS VARCHAR) NOT LIKE '%.BJ' GROUP BY 1,2
        ), prices AS (
          SELECT d.ts_code,d.trade_date,o.market_rank,d.open*a.adj_factor AS adj_open,
                 d.high*a.adj_factor AS adj_high,d.low*a.adj_factor AS adj_low,
                 d.close*a.adj_factor AS adj_close,d.amount*1000.0 AS amount_rmb,
                 d.vol*100.0 AS volume_shares,a.adj_factor
          FROM d JOIN a USING(ts_code,trade_date) JOIN open_days o USING(trade_date)
          WHERE d.n=1 AND d.variants=1 AND a.n=1 AND a.variants=1
            AND d.open>0 AND d.high>0 AND d.low>0 AND d.close>0 AND a.adj_factor>0
        )
        SELECT *,lag(adj_high) OVER(PARTITION BY ts_code ORDER BY trade_date) AS previous_valid_high,
               lag(adj_close) OVER(PARTITION BY ts_code ORDER BY trade_date) AS previous_valid_close,
               adj_close/lag(adj_close) OVER(PARTITION BY ts_code ORDER BY trade_date)-1.0
                 AS security_daily_return
        FROM prices
        """
    )
    connection.execute(
        """
        CREATE TEMP TABLE price_bar_roll AS
        SELECT p.* FROM all_price_bars p JOIN expected e USING(ts_code,trade_date)
        """
    )
    connection.execute(
        """
        CREATE TEMP TABLE member_bars AS
        SELECT p.*,
               CASE
                 WHEN p.ts_code LIKE '688%.SH' OR p.ts_code LIKE '689%.SH' THEN 'star'
                 WHEN p.ts_code LIKE '300%.SZ' OR p.ts_code LIKE '301%.SZ' THEN 'chinext'
                 ELSE 'main' END AS segment,
               CASE
                 WHEN p.ts_code LIKE '688%.SH' OR p.ts_code LIKE '689%.SH' THEN '000688.SH'
                 WHEN p.ts_code LIKE '300%.SZ' OR p.ts_code LIKE '301%.SZ' THEN '399006.SZ'
                 ELSE '000906.SH' END AS segment_code,
               i.industry,b.total_mv*10000.0 AS total_mv_rmb,
               coalesce(s.is_st,0) AS is_st
        FROM price_bar_roll p
        JOIN basic_keys b USING(ts_code,trade_date)
        JOIN industry_hits i USING(ts_code,trade_date)
        LEFT JOIN st_hits s USING(ts_code,trade_date)
        WHERE b.record_count=1 AND b.value_variant_count=1
          AND i.industry_count=1 AND coalesce(s.is_st,0)=0
          AND b.total_mv>0
        """
    )
    connection.execute(
        """
        CREATE TEMP TABLE sector_member_returns AS
        SELECT e.ts_code,e.trade_date,e.market_rank,i.industry,
               CASE
                 WHEN p.ts_code IS NOT NULL THEN p.security_daily_return
                 WHEN v.confirmed_nontrading THEN 0.0
                 ELSE NULL END AS security_daily_return,
               x.daily_return AS segment_daily_return
        FROM expected e
        JOIN availability v USING(ts_code,trade_date)
        JOIN industry_hits i USING(ts_code,trade_date)
        LEFT JOIN price_bar_roll p USING(ts_code,trade_date)
        LEFT JOIN st_hits s USING(ts_code,trade_date)
        LEFT JOIN index_state x
          ON x.ts_code=CASE
            WHEN e.ts_code LIKE '688%.SH' OR e.ts_code LIKE '689%.SH' THEN '000688.SH'
            WHEN e.ts_code LIKE '300%.SZ' OR e.ts_code LIKE '301%.SZ' THEN '399006.SZ'
            ELSE '000906.SH' END
         AND x.trade_date=e.trade_date
        WHERE i.industry_count=1 AND coalesce(s.is_st,0)=0
        """
    )


def prepare_sector_state(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        """
        CREATE TEMP TABLE sector_daily AS
        SELECT trade_date,market_rank,industry,
               count(DISTINCT ts_code) FILTER(WHERE security_daily_return IS NOT NULL)
                 AS valid_member_count,
               avg(security_daily_return) AS sector_daily_return,
               count(DISTINCT ts_code) FILTER(WHERE segment_daily_return IS NOT NULL)
                 AS comparator_member_count,
               avg(segment_daily_return) AS comparator_daily_return
        FROM sector_member_returns GROUP BY 1,2,3
        HAVING valid_member_count>=5 AND comparator_member_count>=5
        """
    )
    connection.execute(
        """
        CREATE TEMP TABLE sector_levels AS
        SELECT *,
               exp(sum(ln(1.0+sector_daily_return)) OVER(
                 PARTITION BY industry ORDER BY trade_date)) AS sector_level,
               exp(sum(ln(1.0+comparator_daily_return)) OVER(
                 PARTITION BY industry ORDER BY trade_date)) AS comparator_level
        FROM sector_daily
        WHERE sector_daily_return>-1.0 AND comparator_daily_return>-1.0
        """
    )
    connection.execute(
        """
        CREATE TEMP TABLE sector_roll AS
        SELECT *,
               avg(sector_level) OVER(PARTITION BY industry ORDER BY trade_date
                 ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS sector_sma20,
               count(*) OVER(PARTITION BY industry ORDER BY trade_date
                 ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS count20,
               lag(sector_level,20) OVER(PARTITION BY industry ORDER BY trade_date) AS sector_lag20,
               lag(comparator_level,20) OVER(PARTITION BY industry ORDER BY trade_date) AS comp_lag20,
               lag(market_rank,20) OVER(PARTITION BY industry ORDER BY trade_date) AS rank_lag20,
               lag(sector_level,60) OVER(PARTITION BY industry ORDER BY trade_date) AS sector_lag60,
               lag(comparator_level,60) OVER(PARTITION BY industry ORDER BY trade_date) AS comp_lag60,
               lag(market_rank,60) OVER(PARTITION BY industry ORDER BY trade_date) AS rank_lag60
        FROM sector_levels
        """
    )
    connection.execute(
        """
        CREATE TEMP TABLE sector_week AS
        WITH weekly AS (
          SELECT industry,
                 strftime(date_trunc('week',strptime(trade_date,'%Y%m%d'))
                   + INTERVAL 4 DAY,'%Y%m%d') AS week_end,
                 min(sector_level) AS week_low
          FROM sector_levels GROUP BY 1,2
        )
        SELECT *,lag(week_low) OVER(PARTITION BY industry ORDER BY week_end) AS prior_week_low
        FROM weekly
        """
    )
    connection.execute(
        """
        CREATE TEMP TABLE sector_gate_base AS
        SELECT r.*,
               r.sector_level/r.sector_lag20-1.0 AS return20,
               r.comparator_level/r.comp_lag20-1.0 AS comparator_return20,
               r.sector_level/r.sector_lag60-1.0 AS return60,
               r.comparator_level/r.comp_lag60-1.0 AS comparator_return60,
               w.prior_week_low IS NOT NULL AND w.week_low>=w.prior_week_low AS week_gate,
               r.count20=20 AND r.market_rank-r.rank_lag20=20
                 AND r.sector_level>r.sector_sma20 AS sma_gate,
               r.rank_lag20 IS NOT NULL AND r.market_rank-r.rank_lag20=20
                 AND r.sector_level/r.sector_lag20>r.comparator_level/r.comp_lag20 AS excess20_gate,
               r.rank_lag60 IS NOT NULL AND r.market_rank-r.rank_lag60=60
                 AND r.sector_level/r.sector_lag60>r.comparator_level/r.comp_lag60 AS excess60_gate
        FROM sector_roll r
        ASOF LEFT JOIN sector_week w
          ON r.industry=w.industry AND r.trade_date>w.week_end
        """
    )
    connection.execute(
        """
        CREATE TEMP TABLE sector_state AS
        WITH gated AS (
          SELECT *,sma_gate AND excess20_gate AND excess60_gate AND week_gate AS gate_pass,
                 return20-comparator_return20 AS excess20
          FROM sector_gate_base
        )
        SELECT *,CASE WHEN gate_pass THEN
          row_number() OVER(PARTITION BY trade_date,gate_pass
            ORDER BY excess20 DESC,industry ASC) ELSE NULL END AS hot_rank
        FROM gated
        """
    )


def prepare_market_and_sector(connection: duckdb.DuckDBPyConnection) -> None:
    prepare_index_state(connection)
    prepare_member_state(connection)
    prepare_sector_state(connection)


def market_summary(connection: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    index_rows = connection.execute(
        """
        SELECT ts_code,min(trade_date) AS first_date,max(trade_date) AS last_date,
               count(*) AS row_count,
               sum((record_count>1)::INTEGER) AS duplicate_date_count,
               sum((value_variant_count>1)::INTEGER) AS conflicting_date_count,
               sum(gate_pass::INTEGER) AS gate_pass_days
        FROM index_state GROUP BY 1 ORDER BY 1
        """
    ).fetchall()
    indexes = [
        dict(zip([column[0] for column in connection.description], row, strict=True))
        for row in index_rows
    ]
    sector = connection.execute(
        """
        SELECT count(*) AS evaluable_sector_days,count(DISTINCT industry) AS industry_count,
               sum(gate_pass::INTEGER) AS all_gate_pass_sector_days,
               sum((gate_pass AND hot_rank<=3)::INTEGER) AS hot_sector_days,
               count(DISTINCT trade_date) FILTER(WHERE gate_pass AND hot_rank<=3)
                 AS days_with_hot_sector
        FROM sector_state
        """
    ).fetchone()
    names = [column[0] for column in connection.description]
    return {
        "official_indexes": [
            {key: int(value) if key.endswith("count") or key.endswith("days") or key == "row_count" else value for key, value in item.items()}
            for item in indexes
        ],
        "derived_sector": {
            key: int(value or 0) for key, value in zip(names, sector, strict=True)
        },
    }

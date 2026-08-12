"""Sequence-aware, result-blind TS v3 pullback state construction."""

from __future__ import annotations

import duckdb


def prepare_period_features(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        """
        CREATE TEMP TABLE r4_market_week_chain AS
        WITH weeks AS (
          SELECT DISTINCT strftime(date_trunc('week',strptime(trade_date,'%Y%m%d'))
            + INTERVAL 4 DAY,'%Y%m%d') AS plan_week FROM open_days
        )
        SELECT plan_week,
               lag(plan_week,1) OVER(ORDER BY plan_week) AS source_week,
               lag(plan_week,2) OVER(ORDER BY plan_week) AS prior_week,
               lag(plan_week,3) OVER(ORDER BY plan_week) AS prior_2_week
        FROM weeks
        """
    )
    connection.execute(
        """
        CREATE TEMP TABLE r4_stock_week AS
        WITH price AS (
          SELECT ts_code,
                 strftime(date_trunc('week',strptime(trade_date,'%Y%m%d'))
                   + INTERVAL 4 DAY,'%Y%m%d') AS week_end,
                 min(adj_low) AS week_low,max(adj_high) AS week_high,
                 arg_max(adj_close,trade_date) AS week_close,
                 sum(amount_rmb) AS week_amount_rmb,
                 sum(amount_rmb*adj_factor)/nullif(sum(volume_shares),0) AS week_vwap,
                 max(adj_high)/min(adj_low)-1.0 AS week_range,
                 stddev_samp(security_daily_return)*sqrt(252.0) AS week_realized_volatility
          FROM all_price_bars GROUP BY 1,2
        ), cap AS (
          SELECT ts_code,
                 strftime(date_trunc('week',strptime(trade_date,'%Y%m%d'))
                   + INTERVAL 4 DAY,'%Y%m%d') AS week_end,
                 arg_max(total_mv_rmb,trade_date) AS week_last_total_mv_rmb
          FROM member_bars GROUP BY 1,2
        )
        SELECT p.*,c.week_last_total_mv_rmb FROM price p LEFT JOIN cap c USING(ts_code,week_end)
        """
    )
    connection.execute(
        """
        CREATE TEMP TABLE r4_stock_month AS
        SELECT ts_code,strftime(last_day(strptime(trade_date,'%Y%m%d')),'%Y%m%d') AS month_end,
               max(adj_high) AS month_high,min(adj_low) AS month_low
        FROM all_price_bars GROUP BY 1,2
        """
    )


def prepare_daily_context(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        """
        CREATE TEMP TABLE r4_daily_context AS
        WITH periods AS (
          SELECT o.*,
                 strftime(date_trunc('week',strptime(o.trade_date,'%Y%m%d'))
                   + INTERVAL 4 DAY,'%Y%m%d') AS plan_week,
                 strftime(last_day(strptime(o.trade_date,'%Y%m%d')-INTERVAL 1 MONTH),'%Y%m%d')
                   AS source_month,
                 strftime(last_day(strptime(o.trade_date,'%Y%m%d')-INTERVAL 2 MONTH),'%Y%m%d')
                   AS prior_month,
                 strftime(last_day(strptime(o.trade_date,'%Y%m%d')-INTERVAL 3 MONTH),'%Y%m%d')
                   AS prior_2_month
          FROM open_days o
        ), base AS (
          SELECT b.*,p.plan_week,wc.source_week,
                 w0.week_low,w0.week_high,w0.week_close,w0.week_amount_rmb,w0.week_vwap,
                 w0.week_range,w0.week_realized_volatility,w0.week_last_total_mv_rmb,
                 w1.week_low AS prior_week_low,w1.week_range AS prior_week_range,
                 w1.week_realized_volatility AS prior_week_realized_volatility,
                 w2.week_low AS prior_2_week_low,
                 m0.month_high,m0.month_low,m1.month_high AS prior_month_high,
                 m1.month_low AS prior_month_low,m2.month_high AS prior_2_month_high,
                 broad.gate_pass AS broad_market_pass,
                 segment.gate_pass AS segment_market_pass,
                 sector.gate_pass AND sector.hot_rank<=3 AS hot_sector_pass
          FROM member_bars b JOIN periods p USING(trade_date)
          LEFT JOIN r4_market_week_chain wc USING(plan_week)
          LEFT JOIN r4_stock_week w0 ON w0.ts_code=b.ts_code AND w0.week_end=wc.source_week
          LEFT JOIN r4_stock_week w1 ON w1.ts_code=b.ts_code AND w1.week_end=wc.prior_week
          LEFT JOIN r4_stock_week w2 ON w2.ts_code=b.ts_code AND w2.week_end=wc.prior_2_week
          LEFT JOIN r4_stock_month m0 ON m0.ts_code=b.ts_code AND m0.month_end=p.source_month
          LEFT JOIN r4_stock_month m1 ON m1.ts_code=b.ts_code AND m1.month_end=p.prior_month
          LEFT JOIN r4_stock_month m2 ON m2.ts_code=b.ts_code AND m2.month_end=p.prior_2_month
          LEFT JOIN index_state broad
            ON broad.ts_code='000906.SH' AND broad.trade_date=b.trade_date
          LEFT JOIN index_state segment
            ON segment.ts_code=b.segment_code AND segment.trade_date=b.trade_date
          LEFT JOIN sector_state sector
            ON sector.industry=b.industry AND sector.trade_date=b.trade_date
        )
        SELECT *,week_vwap*0.96 AS pullback_line,week_low*0.98 AS initial_structure_stop,
          coalesce(broad_market_pass,false) AND coalesce(segment_market_pass,false)
            AND coalesce(hot_sector_pass,false) AS f_daily,
          week_last_total_mv_rmb>=20000000000.0
            AND week_amount_rmb>=5000000000.0
            AND month_high>prior_month_high AND prior_month_high>prior_2_month_high
            AND month_low>=prior_month_low*0.95
            AND week_low>=prior_week_low AND prior_week_low>=prior_2_week_low
            AND week_close>=(week_high+week_low)/2.0
            AND week_realized_volatility BETWEEN 0.20 AND 1.20
            AND prior_week_realized_volatility BETWEEN 0.20 AND 1.20
            AND week_range<=0.30 AND prior_week_range<=0.30 AS f_plan,
          adj_low<=week_vwap*0.96 AS f_touch,
          adj_close<=week_low*0.98 AS f_invalidation,
          adj_close>previous_valid_high AND adj_close>adj_open AS f_recovery
        FROM base
        """
    )


def prepare_sequence_events(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        """
        CREATE TEMP TABLE r4_confirmed_events AS
        WITH plan_state AS (
          SELECT ts_code,plan_week,
                 min(trade_date) FILTER(WHERE f_plan AND f_daily AND f_touch) AS first_touch_date,
                 min(trade_date) FILTER(WHERE f_plan AND f_invalidation) AS first_invalid_date
          FROM r4_daily_context GROUP BY 1,2
        ), confirmation_candidates AS (
          SELECT d.*,s.first_touch_date,s.first_invalid_date
          FROM r4_daily_context d JOIN plan_state s USING(ts_code,plan_week)
          WHERE d.f_plan AND d.f_daily AND d.f_recovery
            AND s.first_touch_date IS NOT NULL AND s.first_touch_date<=d.trade_date
            AND (s.first_invalid_date IS NULL OR s.first_invalid_date>d.trade_date)
        )
        SELECT * EXCLUDE(rn) FROM (
          SELECT *,row_number() OVER(PARTITION BY ts_code,plan_week ORDER BY trade_date) AS rn
          FROM confirmation_candidates
        ) WHERE rn=1
        """
    )
    connection.execute(
        """
        CREATE TEMP TABLE r4_events AS
        SELECT c.ts_code,c.trade_date,c.market_rank,c.plan_week,c.industry,c.segment,
               c.first_touch_date,c.source_week,c.week_vwap,c.initial_structure_stop,
               c.adj_factor AS confirmation_adj_factor,
               n.trade_date AS next_trade_date,n.adj_open AS next_adjusted_open,
               n.adj_factor AS next_adj_factor,n.volume_shares AS next_volume_shares,
               m.ts_code IS NOT NULL AS next_day_eligible,
               CASE WHEN n.adj_open IS NOT NULL THEN
                 1.0-c.initial_structure_stop/n.adj_open ELSE NULL END AS stop_distance,
               CASE
                 WHEN n.ts_code IS NULL THEN 'NO_IMMEDIATE_NEXT_OPEN'
                 WHEN m.ts_code IS NULL THEN 'NEXT_DAY_ELIGIBILITY_OR_LINEAGE_FAILED'
                 WHEN n.adj_factor!=c.adj_factor THEN 'BLOCKED_CORPORATE_ACTION_MAPPING'
                 WHEN n.volume_shares<=0 THEN 'NO_POSITIVE_VOLUME'
                 WHEN n.adj_open<=c.initial_structure_stop THEN 'OPEN_AT_OR_BELOW_STOP'
                 WHEN n.adj_open>c.week_vwap THEN 'OPEN_ABOVE_ANCHOR'
                 WHEN 1.0-c.initial_structure_stop/n.adj_open<=0
                   OR 1.0-c.initial_structure_stop/n.adj_open>=0.15
                   THEN 'STOP_DISTANCE_OUT_OF_RANGE'
                 ELSE 'LEGAL_ENTRY_EVENT' END AS event_status
        FROM r4_confirmed_events c
        LEFT JOIN all_price_bars n
          ON n.ts_code=c.ts_code AND n.market_rank=c.market_rank+1
        LEFT JOIN member_bars m
          ON m.ts_code=c.ts_code AND m.market_rank=c.market_rank+1
        """
    )


def prepare_r4_state(connection: duckdb.DuckDBPyConnection) -> None:
    prepare_period_features(connection)
    prepare_daily_context(connection)
    prepare_sequence_events(connection)

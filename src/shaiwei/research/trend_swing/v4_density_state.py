"""Parameterised, result-blind event state for TS-v4B."""

from __future__ import annotations

import duckdb

from shaiwei.research.trend_swing.r4_state import (
    prepare_daily_context,
    prepare_period_features,
)


def install_arms(
    connection: duckdb.DuckDBPyConnection,
    arms: tuple[tuple[str, float], ...],
) -> None:
    connection.execute(
        "CREATE TEMP TABLE v4_arms(arm_id VARCHAR,pullback_depth_fraction DOUBLE)"
    )
    connection.executemany("INSERT INTO v4_arms VALUES (?,?)", arms)


def prepare_arm_sequences(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        """
        CREATE TEMP TABLE v4_arm_daily AS
        SELECT a.arm_id,a.pullback_depth_fraction,d.*,
               d.week_vwap*(1.0-a.pullback_depth_fraction) AS arm_pullback_line,
               d.adj_low<=d.week_vwap*(1.0-a.pullback_depth_fraction) AS arm_touch
        FROM r4_daily_context d CROSS JOIN v4_arms a
        """
    )
    connection.execute(
        """
        CREATE TEMP TABLE v4_confirmed_events AS
        WITH plan_state AS (
          SELECT arm_id,ts_code,plan_week,
                 min(trade_date) FILTER(WHERE f_plan AND f_daily AND arm_touch)
                   AS first_touch_date,
                 min(trade_date) FILTER(WHERE f_plan AND f_invalidation)
                   AS first_invalid_date
          FROM v4_arm_daily GROUP BY 1,2,3
        ), candidates AS (
          SELECT d.*,s.first_touch_date,s.first_invalid_date
          FROM v4_arm_daily d JOIN plan_state s USING(arm_id,ts_code,plan_week)
          WHERE d.f_plan AND d.f_daily AND d.f_recovery
            AND s.first_touch_date IS NOT NULL AND s.first_touch_date<=d.trade_date
            AND (s.first_invalid_date IS NULL OR s.first_invalid_date>d.trade_date)
        )
        SELECT * EXCLUDE(rn) FROM (
          SELECT *,row_number() OVER(
            PARTITION BY arm_id,ts_code,plan_week ORDER BY trade_date
          ) AS rn FROM candidates
        ) WHERE rn=1
        """
    )


def prepare_arm_next_open(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        """
        CREATE TEMP TABLE v4_events AS
        SELECT c.arm_id,c.pullback_depth_fraction,c.ts_code,c.trade_date,c.market_rank,
               c.plan_week,c.industry,c.segment,c.first_touch_date,c.source_week,
               c.arm_pullback_line,c.week_vwap,c.initial_structure_stop,
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
        FROM v4_confirmed_events c
        LEFT JOIN all_price_bars n
          ON n.ts_code=c.ts_code AND n.market_rank=c.market_rank+1
        LEFT JOIN member_bars m
          ON m.ts_code=c.ts_code AND m.market_rank=c.market_rank+1
        """
    )


def prepare_v4_density_state(
    connection: duckdb.DuckDBPyConnection,
    arms: tuple[tuple[str, float], ...],
) -> None:
    prepare_period_features(connection)
    prepare_daily_context(connection)
    install_arms(connection, arms)
    prepare_arm_sequences(connection)
    prepare_arm_next_open(connection)

"""Result-blind TS stock structure funnel and anonymous candidate profile."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.trend_swing.contract import TrendSwingError, project_path


CANDIDATE_EVENT_PATH = (
    PROJECT_ROOT / "data/research/trend_swing/ts-v3-data-gate-r3/candidate_events.parquet"
)


def prepare_stock_periods(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        """
        CREATE TEMP TABLE stock_week AS
        WITH weekly AS (
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
        )
        SELECT *,
               lag(week_low,1) OVER(PARTITION BY ts_code ORDER BY week_end) AS prior_week_low,
               lag(week_low,2) OVER(PARTITION BY ts_code ORDER BY week_end) AS prior_2_week_low,
               lag(week_range,1) OVER(PARTITION BY ts_code ORDER BY week_end) AS prior_week_range,
               lag(week_realized_volatility,1) OVER(PARTITION BY ts_code ORDER BY week_end)
                 AS prior_week_realized_volatility
        FROM weekly
        """
    )
    connection.execute(
        """
        CREATE TEMP TABLE stock_month AS
        WITH monthly AS (
          SELECT ts_code,strftime(last_day(strptime(trade_date,'%Y%m%d')),'%Y%m%d') AS month_end,
                 max(adj_high) AS month_high,min(adj_low) AS month_low
          FROM all_price_bars GROUP BY 1,2
        )
        SELECT *,
               lag(month_high,1) OVER(PARTITION BY ts_code ORDER BY month_end) AS prior_month_high,
               lag(month_high,2) OVER(PARTITION BY ts_code ORDER BY month_end) AS prior_2_month_high,
               lag(month_low,1) OVER(PARTITION BY ts_code ORDER BY month_end) AS prior_month_low
        FROM monthly
        """
    )


def prepare_candidate_funnel(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        """
        CREATE TEMP TABLE candidate_context AS
        SELECT b.*,
               broad.gate_pass AS broad_market_pass,
               segment.gate_pass AS segment_market_pass,
               sector.gate_pass AND sector.hot_rank<=3 AS hot_sector_pass,
               sector.hot_rank AS hot_sector_rank,
               w.week_end,w.week_low,w.week_high,w.week_close,w.week_amount_rmb,w.week_vwap,
               w.prior_week_low,w.prior_2_week_low,w.week_range,w.prior_week_range,
               w.week_realized_volatility,w.prior_week_realized_volatility,
               m.month_end,m.month_high,m.prior_month_high,m.prior_2_month_high,
               m.month_low,m.prior_month_low,
               next_bar.adj_open AS next_official_day_open
        FROM member_bars b
        LEFT JOIN index_state broad
          ON broad.ts_code='000906.SH' AND broad.trade_date=b.trade_date
        LEFT JOIN index_state segment
          ON segment.ts_code=b.segment_code AND segment.trade_date=b.trade_date
        LEFT JOIN sector_state sector
          ON sector.industry=b.industry AND sector.trade_date=b.trade_date
        ASOF LEFT JOIN stock_week w
          ON b.ts_code=w.ts_code AND b.trade_date>w.week_end
        ASOF LEFT JOIN stock_month m
          ON b.ts_code=m.ts_code AND b.trade_date>m.month_end
        LEFT JOIN all_price_bars next_bar
          ON next_bar.ts_code=b.ts_code AND next_bar.market_rank=b.market_rank+1
        """
    )
    connection.execute(
        """
        CREATE TEMP TABLE candidate_flags AS
        WITH raw AS (
          SELECT *,
            coalesce(broad_market_pass,false) AND coalesce(segment_market_pass,false)
              AS f_market,
            coalesce(hot_sector_pass,false) AS f_sector,
            total_mv_rmb>=20000000000.0 AS f_cap,
            week_amount_rmb>=5000000000.0 AS f_week_amount,
            month_high>prior_month_high AND prior_month_high>prior_2_month_high AS f_month_high,
            week_low>=prior_week_low AND prior_week_low>=prior_2_week_low AS f_week_low,
            week_close>=(week_high+week_low)/2.0 AS f_week_close,
            adj_close>previous_valid_high AND adj_close>adj_open AS f_recovery
          FROM candidate_context
        )
        SELECT *,
          f_market AS s_market,
          f_market AND f_sector AS s_sector,
          f_market AND f_sector AND f_cap AS s_cap,
          f_market AND f_sector AND f_cap AND f_week_amount AS s_week_amount,
          f_market AND f_sector AND f_cap AND f_week_amount AND f_month_high AS s_month_high,
          f_market AND f_sector AND f_cap AND f_week_amount AND f_month_high AND f_week_low
            AS s_week_low,
          f_market AND f_sector AND f_cap AND f_week_amount AND f_month_high AND f_week_low
            AND f_week_close AS s_week_close,
          f_market AND f_sector AND f_cap AND f_week_amount AND f_month_high AND f_week_low
            AND f_week_close AND f_recovery AS is_candidate,
          adj_close/week_vwap-1.0 AS distance_to_previous_week_vwap,
          adj_close/((week_high+week_low)/2.0)-1.0 AS distance_to_previous_week_midpoint,
          month_low/prior_month_low-1.0 AS monthly_low_change,
          next_official_day_open/adj_close-1.0 AS next_open_gap,
          1.0-(week_low*0.98)/next_official_day_open AS stop_distance,
          amount_rmb>=3000000000.0 AS daily_amount_bonus
        FROM raw
        """
    )


def write_candidate_events(
    connection: duckdb.DuckDBPyConnection,
    path: Path = CANDIDATE_EVENT_PATH,
) -> None:
    target = project_path(path)
    if target.exists():
        raise TrendSwingError("TS recovery candidate event artifact already exists")
    target.parent.mkdir(parents=True, exist_ok=True)
    connection.execute(
        """
        COPY (
          SELECT ts_code,trade_date,market_rank,industry,segment,
                 distance_to_previous_week_vwap,distance_to_previous_week_midpoint,
                 monthly_low_change,week_range,prior_week_range,
                 week_realized_volatility,prior_week_realized_volatility,
                 next_open_gap,stop_distance,daily_amount_bonus,
                 next_official_day_open IS NOT NULL AS next_open_executable
          FROM candidate_flags WHERE is_candidate ORDER BY trade_date,ts_code
        ) TO ? (FORMAT PARQUET,COMPRESSION ZSTD)
        """,
        [str(target)],
    )


def prepare_anonymous_daily(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        """
        CREATE TEMP TABLE anonymous_daily AS
        SELECT d.trade_date,
               count(c.ts_code) AS eligible_member_count,
               coalesce(sum(c.s_market::INTEGER),0) AS market_pass_count,
               coalesce(sum(c.s_sector::INTEGER),0) AS sector_pass_count,
               coalesce(sum(c.s_cap::INTEGER),0) AS cap_pass_count,
               coalesce(sum(c.s_week_amount::INTEGER),0) AS weekly_amount_pass_count,
               coalesce(sum(c.s_month_high::INTEGER),0) AS monthly_high_pass_count,
               coalesce(sum(c.s_week_low::INTEGER),0) AS weekly_low_pass_count,
               coalesce(sum(c.s_week_close::INTEGER),0) AS weekly_close_pass_count,
               coalesce(sum(c.is_candidate::INTEGER),0) AS candidate_count,
               coalesce(sum((c.is_candidate AND c.daily_amount_bonus)::INTEGER),0)
                 AS candidate_daily_amount_bonus_count,
               coalesce(sum((c.is_candidate AND c.next_official_day_open IS NOT NULL)::INTEGER),0)
                 AS candidate_next_open_executable_count
        FROM open_days d LEFT JOIN candidate_flags c USING(trade_date)
        GROUP BY 1 ORDER BY 1
        """
    )


def _quantiles(connection: duckdb.DuckDBPyConnection, expression: str) -> dict[str, Any]:
    row = connection.execute(
        f"""
        SELECT count({expression}),avg({expression}),
               quantile_cont({expression},0.05),quantile_cont({expression},0.25),
               quantile_cont({expression},0.5),quantile_cont({expression},0.75),
               quantile_cont({expression},0.95)
        FROM candidate_flags WHERE is_candidate
        """
    ).fetchone()
    keys = ("count", "mean", "p05", "p25", "p50", "p75", "p95")
    return {key: int(value) if key == "count" else (float(value) if value is not None else None) for key, value in zip(keys, row, strict=True)}


def candidate_summary(connection: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    totals = connection.execute(
        """
        SELECT sum(eligible_member_count),sum(market_pass_count),sum(sector_pass_count),
               sum(cap_pass_count),sum(weekly_amount_pass_count),sum(monthly_high_pass_count),
               sum(weekly_low_pass_count),sum(weekly_close_pass_count),sum(candidate_count),
               sum(candidate_daily_amount_bonus_count),sum(candidate_next_open_executable_count),
               count(*) FILTER(WHERE candidate_count>0)
        FROM anonymous_daily
        """
    ).fetchone()
    keys = (
        "eligible_member_days", "market_pass_member_days", "sector_pass_member_days",
        "market_cap_pass_member_days", "weekly_amount_pass_member_days",
        "monthly_high_pass_member_days", "weekly_low_pass_member_days",
        "weekly_close_pass_member_days", "candidate_events", "candidate_daily_amount_bonus_events",
        "candidate_next_open_executable_events", "days_with_candidates",
    )
    funnel = {key: int(value or 0) for key, value in zip(keys, totals, strict=True)}
    longest_empty = connection.execute(
        """
        WITH zero_days AS (
          SELECT *,market_rank-row_number() OVER(ORDER BY market_rank) AS island
          FROM open_days JOIN anonymous_daily USING(trade_date) WHERE candidate_count=0
        )
        SELECT coalesce(max(n),0) FROM (SELECT island,count(*) AS n FROM zero_days GROUP BY island)
        """
    ).fetchone()[0]
    risk = connection.execute(
        """
        SELECT sum((is_candidate AND next_official_day_open IS NOT NULL)::INTEGER),
               sum((is_candidate AND stop_distance>0)::INTEGER),
               sum((is_candidate AND stop_distance>0
                 AND least(0.05,0.005/stop_distance)>0)::INTEGER)
        FROM candidate_flags
        """
    ).fetchone()
    gap_bins = connection.execute(
        """
        SELECT
          sum((is_candidate AND next_open_gap<-0.05)::INTEGER),
          sum((is_candidate AND next_open_gap>=-0.05 AND next_open_gap<-0.02)::INTEGER),
          sum((is_candidate AND next_open_gap>=-0.02 AND next_open_gap<0.0)::INTEGER),
          sum((is_candidate AND next_open_gap>=0.0 AND next_open_gap<0.01)::INTEGER),
          sum((is_candidate AND next_open_gap>=0.01 AND next_open_gap<0.02)::INTEGER),
          sum((is_candidate AND next_open_gap>=0.02 AND next_open_gap<0.03)::INTEGER),
          sum((is_candidate AND next_open_gap>=0.03 AND next_open_gap<0.05)::INTEGER),
          sum((is_candidate AND next_open_gap>=0.05)::INTEGER),
          sum((is_candidate AND next_open_gap IS NULL)::INTEGER)
        FROM candidate_flags
        """
    ).fetchone()
    stop_bins = connection.execute(
        """
        SELECT
          sum((is_candidate AND stop_distance<0.0)::INTEGER),
          sum((is_candidate AND stop_distance>=0.0 AND stop_distance<0.02)::INTEGER),
          sum((is_candidate AND stop_distance>=0.02 AND stop_distance<0.04)::INTEGER),
          sum((is_candidate AND stop_distance>=0.04 AND stop_distance<0.06)::INTEGER),
          sum((is_candidate AND stop_distance>=0.06 AND stop_distance<0.08)::INTEGER),
          sum((is_candidate AND stop_distance>=0.08 AND stop_distance<0.10)::INTEGER),
          sum((is_candidate AND stop_distance>=0.10 AND stop_distance<0.15)::INTEGER),
          sum((is_candidate AND stop_distance>=0.15)::INTEGER),
          sum((is_candidate AND stop_distance IS NULL)::INTEGER)
        FROM candidate_flags
        """
    ).fetchone()
    return {
        "funnel": funnel,
        "longest_consecutive_empty_trade_days": int(longest_empty),
        "risk_feasibility": {
            "next_open_executable_events": int(risk[0] or 0),
            "positive_stop_distance_events": int(risk[1] or 0),
            "positive_first_batch_weight_events": int(risk[2] or 0),
        },
        "fixed_bins": {
            "next_open_gap": dict(
                zip(
                    ("lt_-5pct", "-5_to_-2pct", "-2_to_0pct", "0_to_1pct", "1_to_2pct",
                     "2_to_3pct", "3_to_5pct", "ge_5pct", "not_executable"),
                    (int(value or 0) for value in gap_bins),
                    strict=True,
                )
            ),
            "stop_distance": dict(
                zip(
                    ("lt_0pct", "0_to_2pct", "2_to_4pct", "4_to_6pct", "6_to_8pct",
                     "8_to_10pct", "10_to_15pct", "ge_15pct", "not_evaluable"),
                    (int(value or 0) for value in stop_bins),
                    strict=True,
                )
            ),
        },
        "distributions": {
            name: _quantiles(connection, expression)
            for name, expression in {
                "monthly_low_change": "monthly_low_change",
                "current_week_range": "week_range",
                "previous_week_range": "prior_week_range",
                "current_week_realized_volatility": "week_realized_volatility",
                "previous_week_realized_volatility": "prior_week_realized_volatility",
                "distance_to_previous_week_vwap": "distance_to_previous_week_vwap",
                "distance_to_previous_week_midpoint": "distance_to_previous_week_midpoint",
                "next_open_gap": "next_open_gap",
                "stop_distance": "stop_distance",
                "risk_sized_first_batch_weight": "least(0.05,0.005/nullif(stop_distance,0))",
            }.items()
        },
    }


def prepare_candidate_profile(connection: duckdb.DuckDBPyConnection) -> None:
    prepare_stock_periods(connection)
    prepare_candidate_funnel(connection)
    prepare_anonymous_daily(connection)

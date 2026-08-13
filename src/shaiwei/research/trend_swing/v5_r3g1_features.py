"""PIT feature projection for TS-v5-R3G-1 entry mechanisms."""

from __future__ import annotations

import duckdb

from shaiwei.research.trend_swing.r4_state import prepare_daily_context, prepare_period_features


def prepare_base_features(connection: duckdb.DuckDBPyConnection) -> None:
    prepare_period_features(connection)
    prepare_daily_context(connection)
    connection.execute(
        """
        CREATE TEMP TABLE r3g1_daily_base AS
        SELECT d.*,s.sector_level,
          greatest(adj_high-adj_low,
            abs(adj_high-previous_valid_close),abs(adj_low-previous_valid_close)) AS true_range
        FROM r4_daily_context d
        LEFT JOIN sector_levels s USING(trade_date,industry)
        """
    )
    connection.execute(
        """
        CREATE TEMP TABLE r3g1_daily_roll AS
        SELECT d.*,
          row_number() OVER(PARTITION BY ts_code ORDER BY trade_date) AS security_sequence,
          avg(adj_close) OVER(PARTITION BY ts_code ORDER BY trade_date
            ROWS BETWEEN 10 PRECEDING AND 1 PRECEDING) AS sma10_lagged,
          avg(adj_close) OVER(PARTITION BY ts_code ORDER BY trade_date
            ROWS BETWEEN 35 PRECEDING AND 1 PRECEDING) AS sma35_lagged,
          avg(adj_close) OVER(PARTITION BY ts_code ORDER BY trade_date
            ROWS BETWEEN 60 PRECEDING AND 1 PRECEDING) AS sma60_lagged,
          median(amount_rmb) OVER(PARTITION BY ts_code ORDER BY trade_date
            ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS amount_median20_lagged,
          avg(true_range) OVER(PARTITION BY ts_code ORDER BY trade_date
            ROWS BETWEEN 10 PRECEDING AND 1 PRECEDING) AS atr10_lagged,
          avg(true_range) OVER(PARTITION BY ts_code ORDER BY trade_date
            ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS atr20_lagged,
          avg(true_range) OVER(PARTITION BY ts_code ORDER BY trade_date
            ROWS BETWEEN 30 PRECEDING AND 1 PRECEDING) AS atr30_lagged,
          lag(adj_close,20) OVER(PARTITION BY ts_code ORDER BY trade_date) AS close_lag20,
          lag(adj_close,70) OVER(PARTITION BY ts_code ORDER BY trade_date) AS close_lag70,
          lag(adj_close,120) OVER(PARTITION BY ts_code ORDER BY trade_date) AS close_lag120,
          lag(sector_level,20) OVER(PARTITION BY ts_code ORDER BY trade_date) AS sector_lag20,
          lag(sector_level,70) OVER(PARTITION BY ts_code ORDER BY trade_date) AS sector_lag70,
          lag(sector_level,120) OVER(PARTITION BY ts_code ORDER BY trade_date) AS sector_lag120
        FROM r3g1_daily_base d
        """
    )


def prepare_week_features(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        """
        CREATE TEMP TABLE r3g1_week_features AS
        SELECT w.*,
          max(week_high) OVER(PARTITION BY ts_code ORDER BY week_end
            ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING) AS breakout4,
          max(week_high) OVER(PARTITION BY ts_code ORDER BY week_end
            ROWS BETWEEN 15 PRECEDING AND 1 PRECEDING) AS breakout15,
          max(week_high) OVER(PARTITION BY ts_code ORDER BY week_end
            ROWS BETWEEN 26 PRECEDING AND 1 PRECEDING) AS breakout26,
          quantile_cont(week_range,0.1) OVER(PARTITION BY ts_code ORDER BY week_end
            ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING) AS range_q10_lag3,
          quantile_cont(week_range,0.5) OVER(PARTITION BY ts_code ORDER BY week_end
            ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING) AS range_q50_lag3,
          quantile_cont(week_range,0.1) OVER(PARTITION BY ts_code ORDER BY week_end
            ROWS BETWEEN 8 PRECEDING AND 1 PRECEDING) AS range_q10_lag8,
          quantile_cont(week_range,0.5) OVER(PARTITION BY ts_code ORDER BY week_end
            ROWS BETWEEN 8 PRECEDING AND 1 PRECEDING) AS range_q50_lag8,
          quantile_cont(week_range,0.1) OVER(PARTITION BY ts_code ORDER BY week_end
            ROWS BETWEEN 12 PRECEDING AND 1 PRECEDING) AS range_q10_lag12,
          quantile_cont(week_range,0.5) OVER(PARTITION BY ts_code ORDER BY week_end
            ROWS BETWEEN 12 PRECEDING AND 1 PRECEDING) AS range_q50_lag12
        FROM r4_stock_week w
        """
    )
    connection.execute(
        """
        CREATE TEMP TABLE r3g1_context AS
        SELECT d.*,
          w.breakout4,w.breakout15,w.breakout26,
          w.range_q10_lag3,w.range_q50_lag3,w.range_q10_lag8,w.range_q50_lag8,
          w.range_q10_lag12,w.range_q50_lag12,
          row_number() OVER(PARTITION BY d.ts_code,d.plan_week ORDER BY d.trade_date)=1
            AS first_plan_week_bar
        FROM r3g1_daily_roll d
        LEFT JOIN r3g1_week_features w ON w.ts_code=d.ts_code AND w.week_end=d.source_week
        """
    )


def prepare_relative_strength_features(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        """
        CREATE TEMP TABLE r3g1_rs_base AS
        SELECT *,
          (adj_close/close_lag20)/(sector_level/sector_lag20) AS rs20,
          (adj_close/close_lag70)/(sector_level/sector_lag70) AS rs70,
          (adj_close/close_lag120)/(sector_level/sector_lag120) AS rs120
        FROM r3g1_context
        """
    )
    peak_expressions = []
    for days in (20, 70, 120):
        peak_expressions.append(
            f"max(rs{days}) OVER(PARTITION BY ts_code ORDER BY trade_date "
            f"ROWS BETWEEN {days} PRECEDING AND 1 PRECEDING) AS rs_peak{days}_lagged"
        )
    connection.execute(
        "CREATE TEMP TABLE r3g1_rs_peaks AS SELECT *,"
        + ",".join(peak_expressions)
        + " FROM r3g1_rs_base"
    )
    drawdown_expressions = [
        f"greatest(0.0,(rs_peak{days}_lagged-rs{days})/rs_peak{days}_lagged) AS rs_drawdown{days}"
        for days in (20, 70, 120)
    ]
    connection.execute(
        "CREATE TEMP TABLE r3g1_rs_drawdowns AS SELECT *,"
        + ",".join(drawdown_expressions)
        + " FROM r3g1_rs_peaks"
    )
    expressions = []
    for days in (20, 70, 120):
        for quantile in ("0.1", "0.35", "0.6"):
            label = quantile.replace(".", "_")
            expressions.append(
                f"quantile_cont(rs_drawdown{days},{quantile}) OVER("
                f"PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN {days} PRECEDING "
                f"AND 1 PRECEDING) AS rs_drawdown_q{days}_{label}"
            )
    connection.execute(
        "CREATE TEMP TABLE r3g1_feature_context AS SELECT *,"
        + ",".join(expressions)
        + " FROM r3g1_rs_drawdowns"
    )


def prepare_role_stream(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        """
        CREATE TEMP TABLE r3g1_plans AS
        SELECT DISTINCT ts_code,plan_week,industry,segment,segment_code
        FROM r4_daily_context WHERE f_plan
        """
    )
    connection.execute(
        """
        CREATE TEMP TABLE r3g1_stream AS
        WITH days AS (
          SELECT p.*,o.trade_date,o.market_rank,
            strftime(date_trunc('week',strptime(o.trade_date,'%Y%m%d'))
              + INTERVAL 4 DAY,'%Y%m%d') AS day_plan_week
          FROM r3g1_plans p JOIN open_days o
            ON strftime(date_trunc('week',strptime(o.trade_date,'%Y%m%d'))
              + INTERVAL 4 DAY,'%Y%m%d')=p.plan_week
        )
        SELECT d.* EXCLUDE(trade_date,market_rank,industry,segment,segment_code,plan_week,ts_code),
          x.trade_date,x.market_rank,x.plan_week,x.industry,x.segment,x.segment_code,x.ts_code,
          x.trade_date IS NOT NULL AS has_bar,
          coalesce(d.f_plan,true) AS f_plan,
          coalesce(d.f_daily,false) AS f_daily,
          coalesce(d.amount_rmb>0,false) AS liquidity_gate,
          d.ts_code IS NOT NULL AS security_eligible
        FROM days x LEFT JOIN r3g1_feature_context d
          ON d.ts_code=x.ts_code AND d.trade_date=x.trade_date
        """
    )


def prepare_r3g1_features(connection: duckdb.DuckDBPyConnection) -> None:
    prepare_base_features(connection)
    prepare_week_features(connection)
    prepare_relative_strength_features(connection)
    prepare_role_stream(connection)

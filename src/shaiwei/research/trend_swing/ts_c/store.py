"""TS-C eligibility stack and trigger feature stream built on the bound raw snapshot."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import duckdb

from shaiwei.research.trend_swing.recovery_market import prepare_index_state, prepare_member_state
from shaiwei.research.trend_swing.recovery_store import configure_store, prepare_core_tables


def prepare_tsc_stream(connection: duckdb.DuckDBPyConnection, manifest: Mapping[str, Any], temporary: Path) -> None:
    configure_store(connection, temporary)
    prepare_core_tables(connection, manifest, start_date="20160101", end_date="20251231")
    prepare_index_state(connection)
    prepare_member_state(connection)
    connection.execute(
        """
        CREATE TEMP TABLE tsc_daily_tr AS
        SELECT ts_code, trade_date,
               greatest(adj_high-adj_low, abs(adj_high-previous_valid_close),
                        abs(adj_low-previous_valid_close)) AS tr
        FROM member_bars
        """
    )
    connection.execute(
        """
        CREATE TEMP TABLE tsc_stock_week AS
        WITH weekly AS (
          SELECT ts_code,
                 strftime(date_trunc('week',strptime(trade_date,'%Y%m%d'))
                   + INTERVAL 4 DAY,'%Y%m%d') AS week_end,
                 sum(amount_rmb) AS week_amount,
                 sum(amount_rmb)/nullif(sum(volume_shares),0) AS week_vwap,
                 min(adj_low) AS week_low
          FROM member_bars GROUP BY 1,2
        ), atr AS (
          SELECT ts_code,
                 strftime(date_trunc('week',strptime(t.trade_date,'%Y%m%d'))
                   + INTERVAL 4 DAY,'%Y%m%d') AS week_end,
                 avg(t.tr) AS atr20
          FROM (
            SELECT ts_code, trade_date,
                   avg(tr) OVER(PARTITION BY ts_code ORDER BY trade_date
                     ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS atr20,
                   count(*) OVER(PARTITION BY ts_code ORDER BY trade_date
                     ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS atr_count
            FROM tsc_daily_tr
          ) t WHERE t.atr_count=20 GROUP BY 1,2
        )
        SELECT w.*, a.atr20,
               lag(w.week_low) OVER(PARTITION BY w.ts_code ORDER BY w.week_end) AS w1_low,
               lag(w.week_low,2) OVER(PARTITION BY w.ts_code ORDER BY w.week_end) AS w2_low
        FROM weekly w LEFT JOIN atr a USING(ts_code, week_end)
        """
    )
    connection.execute(
        """
        CREATE TEMP TABLE tsc_stock_month AS
        WITH month_ends AS (
          SELECT ts_code, strftime(strptime(trade_date,'%Y%m%d'),'%Y%m') AS month,
                 max(trade_date) AS month_end, arg_max(adj_close, trade_date) AS month_close
          FROM member_bars GROUP BY 1,2
        ), roll AS (
          SELECT *, avg(month_close) OVER(PARTITION BY ts_code ORDER BY month_end
                   ROWS BETWEEN 5 PRECEDING AND CURRENT ROW) AS sma6,
                 count(*) OVER(PARTITION BY ts_code ORDER BY month_end
                   ROWS BETWEEN 5 PRECEDING AND CURRENT ROW) AS sma6_count
          FROM month_ends
        )
        SELECT ts_code, month, month_end, month_close, sma6, sma6_count,
               lag(month_close) OVER(PARTITION BY ts_code ORDER BY month_end) AS prev_month_close,
               lag(sma6) OVER(PARTITION BY ts_code ORDER BY month_end) AS prev_sma6,
               lag(sma6,2) OVER(PARTITION BY ts_code ORDER BY month_end) AS prev2_sma6
        FROM roll
        """
    )
    connection.execute(
        """
        CREATE TEMP TABLE tsc_index_month AS
        WITH month_ends AS (
          SELECT strftime(strptime(trade_date,'%Y%m%d'),'%Y%m') AS month,
                 max(trade_date) AS month_end, arg_max(close, trade_date) AS month_close
          FROM index_keys WHERE ts_code='000906.SH' GROUP BY 1
        ), roll AS (
          SELECT *, avg(month_close) OVER(ORDER BY month_end
                   ROWS BETWEEN 5 PRECEDING AND CURRENT ROW) AS sma6,
                 count(*) OVER(ORDER BY month_end
                   ROWS BETWEEN 5 PRECEDING AND CURRENT ROW) AS sma6_count
          FROM month_ends
        )
        SELECT month, month_close, sma6, sma6_count,
               lag(month_close) OVER(ORDER BY month_end) AS prev_month_close,
               lag(sma6) OVER(ORDER BY month_end) AS prev_sma6,
               lag(sma6,2) OVER(ORDER BY month_end) AS prev2_sma6
        FROM roll
        """
    )
    connection.execute(
        """
        CREATE TEMP TABLE tsc_stream AS
        SELECT m.ts_code, m.trade_date,
               m.adj_open, m.adj_high, m.adj_low, m.adj_close,
               m.previous_valid_high, m.amount_rmb, m.total_mv_rmb,
               strftime(strptime(m.trade_date,'%Y%m%d'),'%Y%m') AS month,
               w.week_vwap, w.atr20, w.week_amount,
               (w.week_low IS NOT NULL AND w.w1_low IS NOT NULL AND w.w2_low IS NOT NULL
                 AND w.week_low>=w.w1_low AND w.w1_low>=w.w2_low) AS weekly_lows_rising,
               avg(m.adj_close) OVER(PARTITION BY m.ts_code ORDER BY m.trade_date
                 ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS ma20,
               count(*) OVER(PARTITION BY m.ts_code ORDER BY m.trade_date
                 ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS ma20_count,
               max(m.adj_close) OVER(PARTITION BY m.ts_code ORDER BY m.trade_date
                 ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS max_close_20d,
               count(*) OVER(PARTITION BY m.ts_code ORDER BY m.trade_date) AS bar_count,
               t.atr20 AS daily_atr20,
               i.close_above_sma20 AS index_above_sma20
        FROM member_bars m
        LEFT JOIN tsc_daily_tr t USING(ts_code, trade_date)
        ASOF LEFT JOIN tsc_stock_week w
          ON m.ts_code=w.ts_code
          AND strptime(m.trade_date,'%Y%m%d') > strptime(w.week_end,'%Y%m%d') + INTERVAL 3 DAY
        LEFT JOIN index_state i ON i.ts_code='000906.SH' AND i.trade_date=m.trade_date
        ORDER BY m.ts_code, m.trade_date
        """
    )


def load_stream(connection: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    result = connection.execute(
        """
        SELECT s.*, sm.prev_month_close AS stock_prev_month_close,
               sm.prev_sma6 AS stock_prev_sma6, sm.prev2_sma6 AS stock_prev2_sma6,
               im.prev_month_close AS index_prev_month_close,
               im.prev_sma6 AS index_prev_sma6, im.prev2_sma6 AS index_prev2_sma6
        FROM tsc_stream s
        LEFT JOIN tsc_stock_month sm ON sm.ts_code=s.ts_code AND sm.month=s.month
        LEFT JOIN tsc_index_month im ON im.month=s.month
        WHERE s.trade_date BETWEEN '20190102' AND '20251231'
        ORDER BY s.ts_code, s.trade_date
        """
    )
    columns = [item[0] for item in result.description]
    return [dict(zip(columns, values, strict=True)) for values in result.fetchall()]

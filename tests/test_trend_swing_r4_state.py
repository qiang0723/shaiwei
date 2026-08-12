import duckdb
import pandas as pd

from shaiwei.research.trend_swing.r4_state import prepare_r4_state


def _create_tables(connection: duckdb.DuckDBPyConnection) -> None:
    dates = pd.bdate_range("2019-09-02", "2020-03-20").strftime("%Y%m%d").tolist()
    connection.execute(
        "CREATE TABLE open_days(trade_date VARCHAR,market_rank BIGINT)"
    )
    connection.executemany(
        "INSERT INTO open_days VALUES (?,?)", list(zip(dates, range(1, len(dates) + 1), strict=True))
    )
    connection.execute(
        """
        CREATE TABLE all_price_bars(ts_code VARCHAR,trade_date VARCHAR,market_rank BIGINT,
          adj_open DOUBLE,adj_high DOUBLE,adj_low DOUBLE,adj_close DOUBLE,amount_rmb DOUBLE,
          volume_shares DOUBLE,adj_factor DOUBLE,security_daily_return DOUBLE)
        """
    )
    rows = []
    week_starts = sorted({pd.Timestamp(day).to_period("W-FRI").start_time for day in dates})
    week_numbers = {week: index for index, week in enumerate(week_starts)}
    source_week = pd.Timestamp("20200313").to_period("W-FRI").start_time
    source_base = 80.0 + week_numbers[source_week] * 2.0
    for offset, day in enumerate(dates):
        timestamp = pd.Timestamp(day)
        week = timestamp.to_period("W-FRI").start_time
        base = 80.0 + week_numbers[week] * 2.0
        close = base + timestamp.weekday() * 0.1
        low = base - 10.0
        open_price = close - 0.2
        high = close + 1.0
        if day == "20200316":
            open_price, high, low, close = (
                source_base,
                source_base + 3.0,
                source_base - 8.0,
                source_base + 2.0,
            )
        if day == "20200317":
            open_price, high, low, close = (
                source_base,
                source_base + 3.0,
                source_base,
                source_base + 2.5,
            )
        volume = 20_000_000.0
        rows.append(
            (
                "000001.SZ", day, offset + 1, open_price, high, low, close,
                close * volume, volume, 1.0, 0.02 if offset % 2 else -0.02,
            )
        )
    connection.executemany("INSERT INTO all_price_bars VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
    connection.execute(
        """
        CREATE TABLE member_bars AS
        SELECT *, 'main' AS segment,'000906.SH' AS segment_code,'I1' AS industry,
               30000000000.0 AS total_mv_rmb,0 AS is_st,
               lag(adj_high) OVER(PARTITION BY ts_code ORDER BY trade_date) AS previous_valid_high
        FROM all_price_bars
        """
    )
    connection.execute(
        """
        CREATE TABLE index_state(ts_code VARCHAR,trade_date VARCHAR,gate_pass BOOLEAN)
        """
    )
    connection.executemany(
        "INSERT INTO index_state VALUES (?,?,true)",
        [(code, day) for code in ("000906.SH",) for day in dates],
    )
    connection.execute(
        """
        CREATE TABLE sector_state(industry VARCHAR,trade_date VARCHAR,gate_pass BOOLEAN,
          hot_rank BIGINT)
        """
    )
    connection.executemany(
        "INSERT INTO sector_state VALUES (?,?,true,1)", [("I1", day) for day in dates]
    )


def _eligible_connection() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(":memory:")
    _create_tables(connection)
    prepare_r4_state(connection)
    return connection


def test_r4_requires_touch_before_or_on_confirmation() -> None:
    connection = _eligible_connection()
    try:
        events = connection.execute(
            "SELECT first_touch_date,trade_date,event_status FROM r4_events"
        ).fetchall()
    finally:
        connection.close()

    assert events
    assert all(touch <= confirmation for touch, confirmation, _ in events)
    assert any(status == "LEGAL_ENTRY_EVENT" for _, _, status in events)


def test_r4_invalidation_is_absorbing_within_week() -> None:
    connection = duckdb.connect(":memory:")
    try:
        _create_tables(connection)
        connection.execute(
            "UPDATE all_price_bars SET adj_close=80.0 WHERE trade_date='20200316'"
        )
        connection.execute("DROP TABLE member_bars")
        connection.execute(
            """
            CREATE TABLE member_bars AS
            SELECT *, 'main' AS segment,'000906.SH' AS segment_code,'I1' AS industry,
                   30000000000.0 AS total_mv_rmb,0 AS is_st,
                   lag(adj_high) OVER(PARTITION BY ts_code ORDER BY trade_date) AS previous_valid_high
            FROM all_price_bars
            """
        )
        prepare_r4_state(connection)
        event_count = connection.execute(
            "SELECT count(*) FROM r4_events WHERE plan_week='20200320'"
        ).fetchone()[0]
    finally:
        connection.close()

    assert event_count == 0


def test_r4_rejects_factor_change_on_immediate_next_open() -> None:
    connection = _eligible_connection()
    try:
        row = connection.execute(
            "SELECT ts_code,trade_date FROM r4_events WHERE event_status='LEGAL_ENTRY_EVENT' LIMIT 1"
        ).fetchone()
        assert row is not None
        code, signal_date = row
        rank = connection.execute(
            "SELECT market_rank FROM open_days WHERE trade_date=?", [signal_date]
        ).fetchone()[0]
    finally:
        connection.close()

    changed = duckdb.connect(":memory:")
    try:
        _create_tables(changed)
        changed.execute(
            "UPDATE all_price_bars SET adj_factor=2.0 WHERE ts_code=? AND market_rank=?",
            [code, rank + 1],
        )
        prepare_r4_state(changed)
        status = changed.execute(
            "SELECT event_status FROM r4_events WHERE ts_code=? AND trade_date=?",
            [code, signal_date],
        ).fetchone()[0]
    finally:
        changed.close()

    assert status == "BLOCKED_CORPORATE_ACTION_MAPPING"


def test_r4_benchmark_preflight_does_not_accept_price_index() -> None:
    from shaiwei.research.trend_swing.r4_profile import benchmark_preflight

    manifest = {
        "sources": {
            "tushare.index_daily": {
                "artifacts": [{"params": {"ts_code": "000906.SH"}, "path": "price.parquet"}]
            }
        }
    }
    assert benchmark_preflight(manifest)["verdict"] == "BLOCKED_BENCHMARK_DATA"


def test_r4_benchmark_preflight_accepts_explicit_total_return_identity() -> None:
    from shaiwei.research.trend_swing.r4_profile import benchmark_preflight

    manifest = {
        "sources": {
            "official.csi_total_return": {
                "artifacts": [{"params": {"index_id": "H00906"}, "path": "total.parquet"}]
            }
        }
    }
    assert benchmark_preflight(manifest)["verdict"] == "PASS"

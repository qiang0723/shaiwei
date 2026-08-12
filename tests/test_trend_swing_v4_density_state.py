import duckdb

from shaiwei.research.trend_swing.v4_density_state import prepare_v4_density_state
from tests.test_trend_swing_r4_state import _create_tables


ARMS = (
    ("TS4-D015", 0.015),
    ("TS4-D025", 0.025),
    ("TS4-D035", 0.035),
    ("TS4-D040", 0.040),
)


def _connection() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(":memory:")
    _create_tables(connection)
    prepare_v4_density_state(connection, ARMS)
    return connection


def test_v4_density_installs_exact_ordered_depths() -> None:
    connection = _connection()
    try:
        rows = connection.execute(
            "SELECT arm_id,pullback_depth_fraction FROM v4_arms ORDER BY pullback_depth_fraction"
        ).fetchall()
    finally:
        connection.close()

    assert rows == list(ARMS)


def test_v4_density_touch_threshold_is_monotone_by_depth() -> None:
    connection = _connection()
    try:
        violations = connection.execute(
            """
            SELECT count(*) FROM v4_arm_daily shallow
            JOIN v4_arm_daily deep USING(ts_code,trade_date)
            WHERE shallow.pullback_depth_fraction<deep.pullback_depth_fraction
              AND deep.arm_touch AND NOT shallow.arm_touch
            """
        ).fetchone()[0]
    finally:
        connection.close()

    assert violations == 0


def test_v4_density_requires_touch_before_confirmation_for_every_arm() -> None:
    connection = _connection()
    try:
        rows = connection.execute(
            "SELECT arm_id,first_touch_date,trade_date FROM v4_events"
        ).fetchall()
    finally:
        connection.close()

    assert rows
    assert all(touch <= confirmation for _, touch, confirmation in rows)


def test_v4_density_invalidation_is_absorbing_for_all_arms() -> None:
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
                   lag(adj_high) OVER(PARTITION BY ts_code ORDER BY trade_date)
                     AS previous_valid_high
            FROM all_price_bars
            """
        )
        prepare_v4_density_state(connection, ARMS)
        count = connection.execute(
            "SELECT count(*) FROM v4_events WHERE plan_week='20200320'"
        ).fetchone()[0]
    finally:
        connection.close()

    assert count == 0


def test_v4_density_uses_immediate_next_market_open_without_substitution() -> None:
    connection = _connection()
    try:
        mismatches = connection.execute(
            """
            SELECT count(*) FROM v4_events
            WHERE next_trade_date IS NOT NULL AND next_trade_date != (
              SELECT trade_date FROM open_days o WHERE o.market_rank=v4_events.market_rank+1
            )
            """
        ).fetchone()[0]
    finally:
        connection.close()

    assert mismatches == 0

from pathlib import Path

import duckdb
import pandas as pd

from shaiwei.research.trend_swing.recovery_candidate import (
    candidate_summary,
    prepare_candidate_profile,
)
from shaiwei.research.trend_swing.recovery_evidence import (
    alpha158_key_coverage,
    index_completeness,
)


def _dates() -> list[str]:
    return pd.bdate_range("2019-09-02", "2020-04-30").strftime("%Y%m%d").tolist()


def _connection() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(":memory:")
    dates = _dates()
    open_days = pd.DataFrame({"trade_date": dates, "market_rank": range(1, len(dates) + 1)})
    connection.register("open_days_frame", open_days)
    connection.execute("CREATE TEMP TABLE open_days AS SELECT * FROM open_days_frame")

    index_rows = []
    for code in ("000906.SH", "399006.SZ", "000688.SH"):
        for number, day in enumerate(dates):
            price = 1000.0 + number
            index_rows.append((code, day, price, price + 2, price - 2, price, price - 1))
    connection.execute(
        """
        CREATE TEMP TABLE index_daily(ts_code VARCHAR,trade_date VARCHAR,open DOUBLE,
          high DOUBLE,low DOUBLE,close DOUBLE,pre_close DOUBLE)
        """
    )
    connection.executemany("INSERT INTO index_daily VALUES (?,?,?,?,?,?,?)", index_rows)

    members = []
    status = []
    industry = []
    st = []
    for security_index in range(5):
        code = f"00000{security_index + 1}.SZ"
        for number, day in enumerate(dates):
            price = 10.0 + number * 0.3 + security_index * 0.01
            members.append(
                (
                    code, day, number + 1, "main", "000906.SH", "I1",
                    price, price + 0.2, price - 0.2, price + 0.1,
                    1_200_000_000.0, 10_000_000.0, 30_000_000_000.0, 1.0, 0,
                    price - 0.1 if number else None, price if number else None,
                    0.005 if number else None,
                )
            )
            status.append((code, day, number + 1, "I1", 0.005 if number else None, 0.001))
            industry.append((code, day, 1, "I1"))
            st.append((code, day, 0))
    connection.execute(
        """
        CREATE TEMP TABLE all_price_bars(ts_code VARCHAR,trade_date VARCHAR,market_rank BIGINT,
          segment VARCHAR,segment_code VARCHAR,industry VARCHAR,adj_open DOUBLE,adj_high DOUBLE,
          adj_low DOUBLE,adj_close DOUBLE,amount_rmb DOUBLE,volume_shares DOUBLE,total_mv_rmb DOUBLE,
          adj_factor DOUBLE,is_st BIGINT,previous_valid_high DOUBLE,previous_valid_close DOUBLE,
          security_daily_return DOUBLE)
        """
    )
    connection.executemany("INSERT INTO all_price_bars VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", members)
    connection.execute("CREATE TEMP TABLE price_bar_roll AS SELECT * FROM all_price_bars")
    connection.execute("CREATE TEMP TABLE member_bars AS SELECT * FROM all_price_bars")
    connection.execute(
        """
        CREATE TEMP TABLE sector_member_returns(ts_code VARCHAR,trade_date VARCHAR,
          market_rank BIGINT,industry VARCHAR,security_daily_return DOUBLE,
          segment_daily_return DOUBLE)
        """
    )
    connection.executemany("INSERT INTO sector_member_returns VALUES (?,?,?,?,?,?)", status)
    connection.execute(
        "CREATE TEMP TABLE industry_hits(ts_code VARCHAR,trade_date VARCHAR,industry_count BIGINT,industry VARCHAR)"
    )
    connection.executemany("INSERT INTO industry_hits VALUES (?,?,?,?)", industry)
    connection.execute(
        "CREATE TEMP TABLE st_hits(ts_code VARCHAR,trade_date VARCHAR,is_st BIGINT)"
    )
    connection.executemany("INSERT INTO st_hits VALUES (?,?,?)", st)
    return connection


def test_result_blind_pipeline_produces_anonymous_funnel_and_alpha_keys(tmp_path: Path):
    connection = _connection()
    try:
        from shaiwei.research.trend_swing.recovery_market import (
            prepare_index_state,
            prepare_sector_state,
        )

        prepare_index_state(connection)
        prepare_sector_state(connection)
        prepare_candidate_profile(connection)
        summary = candidate_summary(connection)
        events = connection.execute(
            "SELECT ts_code,trade_date FROM candidate_flags WHERE is_candidate"
        ).df()
        alpha_path = tmp_path / "alpha.parquet"
        events.to_parquet(alpha_path, index=False)
        alpha = alpha158_key_coverage(connection, alpha_path, root=tmp_path)
        daily_columns = [row[0] for row in connection.execute("DESCRIBE anonymous_daily").fetchall()]
    finally:
        connection.close()
    assert summary["funnel"]["candidate_events"] > 0
    assert summary["funnel"]["candidate_next_open_executable_events"] > 0
    assert alpha["event_key_coverage"] == 1.0
    assert alpha["pass"] is True
    assert "ts_code" not in daily_columns


def test_index_completeness_fails_closed_on_required_day_gap(monkeypatch):
    connection = _connection()
    try:
        from shaiwei.research.trend_swing.recovery_market import prepare_index_state

        prepare_index_state(connection)
        monkeypatch.setattr(
            "shaiwei.research.trend_swing.recovery_evidence.REQUIRED_INDEX_RANGES",
            {"000906.SH": (_dates()[0], _dates()[-1])},
        )
        connection.execute("DELETE FROM index_keys WHERE ts_code='000906.SH' AND trade_date='20200102'")
        result = index_completeness(connection)
    finally:
        connection.close()
    assert result["pass"] is False
    assert result["indexes"][0]["missing_day_count"] == 1

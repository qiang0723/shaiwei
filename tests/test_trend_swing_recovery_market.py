import duckdb

from shaiwei.research.trend_swing.recovery_market import prepare_index_state


def test_index_state_uses_only_strictly_complete_week():
    connection = duckdb.connect(":memory:")
    try:
        connection.execute(
            """
            CREATE TABLE index_daily(ts_code VARCHAR,trade_date VARCHAR,open DOUBLE,
              high DOUBLE,low DOUBLE,close DOUBLE,pre_close DOUBLE)
            """
        )
        rows = []
        for index, day in enumerate(
            [
                "20200106", "20200107", "20200108", "20200109", "20200110",
                "20200113", "20200114", "20200115", "20200116", "20200117",
                "20200120", "20200121", "20200122", "20200123", "20200124",
                "20200127", "20200128", "20200129", "20200130", "20200131",
                "20200203",
            ]
        ):
            price = 100.0 + index
            rows.append(("000906.SH", day, price, price + 1, price - 1, price, price - 1))
        connection.executemany("INSERT INTO index_daily VALUES (?,?,?,?,?,?,?)", rows)
        prepare_index_state(connection)
        friday = connection.execute(
            "SELECT latest_complete_week FROM index_state WHERE trade_date='20200131'"
        ).fetchone()[0]
        monday = connection.execute(
            "SELECT latest_complete_week FROM index_state WHERE trade_date='20200203'"
        ).fetchone()[0]
    finally:
        connection.close()
    assert friday == "20200124"
    assert monday == "20200131"

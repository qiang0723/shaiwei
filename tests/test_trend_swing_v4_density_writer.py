from pathlib import Path

import duckdb
import pyarrow.parquet as pq

import shaiwei.research.trend_swing.v4_density_profile as profile_module


def test_v4_density_writer_binds_dates_before_explicit_parquet_path(
    tmp_path: Path, monkeypatch
) -> None:
    event_path = tmp_path / "events.parquet"
    daily_path = tmp_path / "daily.parquet"
    output_dir = tmp_path / "scope"
    monkeypatch.setattr(profile_module, "EVENT_PATH", event_path)
    monkeypatch.setattr(profile_module, "DAILY_PATH", daily_path)
    monkeypatch.setattr(profile_module, "REPORT_PATH", output_dir / "report.json")
    monkeypatch.setattr(profile_module, "AUDIT_PATH", output_dir / "audit.json")
    monkeypatch.setattr(profile_module, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(profile_module, "PROJECT_ROOT", tmp_path)

    connection = duckdb.connect(":memory:")
    try:
        connection.execute("CREATE TABLE v4_arms(arm_id VARCHAR)")
        connection.execute("INSERT INTO v4_arms VALUES ('TS4-D015')")
        connection.execute("CREATE TABLE open_days(trade_date VARCHAR)")
        connection.executemany(
            "INSERT INTO open_days VALUES (?)", [("20190101",), ("20190102",), ("20190103",)]
        )
        connection.execute(
            """
            CREATE TABLE v4_events(
              arm_id VARCHAR,pullback_depth_fraction DOUBLE,ts_code VARCHAR,
              trade_date VARCHAR,market_rank BIGINT,plan_week VARCHAR,industry VARCHAR,
              segment VARCHAR,first_touch_date VARCHAR,source_week VARCHAR,
              arm_pullback_line DOUBLE,week_vwap DOUBLE,initial_structure_stop DOUBLE,
              confirmation_adj_factor DOUBLE,next_trade_date VARCHAR,next_adjusted_open DOUBLE,
              next_adj_factor DOUBLE,next_volume_shares DOUBLE,next_day_eligible BOOLEAN,
              stop_distance DOUBLE,event_status VARCHAR
            )
            """
        )
        connection.execute(
            """
            INSERT INTO v4_events VALUES (
              'TS4-D015',0.015,'000001.SZ','20190102',2,'20190104','I1','main',
              '20190102','20181228',9.85,10.0,8.0,1.0,'20190103',9.0,1.0,
              100.0,true,0.111,'LEGAL_ENTRY_EVENT'
            )
            """
        )
        artifacts = profile_module._write_artifacts(connection, "20190102", "20190103")
    finally:
        connection.close()

    assert event_path.is_file() and daily_path.is_file()
    assert pq.read_metadata(event_path).num_rows == 1
    assert pq.read_metadata(daily_path).num_rows == 2
    assert artifacts["arm_event_intermediate"]["contains_post_entry_outcome"] is False
    assert "ts_code" not in pq.read_schema(daily_path).names

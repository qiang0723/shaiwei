from pathlib import Path

import duckdb
import pandas as pd

from shaiwei.research.trend_swing.recovery_store import prepare_core_tables, quality_summary


def _artifact(root: Path, source: str, frame: pd.DataFrame) -> dict:
    path = root / f"{source.replace('.', '-')}.parquet"
    frame.to_parquet(path, index=False)
    return {"path": path.name}


def _manifest(root: Path) -> dict:
    frames = {
        "tushare.trade_cal": pd.DataFrame(
            {"exchange": ["SSE"] * 4, "cal_date": ["20200102", "20200103", "20200106", "20200107"], "is_open": ["1"] * 4}
        ),
        "tushare.stock_basic": pd.DataFrame(
            {"ts_code": ["000001.SZ", "000002.SZ"], "list_date": ["20200103", "20100101"], "delist_date": ["", "20200107"]}
        ),
        "tushare.index_weight": pd.DataFrame(
            {"index_code": ["000906.SH"] * 2, "con_code": ["000001.SZ", "000002.SZ"], "trade_date": ["20200101"] * 2}
        ),
        "tushare.index_daily": pd.DataFrame(
            {
                "ts_code": ["000906.SH"] * 4,
                "trade_date": ["20200102", "20200103", "20200106", "20200107"],
                "open": [4000.0] * 4, "high": [4100.0] * 4, "low": [3900.0] * 4,
                "close": [4050.0] * 4, "pre_close": [4000.0] * 4,
            }
        ),
        "tushare.daily": pd.DataFrame(
            {
                "ts_code": ["000001.SZ", "000001.SZ", "000002.SZ", "000002.SZ", "000002.SZ"],
                "trade_date": ["20200103", "20200107", "20200102", "20200103", "20200106"],
                "open": [10.0] * 5, "high": [11.0] * 5, "low": [9.0] * 5, "close": [10.0] * 5,
                "pre_close": [10.0] * 5, "vol": [100.0] * 5, "amount": [1000.0] * 5,
            }
        ),
        "tushare.adj_factor": pd.DataFrame(
            {"ts_code": ["000001.SZ", "000001.SZ", "000002.SZ", "000002.SZ", "000002.SZ"], "trade_date": ["20200103", "20200107", "20200102", "20200103", "20200106"], "adj_factor": [1.0] * 5}
        ),
        "tushare.daily_basic": pd.DataFrame(
            {"ts_code": ["000001.SZ", "000001.SZ", "000002.SZ", "000002.SZ", "000002.SZ"], "trade_date": ["20200103", "20200107", "20200102", "20200103", "20200106"], "close": [10.0] * 5, "total_mv": [3_000_000.0] * 5}
        ),
        "tushare.suspend_d": pd.DataFrame(
            {"ts_code": ["000001.SZ"], "trade_date": ["20200106"], "suspend_type": ["S"], "suspend_timing": [""]}
        ),
        "baostock.history_k_data_plus": pd.DataFrame(
            {"ts_code": ["000001.SZ"], "trade_date": ["20200106"], "trade_status": ["0"]}
        ),
        "tushare.index_member_all": pd.DataFrame(
            {"ts_code": ["000001.SZ", "000002.SZ"], "l1_code": ["I1", "I1"], "in_date": ["20100101"] * 2, "out_date": [""] * 2}
        ),
        "tushare.namechange": pd.DataFrame(
            {"ts_code": ["000001.SZ", "000002.SZ"], "name": ["甲", "乙"], "start_date": ["20100101"] * 2, "end_date": [""] * 2}
        ),
    }
    return {"sources": {key: {"artifacts": [_artifact(root, key, value)]} for key, value in frames.items()}}


def test_recovery_store_uses_right_open_delist_and_independent_status(tmp_path):
    connection = duckdb.connect(":memory:")
    try:
        prepare_core_tables(
            connection,
            _manifest(tmp_path),
            start_date="20200102",
            end_date="20200107",
            root=tmp_path,
        )
        result = quality_summary(connection)
    finally:
        connection.close()
    assert result["raw_member_days"] == 8
    assert result["before_or_missing_list_days"] == 1
    assert result["on_or_after_delist_days"] == 1
    assert result["eligible_member_days"] == 6
    assert result["bar_days"] == 5
    assert result["confirmed_nontrading_days"] == 1
    assert result["unexplained_missing_days"] == 0
    assert result["status1_without_bar_days"] == 0
    assert result["bar_or_nontrading_coverage"] == 1.0

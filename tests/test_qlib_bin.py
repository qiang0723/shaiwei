from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import qlib
from qlib.config import REG_CN
from qlib.data import D

from shaiwei.transform.qlib_bin import build_qlib_bin, membership_intervals, qlib_code


def test_qlib_code_mapping():
    assert qlib_code("600000.SH") == "SH600000"
    assert qlib_code("000001.SZ") == "SZ000001"


def test_monthly_membership_is_forward_filled_and_contiguous():
    calendar = ["20200102", "20200103", "20200203", "20200204"]
    weights = pd.DataFrame(
        [
            {"con_code": "600001.SH", "trade_date": "20200102"},
            {"con_code": "600001.SH", "trade_date": "20200203"},
            {"con_code": "600002.SH", "trade_date": "20200203"},
        ]
    )
    intervals = membership_intervals(weights, calendar)
    assert intervals.to_dict("records") == [
        {"instrument": "SH600001", "start": "20200102", "end": "20200204"},
        {"instrument": "SH600002", "start": "20200203", "end": "20200204"},
    ]


def test_build_qlib_bin_keeps_suspension_gap_nan(tmp_path: Path):
    market = pd.DataFrame(
        [
            {"ts_code": "600001.SH", "trade_date": "20200102", "open": 1, "high": 1, "low": 1,
             "close": 1, "volume": 100, "vwap": 1, "factor": 1, "change": 0,
             "limit_buy": True, "limit_sell": False},
            {"ts_code": "600001.SH", "trade_date": "20200106", "open": 2, "high": 2, "low": 2,
             "close": 2, "volume": 100, "vwap": 2, "factor": 1, "change": 0,
             "limit_buy": False, "limit_sell": True},
        ]
    )
    calendar = pd.DataFrame({"cal_date": ["20200102", "20200103", "20200106"], "is_open": [1, 1, 1]})
    weights = pd.DataFrame(
        [
            {"index_code": "000906.SH", "con_code": "600001.SH", "trade_date": "20200102"},
            {"index_code": "000300.SH", "con_code": "600001.SH", "trade_date": "20200102"},
        ]
    )
    benchmark = pd.DataFrame(
        [
            {"ts_code": "000906.SH", "trade_date": day, "open": 1, "high": 1, "low": 1,
             "close": 1, "vol": 100, "amount": 100, "pct_chg": 0}
            for day in calendar["cal_date"]
        ]
    )
    instrument_indices = {"csi800": "000906.SH", "csi300": "000300.SH"}
    output = build_qlib_bin(
        tmp_path / "qlib", market, calendar, pd.DataFrame(), weights, benchmark, instrument_indices
    )
    close_bin = np.fromfile(output / "features/sh600001/close.day.bin", dtype="<f4")
    assert close_bin[0] == 0
    assert close_bin[1] == 1
    assert np.isnan(close_bin[2])
    assert close_bin[3] == 2
    assert "SH600001\t20200102\t20200106" in (output / "instruments/all.txt").read_text()
    qlib.init(provider_uri=str(output), region=REG_CN, expression_cache=None, dataset_cache=None)
    loaded = D.features(
        ["SH600001"], ["$close", "$limit_buy", "$limit_sell"],
        start_time="2020-01-02", end_time="2020-01-06", freq="day",
    )
    assert loaded["$close"].iloc[0] == 1
    assert np.isnan(loaded["$close"].iloc[1])
    assert loaded["$close"].iloc[2] == 2
    assert loaded["$limit_buy"].iloc[0] == 1
    assert loaded["$limit_sell"].iloc[2] == 1
    assert "SH600001" in (output / "instruments/csi300.txt").read_text()
    with pytest.raises(FileExistsError):
        build_qlib_bin(output, market, calendar, pd.DataFrame(), weights, benchmark, instrument_indices)

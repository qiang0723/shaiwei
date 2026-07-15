import subprocess

import pandas as pd

from shaiwei.sentinel.checks import (
    s1_completeness,
    s2_dual_calculation,
    s3_reverse_adjustment,
    s4_units,
    s6_suspensions,
    s7_price_volume_logic,
    s8_cross_source,
    s9_st_status,
    s10_git_consistency,
)
from shaiwei.transform.market import transform_market_data


def _market_inputs():
    daily = pd.DataFrame(
        [
            {"ts_code": "A", "trade_date": "20200102", "open": 9, "high": 11, "low": 8,
             "close": 10, "pre_close": 9, "change": 1, "pct_chg": 11, "vol": 2, "amount": 2},
            {"ts_code": "A", "trade_date": "20200103", "open": 10, "high": 12, "low": 10,
             "close": 11, "pre_close": 10, "change": 1, "pct_chg": 10, "vol": 2, "amount": 2.2},
        ]
    )
    factors = pd.DataFrame(
        [
            {"ts_code": "A", "trade_date": "20200102", "adj_factor": 1.0},
            {"ts_code": "A", "trade_date": "20200103", "adj_factor": 1.0},
        ]
    )
    return daily, factors


def test_s1_accepts_only_calendar_minus_suspensions():
    cal = pd.DataFrame({"cal_date": ["20200102", "20200103"], "is_open": [1, 1]})
    stocks = pd.DataFrame([{"ts_code": "A", "list_date": "20200101", "delist_date": None}])
    daily, _ = _market_inputs()
    suspensions = pd.DataFrame(columns=["ts_code", "trade_date", "suspend_type"])
    assert s1_completeness(cal, stocks, daily, suspensions, start="20200101", end="20200103").status == "PASS"
    assert s1_completeness(cal, stocks, daily.iloc[:1], suspensions, start="20200101", end="20200103").status == "FAIL"


def test_s2_s3_s4_and_s7_pass_consistent_market_data():
    daily, factors = _market_inputs()
    transformed = transform_market_data(daily, factors)
    assert s2_dual_calculation(daily, factors).status == "PASS"
    assert s3_reverse_adjustment(transformed, daily).status == "PASS"
    assert s4_units(transformed).status == "PASS"
    assert s7_price_volume_logic(transformed).status == "PASS"


def test_s6_detects_non_nan_suspended_bar():
    suspended = pd.DataFrame([{"ts_code": "A", "trade_date": "20200102", "suspend_type": "S"}])
    aligned = pd.DataFrame([{"ts_code": "A", "trade_date": "20200102", "open": 1.0}])
    assert s6_suspensions(aligned, suspended).status == "FAIL"
    aligned["open"] = float("nan")
    assert s6_suspensions(aligned, suspended).status == "PASS"


def test_s8_checks_close_and_volume_with_same_raw_units():
    daily, _ = _market_inputs()
    ak = daily.loc[:, ["ts_code", "trade_date", "close", "vol"]].copy()
    ak["close"] = ak["close"].astype(float)
    assert s8_cross_source(daily, ak).status == "PASS"
    ak.loc[0, "close"] *= 1.02
    assert s8_cross_source(daily, ak).status == "FAIL"


def test_s9_requires_a_removed_st_sample_and_handles_delisting_name():
    names = pd.DataFrame(
        [
            {"ts_code": "A", "name": "ST旧名", "start_date": "20180101", "end_date": "20181231"},
            {"ts_code": "A", "name": "新名", "start_date": "20190101", "end_date": None},
            {"ts_code": "B", "name": "ST公司退", "start_date": "20190101", "end_date": None},
        ]
    )
    observations = pd.DataFrame(
        [{"ts_code": "A", "trade_date": "20200102"}, {"ts_code": "B", "trade_date": "20200102"}]
    )
    assert s9_st_status(names, observations).status == "PASS"


def test_s10_is_na_in_dev_without_expected_and_passes_exact_head():
    assert s10_git_consistency(environment="dev").status == "NOT_APPLICABLE"
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    assert s10_git_consistency(environment="prod", expected_commit=head).status == "PASS"

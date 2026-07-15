import numpy as np
import pandas as pd

from shaiwei.transform.market import attach_trade_limit_flags, transform_market_data


def test_market_transform_adjusts_prices_and_units_with_reversible_factor():
    daily = pd.DataFrame(
        [
            {
                "ts_code": "A", "trade_date": "20200101", "open": 9.0, "high": 11.0,
                "low": 8.0, "close": 10.0, "pre_close": 9.0, "change": 1.0, "pct_chg": 10.0,
                "vol": 2.0, "amount": 2.0,
            },
            {
                "ts_code": "A", "trade_date": "20200102", "open": 4.5, "high": 5.5,
                "low": 4.0, "close": 5.0, "pre_close": 4.5, "change": 0.5, "pct_chg": 11.11,
                "vol": 4.0, "amount": 2.0,
            },
        ]
    )
    factors = pd.DataFrame(
        [
            {"ts_code": "A", "trade_date": "20200101", "adj_factor": 1.0},
            {"ts_code": "A", "trade_date": "20200102", "adj_factor": 2.0},
        ]
    )
    result = transform_market_data(daily, factors)

    assert result["close"].tolist() == [10.0, 10.0]
    assert result["factor"].tolist() == [1.0, 0.5]
    np.testing.assert_allclose(result["close"] * result["factor"], daily["close"])
    assert result["raw_volume"].tolist() == [200.0, 400.0]
    assert result["volume"].tolist() == [200.0, 200.0]
    assert result["amount"].tolist() == [2000.0, 2000.0]
    assert result["vwap"].tolist() == [10.0, 10.0]
    np.testing.assert_allclose(result["change"], [0.1, 0.1111])
    assert result["price_change"].tolist() == [1.0, 0.5]


def test_market_transform_refuses_missing_factor():
    daily = pd.DataFrame(
        [{
            "ts_code": "A", "trade_date": "20200101", "open": 1, "high": 1, "low": 1,
            "close": 1, "pre_close": 1, "pct_chg": 0, "vol": 1, "amount": 1,
        }]
    )
    factors = pd.DataFrame(columns=["ts_code", "trade_date", "adj_factor"])
    try:
        transform_market_data(daily, factors)
    except ValueError as error:
        assert "missing adj_factor" in str(error)
    else:
        raise AssertionError("missing factor must fail")


def test_trade_limit_flags_cover_board_date_st_and_direction():
    market = pd.DataFrame(
        [
            {"ts_code": "600001.SH", "trade_date": "20200102", "change": 0.10},
            {"ts_code": "300001.SZ", "trade_date": "20200102", "change": 0.10},
            {"ts_code": "300001.SZ", "trade_date": "20200824", "change": 0.10},
            {"ts_code": "688001.SH", "trade_date": "20200102", "change": -0.20},
            {"ts_code": "600002.SH", "trade_date": "20200102", "change": -0.05},
            {"ts_code": "600003.SH", "trade_date": "20200102", "change": 0.10},
        ]
    )
    stock_basic = pd.DataFrame(
        [
            {"ts_code": code, "list_date": "20100101"}
            for code in market["ts_code"].drop_duplicates()
        ]
    )
    stock_basic.loc[stock_basic["ts_code"].eq("600003.SH"), "list_date"] = "20200102"
    names = pd.DataFrame(
        [
            {"ts_code": code, "name": "普通", "start_date": "20100101", "end_date": None}
            for code in market["ts_code"].drop_duplicates()
        ]
        + [{"ts_code": "600002.SH", "name": "*ST样本", "start_date": "20190101", "end_date": None}]
    )
    rules = {
        "main": 0.095,
        "chinext_before_20200824": 0.095,
        "chinext_after_20200824": 0.195,
        "star": 0.195,
        "st": 0.045,
    }

    result = attach_trade_limit_flags(market, stock_basic, names, rules)

    assert result["limit_buy"].tolist() == [True, True, False, False, False, False]
    assert result["limit_sell"].tolist() == [False, False, False, True, True, False]

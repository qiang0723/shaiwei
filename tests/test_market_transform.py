import numpy as np
import pandas as pd

from shaiwei.transform.market import transform_market_data


def test_market_transform_adjusts_prices_and_units_with_reversible_factor():
    daily = pd.DataFrame(
        [
            {
                "ts_code": "A", "trade_date": "20200101", "open": 9.0, "high": 11.0,
                "low": 8.0, "close": 10.0, "pre_close": 9.0, "vol": 2.0, "amount": 2.0,
            },
            {
                "ts_code": "A", "trade_date": "20200102", "open": 4.5, "high": 5.5,
                "low": 4.0, "close": 5.0, "pre_close": 4.5, "vol": 4.0, "amount": 2.0,
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


def test_market_transform_refuses_missing_factor():
    daily = pd.DataFrame(
        [{
            "ts_code": "A", "trade_date": "20200101", "open": 1, "high": 1, "low": 1,
            "close": 1, "pre_close": 1, "vol": 1, "amount": 1,
        }]
    )
    factors = pd.DataFrame(columns=["ts_code", "trade_date", "adj_factor"])
    try:
        transform_market_data(daily, factors)
    except ValueError as error:
        assert "missing adj_factor" in str(error)
    else:
        raise AssertionError("missing factor must fail")

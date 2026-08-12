import pandas as pd
import pytest

from shaiwei.research.trend_swing.contract import TrendSwingError
from shaiwei.research.trend_swing.recovery_contract import CHINEXT_REQUEST
from shaiwei.research.trend_swing.recovery_network import validate_response


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ts_code": ["399006.SZ", "399006.SZ"],
            "trade_date": ["20160104", "20260811"],
            "open": [10.0, 11.0],
            "high": [11.0, 12.0],
            "low": [9.0, 10.0],
            "close": [10.5, 11.5],
            "pre_close": [10.0, 10.5],
            "change": [0.5, 1.0],
            "pct_chg": [5.0, 9.5],
            "vol": [100.0, 200.0],
            "amount": [1000.0, 2000.0],
        }
    )


def test_recovery_response_accepts_exact_bounded_history():
    result = validate_response(_frame(), CHINEXT_REQUEST, {"20160104", "20260811"})
    assert result["trade_date"].tolist() == ["20160104", "20260811"]


def test_recovery_response_rejects_duplicate_and_noncalendar_date():
    duplicate = pd.concat([_frame(), _frame().iloc[[0]]], ignore_index=True)
    with pytest.raises(TrendSwingError, match="duplicate"):
        validate_response(duplicate, CHINEXT_REQUEST, {"20160104", "20260811"})
    with pytest.raises(TrendSwingError, match="non-official"):
        validate_response(_frame(), CHINEXT_REQUEST, {"20160104"})

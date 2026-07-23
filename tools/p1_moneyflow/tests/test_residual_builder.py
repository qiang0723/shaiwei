import pandas as pd
import pytest

from tools.p1_moneyflow.residual_builder import (
    formalize_core_with_oos,
    qlib_to_ts_code,
)


def test_qlib_to_ts_code_is_strict():
    assert qlib_to_ts_code("SH600000") == "600000.SH"
    assert qlib_to_ts_code("SZ000001") == "000001.SZ"
    with pytest.raises(ValueError, match="unsupported"):
        qlib_to_ts_code("600000.SH")


def test_formal_panel_never_falls_back_to_core_inside_oos():
    core = pd.DataFrame(
        [
            {"ts_code": "000001.SZ", "trade_date": "20181231", "source_trade_date": "20181228", "f": 1.0},
            {"ts_code": "000001.SZ", "trade_date": "20190102", "source_trade_date": "20181231", "f": 2.0},
            {"ts_code": "000002.SZ", "trade_date": "20190102", "source_trade_date": "20181231", "f": 3.0},
        ]
    )
    incremental = pd.DataFrame(
        [
            {"ts_code": "000001.SZ", "trade_date": "20190102", "source_trade_date": "20181231", "f": 9.0}
        ]
    )
    formal = formalize_core_with_oos(
        core,
        incremental,
        oos_start="20190101",
        oos_end="20191231",
    )
    assert formal[["ts_code", "trade_date", "f"]].to_dict("records") == [
        {"ts_code": "000001.SZ", "trade_date": "20181231", "f": 1.0},
        {"ts_code": "000001.SZ", "trade_date": "20190102", "f": 9.0},
    ]

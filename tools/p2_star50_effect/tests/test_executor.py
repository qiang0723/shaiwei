from __future__ import annotations

import numpy as np
import pandas as pd

from tools.p2_star50_effect.contract import load_protocol
from tools.p2_star50_effect.executor import execute_period


def _fixture():
    dates = pd.bdate_range("2025-01-02", periods=65)
    date_keys = dates.strftime("%Y%m%d").tolist()
    codes = [f"688{index:03d}.SH" for index in range(1, 17)]
    market_rows = []
    member_rows = []
    prediction_rows = []
    for day_index, day in enumerate(date_keys):
        for code_index, code in enumerate(codes):
            price = 20.0 + code_index + 0.01 * day_index
            market_rows.append(
                {
                    "trade_date": day,
                    "ts_code": code,
                    "open": price,
                    "close": price * 1.001,
                    "amount": 1_000_000_000.0,
                    "limit_buy": False,
                    "limit_sell": False,
                }
            )
            member_rows.append(
                {
                    "trade_date": day,
                    "ts_code": code,
                    "has_market_bar": True,
                    "industry": f"I{code_index // 3}",
                    "is_st": False,
                }
            )
            prediction_rows.append((dates[day_index], f"SH{code[:6]}", float(100 - code_index)))
    prediction_index = pd.MultiIndex.from_tuples(
        [(day, code) for day, code, _ in prediction_rows], names=["datetime", "instrument"]
    )
    predictions = pd.Series([score for _, _, score in prediction_rows], index=prediction_index)
    benchmark = pd.DataFrame(
        {"trade_date": date_keys, "pct_chg": np.zeros(len(date_keys), dtype=float)}
    )
    return (
        predictions,
        pd.DataFrame(market_rows),
        pd.DataFrame(member_rows),
        benchmark,
        dates,
    )


def test_fixture_executor_is_next_open_top10_cash_and_deterministic():
    predictions, market, members, benchmark, dates = _fixture()
    protocol = load_protocol()
    first = execute_period(
        predictions=predictions,
        market=market,
        member_days=members,
        benchmark=benchmark,
        start=dates[0].strftime("%Y-%m-%d"),
        end=dates[-1].strftime("%Y-%m-%d"),
        cost_multiplier=1.0,
        extra_slippage_each_side=0.0,
        protocol=protocol,
    )
    second = execute_period(
        predictions=predictions,
        market=market,
        member_days=members,
        benchmark=benchmark,
        start=dates[0].strftime("%Y-%m-%d"),
        end=dates[-1].strftime("%Y-%m-%d"),
        cost_multiplier=1.0,
        extra_slippage_each_side=0.0,
        protocol=protocol,
    )
    assert not first.trades.empty
    # The first two scheduled decisions retain cash because the fixture has not
    # yet accumulated the frozen 15 liquidity observations.  The day-20 signal
    # becomes tradable only at the following official open.
    assert first.trades["trade_date"].min() == dates[21].strftime("%Y%m%d")
    assert first.holdings.groupby("trade_date")["ts_code"].nunique().max() <= 10
    assert first.metrics["rebalance_count"] == 7
    pd.testing.assert_frame_equal(first.daily, second.daily)
    pd.testing.assert_frame_equal(first.holdings, second.holdings)
    pd.testing.assert_frame_equal(first.trades, second.trades)


def test_buy_limit_keeps_cash_without_fabricating_position():
    predictions, market, members, benchmark, dates = _fixture()
    first_execution_day = dates[1].strftime("%Y%m%d")
    market.loc[market["trade_date"].eq(first_execution_day), "limit_buy"] = True
    result = execute_period(
        predictions=predictions,
        market=market,
        member_days=members,
        benchmark=benchmark,
        start=dates[0].strftime("%Y-%m-%d"),
        end=dates[2].strftime("%Y-%m-%d"),
        cost_multiplier=1.0,
        extra_slippage_each_side=0.0,
        protocol=load_protocol(),
    )
    assert result.trades.empty
    assert result.holdings.empty

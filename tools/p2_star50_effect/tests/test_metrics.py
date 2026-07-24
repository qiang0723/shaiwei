from __future__ import annotations

import pandas as pd

from tools.p2_star50_effect.contract import load_protocol
from tools.p2_star50_effect.metrics import (
    diversification_metrics,
    judge_effect,
    maximum_drawdown_from_returns,
    net_excess_return,
)


def test_compound_excess_and_strategy_nav_drawdown_are_distinct():
    strategy = pd.Series([0.10, -0.10])
    benchmark = pd.Series([0.0, 0.0])
    assert abs(net_excess_return(strategy, benchmark) + 0.01) < 1e-12
    assert abs(maximum_drawdown_from_returns(strategy) - 0.10) < 1e-12


def test_missing_preregistered_comparator_is_not_evaluable_and_no_go():
    protocol = load_protocol()
    diversification = diversification_metrics(
        pd.Series([0.0], index=["2023-01-03"]),
        pd.DataFrame(columns=["trade_date", "ts_code", "weight"]),
        None,
        protocol,
    )
    windows = [
        {
            "trade_days": 230,
            "rebalance_count": 23,
            "base_net_excess": 0.01,
            "base_maximum_drawdown": 0.01,
        }
        for _ in range(3)
    ]
    pressure = [{"base_maximum_drawdown": 0.01} for _ in range(3)]
    decision = judge_effect(
        windows,
        pressure,
        {
            "base_net_excess": 0.01,
            "double_cost_net_excess": 0.0,
            "extra_slippage_net_excess": 0.0,
        },
        diversification,
        True,
        protocol,
    )
    assert diversification["status"] == "NOT_EVALUABLE"
    assert decision["historical_effect_gate"] == "NO_GO"
    assert decision["strategy_effective"] == "REJECT"
    assert decision["production_authorization"] == "none"

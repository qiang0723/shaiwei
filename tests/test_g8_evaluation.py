from datetime import date

import numpy as np
import pandas as pd
import pytest

from shaiwei.config import load
from shaiwei.evaluation.g8 import G8Error, _risk_match_pair, comparator_codes, evaluate


def _returns(*, strategy_drift: float, fund_drift: float) -> pd.DataFrame:
    index = pd.bdate_range("2026-03-02", "2029-07-16")
    phase = np.arange(len(index), dtype=float)
    data = {
        "strategy": strategy_drift + 0.010 * np.sin(phase * 0.47),
    }
    for number, code in enumerate(comparator_codes()):
        data[code] = fund_drift + (0.006 + number * 0.0007) * np.sin(
            phase * (0.31 + number * 0.013) + number
        )
    return pd.DataFrame(data, index=index)


def test_g8_is_not_ready_before_three_years():
    result = evaluate(
        _returns(strategy_drift=0.0005, fund_drift=0.0001),
        as_of=date(2029, 7, 14),
    )
    assert result.status == "NOT_READY"
    assert result.basket_median_annualized_excess is None


def test_g8_pass_requires_median_breadth_and_subperiod_stability():
    result = evaluate(
        _returns(strategy_drift=0.0005, fund_drift=0.0001),
        as_of=date(2029, 7, 16),
    )
    assert result.status == "PASS"
    assert result.basket_median_annualized_excess > 0
    assert result.positive_fund_count == 6
    assert result.positive_subperiod_count == 3
    assert all(pair.maximum_strategy_weight <= 1.0 for pair in result.pair_results)
    assert all(pair.maximum_fund_weight <= 1.0 for pair in result.pair_results)


def test_g8_triggers_when_strategy_loses_after_risk_matching():
    result = evaluate(
        _returns(strategy_drift=-0.0001, fund_drift=0.0005),
        as_of=date(2029, 7, 16),
    )
    assert result.status == "TRIGGER_G8"
    assert result.basket_median_annualized_excess < 0


def test_risk_matching_is_pairwise_and_never_leverages():
    index = pd.bdate_range("2029-01-01", periods=3)
    pair_returns = pd.DataFrame(
        {"strategy": [0.01, -0.01, 0.02], "fund": [0.005, -0.005, 0.01]},
        index=index,
    )
    pair_vol = pd.DataFrame(
        {"strategy": [0.20, 0.10, 0.30], "fund": [0.10, 0.20, 0.15]},
        index=index,
    )
    matched = _risk_match_pair(
        pair_returns,
        pair_vol,
        fund_code="fund",
        maximum_weight=1.0,
        residual_cash_daily_return=0.0,
    )
    assert matched["strategy_weight"].tolist() == pytest.approx([0.5, 1.0, 0.5])
    assert matched["fund_weight"].tolist() == pytest.approx([1.0, 0.5, 1.0])


def test_g8_rejects_missing_values_instead_of_forward_filling():
    returns = _returns(strategy_drift=0.0005, fund_drift=0.0001)
    returns.iloc[100, 2] = np.nan
    with pytest.raises(G8Error, match="forward fill is forbidden"):
        evaluate(returns, as_of=date(2029, 7, 16))


def test_frozen_g8_configuration_matches_formula_contract():
    rule = load().g8_evaluation
    assert rule.volatility_lookback_days == 60
    assert rule.minimum_risk_coverage == 0.95
    assert rule.required_fund_count == 6
    assert rule.minimum_positive_funds == 4
    assert rule.required_subperiods == 3
    assert rule.minimum_positive_subperiods == 2
    assert rule.maximum_risk_weight == 1.0

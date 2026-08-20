from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import yaml
from qlib.backtest.decision import OrderDir

from shaiwei.backtest.full_target import (
    BiweeklyRankHeadEqualWeightStrategy,
    FullTargetStrategyError,
    equal_weight_target_amounts,
    position_deltas,
    ranked_topk,
)
from shaiwei.research.production_conversion.contract import Protocol, ProtocolError


def test_protocol_freezes_one_converter_and_original_g0() -> None:
    bundle = Protocol.load()
    protocol = bundle.document

    assert protocol["single_variable_contract"]["changed_variable_count"] == 1
    assert protocol["frozen_score_surface"]["arm"] == "clean_lgbm_control_v1"
    assert protocol["frozen_score_surface"]["model_fit_count"] == 0
    assert protocol["unchanged_g0_gate"]["required_window_count"] == 6
    assert protocol["unchanged_g0_gate"]["minimum_positive_base_cost_excess_windows"] == 4
    assert protocol["unchanged_g0_gate"]["combined_1_5x_cost_cumulative_excess_minimum"] == 0
    assert protocol["attempt_policy"]["new_portfolio_attempt_count"] == 1
    assert bundle.addendum["correction"]["g0_gate_changed"] is False


def test_protocol_rejects_authority_gate_or_predecessor_drift(tmp_path: Path) -> None:
    source = Protocol.load().document
    cases = []
    broadened = deepcopy(source)
    broadened["authority"]["real_backtest_authorized"] = True
    cases.append(broadened)
    changed_gate = deepcopy(source)
    changed_gate["unchanged_g0_gate"]["minimum_positive_base_cost_excess_windows"] = 3
    cases.append(changed_gate)
    changed_hash = deepcopy(source)
    changed_hash["predecessors"]["historical_control_strategy"]["sha256"] = "0" * 64
    cases.append(changed_hash)

    for index, document in enumerate(cases):
        path = tmp_path / f"changed-{index}.yaml"
        path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
        with pytest.raises(ProtocolError):
            Protocol.load(path)


def test_ranked_topk_matches_production_tie_break_and_fails_closed() -> None:
    scores = pd.Series([0.5, 0.7, 0.7, np.nan], index=["SH3", "SH2", "SH1", "SH4"])

    assert ranked_topk(scores, topk=3) == ("SH1", "SH2", "SH3")
    with pytest.raises(FullTargetStrategyError, match="forbidden BSE"):
        ranked_topk(pd.Series([1.0], index=["BJ430001"]), topk=1)
    with pytest.raises(FullTargetStrategyError, match="unique instrument"):
        ranked_topk(pd.Series([1.0, 2.0], index=["SH1", "SH1"]), topk=1)
    with pytest.raises(FullTargetStrategyError, match="nonfinite"):
        ranked_topk(pd.Series([np.inf], index=["SH1"]), topk=1)
    with pytest.raises(FullTargetStrategyError, match="insufficient"):
        ranked_topk(pd.Series([1.0, np.nan], index=["SH1", "SH2"]), topk=2)


def test_equal_weight_full_target_reweights_retained_names() -> None:
    desired = equal_weight_target_amounts(
        ["SH2", "SH3"],
        account_value=1_000.0,
        risk_degree=1.0,
        prices={"SH2": 10.0, "SH3": 10.0},
        round_amount=lambda _code, amount: float(int(amount)),
    )
    sells, buys = position_deltas({"SH1": 50.0, "SH2": 70.0}, desired)

    assert desired == {"SH2": 50.0, "SH3": 50.0}
    assert sells == {"SH1": 50.0, "SH2": 20.0}
    assert buys == {"SH3": 50.0}


class _Calendar:
    def __init__(self, step: int = 0):
        self.step = step

    def get_trade_step(self):
        return self.step

    def get_step_time(self, _step=None, shift=0):
        day = pd.Timestamp("2091-01-03") - pd.offsets.BDay(shift)
        return day, day


class _Signal:
    def get_signal(self, **_kwargs):
        return pd.Series([1.0, 3.0, 2.0], index=["SH1", "SH2", "SH3"])


class _Position:
    def __init__(self):
        self.cash = 0.0
        self.amounts = {"SH1": 50.0, "SH2": 50.0}

    def get_cash(self):
        return self.cash

    def get_stock_amount_dict(self):
        return dict(self.amounts)

    def get_stock_price(self, _code):
        return 10.0

    def check_stock(self, code):
        return code in self.amounts

    def get_stock_amount(self, code):
        return self.amounts.get(code, 0.0)

    def update_order(self, order, trade_val, cost, trade_price):
        if order.direction == OrderDir.SELL:
            self.amounts[order.stock_id] -= order.deal_amount
            self.cash += trade_val - cost


class _Exchange:
    open_cost = 0.0

    def get_deal_price(self, **_kwargs):
        return 10.0

    def is_stock_tradable(self, **_kwargs):
        return True

    def get_factor(self, **_kwargs):
        return 1.0

    def round_amount_by_trade_unit(self, amount, _factor):
        return float(int(amount))

    def check_order(self, _order):
        return True

    def deal_order(self, order, *, position):
        order.deal_amount = order.amount
        value = order.amount * 10.0
        position.update_order(order, value, 0.0, 10.0)
        return value, 0.0, 10.0


def _strategy(step: int = 0) -> BiweeklyRankHeadEqualWeightStrategy:
    strategy = object.__new__(BiweeklyRankHeadEqualWeightStrategy)
    strategy.topk = 2
    strategy.rebalance_days = 10
    strategy.forbid_all_trade_at_limit = False
    strategy.risk_degree = 1.0
    strategy.level_infra = {"trade_calendar": _Calendar(step)}
    strategy.signal = _Signal()
    strategy.common_infra = {"trade_account": SimpleNamespace(current_position=_Position())}
    strategy._trade_exchange = _Exchange()
    return strategy


def test_strategy_builds_full_target_orders_and_respects_cadence() -> None:
    orders = _strategy().generate_trade_decision().get_decision()

    assert [(order.stock_id, order.direction, order.amount) for order in orders] == [
        ("SH1", OrderDir.SELL, 50.0),
        ("SH3", OrderDir.BUY, 50.0),
    ]
    assert _strategy(step=1).generate_trade_decision().get_decision() == []

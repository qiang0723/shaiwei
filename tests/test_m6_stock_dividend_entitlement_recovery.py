from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest
import yaml

from shaiwei.config import load
from shaiwei.paper.engine import Entitlement, PaperEngineError, PortfolioState, Position
from shaiwei.paper.risk_exit_policy import PaperDelistingRiskPortfolio
from shaiwei.paper.sell_execution import execute_sell
from shaiwei.paper.stock_dividend_entitlement import (
    apply_due_actions_with_detached_stock_credit,
    execute_entitlement_recovery_day,
)
from shaiwei.research.capital_feasibility.stock_dividend_entitlement_recovery_contract import (
    LEGACY_ENGINE_SHA256,
    LEGACY_RISK_ENGINE_SHA256,
    PROTOCOL_PATH,
    load_entitlement_recovery,
)
from shaiwei.research.production_conversion.contract import ProtocolError


ROOT = Path(__file__).parents[1]
DAY = "20260717"
CODE = "600001.SH"


def _entitlement(
    identity: str,
    *,
    code: str = CODE,
    quantity: int = 1_000,
    cash: str = "0",
    stock: str = "0.1",
    pay_date: str = "20260720",
    list_date: str = DAY,
) -> Entitlement:
    return Entitlement(
        action_id=identity,
        ts_code=code,
        record_date="20260710",
        entitled_quantity=quantity,
        cash_per_share=cash,
        stock_per_share=stock,
        pay_date=pay_date,
        div_listdate=list_date,
    )


def _state(*entitlements: Entitlement) -> PortfolioState:
    return PortfolioState(
        account_id="m6_head30_delisting_risk",
        cash="10000.00",
        entitlements={item.action_id: item for item in entitlements},
        benchmark_base_open="100",
        last_trade_date="20260716",
    )


def _policy() -> PaperDelistingRiskPortfolio:
    values = load().paper_portfolio.model_dump()
    values.update(
        account_id="m6_head30_delisting_risk",
        execution_policy_version="paper-v2-delisting-risk-exit",
        initial_cash=10_000,
        risk_trigger_price_cny=1.0,
        risk_trigger_consecutive_closes=10,
        risk_exit_latched=True,
        risk_cash_reserve_authorized=True,
    )
    return PaperDelistingRiskPortfolio(**values)


def test_contract_freezes_one_non_production_change_and_ordinal_two() -> None:
    document = load_entitlement_recovery()

    assert document["single_change"]["detached_stock_credit"]["position_cost_basis"] == "0.00"
    assert document["frozen_legacy"]["paper_v1_engine_sha256"] == LEGACY_ENGINE_SHA256
    assert document["future_attempt"]["attempt_ordinal"] == 2
    assert document["future_attempt"]["family_attempts_before_run"] == 1
    assert document["authority"]["real_effect_read_authorized"] is False
    assert document["authority"]["production_authorization"] == "none"


def test_contract_rejects_authority_broadening(tmp_path: Path) -> None:
    document = yaml.safe_load(PROTOCOL_PATH.read_text(encoding="utf-8"))
    document["authority"]["real_effect_read_authorized"] = True
    changed = tmp_path / "changed.yaml"
    changed.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")

    with pytest.raises(ProtocolError, match="authority was broadened"):
        load_entitlement_recovery(changed)


def test_detached_stock_credit_is_zero_cost_idempotent_and_sellable() -> None:
    state = _state(_entitlement("stock-1"))
    events = apply_due_actions_with_detached_stock_credit(state, day=DAY, actions=[])

    assert state.cash == "10000.00"
    assert state.positions[CODE].quantity == 100
    assert state.positions[CODE].cost_basis == "0.00"
    assert events[0]["event"] == "STOCK_DIVIDEND"
    assert apply_due_actions_with_detached_stock_credit(state, day=DAY, actions=[]) == []
    assert state.positions[CODE].quantity == 100

    outcome = execute_sell(
        code=CODE,
        position=state.positions[CODE],
        desired_quantity=0,
        target_weight=Decimal("0"),
        status="OK",
        price=Decimal("10"),
        policy=_policy(),
        run_id="detached-credit-sell",
        cash=state.cash_value,
        market_batch_id="synthetic",
        reference_close=Decimal("10"),
    )
    assert outcome is not None and outcome.fill is not None
    assert outcome.fill["quantity"] == 100
    assert state.positions[CODE].quantity == 0


def test_existing_position_keeps_total_cost_basis() -> None:
    state = _state(_entitlement("stock-existing"))
    state.positions[CODE] = Position(1_000, "9000.00")

    apply_due_actions_with_detached_stock_credit(state, day=DAY, actions=[])

    assert state.positions[CODE].quantity == 1_100
    assert state.positions[CODE].cost_basis == "9000.00"


def test_fractional_credit_fails_without_leaving_detached_position() -> None:
    state = _state(_entitlement("fractional", quantity=3, stock="0.5"))

    with pytest.raises(PaperEngineError, match="fractional stock dividend"):
        apply_due_actions_with_detached_stock_credit(state, day=DAY, actions=[])

    assert CODE not in state.positions
    assert state.entitlements["fractional"].stock_paid is False


def test_cash_only_entitlement_credits_cash_without_creating_position() -> None:
    state = _state(
        _entitlement(
            "cash-only",
            cash="0.5",
            stock="0",
            pay_date=DAY,
            list_date="20260720",
        )
    )

    events = apply_due_actions_with_detached_stock_credit(state, day=DAY, actions=[])

    assert state.cash == "10500.00"
    assert state.positions == {}
    assert events[0]["event"] == "CASH_DIVIDEND"


def test_multiple_same_code_entitlements_are_deterministic() -> None:
    state = _state(
        _entitlement("first", quantity=100, stock="0.1"),
        _entitlement("second", quantity=100, stock="0.2"),
    )
    replay = deepcopy(state)

    first = apply_due_actions_with_detached_stock_credit(state, day=DAY, actions=[])
    second = apply_due_actions_with_detached_stock_credit(replay, day=DAY, actions=[])

    assert first == second
    assert state.to_dict() == replay.to_dict()
    assert state.positions[CODE].quantity == 30


def test_risk_engine_credits_detached_shares_before_valuation() -> None:
    state = _state(_entitlement("integration"))
    daily = pd.DataFrame(
        [{"ts_code": CODE, "trade_date": DAY, "open": 10, "pre_close": 10, "close": 10, "vol": 1000}]
    )
    result = execute_entitlement_recovery_day(
        policy=_policy(),
        state=state,
        signal={"rebalance_due": False, "orders": []},
        signal_sha256="a" * 64,
        execution_date=DAY,
        daily=daily,
        signal_daily=daily,
        index_row=pd.Series(
            {"ts_code": "000906.SH", "trade_date": DAY, "open": 100, "close": 100}
        ),
        stock_basic=pd.DataFrame(
            [{"ts_code": CODE, "list_date": "20100101", "delist_date": None}]
        ),
        namechange=pd.DataFrame(
            [{"ts_code": CODE, "name": "普通样本", "start_date": "20100101", "end_date": None}]
        ),
        suspend=pd.DataFrame(
            columns=["ts_code", "trade_date", "suspend_timing", "suspend_type"]
        ),
        trade_cal=pd.DataFrame({"cal_date": ["20260716", DAY], "is_open": [1, 1]}),
        dividends=pd.DataFrame(),
        run_id="detached-credit-integration",
        market_batch_id="synthetic",
    )

    assert result.state.positions[CODE].quantity == 100
    assert result.state.positions[CODE].cost_basis == "0.00"
    assert result.nav["market_value"] == "1000.00"
    assert result.nav["equation_difference"] == "0.00"


def test_new_modules_are_bounded_and_legacy_engine_is_byte_stable() -> None:
    engine = ROOT / "src/shaiwei/paper/engine.py"
    risk_engine = ROOT / "src/shaiwei/paper/risk_exit_engine.py"
    modules = [
        ROOT / "src/shaiwei/paper/stock_dividend_entitlement.py",
        ROOT
        / "src/shaiwei/research/capital_feasibility/stock_dividend_entitlement_recovery_contract.py",
    ]
    assert len(engine.read_text(encoding="utf-8").splitlines()) == 860
    assert __import__("hashlib").sha256(engine.read_bytes()).hexdigest() == LEGACY_ENGINE_SHA256
    assert (
        __import__("hashlib").sha256(risk_engine.read_bytes()).hexdigest()
        == LEGACY_RISK_ENGINE_SHA256
    )
    assert all(len(path.read_text(encoding="utf-8").splitlines()) <= 400 for path in modules)

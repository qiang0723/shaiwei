"""Paper-v2 adapter for stock dividends due after the original position was sold."""

from __future__ import annotations

from decimal import ROUND_FLOOR

import pandas as pd

from shaiwei.paper.engine import (
    DayResult,
    PaperEngineError,
    PortfolioState,
    Position,
    _apply_due_actions,
    _decimal,
)
from shaiwei.paper.risk_exit_engine import execute_risk_day
from shaiwei.paper.risk_exit_policy import PaperDelistingRiskPortfolio


def _detached_credit_codes(state: PortfolioState, *, day: str) -> tuple[str, ...]:
    codes: list[str] = []
    for entitlement in state.entitlements.values():
        if entitlement.div_listdate != day or entitlement.stock_paid:
            continue
        raw = _decimal(entitlement.stock_per_share) * entitlement.entitled_quantity
        shares = int(raw.to_integral_value(rounding=ROUND_FLOOR))
        if raw != shares:
            raise PaperEngineError(
                "fractional stock dividend requires authoritative rounding evidence"
            )
        if shares > 0 and entitlement.ts_code not in state.positions:
            codes.append(entitlement.ts_code)
    return tuple(sorted(set(codes)))


def apply_due_actions_with_detached_stock_credit(
    state: PortfolioState,
    *,
    day: str,
    actions: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Preserve record-date stock rights without changing frozen v1 accounting."""
    for code in _detached_credit_codes(state, day=day):
        state.positions[code] = Position(quantity=0, cost_basis="0.00")
    return _apply_due_actions(state, day=day, actions=actions)


def execute_entitlement_recovery_day(
    *,
    policy: PaperDelistingRiskPortfolio,
    state: PortfolioState | None,
    signal: dict[str, object],
    signal_sha256: str,
    execution_date: str,
    daily: pd.DataFrame,
    signal_daily: pd.DataFrame,
    index_row: pd.Series,
    stock_basic: pd.DataFrame,
    namechange: pd.DataFrame,
    suspend: pd.DataFrame,
    trade_cal: pd.DataFrame,
    dividends: pd.DataFrame,
    run_id: str,
    market_batch_id: str,
    forced_exit_codes: tuple[str, ...] = (),
) -> DayResult:
    """Run the entitlement recovery without mutating the archived paper-v2 engine."""
    if state is not None:
        for code in _detached_credit_codes(state, day=execution_date):
            state.positions[code] = Position(quantity=0, cost_basis="0.00")
    return execute_risk_day(
        policy=policy,
        state=state,
        signal=signal,
        signal_sha256=signal_sha256,
        execution_date=execution_date,
        daily=daily,
        signal_daily=signal_daily,
        index_row=index_row,
        stock_basic=stock_basic,
        namechange=namechange,
        suspend=suspend,
        trade_cal=trade_cal,
        dividends=dividends,
        run_id=run_id,
        market_batch_id=market_batch_id,
        forced_exit_codes=forced_exit_codes,
    )

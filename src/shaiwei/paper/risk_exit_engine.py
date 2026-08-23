"""Research-only paper-v2 adapter for latched delisting-risk exits."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pandas as pd

from shaiwei.config import PaperPortfolio
from shaiwei.paper.engine import (
    ZERO,
    DayResult,
    PaperEngineError,
    PortfolioState,
    Position,
    _apply_due_actions,
    _board,
    _capture_entitlements,
    _decimal,
    _desired_quantity,
    _fill,
    _implemented_actions,
    _intermediate_action_events,
    _money,
    _order,
    _valuation,
    calculate_fees,
    execute_day as execute_paper_v1_day,
    opening_status,
)
from shaiwei.paper.risk_exit_policy import PaperDelistingRiskPortfolio
from shaiwei.paper.sell_execution import execute_sell
from shaiwei.shadow.reconciliation import tushare_code


def _target_weights(signal: dict[str, object]) -> tuple[dict[str, Decimal], dict[str, int]]:
    orders = signal.get("orders")
    if not isinstance(orders, list):
        raise PaperEngineError("signal orders must be a list")
    weights: dict[str, Decimal] = {}
    ranks: dict[str, int] = {}
    for order in orders:
        if not isinstance(order, dict):
            raise PaperEngineError("signal order must be a mapping")
        code = tushare_code(str(order["instrument"]))
        if code.endswith(".BJ") or code in weights:
            raise PaperEngineError("paper signal contains forbidden or duplicate instrument")
        weights[code] = _decimal(order["target_weight"])
        ranks[code] = int(order["rank"])
    total = sum(weights.values(), ZERO)
    if total < 0 or total > 1 or any(weight <= 0 for weight in weights.values()):
        raise PaperEngineError("risk-exit signal target weights are invalid")
    return weights, ranks


def _normalize_code(raw_value: object) -> str:
    value = str(raw_value).upper()
    if (
        len(value) == 9
        and value[:6].isdigit()
        and value[6] == "."
        and value[7:] in {"SH", "SZ", "BJ"}
    ):
        return value
    try:
        return tushare_code(value)
    except RuntimeError as exc:
        raise PaperEngineError("forced risk exit instrument is invalid") from exc


def _forced_exits(
    values: tuple[str, ...],
    *,
    state: PortfolioState,
    weights: dict[str, Decimal],
) -> tuple[str, ...]:
    normalized = tuple(_normalize_code(value) for value in values)
    if len(normalized) != len(set(normalized)):
        raise PaperEngineError("forced risk exit contains duplicate instruments")
    if any(code.endswith(".BJ") for code in normalized):
        raise PaperEngineError("BSE instrument is forbidden in forced risk exit")
    if set(normalized) - set(state.positions):
        raise PaperEngineError("forced risk exit contains an unheld instrument")
    if set(normalized) & set(weights):
        raise PaperEngineError("forced risk exit remains in target weights")
    return tuple(sorted(normalized))


def execute_risk_day(
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
    """Execute one paper-v2 day without changing the immutable paper-v1 engine."""
    del signal_sha256
    if not isinstance(policy, PaperDelistingRiskPortfolio):
        raise PaperEngineError("risk exit adapter requires paper-v2-delisting-risk-exit")
    if str(index_row["trade_date"]) != execution_date:
        raise PaperEngineError("benchmark row does not match execution date")
    if state is None:
        state = PortfolioState.initial(policy, index_row["open"])
    if state.account_id != policy.account_id:
        raise PaperEngineError("paper state account does not match policy")
    if state.last_trade_date and state.last_trade_date >= execution_date:
        raise PaperEngineError("paper execution dates must be strictly increasing")
    weights, ranks = _target_weights(signal)
    forced_exits = _forced_exits(forced_exit_codes, state=state, weights=weights)
    action_after = state.last_trade_date or (
        datetime.strptime(execution_date, "%Y%m%d").date() - timedelta(days=1)
    ).strftime("%Y%m%d")
    actions = _implemented_actions(
        dividends,
        relevant_codes=set(state.positions) | set(weights),
        after_date=action_after,
        through_date=execution_date,
    )
    action_events = _intermediate_action_events(
        state,
        execution_date=execution_date,
        actions=actions,
    )
    action_events.extend(_apply_due_actions(state, day=execution_date, actions=actions))
    rebalance_due = bool(signal.get("rebalance_due", True))
    open_prices: dict[str, Decimal] = {}
    for code in set(state.positions) | set(weights):
        rows = daily.loc[daily["ts_code"].astype(str).eq(code)]
        if len(rows) == 1 and pd.notna(rows.iloc[0]["open"]) and float(rows.iloc[0]["open"]) > 0:
            open_prices[code] = _decimal(rows.iloc[0]["open"])
        elif code in state.positions and state.positions[code].last_close:
            open_prices[code] = _decimal(state.positions[code].last_close)
    opening_equity = state.cash_value + sum(
        (open_prices[code] * position.quantity for code, position in state.positions.items()),
        ZERO,
    )
    desired = {
        code: _desired_quantity(code, opening_equity * weight, open_prices[code], policy)
        if code in open_prices
        else 0
        for code, weight in weights.items()
    }
    reference_close = {
        str(row.ts_code): _decimal(row.close)
        for row in signal_daily.loc[:, ["ts_code", "close"]].itertuples(index=False)
        if pd.notna(row.close) and float(row.close) > 0
    }
    orders: list[dict[str, object]] = []
    fills: list[dict[str, object]] = []
    gross_notional = ZERO
    daily_fees = ZERO
    cash = state.cash_value
    sell_intents: list[tuple[str, int, Decimal, str]] = [
        (code, 0, ZERO, "DELISTING_PRICE_RISK_EXIT") for code in forced_exits
    ]
    if rebalance_due:
        sell_intents.extend(
            (code, desired.get(code, 0), weights.get(code, ZERO), "")
            for code, position in sorted(state.positions.items())
            if code not in set(forced_exits) and position.quantity > desired.get(code, 0)
        )
    for code, sell_desired, target_weight, execution_reason in sell_intents:
        position = state.positions[code]
        status, price = opening_status(
            code=code,
            side="SELL",
            trade_date=execution_date,
            daily=daily,
            stock_basic=stock_basic,
            namechange=namechange,
            suspend=suspend,
            trade_cal=trade_cal,
            policy=policy,
        )
        outcome = execute_sell(
            code=code,
            position=position,
            desired_quantity=sell_desired,
            target_weight=target_weight,
            status=status,
            price=price,
            policy=policy,
            run_id=run_id,
            cash=cash,
            market_batch_id=market_batch_id,
            reference_close=reference_close.get(code),
            execution_reason=execution_reason,
        )
        if outcome is None:
            continue
        orders.append(outcome.order)
        if outcome.fill is None:
            continue
        fills.append(outcome.fill)
        cash = outcome.cash_after
        gross_notional += outcome.notional
        daily_fees += outcome.total_fee
        if position.quantity == 0:
            del state.positions[code]
    if rebalance_due:
        for code in sorted(weights, key=lambda name: (ranks[name], name)):
            current = state.positions.get(code, Position(0, "0.00")).quantity
            requested = max(0, desired[code] - current)
            if requested == 0:
                if current == 0 and desired[code] == 0:
                    orders.append(
                        _order(
                            run_id=run_id,
                            code=code,
                            side="BUY",
                            target_weight=weights[code],
                            desired_quantity=0,
                            requested_quantity=0,
                            status="REJECTED",
                            reject_reason="BELOW_MIN_LOT",
                        )
                    )
                continue
            order = _order(
                run_id=run_id,
                code=code,
                side="BUY",
                target_weight=weights[code],
                desired_quantity=desired[code],
                requested_quantity=requested,
            )
            status, price = opening_status(
                code=code,
                side="BUY",
                trade_date=execution_date,
                daily=daily,
                stock_basic=stock_basic,
                namechange=namechange,
                suspend=suspend,
                trade_cal=trade_cal,
                policy=policy,
            )
            if status != "OK" or price is None:
                order.update(status="REJECTED", reject_reason=status)
                orders.append(order)
                continue
            quantity = requested
            step = 1 if _board(code) == "STAR" else policy.main_board_lot_size
            minimum = policy.star_minimum_lot if _board(code) == "STAR" and current == 0 else step
            while quantity >= minimum:
                notional = _money(price * quantity)
                fees = calculate_fees(notional, "BUY", policy)
                if notional + fees["total"] <= cash:
                    break
                quantity -= step
            if quantity < minimum:
                order.update(status="REJECTED", reject_reason="INSUFFICIENT_CASH")
                orders.append(order)
                continue
            notional = _money(price * quantity)
            fees = calculate_fees(notional, "BUY", policy)
            position = state.positions.setdefault(code, Position(0, "0.00"))
            position.quantity += quantity
            position.cost_basis = f"{_money(position.cost + notional + fees['total']):.2f}"
            cash = _money(cash - notional - fees["total"])
            order.update(
                status="FILLED" if quantity == requested else "PARTIALLY_FILLED",
                filled_quantity=quantity,
                reject_reason="" if quantity == requested else "CASH_LIMIT",
            )
            fill = _fill(
                order=order,
                quantity=quantity,
                price=price,
                fees=fees,
                market_batch_id=market_batch_id,
                reference_close=reference_close.get(code),
                cash_after=cash,
                position_after=position.quantity,
            )
            orders.append(order)
            fills.append(fill)
            gross_notional += notional
            daily_fees += fees["total"]
    state.cash = f"{_money(cash):.2f}"
    state.cumulative_fees = f"{_money(_decimal(state.cumulative_fees) + daily_fees):.2f}"
    action_events.extend(_capture_entitlements(state, day=execution_date, actions=actions))
    nav = _valuation(
        state,
        execution_date=execution_date,
        daily=daily,
        index_row=index_row,
        stock_basic=stock_basic,
        trade_cal=trade_cal,
        opening_equity=opening_equity,
        gross_notional=_money(gross_notional),
        daily_fees=_money(daily_fees),
        policy=policy,
    )
    state.last_trade_date = execution_date
    return DayResult(
        state=state,
        orders=tuple(orders),
        fills=tuple(fills),
        corporate_actions=tuple(action_events),
        nav=nav,
    )


def execute_paper_day(
    *,
    policy: PaperPortfolio,
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
    """Dispatch v1 byte-stably or v2 through the isolated risk adapter."""
    arguments = {
        "policy": policy,
        "state": state,
        "signal": signal,
        "signal_sha256": signal_sha256,
        "execution_date": execution_date,
        "daily": daily,
        "signal_daily": signal_daily,
        "index_row": index_row,
        "stock_basic": stock_basic,
        "namechange": namechange,
        "suspend": suspend,
        "trade_cal": trade_cal,
        "dividends": dividends,
        "run_id": run_id,
        "market_batch_id": market_batch_id,
    }
    if isinstance(policy, PaperDelistingRiskPortfolio):
        return execute_risk_day(
            **arguments,
            forced_exit_codes=forced_exit_codes,
        )
    if forced_exit_codes:
        raise PaperEngineError("forced risk exit requires paper-v2-delisting-risk-exit")
    return execute_paper_v1_day(**arguments)

"""Deterministic lot, cash, fee, and capacity execution for M6-5A."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from typing import Iterable

from .contract import Policy


CENT = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Target:
    instrument: str
    score: float
    price: Decimal
    board: str = "MAIN"
    tradable: bool = True
    trailing_median_amount: Decimal = Decimal("100000000")


@dataclass
class Account:
    cash: Decimal
    holdings: dict[str, int]


def _fees(notional: Decimal, side: str, policy: Policy) -> Decimal:
    commission = max(_money(notional * policy.commission_rate), policy.minimum_commission)
    transfer = _money(notional * policy.transfer_fee_rate)
    stamp = _money(notional * policy.stamp_tax_rate) if side == "SELL" else Decimal("0")
    return _money(commission + transfer + stamp)


def _target_quantity(target: Target, notional: Decimal, policy: Policy) -> int:
    raw = int((notional / target.price).to_integral_value(rounding=ROUND_DOWN))
    if target.board == "STAR":
        return raw if raw >= policy.star_minimum else 0
    return raw // policy.main_lot * policy.main_lot


def _policy_evidence(policy: Policy) -> dict[str, str | int]:
    return {
        "initial_cash": str(policy.initial_cash),
        "commission_rate": str(policy.commission_rate),
        "minimum_commission": str(policy.minimum_commission),
        "stamp_tax_rate": str(policy.stamp_tax_rate),
        "transfer_fee_rate": str(policy.transfer_fee_rate),
        "main_lot": policy.main_lot,
        "star_minimum": policy.star_minimum,
        "capacity_fraction": str(policy.capacity_fraction),
    }


def _decrement(board: str, quantity: int, policy: Policy) -> int:
    step = 1 if board == "STAR" else policy.main_lot
    return max(0, quantity - step)


def rebalance(account: Account, targets: Iterable[Target], policy: Policy = Policy()) -> dict:
    ordered = sorted(targets, key=lambda item: (-item.score, item.instrument))
    by_code = {target.instrument: target for target in ordered}
    if len(ordered) != 30 or len(by_code) != 30:
        raise ValueError("M6-5A requires exactly 30 unique targets")
    if any(code.endswith(".BJ") for code in by_code):
        raise ValueError("M6-5A rejects Beijing instruments")
    missing_prices = set(account.holdings) - set(by_code)
    if missing_prices:
        raise ValueError(f"missing liquidation prices: {sorted(missing_prices)}")
    equity_before = account.cash + sum(
        Decimal(quantity) * by_code[code].price for code, quantity in account.holdings.items()
    )
    target_notional = equity_before / Decimal(30)
    desired = {target.instrument: _target_quantity(target, target_notional, policy) for target in ordered}
    fees_total, turnover = Decimal("0"), Decimal("0")
    capacity_violations = invalid_lots = minimum_lot_rejections = 0
    trades: list[dict] = []
    for code in sorted(account.holdings):
        target = by_code[code]
        current = account.holdings.get(code, 0)
        quantity = max(0, current - desired[code])
        if not quantity or not target.tradable:
            continue
        notional = Decimal(quantity) * target.price
        if notional > target.trailing_median_amount * policy.capacity_fraction:
            capacity_violations += 1
            continue
        fee = _fees(notional, "SELL", policy)
        account.cash = _money(account.cash + notional - fee)
        account.holdings[code] = current - quantity
        fees_total, turnover = fees_total + fee, turnover + notional
        trades.append({"instrument": code, "side": "SELL", "quantity": quantity})
    for target in ordered:
        current = account.holdings.get(target.instrument, 0)
        quantity = max(0, desired[target.instrument] - current)
        if quantity == 0:
            if current == 0:
                minimum_lot_rejections += 1
            continue
        if not target.tradable:
            continue
        notional = Decimal(quantity) * target.price
        if notional > target.trailing_median_amount * policy.capacity_fraction:
            capacity_violations += 1
            continue
        fee = _fees(notional, "BUY", policy)
        while quantity and _money(notional + fee) > account.cash:
            quantity = _decrement(target.board, quantity, policy)
            notional = Decimal(quantity) * target.price
            fee = _fees(notional, "BUY", policy) if quantity else Decimal("0")
        if quantity == 0:
            minimum_lot_rejections += 1
            continue
        if target.board != "STAR" and quantity % policy.main_lot:
            invalid_lots += 1
        if target.board == "STAR" and current == 0 and quantity < policy.star_minimum:
            invalid_lots += 1
        account.cash = _money(account.cash - notional - fee)
        account.holdings[target.instrument] = current + quantity
        fees_total, turnover = fees_total + fee, turnover + notional
        trades.append({"instrument": target.instrument, "side": "BUY", "quantity": quantity})
    actual_value = {
        code: Decimal(quantity) * by_code[code].price
        for code, quantity in account.holdings.items() if quantity
    }
    equity_after = account.cash + sum(actual_value.values())
    weights = {code: float(value / equity_after) for code, value in actual_value.items()}
    target_weight = 1 / 30
    l1 = sum(abs(weights.get(code, 0.0) - target_weight) for code in by_code)
    cash_ratio = float(account.cash / equity_after)
    l1 += cash_ratio
    expected_equity_after = equity_before - fees_total
    accounting_difference = equity_after - expected_equity_after
    return {
        "equity_before": str(_money(equity_before)), "equity_after": str(_money(equity_after)),
        "cash": str(account.cash), "cash_ratio": cash_ratio,
        "realized_position_count": len(actual_value), "target_l1_error": l1,
        "fees": str(_money(fees_total)), "turnover": str(_money(turnover)),
        "capacity_violation_count": capacity_violations,
        "invalid_lot_fill_count": invalid_lots,
        "minimum_lot_rejection_count": minimum_lot_rejections,
        "target_buy_leg_count": 30, "negative_cash": account.cash < 0,
        "accounting_difference": str(_money(accounting_difference)),
        "trades": trades, "holdings": dict(sorted(account.holdings.items())),
        "policy": _policy_evidence(policy),
    }

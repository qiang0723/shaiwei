"""Shared deterministic order, fee, fill, and sell-state calculations."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
import hashlib
from typing import Protocol

from shaiwei.config import PaperPortfolio
from shaiwei.paper.engine import PaperEngineError


CENT = Decimal("0.01")
ZERO = Decimal("0")


class MutablePosition(Protocol):
    quantity: int
    cost_basis: str
    realized_pnl: str


@dataclass(frozen=True)
class SellExecutionResult:
    order: dict[str, object]
    fill: dict[str, object] | None
    cash_after: Decimal
    notional: Decimal
    total_fee: Decimal


def _decimal(value: object) -> Decimal:
    return Decimal(str(value))


def _money(value: Decimal | float | str) -> Decimal:
    return _decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_fees(
    notional: Decimal, side: str, policy: PaperPortfolio
) -> dict[str, Decimal]:
    if notional <= 0:
        raise PaperEngineError("fee notional must be positive")
    commission = max(
        _money(notional * _decimal(policy.commission_rate)),
        _money(policy.minimum_commission),
    )
    transfer = _money(notional * _decimal(policy.transfer_fee_rate))
    stamp = _money(notional * _decimal(policy.stamp_tax_rate)) if side == "SELL" else ZERO
    return {
        "commission": commission,
        "stamp_tax": stamp,
        "transfer_fee": transfer,
        "total": _money(commission + stamp + transfer),
    }


def sell_quantity(
    *, code: str, current: int, desired: int, policy: PaperPortfolio
) -> int:
    difference = current - desired
    if difference <= 0:
        return 0
    if desired == 0:
        return current
    if code.startswith(("688", "689")) and code.endswith(".SH"):
        return difference if difference >= policy.star_minimum_lot else 0
    return difference // policy.main_board_lot_size * policy.main_board_lot_size


def build_order(
    *,
    run_id: str,
    code: str,
    side: str,
    target_weight: Decimal,
    desired_quantity: int,
    requested_quantity: int,
    status: str = "PENDING",
    reject_reason: str = "",
    execution_reason: str = "",
) -> dict[str, object]:
    key = f"{run_id}|{code}|{side}"
    order: dict[str, object] = {
        "order_id": hashlib.sha256(key.encode()).hexdigest()[:20],
        "ts_code": code,
        "side": side,
        "target_weight": str(target_weight),
        "desired_quantity": desired_quantity,
        "requested_quantity": requested_quantity,
        "filled_quantity": 0,
        "status": status,
        "reject_reason": reject_reason,
    }
    if execution_reason:
        order["execution_reason"] = execution_reason
    return order


def build_fill(
    *,
    order: dict[str, object],
    quantity: int,
    price: Decimal,
    fees: dict[str, Decimal],
    market_batch_id: str,
    reference_close: Decimal | None,
    cash_after: Decimal,
    position_after: int,
) -> dict[str, object]:
    notional = _money(price * quantity)
    deviation = None if reference_close is None else float(price / reference_close - 1)
    return {
        "fill_id": hashlib.sha256(
            f"{order['order_id']}|{quantity}|{price}".encode()
        ).hexdigest()[:20],
        "order_id": order["order_id"],
        "ts_code": order["ts_code"],
        "side": order["side"],
        "quantity": quantity,
        "price": str(price),
        "notional": f"{notional:.2f}",
        "commission": f"{fees['commission']:.2f}",
        "stamp_tax": f"{fees['stamp_tax']:.2f}",
        "transfer_fee": f"{fees['transfer_fee']:.2f}",
        "total_fee": f"{fees['total']:.2f}",
        "market_batch_id": market_batch_id,
        "open_deviation": deviation,
        "cash_after": f"{cash_after:.2f}",
        "position_after": position_after,
    }


def execute_sell(
    *,
    code: str,
    position: MutablePosition,
    desired_quantity: int,
    target_weight: Decimal,
    status: str,
    price: Decimal | None,
    policy: PaperPortfolio,
    run_id: str,
    cash: Decimal,
    market_batch_id: str,
    reference_close: Decimal | None,
    execution_reason: str = "",
) -> SellExecutionResult | None:
    """Apply one sell atomically to a mutable position after market-state adjudication."""
    quantity = sell_quantity(
        code=code,
        current=position.quantity,
        desired=desired_quantity,
        policy=policy,
    )
    if quantity <= 0:
        return None
    order = build_order(
        run_id=run_id,
        code=code,
        side="SELL",
        target_weight=target_weight,
        desired_quantity=desired_quantity,
        requested_quantity=quantity,
        execution_reason=execution_reason,
    )
    if status != "OK" or price is None:
        order.update(status="REJECTED", reject_reason=status)
        return SellExecutionResult(order, None, cash, ZERO, ZERO)
    notional = _money(price * quantity)
    fees = calculate_fees(notional, "SELL", policy)
    old_quantity = position.quantity
    position_cost = _decimal(position.cost_basis)
    removed_cost = _money(position_cost * quantity / old_quantity)
    realized = _money(notional - fees["total"] - removed_cost)
    position.quantity -= quantity
    position.cost_basis = f"{_money(position_cost - removed_cost):.2f}"
    position.realized_pnl = f"{_money(_decimal(position.realized_pnl) + realized):.2f}"
    cash_after = _money(cash + notional - fees["total"])
    order.update(status="FILLED", filled_quantity=quantity)
    fill = build_fill(
        order=order,
        quantity=quantity,
        price=price,
        fees=fees,
        market_batch_id=market_batch_id,
        reference_close=reference_close,
        cash_after=cash_after,
        position_after=position.quantity,
    )
    return SellExecutionResult(order, fill, cash_after, notional, fees["total"])

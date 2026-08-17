"""R3G-2 sizing, lot accounting, capacity, and fill operations."""

from __future__ import annotations

import math
from typing import Any

from shaiwei.research.trend_swing.r3g2.contract import R3G2Error
from shaiwei.research.trend_swing.r3g2.effect_fees import adverse_price, fees, opening_legal
from shaiwei.research.trend_swing.r3g2.effect_models import (
    Lot,
    PortfolioState,
    Position,
    Scenario,
)


LOT_SIZE = 100


def position_values(
    state: PortfolioState,
    day: str,
    bars: dict[tuple[str, str], dict[str, Any]],
    last_close: dict[str, float],
    field: str,
) -> dict[str, float]:
    values: dict[str, float] = {}
    for code, position in state.positions.items():
        row = bars.get((day, code))
        price = float(row[field]) if row is not None else last_close.get(code)
        if price is None or not math.isfinite(price) or price <= 0:
            raise R3G2Error(f"R3G-2 cannot value held security {code} on {day}")
        values[code] = position.value(price)
    return values


def _open_risk(
    state: PortfolioState,
    day: str,
    bars: dict[tuple[str, str], dict[str, Any]],
    last_close: dict[str, float],
) -> float:
    total = 0.0
    for code, position in state.positions.items():
        row = bars.get((day, code))
        price = float(row["adj_open"]) if row is not None else last_close[code]
        total += position.value(price) * max(0.0, 1.0 - position.stop_adjusted / price)
    return total


def _buy_limit(
    state: PortfolioState,
    event: dict[str, Any],
    row: dict[str, Any],
    equity: float,
    values: dict[str, float],
    current: Scenario,
    batch: int,
    last_close: dict[str, float],
    bars: dict[tuple[str, str], dict[str, Any]],
) -> tuple[int, float, float, str, bool]:
    if equity <= 0 or not opening_legal(row, "BUY"):
        return 0, 0.0, 0.0, "OPEN_NOT_BUYABLE", False
    capacity = float(row["amount_median20_rmb"]) * 0.05
    if not math.isfinite(capacity) or capacity <= 0:
        return 0, 0.0, 0.0, "CAPACITY_HISTORY_INSUFFICIENT", True
    raw_price = adverse_price(float(row["raw_open"]), "BUY", current)
    adjusted_price = raw_price * float(row["adj_factor"])
    stop = float(event["initial_stop_adjusted"])
    risk_fraction = 1.0 - stop / adjusted_price
    if not 0 < risk_fraction < 1:
        return 0, raw_price, adjusted_price, "STOP_DISTANCE_INVALID", False
    code, industry = str(event["ts_code"]), str(event["industry"])
    current_security = values.get(code, 0.0)
    current_industry = sum(
        value for held, value in values.items() if state.positions[held].industry == industry
    )
    current_risk = _open_risk(state, str(row["trade_date"]), bars, last_close)
    position_risk_cap = (0.0025 if batch == 1 else 0.005) * equity
    existing_risk = current_security * risk_fraction if batch == 2 else 0.0
    remaining_position_risk = max(0.0, position_risk_cap - existing_risk)
    limits = (
        0.05 * equity,
        0.10 * equity - current_security,
        0.70 * equity - sum(values.values()),
        0.30 * equity - current_industry,
        remaining_position_risk / risk_fraction,
        (0.03 * equity - current_risk) / risk_fraction,
        capacity,
        state.cash,
    )
    binding_limit = min(limits)
    capacity_limited = capacity <= binding_limit + 1e-9
    shares = int(max(0.0, binding_limit) / raw_price) // LOT_SIZE * LOT_SIZE
    while shares >= LOT_SIZE:
        gross = shares * raw_price
        if gross + fees(gross, "BUY", str(row["trade_date"]), current) <= state.cash + 1e-9:
            break
        shares -= LOT_SIZE
    return (
        max(0, shares), raw_price, adjusted_price,
        "" if shares >= LOT_SIZE else "BELOW_LIMIT_OR_LOT", capacity_limited,
    )


def record_order(
    state: PortfolioState,
    *,
    day: str,
    code: str,
    side: str,
    reason: str,
    status: str,
    batch: int = 0,
    filled_notional: float = 0.0,
    capacity_limited: bool = False,
) -> None:
    state.orders.append(
        {
            "trade_date": day,
            "ts_code": code,
            "side": side,
            "batch": batch,
            "reason": reason,
            "status": status,
            "filled_notional": filled_notional,
            "capacity_limited": capacity_limited,
        }
    )


def fill_buy(
    state: PortfolioState,
    event: dict[str, Any],
    row: dict[str, Any],
    current: Scenario,
    batch: int,
    day_index: int,
    last_close: dict[str, float],
    bars: dict[tuple[str, str], dict[str, Any]],
) -> None:
    day, code = str(row["trade_date"]), str(event["ts_code"])
    values = position_values(state, day, bars, last_close, "adj_open")
    equity = state.cash + sum(values.values())
    shares, raw_price, adjusted_price, reject, capacity_limited = _buy_limit(
        state, event, row, equity, values, current, batch, last_close, bars
    )
    if shares == 0:
        record_order(
            state, day=day, code=code, side="BUY", batch=batch, reason=reject,
            status="REJECTED", capacity_limited=capacity_limited,
        )
        return
    notional, charge = raw_price * shares, fees(raw_price * shares, "BUY", day, current)
    lot = Lot(batch, day, shares, raw_price, adjusted_price, notional, charge)
    if batch == 1:
        stop, risk = float(event["initial_stop_adjusted"]), adjusted_price - float(
            event["initial_stop_adjusted"]
        )
        position = Position(
            episode_id=f"{event['point_hash']}:{code}:{event['signal_date']}",
            ts_code=code,
            industry=str(event["industry"]),
            original_rank=int(event["signal_rank"]),
            reference_adjusted=float(event["frozen_reference_adjusted"]),
            stop_adjusted=stop,
            target_adjusted=min(adjusted_price + 1.5 * risk, adjusted_price * 1.20),
            first_fill_date=day,
            first_fill_index=day_index,
            first_fill_adjusted=adjusted_price,
            initial_risk_fraction=risk / adjusted_price,
            last_adj_factor=float(row["adj_factor"]),
        )
        state.positions[code] = position
    else:
        position = state.positions[code]
        position.second_attempted, position.second_scheduled_date = True, ""
    position.lots.append(lot)
    position.cumulative_entry_cash += notional + charge
    state.cash -= notional + charge
    record_order(
        state, day=day, code=code, side="BUY", batch=batch,
        reason="FIRST_ENTRY" if batch == 1 else "SECOND_BATCH", status="FILLED",
        filled_notional=notional,
        capacity_limited=capacity_limited,
    )
    state.trades.append(
        {
            "trade_date": day, "episode_id": position.episode_id, "ts_code": code,
            "side": "BUY", "batch": batch, "reason": "ENTRY",
            "industry": position.industry,
            "gross_notional": notional, "fees": charge, "closed_trade": False,
            "closed_trade_pnl": 0.0,
        }
    )


def _sell_capacity(
    position: Position, adjusted_price: float, row: dict[str, Any]
) -> tuple[float, bool]:
    capacity = float(row["amount_median20_rmb"]) * 0.05
    eligible = sum(
        lot.value(adjusted_price)
        for lot in position.lots
        if lot.fill_date < str(row["trade_date"]) and lot.remaining_fraction > 1e-12
    )
    if not math.isfinite(capacity) or capacity <= 0:
        return 0.0, True
    return min(capacity, eligible), capacity + 1e-9 < eligible


def fill_sell(
    state: PortfolioState,
    position: Position,
    row: dict[str, Any],
    current: Scenario,
    reason: str,
    adjusted_reference: float,
) -> None:
    day, code = str(row["trade_date"]), position.ts_code
    if not opening_legal(row, "SELL"):
        record_order(state, day=day, code=code, side="SELL", reason=reason, status="PENDING")
        position.pending_exit = reason
        return
    raw_price = adverse_price(adjusted_reference / float(row["adj_factor"]), "SELL", current)
    adjusted_price = raw_price * float(row["adj_factor"])
    sell_value, capacity_limited = _sell_capacity(position, adjusted_price, row)
    if sell_value <= 0:
        record_order(
            state, day=day, code=code, side="SELL", reason=reason, status="PENDING",
            capacity_limited=capacity_limited,
        )
        position.pending_exit = reason
        return
    remaining, gross = sell_value, 0.0
    for lot in sorted(position.lots, key=lambda item: (item.fill_date, item.batch)):
        if lot.fill_date >= day or lot.remaining_fraction <= 1e-12:
            continue
        value = lot.value(adjusted_price)
        taken = min(value, remaining)
        lot.remaining_fraction *= max(0.0, 1.0 - taken / value)
        gross, remaining = gross + taken, remaining - taken
        if remaining <= 1e-8:
            break
    charge, closed = fees(gross, "SELL", day, current), position.is_empty()
    state.cash, position.cumulative_exit_cash = (
        state.cash + gross - charge,
        position.cumulative_exit_cash + gross - charge,
    )
    pnl = position.cumulative_exit_cash - position.cumulative_entry_cash if closed else 0.0
    record_order(
        state, day=day, code=code, side="SELL", reason=reason,
        status="FILLED" if closed else "PARTIAL", filled_notional=gross,
        capacity_limited=capacity_limited,
    )
    state.trades.append(
        {
            "trade_date": day, "episode_id": position.episode_id, "ts_code": code,
            "side": "SELL", "batch": 0, "reason": reason, "industry": position.industry,
            "gross_notional": gross,
            "fees": charge, "closed_trade": closed, "closed_trade_pnl": pnl,
        }
    )
    if closed:
        del state.positions[code]
    else:
        position.pending_exit = reason

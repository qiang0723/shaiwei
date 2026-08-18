"""TS-v6-4 fill operation with the fixed take-profit line removed.

Byte-equivalent to the parent R3G-2 fill except that the position target is set to
+infinity, so the removed take-profit mechanism can never trigger. Every other
sizing, lot, fee and risk rule is inherited unchanged.
"""

from __future__ import annotations

import math
from typing import Any

from shaiwei.research.trend_swing.r3g2.effect_fees import fees
from shaiwei.research.trend_swing.r3g2.effect_models import Lot, Position, Scenario
from shaiwei.research.trend_swing.r3g2.effect_orders import (
    _buy_limit,
    position_values,
    record_order,
)
from shaiwei.research.trend_swing.r3g2.effect_models import PortfolioState


def fill_buy_no_takeprofit(
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
            target_adjusted=math.inf,
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

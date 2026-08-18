"""TS-v6-4 execution loop: parent R3G-2 simulate with the take-profit fill removed.

The daily loop is inherited unchanged; the only difference is that batch fills use
:func:`fill_buy_no_takeprofit`, which sets the position target to +infinity. The
parent take-profit checks therefore can never trigger, while the structural stop
ratchet and the day-15 time exit behave exactly as in the parent.
"""

from __future__ import annotations

from typing import Any, Iterable

import pandas as pd

from shaiwei.research.trend_swing.r3g2.contract import R3G2Error
from shaiwei.research.trend_swing.r3g2.effect_execution import (
    _close_state,
    _intraday_targets,
    _maps,
    _nav_row,
    _observe_corporate_actions,
    _open_exits,
)
from shaiwei.research.trend_swing.r3g2.effect_models import (
    PortfolioState,
    Scenario,
    SimulationResult,
)
from shaiwei.research.trend_swing.r3g2.effect_orders import record_order
from shaiwei.research.trend_swing.v6_4.orders import fill_buy_no_takeprofit


def simulate_no_takeprofit(
    *,
    events: pd.DataFrame,
    bars: pd.DataFrame,
    benchmark: pd.DataFrame,
    calendar: Iterable[str],
    current: Scenario,
) -> SimulationResult:
    days = [str(value) for value in calendar]
    if len(days) != len(set(days)) or days != sorted(days):
        raise R3G2Error("TS-v6-4 calendar is duplicated or unordered")
    event_days, market = _maps(events, bars)
    market_days: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for (bar_day, code), row in market.items():
        market_days.setdefault(bar_day, []).append((code, row))
    benchmark_map = {
        str(row["trade_date"]): float(row["benchmark_return"])
        for row in benchmark.to_dict("records")
    }
    if set(days) != set(benchmark_map):
        raise R3G2Error("TS-v6-4 benchmark and partition calendars differ")
    state, last_close = PortfolioState(500_000.0), {}
    previous_nav, nav_rows = 500_000.0, []
    for index, day in enumerate(days):
        for code, row in market_days.get(day, []):
            last_close.setdefault(code, float(row["adj_close"]))
        _observe_corporate_actions(state, day, market)
        _open_exits(state, day, index, market, current)
        second = sorted(
            (
                position for position in state.positions.values()
                if position.second_scheduled_date == day and not position.pending_exit
            ),
            key=lambda position: (position.original_rank, position.ts_code),
        )
        for position in second:
            position.second_attempted = True
            event = {
                "ts_code": position.ts_code,
                "industry": position.industry,
                "initial_stop_adjusted": position.stop_adjusted,
                "point_hash": position.episode_id.split(":", 1)[0],
                "signal_date": position.episode_id.rsplit(":", 1)[-1],
                "signal_rank": position.original_rank,
                "frozen_reference_adjusted": position.reference_adjusted,
            }
            row = market.get((day, position.ts_code))
            if row is None:
                record_order(
                    state, day=day, code=position.ts_code, side="BUY", batch=2,
                    reason="NO_BAR", status="REJECTED",
                )
            else:
                fill_buy_no_takeprofit(state, event, row, current, 2, index, last_close, market)
        for event in event_days.get(day, []):
            code = str(event["ts_code"])
            if code in state.positions or len(state.positions) >= 7:
                record_order(
                    state, day=day, code=code, side="BUY", batch=1,
                    reason="ALREADY_HELD_OR_POSITION_CAP", status="REJECTED",
                )
                continue
            row = market.get((day, code))
            if row is None:
                record_order(
                    state, day=day, code=code, side="BUY", batch=1,
                    reason="NO_BAR", status="REJECTED",
                )
            else:
                fill_buy_no_takeprofit(state, event, row, current, 1, index, last_close, market)
        _intraday_targets(state, day, market, current)
        _close_state(state, day, index, days, market)
        nav, previous_nav = _nav_row(
            state, day, market, last_close, previous_nav, benchmark_map
        )
        nav_rows.append(nav)
        for code, row in market_days.get(day, []):
            last_close[code] = float(row["adj_close"])
    blocked = "UNRESOLVED_LEGAL_EXIT_AT_PARTITION_END" if state.positions else ""
    return SimulationResult(
        tuple(nav_rows), tuple(state.orders), tuple(state.trades), blocked
    )

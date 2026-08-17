"""Pure event-driven economic portfolio execution for frozen R3G-2."""

from __future__ import annotations

import math
from typing import Any, Iterable

import pandas as pd

from shaiwei.research.trend_swing.r3g2.contract import R3G2Error
from shaiwei.research.trend_swing.r3g2.effect_models import (
    PortfolioState,
    Scenario,
    SimulationResult,
)
from shaiwei.research.trend_swing.r3g2.effect_orders import (
    fill_buy,
    fill_sell,
    position_values,
    record_order,
)


INITIAL_CAPITAL = 500_000.0


def _records(frame: pd.DataFrame, keys: tuple[str, ...], label: str) -> list[dict[str, Any]]:
    missing = set(keys) - set(frame.columns)
    if frame.empty or missing:
        detail = sorted(missing) if not frame.empty else ["empty"]
        raise R3G2Error(f"R3G-2 {label} is incomplete: {detail}")
    if frame.duplicated(list(keys)).any():
        raise R3G2Error(f"R3G-2 {label} keys are duplicated")
    return frame.sort_values(list(keys)).to_dict("records")


def _maps(
    events: pd.DataFrame, bars: pd.DataFrame
) -> tuple[dict[str, list[dict[str, Any]]], dict[tuple[str, str], dict[str, Any]]]:
    event_rows = _records(events, ("point_hash", "execution_date", "ts_code"), "events")
    bar_rows = _records(bars, ("trade_date", "ts_code"), "market bars")
    by_day: dict[str, list[dict[str, Any]]] = {}
    for event in event_rows:
        by_day.setdefault(str(event["execution_date"]), []).append(event)
    for rows in by_day.values():
        rows.sort(key=lambda row: (int(row["signal_rank"]), str(row["ts_code"])))
    return by_day, {(str(row["trade_date"]), str(row["ts_code"])): row for row in bar_rows}


def _open_exits(
    state: PortfolioState,
    day: str,
    index: int,
    bars: dict[tuple[str, str], dict[str, Any]],
    current: Scenario,
) -> None:
    for code in sorted(tuple(state.positions)):
        position = state.positions[code]
        row = bars.get((day, code))
        if row is None:
            if position.pending_exit or index - position.first_fill_index >= 15:
                position.pending_exit = position.pending_exit or "TIME_EXIT"
            continue
        if not position.pending_exit and index - position.first_fill_index >= 15:
            position.pending_exit = "TIME_EXIT"
        if not position.pending_exit and float(row["adj_open"]) >= position.target_adjusted:
            position.pending_exit = "TAKE_PROFIT"
        if position.pending_exit:
            reference = (
                position.target_adjusted
                if position.pending_exit == "TAKE_PROFIT"
                else float(row["adj_open"])
            )
            if position.pending_exit == "TAKE_PROFIT":
                reference = max(reference, float(row["adj_open"]))
            fill_sell(state, position, row, current, position.pending_exit, reference)


def _intraday_targets(
    state: PortfolioState,
    day: str,
    bars: dict[tuple[str, str], dict[str, Any]],
    current: Scenario,
) -> None:
    for code in sorted(tuple(state.positions)):
        position = state.positions[code]
        if position.pending_exit:
            continue
        row = bars.get((day, code))
        if row is not None and float(row["adj_high"]) >= position.target_adjusted:
            fill_sell(state, position, row, current, "TAKE_PROFIT", position.target_adjusted)


def _close_state(
    state: PortfolioState,
    day: str,
    index: int,
    calendar: list[str],
    bars: dict[tuple[str, str], dict[str, Any]],
) -> None:
    for code, position in tuple(state.positions.items()):
        row = bars.get((day, code))
        if row is None:
            continue
        latest_week_low = float(row["latest_complete_week_low"])
        if math.isfinite(latest_week_low) and latest_week_low > 0:
            position.stop_adjusted = max(position.stop_adjusted, latest_week_low * 0.98)
        if float(row["adj_close"]) <= position.stop_adjusted:
            position.pending_exit = "STOP_EXIT"
            position.second_scheduled_date = ""
        age = index - position.first_fill_index
        profitable = float(row["adj_close"]) > max(
            position.first_fill_adjusted, position.reference_adjusted
        )
        if (
            not position.pending_exit
            and not position.second_attempted
            and not position.second_scheduled_date
            and 1 <= age <= 5
            and profitable
            and index + 1 < len(calendar)
        ):
            position.second_scheduled_date = calendar[index + 1]


def _observe_corporate_actions(
    state: PortfolioState,
    day: str,
    bars: dict[tuple[str, str], dict[str, Any]],
) -> None:
    for code, position in state.positions.items():
        row = bars.get((day, code))
        if row is None:
            continue
        current = float(row["adj_factor"])
        if not math.isfinite(current) or current <= 0:
            raise R3G2Error("R3G-2 adjustment factor is invalid while held")
        if not math.isclose(current, position.last_adj_factor, rel_tol=0.0, abs_tol=1e-12):
            state.corporate_action_overlap_count += 1
            position.last_adj_factor = current


def _nav_row(
    state: PortfolioState,
    day: str,
    bars: dict[tuple[str, str], dict[str, Any]],
    last_close: dict[str, float],
    previous_nav: float,
    benchmark: dict[str, float],
) -> tuple[dict[str, Any], float]:
    values = position_values(state, day, bars, last_close, "adj_close")
    nav = state.cash + sum(values.values())
    if not math.isfinite(nav) or nav <= 0:
        raise R3G2Error("R3G-2 economic NAV is invalid")
    gross = sum(values.values()) / nav
    security_weight = max(values.values(), default=0.0) / nav
    industries: dict[str, float] = {}
    for code, value in values.items():
        industry = state.positions[code].industry
        industries[industry] = industries.get(industry, 0.0) + value
    row = {
        "trade_date": day,
        "nav": nav,
        "daily_return": nav / previous_nav - 1.0,
        "benchmark_return": float(benchmark[day]),
        "active_return": nav / previous_nav - 1.0 - float(benchmark[day]),
        "cash_ratio": state.cash / nav,
        "gross_weight": gross,
        "maximum_security_weight": security_weight,
        "maximum_industry_weight": max(industries.values(), default=0.0) / nav,
        "position_count": len(state.positions),
        "corporate_action_overlap_count": state.corporate_action_overlap_count,
    }
    return row, nav


def simulate(
    *,
    events: pd.DataFrame,
    bars: pd.DataFrame,
    benchmark: pd.DataFrame,
    calendar: Iterable[str],
    current: Scenario,
) -> SimulationResult:
    days = [str(value) for value in calendar]
    if len(days) != len(set(days)) or days != sorted(days):
        raise R3G2Error("R3G-2 calendar is duplicated or unordered")
    event_days, market = _maps(events, bars)
    market_days: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for (bar_day, code), row in market.items():
        market_days.setdefault(bar_day, []).append((code, row))
    benchmark_rows = _records(benchmark, ("trade_date",), "benchmark")
    benchmark_map = {str(row["trade_date"]): float(row["benchmark_return"]) for row in benchmark_rows}
    if set(days) != set(benchmark_map):
        raise R3G2Error("R3G-2 benchmark and partition calendars differ")
    state, last_close = PortfolioState(INITIAL_CAPITAL), {}
    previous_nav, nav_rows = INITIAL_CAPITAL, []
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
                fill_buy(state, event, row, current, 2, index, last_close, market)
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
                fill_buy(state, event, row, current, 1, index, last_close, market)
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

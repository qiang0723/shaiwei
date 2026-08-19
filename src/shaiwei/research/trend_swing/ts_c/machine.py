"""Pure episode state machine for the three TS-C trigger arms (density only)."""

from __future__ import annotations

from typing import Any, Mapping

from shaiwei.research.trend_swing.ts_c.contract import TQCError


TRIGGERS = ("VWAP_ANCHOR_PULLBACK", "HIGH20_DRAWDOWN", "MA20_PULLBACK")
MAX_WAIT_DAYS = 10


def _num(row: Mapping[str, Any], key: str) -> float | None:
    value = row.get(key)
    if value is None:
        return None
    result = float(value)
    return result if result == result else None


def eligible(row: Mapping[str, Any]) -> bool:
    """The frozen v3 eligibility stack evaluated on completed daily data only."""
    required = (
        _num(row, "week_vwap"), _num(row, "atr20"), _num(row, "ma20"),
        _num(row, "max_close_20d"), _num(row, "daily_atr20"),
    )
    if any(value is None or value <= 0 for value in required):
        return False
    if int(row.get("bar_count") or 0) < 27:
        return False
    if int(row.get("ma20_count") or 0) < 20:
        return False
    if float(row.get("total_mv_rmb") or 0.0) < 20_000_000_000.0:
        return False
    if float(row.get("week_amount") or 0.0) < 5_000_000_000.0:
        return False
    if not row.get("weekly_lows_rising"):
        return False
    stock_perm = (
        row.get("stock_prev_month_close") is not None
        and row.get("stock_prev_sma6") is not None
        and row.get("stock_prev2_sma6") is not None
        and float(row["stock_prev_month_close"]) > float(row["stock_prev_sma6"])
        and float(row["stock_prev_sma6"]) > float(row["stock_prev2_sma6"])
    )
    index_perm = (
        row.get("index_prev_month_close") is not None
        and row.get("index_prev_sma6") is not None
        and row.get("index_prev2_sma6") is not None
        and float(row["index_prev_month_close"]) > float(row["index_prev_sma6"])
        and float(row["index_prev_sma6"]) > float(row["index_prev2_sma6"])
    )
    return bool(stock_perm and index_perm)


def arm_line(trigger: str, row: Mapping[str, Any]) -> float:
    if trigger == "VWAP_ANCHOR_PULLBACK":
        return float(row["week_vwap"]) - float(row["atr20"])
    if trigger == "HIGH20_DRAWDOWN":
        return float(row["max_close_20d"]) - float(row["daily_atr20"])
    if trigger == "MA20_PULLBACK":
        return float(row["ma20"])
    raise TQCError(f"TS-C trigger is not executable: {trigger}")


def arms(trigger: str, row: Mapping[str, Any]) -> bool:
    line = arm_line(trigger, row)
    low = float(row["adj_low"])
    if trigger == "MA20_PULLBACK":
        return low <= line <= float(row["adj_close"])
    return low <= line


def confirms(row: Mapping[str, Any]) -> bool:
    prior_high = _num(row, "previous_valid_high")
    if prior_high is None or not row.get("index_above_sma20"):
        return False
    close, open_ = float(row["adj_close"]), float(row["adj_open"])
    return close > prior_high and close > open_


def project_events(
    rows: list[Mapping[str, Any]], trigger: str
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Run the episode machine over one security's rows; return confirmed events."""
    events: list[dict[str, Any]] = []
    stats = {"armed": 0, "confirmed": 0, "cancelled_invalidation": 0, "cancelled_wait": 0}
    state: dict[str, Any] | None = None
    for row in rows:
        terminated = False
        if state is not None:
            state["wait"] += 1
            if float(row["adj_close"]) < state["line"] - state["atr"]:
                stats["cancelled_invalidation"] += 1
                state = None
                terminated = True
            elif confirms(row):
                stats["confirmed"] += 1
                events.append({
                    "ts_code": str(row["ts_code"]),
                    "signal_date": str(row["trade_date"]),
                    "trigger_id": trigger,
                })
                state = None
                terminated = True
            elif state["wait"] > MAX_WAIT_DAYS:
                stats["cancelled_wait"] += 1
                state = None
                terminated = True
        if not terminated and state is None and eligible(row) and arms(trigger, row):
            stats["armed"] += 1
            line = arm_line(trigger, row)
            atr = float(row["daily_atr20"])
            state = {"line": line, "atr": atr, "wait": 0}
            if confirms(row):
                stats["confirmed"] += 1
                events.append({
                    "ts_code": str(row["ts_code"]),
                    "signal_date": str(row["trade_date"]),
                    "trigger_id": trigger,
                })
                state = None
    return events, stats

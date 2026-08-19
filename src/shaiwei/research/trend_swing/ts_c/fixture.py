"""Synthetic fixtures for the TS-C trigger qualification machinery."""

from __future__ import annotations

from typing import Any

from shaiwei.research.trend_swing.ts_c.contract import TQCError
from shaiwei.research.trend_swing.ts_c.machine import project_events


def _row(day: int, low: float, close: float, *, open_: float | None = None,
         prior_high: float = 100.5, index_ok: bool = True) -> dict[str, Any]:
    return {
        "ts_code": "600000.SH",
        "trade_date": f"202401{day:02d}",
        "adj_open": close if open_ is None else open_,
        "adj_high": max(close, prior_high - 0.2),
        "adj_low": low,
        "adj_close": close,
        "previous_valid_high": prior_high,
        "amount_rmb": 2e9,
        "total_mv_rmb": 3e10,
        "week_vwap": 100.0,
        "atr20": 2.0,
        "week_amount": 6e9,
        "weekly_lows_rising": True,
        "ma20": 100.0,
        "ma20_count": 20,
        "max_close_20d": 102.0,
        "bar_count": 100,
        "daily_atr20": 2.0,
        "index_above_sma20": index_ok,
        "stock_prev_month_close": 101.0,
        "stock_prev_sma6": 100.0,
        "stock_prev2_sma6": 99.0,
        "index_prev_month_close": 4001.0,
        "index_prev_sma6": 4000.0,
        "index_prev2_sma6": 3999.0,
    }


def fixture() -> dict[str, Any]:
    # arm on day 1 (low 97 <= 100-2), confirm on day 2 (close 101 > prior high, close > open)
    rows = [_row(3, 97.0, 98.0), _row(4, 99.0, 101.0, open_=100.0)]
    for trigger in ("VWAP_ANCHOR_PULLBACK", "HIGH20_DRAWDOWN", "MA20_PULLBACK"):
        events, stats = project_events(rows, trigger)
        if len(events) != 1 or stats["confirmed"] != 1:
            raise TQCError(f"TS-C fixture confirm path differs: {trigger}")
    # invalidation: day after arm closes below line-atr
    rows = [_row(3, 97.0, 98.0), _row(4, 94.0, 94.5, open_=95.0)]
    events, stats = project_events(rows, "VWAP_ANCHOR_PULLBACK")
    if events or stats["cancelled_invalidation"] != 1:
        raise TQCError("TS-C fixture invalidation path differs")
    # wait expiry
    rows = [_row(3, 97.0, 98.0)] + [_row(10 + index, 98.0, 98.2, open_=98.2) for index in range(12)]
    events, stats = project_events(rows, "VWAP_ANCHOR_PULLBACK")
    if events or stats["cancelled_wait"] != 1:
        raise TQCError("TS-C fixture wait-expiry path differs")
    # index gate blocks confirmation
    rows = [_row(3, 97.0, 98.0), _row(4, 99.0, 101.0, open_=100.0, index_ok=False)]
    events, stats = project_events(rows, "VWAP_ANCHOR_PULLBACK")
    if events or stats["confirmed"] != 0:
        raise TQCError("TS-C fixture index-gate path differs")
    return {"fixture_pass": True, "trigger_paths": 3, "episode_paths": 3}

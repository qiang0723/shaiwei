"""Frozen A-share fee and opening-limit calculations for R3G-2."""

from __future__ import annotations

import math

from shaiwei.research.trend_swing.r3g2.effect_models import Scenario


def adverse_price(raw_price: float, side: str, current: Scenario) -> float:
    direction = 1.0 if side == "BUY" else -1.0
    value = raw_price * (1.0 + direction * current.slippage)
    if not math.isfinite(value) or value <= 0:
        raise ValueError("R3G-2 execution price is invalid")
    return value


def fees(notional: float, side: str, trade_date: str, current: Scenario) -> float:
    if not math.isfinite(notional) or notional <= 0 or side not in {"BUY", "SELL"}:
        raise ValueError("R3G-2 fee input is invalid")
    commission = max(notional * 0.0003, 5.0)
    transfer_rate = 0.00002 if trade_date < "20220429" else 0.00001
    stamp_rate = 0.0
    if side == "SELL":
        stamp_rate = 0.001 if trade_date < "20230828" else 0.0005
    return current.fee_multiplier * (
        commission + notional * transfer_rate + notional * stamp_rate
    )


def board(ts_code: str) -> str:
    if ts_code.endswith(".BJ"):
        raise ValueError("R3G-2 forbids BSE securities")
    if ts_code.startswith(("688", "689")) and ts_code.endswith(".SH"):
        return "STAR"
    if ts_code.startswith(("300", "301")) and ts_code.endswith(".SZ"):
        return "CHINEXT"
    return "MAIN"


def opening_legal(row: dict[str, object], side: str) -> bool:
    numeric = ("raw_open", "prior_raw_close", "volume_shares")
    try:
        values = {name: float(row[name]) for name in numeric}
    except (KeyError, TypeError, ValueError):
        return False
    if any(not math.isfinite(value) or value <= 0 for value in values.values()):
        return False
    if not bool(row.get("security_eligible", True)) and side == "BUY":
        return False
    if int(row.get("listing_session_age", 6)) <= 5:
        return True
    code, date = str(row["ts_code"]), str(row["trade_date"])
    kind = board(code)
    threshold = 0.20 if kind == "STAR" else 0.10
    if kind == "CHINEXT" and date >= "20200824":
        threshold = 0.20
    change = values["raw_open"] / values["prior_raw_close"] - 1.0
    tolerance = 0.01 / values["prior_raw_close"]
    if side == "BUY":
        return change < threshold - tolerance
    return change > -threshold + tolerance

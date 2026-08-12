"""Pure, result-blind TS calendar and structural feature calculations."""

from __future__ import annotations

import numpy as np
import pandas as pd

from shaiwei.research.trend_swing.contract import TrendSwingError


BAR_COLUMNS = {"ts_code", "trade_date", "open", "high", "low", "close", "amount"}


def listing_segment(ts_code: object) -> str:
    code = str(ts_code)
    if code.endswith(".BJ"):
        raise TrendSwingError(".BJ security entered TS feature calculation")
    digits = code.split(".", 1)[0]
    if code.endswith(".SH") and digits.startswith(("688", "689")):
        return "star"
    if code.endswith(".SZ") and digits.startswith(("300", "301")):
        return "chinext"
    return "main"


def _bars(frame: pd.DataFrame) -> pd.DataFrame:
    if missing := BAR_COLUMNS - set(frame.columns):
        raise TrendSwingError(f"TS bars missing columns: {sorted(missing)}")
    if frame["ts_code"].astype(str).str.endswith(".BJ").any():
        raise TrendSwingError(".BJ security entered TS feature calculation")
    if frame.duplicated(["ts_code", "trade_date"]).any():
        raise TrendSwingError("TS bars contain duplicate security-day keys")
    result = frame.copy()
    result["_date"] = pd.to_datetime(result["trade_date"].astype(str), format="%Y%m%d", errors="raise")
    return result.sort_values(["ts_code", "_date"]).reset_index(drop=True)


def weekly_aggregates(frame: pd.DataFrame) -> pd.DataFrame:
    bars = _bars(frame)
    bars["week_end"] = bars["_date"].dt.to_period("W-FRI").dt.end_time.dt.normalize()
    bars["_value"] = pd.to_numeric(bars["amount"], errors="coerce")
    rows = []
    for (code, week_end), group in bars.groupby(["ts_code", "week_end"], sort=True):
        ordered = group.sort_values("_date")
        low = pd.to_numeric(ordered["low"], errors="coerce")
        high = pd.to_numeric(ordered["high"], errors="coerce")
        close = pd.to_numeric(ordered["close"], errors="coerce")
        daily = close.pct_change(fill_method=None)
        rows.append(
            {
                "ts_code": code,
                "week_end": week_end,
                "weekly_low": float(low.min()),
                "weekly_high": float(high.max()),
                "weekly_close": float(close.iloc[-1]),
                "weekly_amount": float(ordered["_value"].sum()),
                "weekly_range": float(high.max() / low.min() - 1.0),
                "weekly_realized_vol": float(daily.std(ddof=1) * np.sqrt(252)) if daily.notna().sum() > 1 else np.nan,
            }
        )
    result = pd.DataFrame(rows)
    grouped = result.groupby("ts_code", sort=False)
    for column in ("weekly_low", "weekly_range", "weekly_realized_vol"):
        result[f"previous_{column}"] = grouped[column].shift(1)
        result[f"previous_2_{column}"] = grouped[column].shift(2)
    return result


def monthly_aggregates(frame: pd.DataFrame) -> pd.DataFrame:
    bars = _bars(frame)
    bars["month_end"] = bars["_date"].dt.to_period("M").dt.end_time.dt.normalize()
    rows = []
    for (code, month_end), group in bars.groupby(["ts_code", "month_end"], sort=True):
        ordered = group.sort_values("_date")
        rows.append(
            {
                "ts_code": code,
                "month_end": month_end,
                "monthly_high": float(pd.to_numeric(ordered["high"], errors="coerce").max()),
                "monthly_low": float(pd.to_numeric(ordered["low"], errors="coerce").min()),
                "monthly_close": float(pd.to_numeric(ordered["close"], errors="coerce").iloc[-1]),
            }
        )
    result = pd.DataFrame(rows)
    grouped = result.groupby("ts_code", sort=False)
    for column in ("monthly_high", "monthly_low"):
        result[f"previous_{column}"] = grouped[column].shift(1)
        result[f"previous_2_{column}"] = grouped[column].shift(2)
    return result


def completed_period_on(observation: str, aggregates: pd.DataFrame, end_column: str) -> pd.Series:
    date = pd.to_datetime(str(observation), format="%Y%m%d", errors="raise")
    eligible = aggregates.loc[aggregates[end_column].lt(date)]
    if eligible.empty:
        return pd.Series(dtype=object)
    latest = eligible[end_column].max()
    return eligible.loc[eligible[end_column].eq(latest)].iloc[-1]


def structural_gate_flags(frame: pd.DataFrame) -> pd.DataFrame:
    required = {
        "total_mv_rmb",
        "weekly_amount_rmb",
        "monthly_high",
        "previous_monthly_high",
        "previous_2_monthly_high",
        "weekly_low",
        "previous_weekly_low",
        "previous_2_weekly_low",
        "weekly_close",
        "weekly_high",
    }
    if missing := required - set(frame.columns):
        raise TrendSwingError(f"TS structural frame missing columns: {sorted(missing)}")
    result = pd.DataFrame(index=frame.index)
    result["market_cap"] = frame["total_mv_rmb"].ge(20_000_000_000)
    result["weekly_amount"] = frame["weekly_amount_rmb"].ge(5_000_000_000)
    result["monthly_highs"] = (
        frame["monthly_high"].gt(frame["previous_monthly_high"])
        & frame["previous_monthly_high"].gt(frame["previous_2_monthly_high"])
    )
    result["weekly_lows"] = (
        frame["weekly_low"].ge(frame["previous_weekly_low"])
        & frame["previous_weekly_low"].ge(frame["previous_2_weekly_low"])
    )
    midpoint = (frame["weekly_high"] + frame["weekly_low"]) / 2.0
    result["weekly_close"] = frame["weekly_close"].ge(midpoint)
    result["all"] = result.all(axis=1)
    return result


def sector_daily_return(frame: pd.DataFrame, minimum_constituents: int = 5) -> pd.DataFrame:
    required = {"trade_date", "industry", "ts_code", "daily_return"}
    if missing := required - set(frame.columns):
        raise TrendSwingError(f"TS sector frame missing columns: {sorted(missing)}")
    valid = frame.dropna(subset=["industry", "daily_return"]).copy()
    grouped = valid.groupby(["trade_date", "industry"], sort=True)
    result = grouped.agg(
        constituent_count=("ts_code", "nunique"),
        equal_weight_return=("daily_return", "mean"),
    ).reset_index()
    result["eligible"] = result["constituent_count"].ge(minimum_constituents)
    result.loc[~result["eligible"], "equal_weight_return"] = np.nan
    return result

"""交易可用性证据：区分全天停牌、日内停牌和独立交易状态。"""

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class StatusWindow:
    ts_code: str
    start_date: str
    end_date: str
    required_dates: tuple[str, ...]


def full_day_suspension_keys(suspend_d: pd.DataFrame) -> set[tuple[str, str]]:
    """Return Tushare full-day suspension keys; timed rows are intraday events."""
    if suspend_d.empty:
        return set()
    suspended = suspend_d.loc[suspend_d["suspend_type"].astype("string").eq("S")].copy()
    if "suspend_timing" in suspended:
        timing = suspended["suspend_timing"].astype("string").str.strip()
        suspended = suspended.loc[timing.isna() | timing.eq("")]
    return set(
        suspended.loc[:, ["ts_code", "trade_date"]]
        .astype(str)
        .itertuples(index=False, name=None)
    )


def trade_status_sets(trade_status: pd.DataFrame | None) -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
    """Split independently observed keys into nontrading (0) and trading (1)."""
    if trade_status is None or trade_status.empty:
        return set(), set()
    required = {"ts_code", "trade_date", "trade_status"}
    if missing := required - set(trade_status.columns):
        raise ValueError(f"trade status evidence missing fields: {sorted(missing)}")
    frame = trade_status.loc[:, sorted(required)].copy()
    frame["ts_code"] = frame["ts_code"].astype(str)
    frame["trade_date"] = frame["trade_date"].astype(str)
    frame["trade_status"] = frame["trade_status"].astype(str).str.strip()
    invalid = frame.loc[~frame["trade_status"].isin({"0", "1"})]
    if not invalid.empty:
        raise ValueError("trade status evidence contains values other than 0/1")
    conflicts = frame.groupby(["ts_code", "trade_date"])["trade_status"].nunique()
    if (conflicts > 1).any():
        raise ValueError("trade status evidence conflicts for the same security-date")
    frame = frame.drop_duplicates(["ts_code", "trade_date"], keep="last")
    status0 = set(
        frame.loc[frame["trade_status"].eq("0"), ["ts_code", "trade_date"]]
        .itertuples(index=False, name=None)
    )
    status1 = set(
        frame.loc[frame["trade_status"].eq("1"), ["ts_code", "trade_date"]]
        .itertuples(index=False, name=None)
    )
    return status0, status1


def authoritative_suspension_keys(
    suspend_d: pd.DataFrame,
    trade_status: pd.DataFrame | None = None,
) -> set[tuple[str, str]]:
    """Combine full-day source events with independent status, resolving source conflicts."""
    source = full_day_suspension_keys(suspend_d)
    status0, status1 = trade_status_sets(trade_status)
    return (source - status1) | status0


def build_status_crosscheck_plan(
    trade_cal: pd.DataFrame,
    stock_basic: pd.DataFrame,
    daily: pd.DataFrame,
    suspend_d: pd.DataFrame,
    *,
    start: str,
    end: str,
    include_bse: bool,
) -> list[StatusWindow]:
    """Plan only ambiguous missing bars and full-day-source/bar conflicts."""
    ordered_open_days = sorted(
        {
            str(day)
            for day in trade_cal.loc[
                trade_cal["is_open"].astype(str).eq("1"), "cal_date"
            ]
            if start <= str(day) <= end
        }
    )
    day_position = {day: position for position, day in enumerate(ordered_open_days)}
    bars = {
        str(code): set(group["trade_date"].astype(str))
        for code, group in daily.groupby("ts_code", sort=False)
    }
    suspensions_by_code: dict[str, set[str]] = {}
    for code, day in full_day_suspension_keys(suspend_d):
        suspensions_by_code.setdefault(code, set()).add(day)

    securities = stock_basic.drop_duplicates("ts_code")
    if not include_bse:
        securities = securities.loc[
            ~securities["ts_code"].astype("string").str.endswith(".BJ", na=False)
        ]
    windows: list[StatusWindow] = []
    for security in securities.itertuples(index=False):
        code = str(security.ts_code)
        life_start = max(start, str(security.list_date))
        delist = (
            str(security.delist_date)
            if pd.notna(security.delist_date) and str(security.delist_date)
            else None
        )
        if life_start > end:
            continue
        # `delist_date` is the effective removal date, not a trading session:
        # the full source snapshot has zero bars on that date for all delisted names.
        expected = {
            day for day in ordered_open_days
            if life_start <= day <= end and (delist is None or day < delist)
        }
        security_bars = bars.get(code, set()) & expected
        source = suspensions_by_code.get(code, set()) & expected
        required = sorted((expected - security_bars - source) | (security_bars & source))
        if not required:
            continue
        group = [required[0]]
        for day in required[1:]:
            if day_position[day] == day_position[group[-1]] + 1:
                group.append(day)
                continue
            windows.append(StatusWindow(code, group[0], group[-1], tuple(group)))
            group = [day]
        windows.append(StatusWindow(code, group[0], group[-1], tuple(group)))
    return windows

"""Monthly formation schedule and exact next-open PIT memberships for three pools."""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from .contract import M5DataProtocol, M5GateError


SECURITY_RE = re.compile(r"^[0-9]{6}\.SH$")
MEMBER_KEYS = ["formation_date", "effective_date", "universe_id", "ts_code"]


def formation_schedule(
    trade_calendar: pd.DataFrame,
    *,
    start_month: str,
    end_month: str,
) -> pd.DataFrame:
    required = {"exchange", "cal_date", "is_open"}
    if missing := required - set(trade_calendar.columns):
        raise M5GateError(f"trade calendar missing columns: {sorted(missing)}")
    calendar = trade_calendar.loc[
        trade_calendar["exchange"].astype(str).eq("SSE")
    ].copy()
    calendar["cal_date"] = calendar["cal_date"].astype(str).str.replace("-", "", regex=False)
    if calendar["cal_date"].duplicated().any():
        raise M5GateError("SSE trade calendar contains duplicate dates")
    open_days = sorted(
        calendar.loc[calendar["is_open"].astype(str).eq("1"), "cal_date"].unique()
    )
    if not open_days:
        raise M5GateError("SSE trade calendar has no open dates")
    months = pd.period_range(start_month, end_month, freq="M").astype(str).tolist()
    positions = {day: index for index, day in enumerate(open_days)}
    rows: list[tuple[str, str, str]] = []
    for month in months:
        compact = month.replace("-", "")
        eligible = [day for day in open_days if day.startswith(compact)]
        if not eligible:
            raise M5GateError(f"SSE calendar has no open day in formation month {month}")
        formation = eligible[-1]
        position = positions[formation]
        if position + 1 >= len(open_days):
            raise M5GateError("last formation month lacks a next SSE open day")
        rows.append((month, formation, open_days[position + 1]))
    result = pd.DataFrame(rows, columns=["formation_month", "formation_date", "effective_date"])
    if len(result) != len(months) or result[["formation_date", "effective_date"]].duplicated().any():
        raise M5GateError("formation schedule is incomplete or duplicated")
    if not result["effective_date"].gt(result["formation_date"]).all():
        raise M5GateError("formation schedule does not use a strict next open date")
    return result


def _pool_members(
    protocol: M5DataProtocol,
    universe_id: str,
    schedule: pd.DataFrame,
    source: pd.DataFrame,
) -> pd.DataFrame:
    universe = next(item for item in protocol.universes if item.universe_id == universe_id)
    required = {"trade_date", "ts_code"}
    if universe.filter_column:
        required |= {universe.filter_column, "formation_date"}
    if missing := required - set(source.columns):
        raise M5GateError(f"{universe_id} membership missing columns: {sorted(missing)}")
    frame = source.loc[:, sorted(required)].copy()
    frame["trade_date"] = frame["trade_date"].astype(str).str.replace("-", "", regex=False)
    frame["ts_code"] = frame["ts_code"].astype(str).str.upper()
    if universe.filter_column:
        frame = frame.loc[
            frame[universe.filter_column].astype(str).eq(str(universe.filter_value))
        ].copy()
        frame["formation_date"] = (
            frame["formation_date"].astype(str).str.replace("-", "", regex=False)
        )
    selected = schedule.merge(
        frame,
        left_on="effective_date",
        right_on="trade_date",
        how="left",
        validate="one_to_many",
    )
    if selected["ts_code"].isna().any():
        missing_dates = selected.loc[selected["ts_code"].isna(), "effective_date"].tolist()
        raise M5GateError(f"{universe_id} lacks exact next-open members: {missing_dates}")
    if universe.filter_column:
        wrong = selected["formation_date_x"].ne(selected["formation_date_y"])
        if wrong.any():
            raise M5GateError(f"{universe_id} source formation does not match month-end")
        selected["source_formation_date"] = selected["formation_date_y"]
        selected["formation_date"] = selected["formation_date_x"]
    else:
        selected["source_formation_date"] = selected["formation_date"]
    selected["universe_id"] = universe_id
    result = selected[
        [*MEMBER_KEYS, "source_formation_date"]
    ].sort_values(MEMBER_KEYS, kind="stable").reset_index(drop=True)
    if result.duplicated(MEMBER_KEYS).any():
        raise M5GateError(f"{universe_id} membership contains duplicate keys")
    if result["ts_code"].eq("").any() or result["ts_code"].str.endswith(".BJ").any():
        raise M5GateError(f"{universe_id} membership contains empty or .BJ identity")
    if not result["ts_code"].map(lambda value: SECURITY_RE.fullmatch(value) is not None).all():
        raise M5GateError(f"{universe_id} membership contains a non-SSE security")
    counts = result.groupby("formation_date")["ts_code"].nunique()
    if len(counts) != len(schedule) or counts.le(0).any():
        raise M5GateError(f"{universe_id} membership is incomplete")
    return result


def build_membership_panel(
    protocol: M5DataProtocol,
    trade_calendar: pd.DataFrame,
    membership_frames: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    gate = protocol.document["data_gate"]
    schedule = formation_schedule(
        trade_calendar,
        start_month=str(gate["quality_start_month"]),
        end_month=str(gate["quality_end_month"]),
    )
    if set(membership_frames) != set(protocol.universe_ids):
        raise M5GateError("membership frame keys differ from the frozen three pools")
    pools = [
        _pool_members(protocol, universe_id, schedule, membership_frames[universe_id])
        for universe_id in protocol.universe_ids
    ]
    panel = pd.concat(pools, ignore_index=True).sort_values(MEMBER_KEYS, kind="stable")
    if panel.duplicated(MEMBER_KEYS).any() or panel["ts_code"].str.endswith(".BJ").any():
        raise M5GateError("combined M5 membership violates unique-key or .BJ gate")
    diagnostics = {
        "formation_month_count": len(schedule),
        "formation_date_first": schedule["formation_date"].iloc[0],
        "formation_date_last": schedule["formation_date"].iloc[-1],
        "effective_date_first": schedule["effective_date"].iloc[0],
        "effective_date_last": schedule["effective_date"].iloc[-1],
        "member_rows_by_universe": {
            universe_id: int(panel["universe_id"].eq(universe_id).sum())
            for universe_id in protocol.universe_ids
        },
        "bse_rows": int(panel["ts_code"].str.endswith(".BJ").sum()),
        "duplicate_keys": int(panel.duplicated(MEMBER_KEYS).sum()),
    }
    return panel.reset_index(drop=True), diagnostics

"""财务三表 point-in-time 快照。公告日按下一交易日可用，防盘后前视。"""

import pandas as pd


def financial_pit_snapshot(statements: pd.DataFrame, trade_calendar: pd.DataFrame, as_of: str) -> pd.DataFrame:
    required = {"ts_code", "f_ann_date", "end_date", "report_type", "update_flag"}
    if missing := required - set(statements.columns):
        raise ValueError(f"statements missing fields: {sorted(missing)}")
    if missing := {"cal_date", "is_open"} - set(trade_calendar.columns):
        raise ValueError(f"trade_calendar missing fields: {sorted(missing)}")

    open_days = pd.to_datetime(
        trade_calendar.loc[pd.to_numeric(trade_calendar["is_open"], errors="coerce").eq(1), "cal_date"],
        format="%Y%m%d",
        errors="coerce",
    ).dropna().drop_duplicates().sort_values()
    if open_days.empty:
        raise ValueError("trade_calendar has no open days")

    frame = statements.copy()
    frame["_f_ann"] = pd.to_datetime(frame["f_ann_date"], format="%Y%m%d", errors="coerce")
    frame["_end"] = pd.to_datetime(frame["end_date"], format="%Y%m%d", errors="coerce")
    frame = frame.loc[frame["_f_ann"].notna() & frame["_end"].notna()].copy()
    positions = open_days.searchsorted(frame["_f_ann"], side="right")
    available = pd.Series(pd.NaT, index=frame.index, dtype="datetime64[ns]")
    valid = positions < len(open_days)
    available.loc[valid] = open_days.iloc[positions[valid]].to_numpy()
    frame["available_date"] = available
    frame = frame.loc[frame["available_date"].le(pd.Timestamp(as_of))].copy()
    if frame.empty:
        return frame.drop(columns=["_f_ann", "_end"])

    keys = ["ts_code", "end_date"]
    frame["_latest_announcement"] = frame.groupby(keys)["_f_ann"].transform("max")
    latest = frame.loc[frame["_f_ann"].eq(frame["_latest_announcement"])].copy()
    latest["_report_priority"] = latest["report_type"].astype("string").map({"1": 2, "5": 1}).fillna(0)
    latest["_update_priority"] = pd.to_numeric(latest["update_flag"], errors="coerce").fillna(-1)
    latest = latest.sort_values(keys + ["_report_priority", "_update_priority"], ascending=[True, True, False, False])
    return latest.drop_duplicates(keys, keep="first").drop(
        columns=["_f_ann", "_end", "_latest_announcement", "_report_priority", "_update_priority"]
    ).reset_index(drop=True)

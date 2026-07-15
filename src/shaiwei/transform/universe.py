"""动态股票池与 ST 的 point-in-time 逻辑。"""

from datetime import date

import pandas as pd


def _date_column(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series.astype("string"), format="%Y%m%d", errors="coerce")


def active_securities(stock_basic: pd.DataFrame, on_date: date, *, include_bse: bool) -> pd.DataFrame:
    """Return securities alive on a date, retaining delisted names before delisting."""
    required = {"ts_code", "list_date", "delist_date"}
    missing = required - set(stock_basic.columns)
    if missing:
        raise ValueError(f"stock_basic missing fields: {sorted(missing)}")
    frame = stock_basic.copy()
    frame["_list_date"] = _date_column(frame["list_date"])
    frame["_delist_date"] = _date_column(frame["delist_date"])
    point = pd.Timestamp(on_date)
    mask = frame["_list_date"].le(point) & (frame["_delist_date"].isna() | frame["_delist_date"].ge(point))
    if not include_bse:
        mask &= ~frame["ts_code"].astype("string").str.endswith(".BJ", na=False)
    result = frame.loc[mask].drop(columns=["_list_date", "_delist_date"])
    return result.sort_values("ts_code").drop_duplicates("ts_code", keep="last").reset_index(drop=True)


def index_members_on(index_weight: pd.DataFrame, on_date: date) -> pd.DataFrame:
    """Forward-fill a monthly index snapshot without looking beyond ``on_date``."""
    required = {"index_code", "con_code", "trade_date", "weight"}
    missing = required - set(index_weight.columns)
    if missing:
        raise ValueError(f"index_weight missing fields: {sorted(missing)}")
    frame = index_weight.copy()
    frame["_trade_date"] = _date_column(frame["trade_date"])
    eligible = frame.loc[frame["_trade_date"].le(pd.Timestamp(on_date))]
    if eligible.empty:
        return frame.iloc[0:0].drop(columns=["_trade_date"])
    snapshot_date = eligible["_trade_date"].max()
    result = eligible.loc[eligible["_trade_date"].eq(snapshot_date)].drop(columns=["_trade_date"])
    return result.sort_values("con_code").drop_duplicates("con_code", keep="last").reset_index(drop=True)


def _name_is_st(name: object) -> bool:
    rendered = str(name).strip().upper()
    return "ST" in rendered and not rendered.endswith("退")


def st_status_on(namechange: pd.DataFrame, observations: pd.DataFrame) -> pd.DataFrame:
    """Resolve the latest effective name for each (ts_code, trade_date), conservatively on ties."""
    history_required = {"ts_code", "name", "start_date", "end_date"}
    observation_required = {"ts_code", "trade_date"}
    if missing := history_required - set(namechange.columns):
        raise ValueError(f"namechange missing fields: {sorted(missing)}")
    if missing := observation_required - set(observations.columns):
        raise ValueError(f"observations missing fields: {sorted(missing)}")

    history = namechange.loc[:, ["ts_code", "name", "start_date", "end_date"]].copy()
    history["_start"] = _date_column(history["start_date"])
    history["_end"] = _date_column(history["end_date"])
    points = observations.loc[:, ["ts_code", "trade_date"]].copy()
    points["_point"] = _date_column(points["trade_date"])
    points["_row"] = range(len(points))

    joined = points.merge(history, on="ts_code", how="left")
    effective = joined.loc[
        joined["_start"].le(joined["_point"])
        & (joined["_end"].isna() | joined["_end"].ge(joined["_point"]))
    ].copy()
    if effective.empty:
        result = points.loc[:, ["_row", "ts_code", "trade_date"]].copy()
        result["effective_name"] = pd.NA
        result["is_st"] = False
        return result.sort_values("_row").drop(columns="_row").reset_index(drop=True)

    effective["_latest"] = effective.groupby("_row")["_start"].transform("max")
    latest = effective.loc[effective["_start"].eq(effective["_latest"])].copy()
    latest["_is_st"] = latest["name"].map(_name_is_st)
    resolved = latest.groupby("_row", as_index=False).agg(
        effective_name=("name", lambda values: "|".join(sorted({str(value) for value in values}))),
        is_st=("_is_st", "any"),
    )
    result = points.merge(resolved, on="_row", how="left")
    result["is_st"] = result["is_st"].fillna(False).astype(bool)
    return result.loc[:, ["ts_code", "trade_date", "effective_name", "is_st"]]

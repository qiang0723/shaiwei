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
    result = points.loc[:, ["_row", "ts_code", "trade_date"]].copy()
    result["effective_name"] = pd.Series(pd.NA, index=result.index, dtype="string")
    result["is_st"] = False

    # Do interval resolution one security at a time.  A whole-market point-in-time
    # table contains millions of observations; a many-to-many merge with every
    # historical name can multiply memory usage enough to invalidate the Day 7
    # CPU benchmark itself.
    history_by_code = {code: frame for code, frame in history.groupby("ts_code", sort=False)}
    for code, point_index in points.groupby("ts_code", sort=False).groups.items():
        security_history = history_by_code.get(code)
        if security_history is None:
            continue
        dates = points.loc[point_index, "_point"]
        best_start = pd.Series(pd.NaT, index=point_index, dtype="datetime64[ns]")
        names: dict[int, set[str]] = {}
        st_flags = pd.Series(False, index=point_index)
        intervals = security_history.loc[:, ["name", "_start", "_end"]]
        for name, interval_start, interval_end in intervals.itertuples(index=False, name=None):
            if pd.isna(interval_start):
                continue
            active = dates.ge(interval_start) & (pd.isna(interval_end) | dates.le(interval_end))
            newer = active & (best_start.isna() | best_start.lt(interval_start))
            tied = active & best_start.eq(interval_start)
            for index in dates.index[newer]:
                names[index] = {str(name)}
            for index in dates.index[tied]:
                names.setdefault(index, set()).add(str(name))
            best_start.loc[newer] = interval_start
            st_flags.loc[newer] = _name_is_st(name)
            st_flags.loc[tied] |= _name_is_st(name)
        resolved_index = list(names)
        result.loc[resolved_index, "effective_name"] = ["|".join(sorted(names[index])) for index in resolved_index]
        result.loc[point_index, "is_st"] = st_flags.astype(bool)

    return result.sort_values("_row").loc[:, ["ts_code", "trade_date", "effective_name", "is_st"]].reset_index(
        drop=True
    )

"""Pure PIT construction and quality checks for the three custom STAR pools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from tools.m3_star_custom_pit.contract import GateFailure
from tools.m3_star_custom_pit.inputs import InputBundle
from tools.m3_star_custom_pit.quality import dates, normalize_calendar, normalize_market, normalize_stock


@dataclass(frozen=True)
class BuildResult:
    formation_members: pd.DataFrame
    daily_members: pd.DataFrame
    metrics: dict[str, Any]


def _name_is_st(value: object) -> bool:
    rendered = str(value).strip().upper()
    return "ST" in rendered and not rendered.endswith("退")


def risk_flags_on(history: pd.DataFrame, observations: pd.DataFrame) -> pd.Series:
    """Resolve PIT ST state; an announcement later than start_date delays availability."""
    required_history = {"ts_code", "name", "start_date", "end_date", "ann_date"}
    required_points = {"ts_code", "trade_date"}
    if missing := required_history - set(history.columns):
        raise GateFailure(f"namechange missing fields: {sorted(missing)}")
    if missing := required_points - set(observations.columns):
        raise GateFailure(f"risk observations missing fields: {sorted(missing)}")

    rows = history.loc[:, list(required_history)].copy()
    rows["_start"] = dates(rows["start_date"])
    rows["_ann"] = dates(rows["ann_date"])
    rows["_effective"] = rows[["_start", "_ann"]].max(axis=1)
    rows["_end"] = dates(rows["end_date"])
    points = observations.loc[:, ["ts_code", "trade_date"]].reset_index(drop=True)
    points["_point"] = dates(points["trade_date"])
    result = pd.Series(False, index=points.index, dtype=bool)
    by_code = {str(code): frame for code, frame in rows.groupby("ts_code", sort=False)}
    for code, point_index in points.groupby("ts_code", sort=False).groups.items():
        security = by_code.get(str(code))
        if security is None:
            continue
        point_dates = points.loc[point_index, "_point"]
        best = pd.Series(pd.NaT, index=point_index, dtype="datetime64[ns]")
        flags = pd.Series(False, index=point_index, dtype=bool)
        for name, effective, end in security[["name", "_effective", "_end"]].itertuples(
            index=False, name=None
        ):
            if pd.isna(effective):
                continue
            active = point_dates.ge(effective) & (pd.isna(end) | point_dates.le(end))
            newer = active & (best.isna() | best.lt(effective))
            tied = active & best.eq(effective)
            best.loc[newer] = effective
            flags.loc[newer] = _name_is_st(name)
            flags.loc[tied] |= _name_is_st(name)
        result.loc[point_index] = flags
    return result


def _formation_dates(calendar: list[str]) -> list[tuple[str, str]]:
    frame = pd.DataFrame({"date": calendar})
    frame["month"] = frame["date"].str[:6]
    month_ends = frame.groupby("month", sort=True)["date"].max().tolist()
    positions = {day: index for index, day in enumerate(calendar)}
    return [
        (day, calendar[positions[day] + 1])
        for day in month_ends
        if positions[day] + 1 < len(calendar)
    ]


def _partition_sizes(count: int) -> tuple[int, int, int]:
    quotient, remainder = divmod(count, 3)
    return tuple(quotient + int(index < remainder) for index in range(3))  # type: ignore[return-value]


def _build_formations(
    stock: pd.DataFrame,
    history: pd.DataFrame,
    market: pd.DataFrame,
    size: pd.DataFrame,
    calendar: list[str],
    protocol: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    formation_dates = _formation_dates(calendar)
    observations = pd.DataFrame(
        [
            {"ts_code": code, "trade_date": formation}
            for formation, _ in formation_dates
            for code in stock["ts_code"]
        ]
    )
    observations["is_st"] = risk_flags_on(history, observations).to_numpy()
    risk = observations.set_index(["trade_date", "ts_code"])["is_st"]
    positions = {day: index for index, day in enumerate(calendar)}
    ids = protocol["identity"]["universe_ids"]
    liquidity_rule = protocol["liquidity"]
    size_rule = protocol["size"]
    member_frames: list[pd.DataFrame] = []
    summaries: list[dict[str, Any]] = []
    for formation, effective in formation_dates:
        point = pd.Timestamp(formation)
        seasoned_at = stock["_list"] + pd.DateOffset(months=12)
        active = seasoned_at.le(point) & (stock["_delist"].isna() | stock["_delist"].gt(point))
        candidates = stock.loc[active, ["ts_code"]].copy()
        if not candidates.empty:
            candidates["is_st"] = [bool(risk.get((formation, code), False)) for code in candidates["ts_code"]]
            candidates = candidates.loc[~candidates["is_st"]].drop(columns="is_st")

        position = positions[formation]
        liquidity_days = calendar[
            max(0, position - int(liquidity_rule["lookback_open_trade_days"]) + 1) : position + 1
        ]
        size_days = calendar[
            max(0, position - int(size_rule["lookback_open_trade_days"]) + 1) : position + 1
        ]
        liquidity = market.loc[
            market["trade_date"].isin(liquidity_days)
            & np.isfinite(market["amount_rmb"])
            & market["amount_rmb"].gt(0)
        ].groupby("ts_code")["amount_rmb"].agg(["count", "median"])
        caps = size.loc[
            size["trade_date"].isin(size_days)
            & np.isfinite(size["total_mv_rmb"])
            & size["total_mv_rmb"].gt(0)
        ].groupby("ts_code")["total_mv_rmb"].agg(["count", "median"])
        candidates = candidates.join(liquidity, on="ts_code").rename(
            columns={"count": "liquidity_valid_days", "median": "median_amount_rmb"}
        )
        candidates = candidates.join(caps, on="ts_code").rename(
            columns={"count": "size_valid_days", "median": "median_total_mv_rmb"}
        )
        liquidity_pass = candidates["liquidity_valid_days"].ge(
            int(liquidity_rule["minimum_valid_days"])
        ) & candidates["median_amount_rmb"].ge(float(liquidity_rule["minimum_median_daily_amount_rmb"]))
        size_pass = candidates["size_valid_days"].ge(int(size_rule["minimum_valid_days"]))
        eligible = candidates.loc[liquidity_pass & size_pass].copy()
        eligible = eligible.sort_values(
            ["median_total_mv_rmb", "ts_code"], ascending=[False, True]
        ).reset_index(drop=True)
        large_count, mid_count, small_count = _partition_sizes(len(eligible))
        eligible["segment"] = (
            ["large_unregistered"] * large_count
            + ["midcap"] * mid_count
            + ["smallcap"] * small_count
        )
        eligible["formation_date"] = formation
        eligible["effective_date"] = effective

        all_rows = eligible.assign(universe_id=ids["all"])
        mid_rows = eligible.loc[eligible["segment"].eq("midcap")].assign(universe_id=ids["midcap"])
        small_rows = eligible.loc[eligible["segment"].eq("smallcap")].assign(
            universe_id=ids["smallcap"]
        )
        member_frames.extend((all_rows, mid_rows, small_rows))
        summaries.append(
            {
                "formation_date": formation,
                "effective_date": effective,
                "seasoned_non_st_candidate_count": int(len(candidates)),
                "all_count": int(len(eligible)),
                "midcap_count": mid_count,
                "smallcap_count": small_count,
            }
        )
    columns = [
        "formation_date", "effective_date", "universe_id", "ts_code", "segment",
        "liquidity_valid_days", "median_amount_rmb", "size_valid_days", "median_total_mv_rmb",
    ]
    members = pd.concat(member_frames, ignore_index=True).loc[:, columns]
    return members.sort_values(["formation_date", "universe_id", "ts_code"]).reset_index(drop=True), pd.DataFrame(summaries)


def _usable_start(summary: pd.DataFrame, protocol: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    gate = protocol["readiness"]
    ready = summary["all_count"].ge(int(gate["all_minimum_names"]))
    ready &= summary["midcap_count"].ge(int(gate["midcap_minimum_names"]))
    ready &= summary["smallcap_count"].ge(int(gate["smallcap_minimum_names"]))
    if not ready.any():
        raise GateFailure("no M3 formation reaches the frozen readiness counts")
    first = int(np.flatnonzero(ready.to_numpy())[0])
    after = ready.iloc[first:]
    if not bool(after.all()):
        failed = summary.loc[after.index[~after], "formation_date"].astype(str).tolist()
        raise GateFailure(f"formation readiness failed after usable start: {failed}")
    if len(after) < int(gate["minimum_consecutive_ready_formations"]):
        raise GateFailure(f"only {len(after)} consecutive ready formations")
    row = summary.iloc[first]
    return str(row["effective_date"]), {
        "first_ready_formation_date": str(row["formation_date"]),
        "usable_start_date": str(row["effective_date"]),
        "not_ready_formation_count": first,
        "consecutive_ready_formation_count": int(len(after)),
        "ready_all_count_minimum": int(summary.iloc[first:]["all_count"].min()),
        "ready_all_count_maximum": int(summary.iloc[first:]["all_count"].max()),
        "ready_midcap_count_minimum": int(summary.iloc[first:]["midcap_count"].min()),
        "ready_midcap_count_maximum": int(summary.iloc[first:]["midcap_count"].max()),
        "ready_smallcap_count_minimum": int(summary.iloc[first:]["smallcap_count"].min()),
        "ready_smallcap_count_maximum": int(summary.iloc[first:]["smallcap_count"].max()),
    }


def _build_daily(
    formations: pd.DataFrame,
    stock: pd.DataFrame,
    history: pd.DataFrame,
    calendar: list[str],
    usable_start: str,
) -> pd.DataFrame:
    effective = formations[["formation_date", "effective_date"]].drop_duplicates().sort_values("effective_date")
    days = pd.DataFrame({"trade_date": [day for day in calendar if day >= usable_start]})
    effective["_effective_point"] = dates(effective["effective_date"])
    days["_trade_point"] = dates(days["trade_date"])
    day_map = pd.merge_asof(
        days.sort_values("_trade_point"),
        effective.sort_values("_effective_point"),
        left_on="_trade_point",
        right_on="_effective_point",
        direction="backward",
    ).dropna(subset=["formation_date"])
    daily = day_map[["trade_date", "formation_date"]].merge(
        formations[["formation_date", "universe_id", "ts_code", "segment"]],
        on="formation_date",
        how="inner",
        validate="many_to_many",
    )
    unique_points = daily[["ts_code", "trade_date"]].drop_duplicates().reset_index(drop=True)
    unique_points["is_st"] = risk_flags_on(history, unique_points).to_numpy()
    daily = daily.merge(unique_points, on=["ts_code", "trade_date"], how="left", validate="many_to_one")
    daily = daily.merge(stock[["ts_code", "_list", "_delist"]], on="ts_code", how="left", validate="many_to_one")
    points = dates(daily["trade_date"])
    active = daily["_list"].le(points) & (daily["_delist"].isna() | daily["_delist"].gt(points))
    daily = daily.loc[active & ~daily["is_st"]]
    return daily[["trade_date", "formation_date", "universe_id", "ts_code", "segment"]].sort_values(
        ["trade_date", "universe_id", "ts_code"]
    ).reset_index(drop=True)


def _validate_outputs(formations: pd.DataFrame, daily: pd.DataFrame, protocol: dict[str, Any]) -> dict[str, Any]:
    formation_keys = ["formation_date", "universe_id", "ts_code"]
    daily_keys = ["trade_date", "universe_id", "ts_code"]
    if formations.duplicated(formation_keys).any() or daily.duplicated(daily_keys).any():
        raise GateFailure("M3 output contains duplicate primary keys")
    forbidden = protocol["sources"]["bse_suffix_forbidden"]
    bse_rows = int(formations["ts_code"].str.endswith(forbidden, na=False).sum())
    bse_rows += int(daily["ts_code"].str.endswith(forbidden, na=False).sum())
    if bse_rows:
        raise GateFailure("M3 output contains forbidden .BJ")
    ids = protocol["identity"]["universe_ids"]
    for frame, date_column in ((formations, "formation_date"), (daily, "trade_date")):
        all_keys = pd.MultiIndex.from_frame(
            frame.loc[frame["universe_id"].eq(ids["all"]), [date_column, "ts_code"]]
        )
        mid_keys = pd.MultiIndex.from_frame(
            frame.loc[frame["universe_id"].eq(ids["midcap"]), [date_column, "ts_code"]]
        )
        small_keys = pd.MultiIndex.from_frame(
            frame.loc[frame["universe_id"].eq(ids["smallcap"]), [date_column, "ts_code"]]
        )
        if not mid_keys.isin(all_keys).all() or not small_keys.isin(all_keys).all():
            raise GateFailure("M3 mid/small output is not a subset of all")
        if mid_keys.isin(small_keys).any():
            raise GateFailure("M3 midcap and smallcap outputs overlap")
    counts = daily.groupby("universe_id")["ts_code"].count()
    return {
        "formation_row_count": int(len(formations)),
        "daily_row_count": int(len(daily)),
        "daily_trade_date_count": int(daily["trade_date"].nunique()),
        "unique_security_count": int(daily["ts_code"].nunique()),
        "daily_rows_by_universe": {str(key): int(value) for key, value in counts.items()},
        "duplicate_formation_key_count": 0,
        "duplicate_daily_key_count": 0,
        "bse_row_count": bse_rows,
        "subset_and_disjoint_gate_pass": True,
    }


def build_membership(inputs: InputBundle, protocol: dict[str, Any]) -> BuildResult:
    calendar = normalize_calendar(inputs.trade_cal, protocol)
    stock = normalize_stock(inputs.stock_basic)
    market, size, source_metrics = normalize_market(inputs.daily, inputs.daily_basic, protocol)
    formations, summary = _build_formations(
        stock, inputs.namechange, market, size, calendar, protocol
    )
    usable_start, readiness = _usable_start(summary, protocol)
    daily = _build_daily(formations, stock, inputs.namechange, calendar, usable_start)
    output_metrics = _validate_outputs(formations, daily, protocol)
    future_event_rows = 0
    if not inputs.namechange.empty:
        event_dates = pd.concat(
            [dates(inputs.namechange["start_date"]), dates(inputs.namechange["ann_date"])], axis=1
        ).max(axis=1)
        cutoff = pd.Timestamp(protocol["identity"]["source_cutoff_date"])
        future_event_rows = int(event_dates.gt(cutoff).sum())
    return BuildResult(
        formation_members=formations,
        daily_members=daily,
        metrics={
            "calendar_trade_date_count": len(calendar),
            "calendar_start": calendar[0],
            "calendar_end": calendar[-1],
            "star_security_identity_count": len(inputs.star_codes),
            "namechange_future_event_rows_ignored": future_event_rows,
            "source": source_metrics,
            "readiness": readiness,
            "output": output_metrics,
            "source_gate_pass": True,
            "pit_gate_pass": True,
            "readiness_gate_pass": True,
            "output_gate_pass": True,
        },
    )

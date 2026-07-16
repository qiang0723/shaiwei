"""行业 + 对数市值中性化残差 RankIC，独立于 AlphaGen 的池目标。"""

import numpy as np
import pandas as pd


def industry_pit_exposure(observations: pd.DataFrame, membership: pd.DataFrame) -> pd.DataFrame:
    """Resolve SW level-1 industry from in/out intervals without future membership."""
    if missing := {"ts_code", "trade_date"} - set(observations.columns):
        raise ValueError(f"observations missing fields: {sorted(missing)}")
    required = {"ts_code", "l1_code", "in_date", "out_date"}
    if missing := required - set(membership.columns):
        raise ValueError(f"industry membership missing fields: {sorted(missing)}")
    points = observations.loc[:, ["ts_code", "trade_date"]].reset_index(drop=True)
    points["_row"] = points.index
    points["_point"] = pd.to_datetime(points["trade_date"], format="%Y%m%d", errors="coerce")
    intervals = membership.loc[:, ["ts_code", "l1_code", "in_date", "out_date"]].copy()
    intervals["_in"] = pd.to_datetime(intervals["in_date"], format="%Y%m%d", errors="coerce")
    intervals["_out"] = pd.to_datetime(intervals["out_date"], format="%Y%m%d", errors="coerce")
    joined = points.merge(intervals, on="ts_code", how="left")
    effective = joined.loc[
        joined["_in"].le(joined["_point"])
        & (joined["_out"].isna() | joined["_out"].ge(joined["_point"]))
    ].copy()
    if effective.empty:
        result = points.loc[:, ["ts_code", "trade_date"]].copy()
        result["industry"] = pd.NA
        return result
    effective["_latest"] = effective.groupby("_row")["_in"].transform("max")
    latest = effective.loc[effective["_in"].eq(effective["_latest"])]
    resolved = latest.groupby("_row")["l1_code"].agg(
        lambda values: "|".join(sorted({str(value) for value in values if pd.notna(value)}))
    )
    result = points.loc[:, ["_row", "ts_code", "trade_date"]].merge(
        resolved.rename("industry"), left_on="_row", right_index=True, how="left"
    )
    return result.loc[:, ["ts_code", "trade_date", "industry"]]


def forward_open_return(open_prices: pd.DataFrame, holding_days: int = 10) -> pd.DataFrame:
    """Signal at t executes at t+1 open and exits after ``holding_days`` trading days."""
    if holding_days < 1:
        raise ValueError("holding_days must be positive")
    return open_prices.shift(-(holding_days + 1)) / open_prices.shift(-1) - 1.0


def _neutralized_residual(group: pd.DataFrame) -> pd.Series:
    valid = group.dropna(subset=["factor", "label", "industry", "market_cap"]).copy()
    valid = valid.loc[valid["market_cap"].gt(0)]
    if valid.empty:
        return pd.Series(dtype=float)
    industries = pd.get_dummies(valid["industry"].astype(str), prefix="industry", drop_first=True, dtype=float)
    design = pd.concat(
        [pd.Series(1.0, index=valid.index, name="intercept"), np.log(valid["market_cap"]).rename("log_cap"), industries],
        axis=1,
    )
    matrix = design.to_numpy(dtype=float)
    factor = valid["factor"].to_numpy(dtype=float)
    coefficients, *_ = np.linalg.lstsq(matrix, factor, rcond=None)
    return pd.Series(factor - matrix @ coefficients, index=valid.index)


def neutralized_factor_values(
    observations: pd.DataFrame,
    min_cross_section: int = 30,
) -> pd.Series:
    """Return PIT industry/size residuals on a datetime/instrument index."""
    required = {"trade_date", "instrument", "factor", "industry", "market_cap"}
    if missing := required - set(observations.columns):
        raise ValueError(f"fitness observations missing fields: {sorted(missing)}")
    residuals = []
    for _, group in observations.groupby("trade_date", sort=True):
        residual = _neutralized_residual(group)
        if len(residual) < min_cross_section or residual.nunique() < 2:
            continue
        frame = observations.loc[residual.index, ["trade_date", "instrument"]].copy()
        frame["factor"] = residual.to_numpy()
        residuals.append(frame)
    if not residuals:
        return pd.Series(dtype=float, name="factor")
    combined = pd.concat(residuals, ignore_index=True)
    index = pd.MultiIndex.from_frame(
        combined.loc[:, ["trade_date", "instrument"]],
        names=["datetime", "instrument"],
    )
    return pd.Series(combined["factor"].to_numpy(dtype=float), index=index, name="factor")


def neutralized_rank_ic(observations: pd.DataFrame, min_cross_section: int = 30) -> tuple[float, pd.Series]:
    required = {"trade_date", "instrument", "factor", "label", "industry", "market_cap"}
    if missing := required - set(observations.columns):
        raise ValueError(f"fitness observations missing fields: {sorted(missing)}")
    daily = {}
    for trade_date, group in observations.groupby("trade_date", sort=True):
        residual = _neutralized_residual(group)
        if len(residual) < min_cross_section or residual.nunique() < 2:
            continue
        labels = group.loc[residual.index, "label"]
        if labels.nunique() < 2:
            continue
        daily[trade_date] = residual.rank(pct=True).corr(labels.rank(pct=True))
    daily_series = pd.Series(daily, dtype=float).dropna()
    return (float(daily_series.mean()) if not daily_series.empty else float("nan"), daily_series)


def screened_rank_ic(rank_ic: float, daily_ic_count: int, minimum: int) -> tuple[float, str]:
    """Reject attractive-looking IC estimates that have no credible time-series depth."""
    if minimum < 1:
        raise ValueError("minimum daily IC observations must be positive")
    if not np.isfinite(rank_ic):
        return -1.0, "rank_ic_nan"
    if daily_ic_count < minimum:
        return -1.0, f"insufficient_daily_ic:{daily_ic_count}"
    return float(rank_ic), ""


def benchmark_decision(
    elapsed_seconds: float,
    best_rank_ic: float,
    *,
    rank_ic_threshold: float = 0.03,
    scale_hours: float,
    abort_hours: float,
) -> str:
    if elapsed_seconds > abort_hours * 3600:
        return "fallback_or_reduce"
    if elapsed_seconds < scale_hours * 3600 and best_rank_ic > rank_ic_threshold:
        return "scale_stage1"
    return "reduce_and_rerun"

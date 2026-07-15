"""行业 + 对数市值中性化残差 RankIC，独立于 AlphaGen 的池目标。"""

import numpy as np
import pandas as pd


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

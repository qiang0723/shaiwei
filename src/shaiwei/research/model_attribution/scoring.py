"""Deterministic score alignment and portfolio-conversion summaries for M6."""

from __future__ import annotations

import math
from typing import Iterable

import numpy as np
import pandas as pd

from shaiwei.research.model_attribution.contract import AttributionError


def _validate_series(series: pd.Series, name: str) -> pd.Series:
    if not isinstance(series, pd.Series) or not isinstance(series.index, pd.MultiIndex):
        raise AttributionError(f"M6 {name} must be a MultiIndex Series")
    if series.index.nlevels != 2 or series.index.has_duplicates:
        raise AttributionError(f"M6 {name} keys are duplicated or malformed")
    numeric = pd.to_numeric(series, errors="raise").astype(float).sort_index()
    if numeric.empty or not np.isfinite(numeric.to_numpy()).all():
        raise AttributionError(f"M6 {name} is empty or nonfinite")
    return numeric


def rank_blend(control: pd.Series, ridge: pd.Series) -> pd.Series:
    control = _validate_series(control, "control prediction")
    ridge = _validate_series(ridge, "ridge prediction")
    if not control.index.equals(ridge.index):
        raise AttributionError("M6 prediction member-day keys differ")
    control_rank = control.groupby(level=0).rank(method="average", pct=True, ascending=True)
    ridge_rank = ridge.groupby(level=0).rank(method="average", pct=True, ascending=True)
    blend = 0.5 * control_rank + 0.5 * ridge_rank
    return _validate_series(blend.rename("score"), "rank blend")


def daily_rank_ic(prediction: pd.Series, label: pd.Series) -> pd.Series:
    prediction = _validate_series(prediction, "prediction")
    label = _validate_series(label, "label")
    if not prediction.index.equals(label.index):
        raise AttributionError("M6 prediction and label keys differ")
    values: dict[object, float] = {}
    for day, scores in prediction.groupby(level=0, sort=True):
        targets = label.xs(day, level=0)
        scores = scores.droplevel(0)
        if len(scores) < 3 or scores.nunique() < 2 or targets.nunique() < 2:
            raise AttributionError("M6 RankIC cross-section is degenerate")
        value = float(scores.corr(targets, method="spearman"))
        if not math.isfinite(value):
            raise AttributionError("M6 RankIC is nonfinite")
        values[day] = value
    return pd.Series(values, dtype=float, name="rank_ic").sort_index()


def score_improvement_summary(
    windows: dict[str, tuple[pd.Series, pd.Series, pd.Series]],
    *,
    minimum_days: int,
    minimum_pooled_days: int,
    minimum_positive_windows: int,
) -> dict[str, object]:
    window_deltas: dict[str, float] = {}
    daily_parts: list[pd.Series] = []
    coverage: dict[str, int] = {}
    for name, (control, alternative, labels) in windows.items():
        control_ic = daily_rank_ic(control, labels)
        alternative_ic = daily_rank_ic(alternative, labels)
        if not control_ic.index.equals(alternative_ic.index):
            raise AttributionError(f"M6 {name} RankIC dates differ")
        delta = alternative_ic - control_ic
        coverage[name] = len(delta)
        window_deltas[name] = float(delta.mean())
        daily_parts.append(delta)
    pooled = pd.concat(daily_parts, axis=0)
    coverage_pass = bool(
        coverage
        and all(value >= minimum_days for value in coverage.values())
        and len(pooled) >= minimum_pooled_days
    )
    positive = sum(value > 0 for value in window_deltas.values())
    pooled_mean = float(pooled.mean())
    return {
        "coverage_by_window": coverage,
        "pooled_day_count": len(pooled),
        "coverage_pass": coverage_pass,
        "window_mean_rank_ic_delta": window_deltas,
        "positive_delta_windows": positive,
        "pooled_mean_rank_ic_delta": pooled_mean,
        "score_pass": bool(
            coverage_pass and pooled_mean > 0 and positive >= minimum_positive_windows
        ),
    }


def compound(returns: Iterable[float]) -> float:
    values = np.asarray(tuple(returns), dtype=float)
    if values.size == 0 or not np.isfinite(values).all() or (values <= -1).any():
        raise AttributionError("M6 returns cannot be compounded")
    return float(np.prod(1.0 + values) - 1.0)


def maximum_drawdown(returns: Iterable[float]) -> float:
    values = np.asarray(tuple(returns), dtype=float)
    if values.size == 0 or not np.isfinite(values).all() or (values <= -1).any():
        raise AttributionError("M6 returns cannot form a drawdown")
    nav = np.cumprod(1.0 + values)
    peak = np.maximum.accumulate(np.concatenate(([1.0], nav)))
    nav_with_start = np.concatenate(([1.0], nav))
    return float(np.max(1.0 - nav_with_start / peak))


def portfolio_conversion_summary(
    control: dict[str, dict[str, tuple[float, ...]]],
    alternative: dict[str, dict[str, tuple[float, ...]]],
    *,
    control_turnover: float,
    alternative_turnover: float,
) -> dict[str, object]:
    scenarios = ("1", "1.5", "2")
    if set(control) != set(scenarios) or set(alternative) != set(scenarios):
        raise AttributionError("M6 cost scenario set differs")
    windows = tuple(control["1"])
    if windows != ("W1", "W2", "W3", "W4", "W5", "W6"):
        raise AttributionError("M6 portfolio window order differs")
    pooled_deltas: dict[str, float] = {}
    base_window_deltas: dict[str, float] = {}
    base_daily_delta: list[float] = []
    drawdowns: dict[str, float] = {}
    for scenario in scenarios:
        if tuple(alternative[scenario]) != windows:
            raise AttributionError("M6 alternative window order differs")
        control_pool: list[float] = []
        alternative_pool: list[float] = []
        for window in windows:
            control_values = tuple(float(value) for value in control[scenario][window])
            alternative_values = tuple(float(value) for value in alternative[scenario][window])
            if len(control_values) != len(alternative_values) or not control_values:
                raise AttributionError("M6 paired portfolio return lengths differ")
            control_pool.extend(control_values)
            alternative_pool.extend(alternative_values)
            if scenario == "1":
                base_window_deltas[window] = compound(alternative_values) - compound(control_values)
                base_daily_delta.extend(
                    alternative_value - control_value
                    for control_value, alternative_value in zip(
                        control_values, alternative_values, strict=True
                    )
                )
                drawdowns[window] = maximum_drawdown(alternative_values)
        pooled_deltas[scenario] = compound(alternative_pool) - compound(control_pool)
    if not math.isfinite(control_turnover) or control_turnover <= 0:
        raise AttributionError("M6 control turnover is invalid")
    turnover_ratio = float(alternative_turnover / control_turnover)
    if not math.isfinite(turnover_ratio) or turnover_ratio < 0:
        raise AttributionError("M6 turnover ratio is invalid")
    return {
        "base_daily_return_delta": base_daily_delta,
        "base_window_net_excess_delta": base_window_deltas,
        "positive_base_delta_windows": sum(value > 0 for value in base_window_deltas.values()),
        "pooled_cost_delta": pooled_deltas,
        "turnover_ratio": turnover_ratio,
        "maximum_drawdown": max(drawdowns.values()),
        "drawdown_by_window": drawdowns,
    }

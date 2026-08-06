"""Independent M6-2 statistics; no imports from the primary metric or inference path."""

from __future__ import annotations

import math
from typing import Any, Iterable

import numpy as np
import pandas as pd
from scipy.stats import norm

from shaiwei.research.model_attribution.contract import AttributionError
from shaiwei.research.model_attribution.effect_schema import (
    ALTERNATIVES,
    ARMS,
    SCENARIOS,
    WINDOWS,
)


def _member_series(value: pd.Series, name: str) -> pd.Series:
    if not isinstance(value, pd.Series) or not isinstance(value.index, pd.MultiIndex):
        raise AttributionError(f"M6 audit {name} is not a member-day Series")
    result = pd.to_numeric(value, errors="raise").astype(float).sort_index()
    if result.empty or result.index.has_duplicates or not np.isfinite(result.to_numpy()).all():
        raise AttributionError(f"M6 audit {name} is empty, duplicated, or nonfinite")
    return result


def _rank_ic(prediction: pd.Series, label: pd.Series) -> pd.Series:
    prediction = _member_series(prediction, "prediction")
    label = _member_series(label, "label")
    if not prediction.index.equals(label.index):
        raise AttributionError("M6 audit prediction and label keys differ")
    values: dict[pd.Timestamp, float] = {}
    for day, scores in prediction.groupby(level=0, sort=True):
        scores = scores.droplevel(0)
        targets = label.xs(day, level=0)
        if len(scores) < 30 or scores.nunique() < 2 or targets.nunique() < 2:
            raise AttributionError("M6 audit RankIC cross-section is insufficient")
        value = float(scores.corr(targets, method="spearman"))
        if not math.isfinite(value):
            raise AttributionError("M6 audit RankIC is nonfinite")
        values[pd.Timestamp(day)] = value
    return pd.Series(values, name="rank_ic", dtype=float).sort_index()


def _score_evidence(
    predictions: dict[str, dict[str, pd.Series]],
    labels: dict[str, pd.Series],
    protocol: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    if tuple(predictions) != WINDOWS or tuple(labels) != WINDOWS:
        raise AttributionError("M6 audit score window order differs")
    gate = protocol["coverage_gate"]
    output: dict[str, dict[str, Any]] = {}
    for alternative in ALTERNATIVES:
        coverage: dict[str, int] = {}
        window_delta: dict[str, float] = {}
        daily: list[pd.Series] = []
        for window in WINDOWS:
            arms = predictions[window]
            if tuple(arms) != ARMS:
                raise AttributionError("M6 audit score arm order differs")
            if not all(arms[ARMS[0]].index.equals(arms[arm].index) for arm in ARMS[1:]):
                raise AttributionError("M6 audit prediction keys differ across arms")
            control_ic = _rank_ic(arms[ARMS[0]], labels[window])
            alternative_ic = _rank_ic(arms[alternative], labels[window])
            delta = alternative_ic - control_ic
            coverage[window] = len(delta)
            window_delta[window] = float(delta.mean())
            daily.append(delta)
        pooled = pd.concat(daily)
        coverage_pass = all(
            count >= int(gate["minimum_mature_score_days_per_window"]) for count in coverage.values()
        ) and len(pooled) >= int(gate["minimum_pooled_mature_score_days"])
        positive = sum(value > 0 for value in window_delta.values())
        pooled_mean = float(pooled.mean())
        required_positive = int(
            protocol["diagnostics"]["score_improvement"]["minimum_positive_delta_windows"]
        )
        output[alternative] = {
            "coverage_by_window": coverage,
            "pooled_day_count": len(pooled),
            "coverage_pass": coverage_pass,
            "window_mean_rank_ic_delta": window_delta,
            "positive_delta_windows": positive,
            "pooled_mean_rank_ic_delta": pooled_mean,
            "score_pass": bool(coverage_pass and pooled_mean > 0 and positive >= required_positive),
        }
    return output


def _report(value: pd.DataFrame) -> pd.DataFrame:
    expected = ["gross_return", "benchmark_return", "recorded_cost", "turnover"]
    if list(value.columns) != expected:
        raise AttributionError("M6 audit report columns differ")
    frame = value.copy().sort_index()
    for column in expected:
        frame[column] = pd.to_numeric(frame[column], errors="raise").astype(float)
    if frame.empty or frame.index.has_duplicates or not np.isfinite(frame.to_numpy()).all():
        raise AttributionError("M6 audit report is empty, duplicated, or nonfinite")
    if (frame[["gross_return", "benchmark_return"]] <= -1).any().any():
        raise AttributionError("M6 audit report is not compoundable")
    return frame


def _scenario(value: pd.DataFrame, multiplier: float) -> tuple[pd.Series, pd.Series]:
    frame = _report(value)
    net = frame["gross_return"] - multiplier * frame["recorded_cost"]
    active = (1.0 + net) / (1.0 + frame["benchmark_return"]) - 1.0
    if (net <= -1).any() or not np.isfinite(active.to_numpy()).all():
        raise AttributionError("M6 audit cost scenario is invalid")
    return net, active


def _compound(values: Iterable[float]) -> float:
    data = np.asarray(tuple(values), dtype=float)
    if data.size == 0 or not np.isfinite(data).all() or (data <= -1).any():
        raise AttributionError("M6 audit returns cannot be compounded")
    return float(np.prod(1.0 + data) - 1.0)


def _drawdown(values: Iterable[float]) -> float:
    data = np.asarray(tuple(values), dtype=float)
    if data.size == 0 or not np.isfinite(data).all() or (data <= -1).any():
        raise AttributionError("M6 audit returns cannot form drawdown")
    nav = np.cumprod(1.0 + data)
    nav = np.concatenate(([1.0], nav))
    peak = np.maximum.accumulate(nav)
    return float(np.max(1.0 - nav / peak))


def _portfolio_evidence(
    reports: dict[str, dict[str, pd.DataFrame]],
    stress_reports: dict[str, pd.DataFrame],
) -> dict[str, dict[str, Any]]:
    if tuple(reports) != WINDOWS or tuple(stress_reports) != ARMS:
        raise AttributionError("M6 audit portfolio keys differ")
    control = ARMS[0]
    control_turnover = sum(float(_report(reports[w][control])["turnover"].sum()) for w in WINDOWS)
    if control_turnover <= 0:
        raise AttributionError("M6 audit control turnover is non-positive")
    output: dict[str, dict[str, Any]] = {}
    for arm in ALTERNATIVES:
        pooled_delta: dict[str, float] = {}
        window_delta: dict[str, float] = {}
        paired_daily: list[float] = []
        drawdowns: dict[str, float] = {}
        for scenario in SCENARIOS:
            control_pool: list[float] = []
            arm_pool: list[float] = []
            benchmark_pool: list[float] = []
            for window in WINDOWS:
                control_frame = _report(reports[window][control])
                arm_frame = _report(reports[window][arm])
                if not control_frame.index.equals(arm_frame.index):
                    raise AttributionError("M6 audit paired backtest dates differ")
                if not control_frame["benchmark_return"].equals(arm_frame["benchmark_return"]):
                    raise AttributionError("M6 audit paired benchmark returns differ")
                control_net, control_active = _scenario(control_frame, float(scenario))
                arm_net, arm_active = _scenario(arm_frame, float(scenario))
                control_pool.extend(control_net.tolist())
                arm_pool.extend(arm_net.tolist())
                benchmark_pool.extend(control_frame["benchmark_return"].tolist())
                if scenario == "1":
                    paired_daily.extend((arm_active - control_active).tolist())
                    benchmark_nav = 1 + _compound(control_frame["benchmark_return"])
                    control_excess = (1 + _compound(control_net)) / benchmark_nav - 1
                    arm_excess = (1 + _compound(arm_net)) / benchmark_nav - 1
                    window_delta[window] = float(arm_excess - control_excess)
                    drawdowns[window] = _drawdown(arm_net)
            benchmark_nav = 1 + _compound(benchmark_pool)
            control_excess = (1 + _compound(control_pool)) / benchmark_nav - 1
            arm_excess = (1 + _compound(arm_pool)) / benchmark_nav - 1
            pooled_delta[scenario] = float(arm_excess - control_excess)
        stress_net, _ = _scenario(stress_reports[arm], 1.0)
        drawdowns["volume_price_drawdown_2026h1"] = _drawdown(stress_net)
        w6_net, _ = _scenario(reports["W6"][arm], 1.0)
        drawdowns["microcap_crash_2024"] = _drawdown(w6_net.loc["2024-01-01":"2024-02-29"])
        arm_turnover = sum(float(_report(reports[w][arm])["turnover"].sum()) for w in WINDOWS)
        output[arm] = {
            "base_daily_return_delta": paired_daily,
            "base_window_net_excess_delta": window_delta,
            "positive_base_delta_windows": sum(value > 0 for value in window_delta.values()),
            "pooled_cost_delta": pooled_delta,
            "turnover_ratio": float(arm_turnover / control_turnover),
            "maximum_drawdown": max(drawdowns.values()),
            "drawdown_by_window_and_stress": drawdowns,
        }
    return output


def _newey_west(values: list[float], lags: int) -> float:
    data = np.asarray(values, dtype=float)
    if data.ndim != 1 or len(data) <= lags or not np.isfinite(data).all():
        raise AttributionError("M6 audit HAC input is invalid")
    centered = data - data.mean()
    variance = float(np.dot(centered, centered) / len(data))
    for lag in range(1, lags + 1):
        covariance = float(np.dot(centered[lag:], centered[:-lag]) / len(data))
        variance += 2.0 * (1.0 - lag / (lags + 1.0)) * covariance
    variance /= len(data)
    if not math.isfinite(variance) or variance <= 0:
        raise AttributionError("M6 audit HAC variance is non-positive")
    return float(data.mean() / math.sqrt(variance))


def _holm(raw: dict[str, float]) -> dict[str, float]:
    ordered = sorted(raw.items(), key=lambda item: (item[1], item[0]))
    if len(ordered) != 2:
        raise AttributionError("M6 audit Holm family differs")
    output: dict[str, float] = {}
    running = 0.0
    for index, (name, value) in enumerate(ordered):
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise AttributionError("M6 audit Holm p-value is invalid")
        running = max(running, min(1.0, (2 - index) * value))
        output[name] = running
    return output


def _decision(passes: dict[str, dict[str, bool]], blocked: bool) -> str:
    if blocked:
        return "BLOCKED"
    if any(row["score_pass"] and row["portfolio_pass"] for row in passes.values()):
        return "MODEL_STRUCTURE_SUPPORTED"
    if any(row["score_pass"] for row in passes.values()) and not any(
        row["portfolio_pass"] for row in passes.values()
    ):
        return "PORTFOLIO_CONVERSION_BOTTLENECK_INDICATED"
    if not any(row["score_pass"] or row["portfolio_pass"] for row in passes.values()):
        return "FEATURE_INFORMATION_BOTTLENECK_INDICATED"
    return "MIXED_NOT_CONCLUSIVE"


def independently_evaluate(
    predictions: dict[str, dict[str, pd.Series]],
    labels: dict[str, pd.Series],
    reports: dict[str, dict[str, pd.DataFrame]],
    stress_reports: dict[str, pd.DataFrame],
    protocol: dict[str, Any],
) -> dict[str, Any]:
    scores = _score_evidence(predictions, labels, protocol)
    portfolios = _portfolio_evidence(reports, stress_reports)
    lags = int(protocol["primary_inference"]["hac_lags"])
    t_values = {arm: _newey_west(portfolios[arm]["base_daily_return_delta"], lags) for arm in ALTERNATIVES}
    raw = {arm: float(norm.sf(t_values[arm])) for arm in ALTERNATIVES}
    adjusted = _holm(raw)
    gates = protocol["diagnostics"]["portfolio_conversion"]
    blocked = any(not scores[arm]["coverage_pass"] for arm in ALTERNATIVES)
    passes: dict[str, dict[str, bool]] = {}
    details: dict[str, dict[str, Any]] = {}
    for arm in ALTERNATIVES:
        portfolio = portfolios[arm]
        before_p = bool(
            portfolio["pooled_cost_delta"]["1"] > 0
            and portfolio["positive_base_delta_windows"] >= gates["minimum_positive_base_delta_windows"]
            and portfolio["pooled_cost_delta"]["1.5"] >= 0
            and portfolio["pooled_cost_delta"]["2"] >= 0
            and portfolio["turnover_ratio"] <= gates["maximum_turnover_ratio_vs_control"]
            and portfolio["maximum_drawdown"] <= gates["maximum_test_or_evaluable_stress_drawdown"]
        )
        portfolio_pass = bool(before_p and adjusted[arm] <= protocol["primary_inference"]["familywise_alpha"])
        passes[arm] = {"score_pass": scores[arm]["score_pass"], "portfolio_pass": portfolio_pass}
        details[arm] = {
            "score_pass": scores[arm]["score_pass"],
            "portfolio_before_primary_inference": before_p,
            "hac_t": t_values[arm],
            "raw_one_sided_p": raw[arm],
            "holm_adjusted_p": adjusted[arm],
            "portfolio_pass": portfolio_pass,
        }
    return {
        "score": scores,
        "portfolio": portfolios,
        "inference": {
            "blocked": blocked,
            "alternatives": details,
            "decision_inputs": passes,
            "decision": _decision(passes, blocked),
        },
    }


def independently_score_diagnostics(
    predictions: dict[str, dict[str, pd.Series]],
    stored_top30: dict[str, dict[str, dict[str, list[str]]]],
    rebalance_days: int,
) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for window in WINDOWS:
        arms = predictions[window]
        control = _member_series(arms[ARMS[0]], "test prediction")
        window_output: dict[str, Any] = {}
        recomputed: dict[str, dict[str, list[str]]] = {}
        for arm in ARMS:
            value = _member_series(arms[arm], "test prediction")
            if not control.index.equals(value.index):
                raise AttributionError("M6 audit test prediction keys differ")
            dates = sorted(pd.to_datetime(value.index.get_level_values(0)).unique())
            schedule: dict[str, list[str]] = {}
            for step, day in enumerate(dates):
                if step % rebalance_days:
                    continue
                cross = value.xs(day, level=0).rename("score").reset_index()
                cross["instrument"] = cross["instrument"].astype(str)
                cross = cross.sort_values(["score", "instrument"], ascending=[False, True])
                if len(cross) < 30:
                    raise AttributionError("M6 audit Top30 cross-section is insufficient")
                schedule[pd.Timestamp(day).strftime("%Y-%m-%d")] = cross["instrument"].head(30).tolist()
            if schedule != stored_top30[window][arm]:
                raise AttributionError("M6 audit stored Top30 differs")
            recomputed[arm] = schedule
        for arm in ALTERNATIVES:
            correlations = []
            for day, scores in control.groupby(level=0, sort=True):
                correlation = float(scores.droplevel(0).corr(arms[arm].xs(day, level=0), method="spearman"))
                if not math.isfinite(correlation):
                    raise AttributionError("M6 audit score correlation is nonfinite")
                correlations.append(correlation)
            overlaps = [
                len(set(recomputed[ARMS[0]][day]) & set(recomputed[arm][day])) / 30.0
                for day in recomputed[ARMS[0]]
            ]
            window_output[arm] = {
                "mean_daily_score_spearman_vs_control": float(pd.Series(correlations).mean()),
                "mean_scheduled_signal_top30_overlap": float(pd.Series(overlaps).mean()),
                "scheduled_rebalance_count": len(overlaps),
            }
        output[window] = window_output
    return output

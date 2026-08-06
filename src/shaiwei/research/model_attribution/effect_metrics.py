"""Pure M6-2 score, execution, and portfolio attribution calculations."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from shaiwei.research.model_attribution.contract import AttributionError
from shaiwei.research.model_attribution.inference import evaluate_alternatives
from shaiwei.research.model_attribution.scoring import compound, maximum_drawdown
from shaiwei.research.model_attribution.effect_schema import (
    ALTERNATIVES,
    ARMS,
    SCENARIOS,
    WINDOWS,
)


def _series(value: pd.Series, name: str) -> pd.Series:
    if not isinstance(value, pd.Series) or not isinstance(value.index, pd.MultiIndex):
        raise AttributionError(f"M6 {name} is not a member-day Series")
    result = pd.to_numeric(value, errors="raise").astype(float).sort_index()
    if result.index.has_duplicates or result.empty or not np.isfinite(result.to_numpy()).all():
        raise AttributionError(f"M6 {name} is duplicated, empty, or nonfinite")
    return result


def daily_rank_ic(prediction: pd.Series, label: pd.Series, *, minimum_members: int = 30) -> pd.Series:
    prediction, label = _series(prediction, "prediction"), _series(label, "label")
    if not prediction.index.equals(label.index):
        raise AttributionError("M6 prediction and mature label keys differ")
    values: dict[pd.Timestamp, float] = {}
    for day, scores in prediction.groupby(level=0, sort=True):
        scores = scores.droplevel(0)
        targets = label.xs(day, level=0)
        if len(scores) < minimum_members or scores.nunique() < 2 or targets.nunique() < 2:
            raise AttributionError("M6 real RankIC cross-section is insufficient")
        value = float(scores.corr(targets, method="spearman"))
        if not math.isfinite(value):
            raise AttributionError("M6 real RankIC is nonfinite")
        values[pd.Timestamp(day)] = value
    return pd.Series(values, name="rank_ic", dtype=float).sort_index()


def score_evidence(
    predictions: dict[str, dict[str, pd.Series]],
    labels: dict[str, pd.Series],
    protocol: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    if tuple(predictions) != WINDOWS or tuple(labels) != WINDOWS:
        raise AttributionError("M6 score window order differs")
    output: dict[str, dict[str, Any]] = {}
    gate = protocol["coverage_gate"]
    for alternative in ALTERNATIVES:
        coverage: dict[str, int] = {}
        window_delta: dict[str, float] = {}
        daily: list[pd.Series] = []
        for window in WINDOWS:
            arms = predictions[window]
            if tuple(arms) != ARMS:
                raise AttributionError("M6 prediction arm order differs")
            indexes = [arms[arm].index for arm in ARMS]
            if not all(indexes[0].equals(index) for index in indexes[1:]):
                raise AttributionError("M6 prediction keys differ across arms")
            control_ic = daily_rank_ic(arms[ARMS[0]], labels[window])
            alternative_ic = daily_rank_ic(arms[alternative], labels[window])
            delta = alternative_ic - control_ic
            coverage[window] = len(delta)
            window_delta[window] = float(delta.mean())
            daily.append(delta)
        pooled = pd.concat(daily)
        coverage_pass = all(
            value >= int(gate["minimum_mature_score_days_per_window"]) for value in coverage.values()
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


def normalize_report(report: pd.DataFrame) -> pd.DataFrame:
    normalized = ["gross_return", "benchmark_return", "recorded_cost", "turnover"]
    if list(report.columns) == normalized:
        frame = report.copy()
    else:
        required = {"return", "bench", "cost"}
        if missing := required - set(report.columns):
            raise AttributionError(f"M6 qlib report lacks {sorted(missing)}")
        turnover = "turnover" if "turnover" in report.columns else "total_turnover"
        if turnover not in report.columns:
            raise AttributionError("M6 qlib report lacks turnover evidence")
        frame = report[["return", "bench", "cost", turnover]].copy()
        frame.columns = normalized
    frame.index = pd.to_datetime(frame.index)
    frame = frame.sort_index()
    for column in frame.columns:
        frame[column] = pd.to_numeric(frame[column], errors="raise").astype(float)
    if frame.empty or frame.index.has_duplicates or not np.isfinite(frame.to_numpy()).all():
        raise AttributionError("M6 qlib report is empty, duplicated, or nonfinite")
    if (frame[["gross_return", "benchmark_return"]] <= -1).any().any():
        raise AttributionError("M6 daily return is not compoundable")
    return frame


def scenario_returns(report: pd.DataFrame, multiplier: float) -> tuple[pd.Series, pd.Series]:
    frame = normalize_report(report)
    net = frame["gross_return"] - float(multiplier) * frame["recorded_cost"]
    active = (1.0 + net) / (1.0 + frame["benchmark_return"]) - 1.0
    if (net <= -1).any() or not np.isfinite(active.to_numpy()).all():
        raise AttributionError("M6 cost scenario return is invalid")
    return net.rename("net_return"), active.rename("net_active_return")


def portfolio_evidence(
    reports: dict[str, dict[str, pd.DataFrame]],
    stress_reports: dict[str, pd.DataFrame],
    protocol: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    if tuple(reports) != WINDOWS or tuple(stress_reports) != ARMS:
        raise AttributionError("M6 portfolio evidence keys differ")
    outputs: dict[str, dict[str, Any]] = {}
    control = ARMS[0]
    control_turnover = sum(float(normalize_report(reports[w][control])["turnover"].sum()) for w in WINDOWS)
    if control_turnover <= 0:
        raise AttributionError("M6 control turnover is non-positive")
    for arm in ALTERNATIVES:
        pooled_delta: dict[str, float] = {}
        window_base_delta: dict[str, float] = {}
        paired_daily: list[float] = []
        drawdowns: dict[str, float] = {}
        for scenario in SCENARIOS:
            multiplier = float(scenario)
            control_pool: list[float] = []
            arm_pool: list[float] = []
            benchmark_pool: list[float] = []
            for window in WINDOWS:
                control_net, control_active = scenario_returns(reports[window][control], multiplier)
                arm_net, arm_active = scenario_returns(reports[window][arm], multiplier)
                control_frame = normalize_report(reports[window][control])
                arm_frame = normalize_report(reports[window][arm])
                if not control_frame.index.equals(arm_frame.index):
                    raise AttributionError("M6 paired backtest dates differ")
                if not control_frame["benchmark_return"].equals(arm_frame["benchmark_return"]):
                    raise AttributionError("M6 paired benchmark returns differ")
                control_pool.extend(control_net.tolist())
                arm_pool.extend(arm_net.tolist())
                benchmark_pool.extend(control_frame["benchmark_return"].tolist())
                if scenario == "1":
                    paired_daily.extend((arm_active - control_active).tolist())
                    control_excess = (1 + compound(control_net)) / (
                        1 + compound(control_frame["benchmark_return"])
                    ) - 1
                    arm_excess = (1 + compound(arm_net)) / (1 + compound(arm_frame["benchmark_return"])) - 1
                    window_base_delta[window] = float(arm_excess - control_excess)
                    drawdowns[window] = maximum_drawdown(arm_net)
            benchmark_nav = 1 + compound(benchmark_pool)
            control_excess = (1 + compound(control_pool)) / benchmark_nav - 1
            arm_excess = (1 + compound(arm_pool)) / benchmark_nav - 1
            pooled_delta[scenario] = float(arm_excess - control_excess)
        stress_net, _ = scenario_returns(stress_reports[arm], 1.0)
        drawdowns["volume_price_drawdown_2026h1"] = maximum_drawdown(stress_net)
        w6_net, _ = scenario_returns(reports["W6"][arm], 1.0)
        microcap = w6_net.loc["2024-01-01":"2024-02-29"]
        drawdowns["microcap_crash_2024"] = maximum_drawdown(microcap)
        arm_turnover = sum(float(normalize_report(reports[w][arm])["turnover"].sum()) for w in WINDOWS)
        outputs[arm] = {
            "base_daily_return_delta": paired_daily,
            "base_window_net_excess_delta": window_base_delta,
            "positive_base_delta_windows": sum(value > 0 for value in window_base_delta.values()),
            "pooled_cost_delta": pooled_delta,
            "turnover_ratio": float(arm_turnover / control_turnover),
            "maximum_drawdown": max(drawdowns.values()),
            "drawdown_by_window_and_stress": drawdowns,
        }
    return outputs


def evaluate_effect(
    predictions: dict[str, dict[str, pd.Series]],
    labels: dict[str, pd.Series],
    reports: dict[str, dict[str, pd.DataFrame]],
    stress_reports: dict[str, pd.DataFrame],
    protocol: dict[str, Any],
) -> dict[str, Any]:
    scores = score_evidence(predictions, labels, protocol)
    portfolios = portfolio_evidence(reports, stress_reports, protocol)
    family = tuple(protocol["primary_inference"]["hypothesis_family"])
    evidence = {arm: {"score": scores[arm], "portfolio": portfolios[arm]} for arm in family}
    return {
        "score": scores,
        "portfolio": portfolios,
        "inference": evaluate_alternatives(evidence, protocol),
    }

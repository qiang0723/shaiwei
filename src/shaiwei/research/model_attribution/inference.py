"""M6 paired HAC inference, Holm control, and unique attribution decision."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy.stats import norm

from shaiwei.research.model_attribution.contract import AttributionError


def newey_west_mean_t(values: list[float], *, lags: int) -> float:
    data = np.asarray(values, dtype=float)
    if data.ndim != 1 or len(data) <= lags or not np.isfinite(data).all():
        raise AttributionError("M6 HAC input is invalid")
    centered = data - data.mean()
    variance = float(np.dot(centered, centered) / len(data))
    for lag in range(1, lags + 1):
        covariance = float(np.dot(centered[lag:], centered[:-lag]) / len(data))
        variance += 2.0 * (1.0 - lag / (lags + 1.0)) * covariance
    variance_of_mean = variance / len(data)
    if not math.isfinite(variance_of_mean) or variance_of_mean <= 0:
        raise AttributionError("M6 HAC variance is non-positive")
    return float(data.mean() / math.sqrt(variance_of_mean))


def one_sided_p_value(t_value: float) -> float:
    if not math.isfinite(t_value):
        raise AttributionError("M6 HAC t is nonfinite")
    return float(norm.sf(t_value))


def holm_adjust(p_values: dict[str, float]) -> dict[str, float]:
    if len(p_values) != 2 or any(not math.isfinite(value) or not 0 <= value <= 1 for value in p_values.values()):
        raise AttributionError("M6 Holm family must contain two finite p-values")
    ordered = sorted(p_values.items(), key=lambda item: (item[1], item[0]))
    adjusted: dict[str, float] = {}
    running = 0.0
    total = len(ordered)
    for index, (name, value) in enumerate(ordered):
        running = max(running, min(1.0, (total - index) * value))
        adjusted[name] = running
    return adjusted


def _portfolio_before_p(summary: dict[str, Any], protocol: dict[str, Any]) -> bool:
    gates = protocol["diagnostics"]["portfolio_conversion"]
    pooled = summary["pooled_cost_delta"]
    return bool(
        pooled["1"] > 0
        and int(summary["positive_base_delta_windows"])
        >= int(gates["minimum_positive_base_delta_windows"])
        and pooled["1.5"] >= 0
        and pooled["2"] >= 0
        and float(summary["turnover_ratio"]) <= float(gates["maximum_turnover_ratio_vs_control"])
        and float(summary["maximum_drawdown"])
        <= float(gates["maximum_test_or_evaluable_stress_drawdown"])
    )


def decide_from_passes(
    alternatives: dict[str, dict[str, bool]],
    *,
    blocked: bool,
) -> str:
    if blocked:
        return "BLOCKED"
    if any(value["score_pass"] and value["portfolio_pass"] for value in alternatives.values()):
        return "MODEL_STRUCTURE_SUPPORTED"
    if any(value["score_pass"] for value in alternatives.values()) and not any(
        value["portfolio_pass"] for value in alternatives.values()
    ):
        return "PORTFOLIO_CONVERSION_BOTTLENECK_INDICATED"
    if not any(
        value["score_pass"] or value["portfolio_pass"] for value in alternatives.values()
    ):
        return "FEATURE_INFORMATION_BOTTLENECK_INDICATED"
    return "MIXED_NOT_CONCLUSIVE"


def evaluate_alternatives(
    evidence: dict[str, dict[str, Any]],
    protocol: dict[str, Any],
) -> dict[str, Any]:
    expected = tuple(protocol["primary_inference"]["hypothesis_family"])
    if tuple(evidence) != expected:
        raise AttributionError("M6 evidence arm family or order differs")
    lags = int(protocol["primary_inference"]["hac_lags"])
    raw_p: dict[str, float] = {}
    t_values: dict[str, float] = {}
    blocked = False
    for arm, values in evidence.items():
        score = values["score"]
        if not score.get("coverage_pass", False):
            blocked = True
        t_value = newey_west_mean_t(values["portfolio"]["base_daily_return_delta"], lags=lags)
        t_values[arm] = t_value
        raw_p[arm] = one_sided_p_value(t_value)
    adjusted = holm_adjust(raw_p)
    alpha = float(protocol["primary_inference"]["familywise_alpha"])
    passes: dict[str, dict[str, bool]] = {}
    details: dict[str, dict[str, Any]] = {}
    for arm, values in evidence.items():
        score_pass = bool(values["score"]["score_pass"])
        portfolio_before_p = _portfolio_before_p(values["portfolio"], protocol)
        portfolio_pass = bool(portfolio_before_p and adjusted[arm] <= alpha)
        passes[arm] = {"score_pass": score_pass, "portfolio_pass": portfolio_pass}
        details[arm] = {
            "score_pass": score_pass,
            "portfolio_before_primary_inference": portfolio_before_p,
            "hac_t": t_values[arm],
            "raw_one_sided_p": raw_p[arm],
            "holm_adjusted_p": adjusted[arm],
            "portfolio_pass": portfolio_pass,
        }
    return {
        "blocked": blocked,
        "alternatives": details,
        "decision_inputs": passes,
        "decision": decide_from_passes(passes, blocked=blocked),
    }

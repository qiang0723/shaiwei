"""Primary M6-3 Top20 conversion metrics, inference, and decision."""

from __future__ import annotations

from typing import Any, Iterable

import numpy as np

from shaiwei.research.model_attribution.contract import AttributionError
from shaiwei.research.model_attribution.inference import (
    holm_adjust,
    newey_west_mean_t,
    one_sided_p_value,
)
from shaiwei.research.topk_conversion.contract import ConversionError
from shaiwei.research.topk_conversion.schema import (
    ALTERNATIVES,
    ARMS,
    REPORT_FIELDS,
    SCENARIOS,
    STRESS_PERIODS,
    TOPK_KEYS,
    WINDOWS,
)


def _report(rows: object, name: str) -> dict[str, np.ndarray]:
    if not isinstance(rows, list) or not rows:
        raise ConversionError(f"M6-3 {name} report is empty")
    if any(not isinstance(row, dict) or set(row) != set(REPORT_FIELDS) for row in rows):
        raise ConversionError(f"M6-3 {name} report fields differ")
    dates = [str(row["date"]) for row in rows]
    if dates != sorted(set(dates)):
        raise ConversionError(f"M6-3 {name} report dates differ")
    output: dict[str, np.ndarray] = {"date": np.asarray(dates, dtype=object)}
    for field in REPORT_FIELDS[1:]:
        try:
            values = np.asarray([float(row[field]) for row in rows], dtype=float)
        except (TypeError, ValueError) as exc:
            raise ConversionError(f"M6-3 {name} report contains nonnumeric values") from exc
        if not np.isfinite(values).all():
            raise ConversionError(f"M6-3 {name} report is nonfinite")
        output[field] = values
    if (output["gross_return"] <= -1).any() or (output["benchmark_return"] <= -1).any():
        raise ConversionError(f"M6-3 {name} report is not compoundable")
    if (output["recorded_cost"] < 0).any() or (output["turnover"] < 0).any():
        raise ConversionError(f"M6-3 {name} cost or turnover is negative")
    return output


def _compound(values: Iterable[float]) -> float:
    data = np.asarray(tuple(values), dtype=float)
    if data.size == 0 or not np.isfinite(data).all() or (data <= -1).any():
        raise ConversionError("M6-3 returns cannot be compounded")
    return float(np.prod(1.0 + data) - 1.0)


def _drawdown(values: Iterable[float]) -> float:
    data = np.asarray(tuple(values), dtype=float)
    if data.size == 0 or not np.isfinite(data).all() or (data <= -1).any():
        raise ConversionError("M6-3 returns cannot form drawdown")
    nav = np.concatenate(([1.0], np.cumprod(1.0 + data)))
    peak = np.maximum.accumulate(nav)
    return float(np.max(1.0 - nav / peak))


def _scenario(report: dict[str, np.ndarray], multiplier: float) -> tuple[np.ndarray, np.ndarray]:
    net = report["gross_return"] - multiplier * report["recorded_cost"]
    active = (1.0 + net) / (1.0 + report["benchmark_return"]) - 1.0
    if (net <= -1).any() or not np.isfinite(active).all():
        raise ConversionError("M6-3 cost scenario is invalid")
    return net, active


def _reports(case: dict[str, Any]) -> dict[str, dict[str, dict[str, dict[str, np.ndarray]]]]:
    raw = case.get("reports")
    if not isinstance(raw, dict) or set(raw) != set(TOPK_KEYS):
        raise ConversionError("M6-3 TopK report keys differ")
    output: dict[str, dict[str, dict[str, dict[str, np.ndarray]]]] = {}
    for topk in TOPK_KEYS:
        if not isinstance(raw[topk], dict) or set(raw[topk]) != set(WINDOWS):
            raise ConversionError("M6-3 report window order differs")
        output[topk] = {}
        for window in WINDOWS:
            values = raw[topk][window]
            if not isinstance(values, dict) or set(values) != set(ARMS):
                raise ConversionError("M6-3 report arm order differs")
            output[topk][window] = {
                arm: _report(values[arm], f"{topk}/{window}/{arm}") for arm in ARMS
            }
    if case.get("top30_reference") != raw["30"]:
        raise ConversionError("M6-3 Top30 replay differs from predecessor reference")
    for window in WINDOWS:
        control = output["30"][window][ARMS[0]]
        for topk in TOPK_KEYS:
            for arm in ARMS:
                value = output[topk][window][arm]
                if not np.array_equal(control["date"], value["date"]):
                    raise ConversionError("M6-3 paired report dates differ")
                if not np.array_equal(control["benchmark_return"], value["benchmark_return"]):
                    raise ConversionError("M6-3 paired benchmark returns differ")
    return output


def _stress(case: dict[str, Any]) -> dict[str, dict[str, dict[str, dict[str, np.ndarray]]]]:
    raw = case.get("stress_reports")
    if not isinstance(raw, dict) or set(raw) != set(TOPK_KEYS):
        raise ConversionError("M6-3 stress TopK keys differ")
    output: dict[str, dict[str, dict[str, dict[str, np.ndarray]]]] = {}
    for topk in TOPK_KEYS:
        if not isinstance(raw[topk], dict) or set(raw[topk]) != set(STRESS_PERIODS):
            raise ConversionError("M6-3 stress period order differs")
        output[topk] = {}
        for period in STRESS_PERIODS:
            values = raw[topk][period]
            if not isinstance(values, dict) or set(values) != set(ARMS):
                raise ConversionError("M6-3 stress arm order differs")
            output[topk][period] = {
                arm: _report(values[arm], f"{topk}/{period}/{arm}") for arm in ARMS
            }
    return output


def _name_overlap(case: dict[str, Any], arm: str) -> float:
    schedules = case.get("scheduled_names")
    if not isinstance(schedules, dict) or set(schedules) != set(TOPK_KEYS):
        raise ConversionError("M6-3 scheduled TopK keys differ")
    ratios: list[float] = []
    expected_dates: dict[str, tuple[str, ...]] = {}
    for topk in TOPK_KEYS:
        expected_count = int(topk)
        if not isinstance(schedules[topk], dict) or set(schedules[topk]) != set(WINDOWS):
            raise ConversionError("M6-3 scheduled windows differ")
        for window in WINDOWS:
            values = schedules[topk][window]
            if not isinstance(values, dict) or set(values) != set(ARMS):
                raise ConversionError("M6-3 scheduled arms differ")
            date_keys: tuple[str, ...] | None = None
            for schedule in values.values():
                if not isinstance(schedule, dict) or not schedule:
                    raise ConversionError("M6-3 scheduled date map differs")
                dates = tuple(schedule)
                if dates != tuple(sorted(set(dates))):
                    raise ConversionError("M6-3 scheduled dates differ")
                if date_keys is None:
                    date_keys = dates
                elif dates != date_keys:
                    raise ConversionError("M6-3 scheduled arm dates differ")
                for names in schedule.values():
                    if len(names) != expected_count or len(set(names)) != expected_count:
                        raise ConversionError("M6-3 scheduled set size or uniqueness differs")
                    if any(str(name).endswith(".BJ") for name in names):
                        raise ConversionError("M6-3 scheduled set contains .BJ")
            if date_keys is None:
                raise ConversionError("M6-3 scheduled dates are absent")
            if window in expected_dates and date_keys != expected_dates[window]:
                raise ConversionError("M6-3 scheduled TopK dates differ")
            expected_dates[window] = date_keys
            if topk == "20":
                for day in date_keys:
                    control = set(values[ARMS[0]][day])
                    ratios.append(len(control & set(values[arm][day])) / 20.0)
    return float(np.mean(ratios))


def _interaction(
    reports: dict[str, dict[str, dict[str, dict[str, np.ndarray]]]],
    arm: str,
) -> dict[str, Any]:
    daily: list[float] = []
    window_means: dict[str, float] = {}
    for window in WINDOWS:
        active: dict[tuple[str, str], np.ndarray] = {}
        for topk in TOPK_KEYS:
            for member in (ARMS[0], arm):
                _, values = _scenario(reports[topk][window][member], 1.0)
                active[(topk, member)] = values
        did = (active[("20", arm)] - active[("20", ARMS[0])]) - (
            active[("30", arm)] - active[("30", ARMS[0])]
        )
        window_means[window] = float(np.mean(did))
        daily.extend(did.tolist())
    return {
        "daily_count": len(daily),
        "daily_values": daily,
        "window_mean": window_means,
        "positive_windows": sum(value > 0 for value in window_means.values()),
        "pooled_mean": float(np.mean(daily)),
    }


def _direct(
    reports: dict[str, dict[str, dict[str, dict[str, np.ndarray]]]],
    stress: dict[str, dict[str, dict[str, dict[str, np.ndarray]]]],
    arm: str,
) -> dict[str, Any]:
    pooled_delta: dict[str, float] = {}
    window_delta: dict[str, float] = {}
    drawdowns: dict[str, float] = {}
    for scenario in SCENARIOS:
        control_pool: list[float] = []
        arm_pool: list[float] = []
        benchmark_pool: list[float] = []
        for window in WINDOWS:
            control = reports["20"][window][ARMS[0]]
            alternative = reports["20"][window][arm]
            control_net, _ = _scenario(control, float(scenario))
            arm_net, _ = _scenario(alternative, float(scenario))
            control_pool.extend(control_net.tolist())
            arm_pool.extend(arm_net.tolist())
            benchmark_pool.extend(control["benchmark_return"].tolist())
            if scenario == "1":
                benchmark_nav = 1.0 + _compound(control["benchmark_return"])
                window_delta[window] = float(
                    (1.0 + _compound(arm_net)) / benchmark_nav
                    - (1.0 + _compound(control_net)) / benchmark_nav
                )
                drawdowns[window] = _drawdown(arm_net)
        benchmark_nav = 1.0 + _compound(benchmark_pool)
        pooled_delta[scenario] = float(
            (1.0 + _compound(arm_pool)) / benchmark_nav
            - (1.0 + _compound(control_pool)) / benchmark_nav
        )
    for period in STRESS_PERIODS:
        net, _ = _scenario(stress["20"][period][arm], 1.0)
        drawdowns[period] = _drawdown(net)
    control_turnover = sum(
        float(reports["20"][window][ARMS[0]]["turnover"].sum()) for window in WINDOWS
    )
    arm_turnover = sum(
        float(reports["20"][window][arm]["turnover"].sum()) for window in WINDOWS
    )
    if control_turnover <= 0:
        raise ConversionError("M6-3 Top20 control turnover is non-positive")
    return {
        "base_window_net_excess_delta": window_delta,
        "positive_base_delta_windows": sum(value > 0 for value in window_delta.values()),
        "pooled_cost_delta": pooled_delta,
        "turnover_ratio": float(arm_turnover / control_turnover),
        "maximum_drawdown": max(drawdowns.values()),
        "drawdown_by_window_and_stress": drawdowns,
    }


def _decision(alternatives: dict[str, dict[str, Any]], *, blocked: bool) -> str:
    if blocked:
        return "BLOCKED"
    if any(row["conversion_supported"] for row in alternatives.values()):
        return "TOPK20_CONVERSION_SUPPORTED"
    if not any(row["interaction_pass"] for row in alternatives.values()) and not any(
        row["direct_pass"] for row in alternatives.values()
    ):
        return "TOPK20_CONVERSION_NOT_SUPPORTED"
    return "MIXED_NOT_CONCLUSIVE"


def evaluate_case(case: dict[str, Any], protocol: dict[str, Any]) -> dict[str, Any]:
    reports = _reports(case)
    stress = _stress(case)
    blocked_reasons = case.get("preflight_blocked_reasons", [])
    if not isinstance(blocked_reasons, list) or any(not isinstance(value, str) for value in blocked_reasons):
        raise ConversionError("M6-3 blocked reasons differ")
    if blocked_reasons:
        return {
            "blocked": True,
            "blocked_reasons": blocked_reasons,
            "alternatives": {},
            "decision": "BLOCKED",
        }
    interactions = {arm: _interaction(reports, arm) for arm in ALTERNATIVES}
    directs = {arm: _direct(reports, stress, arm) for arm in ALTERNATIVES}
    try:
        t_values = {
            arm: newey_west_mean_t(
                interactions[arm]["daily_values"],
                lags=int(protocol["primary_inference"]["hac_lags"]),
            )
            for arm in ALTERNATIVES
        }
        raw_p = {arm: one_sided_p_value(t_values[arm]) for arm in ALTERNATIVES}
        adjusted = holm_adjust(raw_p)
    except AttributionError as exc:
        raise ConversionError("M6-3 primary inference failed") from exc
    alpha = float(protocol["primary_inference"]["familywise_alpha"])
    interaction_gate = protocol["conversion_gate"]["interaction"]
    direct_gate = protocol["conversion_gate"]["top20_direct_vs_clean_control"]
    alternatives: dict[str, dict[str, Any]] = {}
    for arm in ALTERNATIVES:
        interaction = interactions[arm]
        direct = directs[arm]
        before_p = bool(
            interaction["pooled_mean"] > 0
            and interaction["positive_windows"]
            >= int(interaction_gate["minimum_positive_difference_in_differences_windows"])
        )
        interaction_pass = bool(before_p and adjusted[arm] <= alpha)
        direct_pass = bool(
            direct["pooled_cost_delta"]["1"] > 0
            and direct["positive_base_delta_windows"]
            >= int(direct_gate["minimum_positive_base_delta_windows"])
            and direct["pooled_cost_delta"]["1.5"] >= 0
            and direct["pooled_cost_delta"]["2"] >= 0
            and direct["turnover_ratio"]
            <= float(direct_gate["maximum_turnover_ratio_vs_top20_clean_control"])
            and direct["maximum_drawdown"]
            <= float(direct_gate["maximum_test_or_evaluable_stress_drawdown"])
        )
        alternatives[arm] = {
            "interaction": {key: value for key, value in interaction.items() if key != "daily_values"},
            "hac_t": t_values[arm],
            "raw_one_sided_p": raw_p[arm],
            "holm_adjusted_p": adjusted[arm],
            "interaction_before_primary_inference": before_p,
            "interaction_pass": interaction_pass,
            "direct_top20": direct,
            "direct_pass": direct_pass,
            "scheduled_top20_overlap_vs_clean_control": _name_overlap(case, arm),
            "conversion_supported": bool(interaction_pass and direct_pass),
        }
    decision = _decision(alternatives, blocked=False)
    return {
        "blocked": False,
        "blocked_reasons": [],
        "alternatives": alternatives,
        "decision": decision,
    }

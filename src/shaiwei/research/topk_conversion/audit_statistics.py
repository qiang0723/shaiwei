"""Independent M6-3 statistics with no primary execution or metric imports."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import norm

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


def _frame(rows: object, name: str) -> pd.DataFrame:
    if not isinstance(rows, list) or not rows:
        raise ConversionError(f"M6-3 audit {name} report is empty")
    if any(not isinstance(row, dict) or set(row) != set(REPORT_FIELDS) for row in rows):
        raise ConversionError(f"M6-3 audit {name} report fields differ")
    frame = pd.DataFrame(rows, columns=REPORT_FIELDS).set_index("date")
    if list(frame.index) != sorted(set(frame.index)):
        raise ConversionError(f"M6-3 audit {name} dates differ")
    for column in REPORT_FIELDS[1:]:
        frame[column] = pd.to_numeric(frame[column], errors="raise").astype(float)
    if not np.isfinite(frame.to_numpy()).all():
        raise ConversionError(f"M6-3 audit {name} report is nonfinite")
    if (frame[["gross_return", "benchmark_return"]] <= -1).any().any():
        raise ConversionError(f"M6-3 audit {name} report is not compoundable")
    if (frame[["recorded_cost", "turnover"]] < 0).any().any():
        raise ConversionError(f"M6-3 audit {name} cost or turnover is negative")
    return frame


def _all_reports(case: dict[str, Any]) -> dict[str, dict[str, dict[str, pd.DataFrame]]]:
    raw = case.get("reports")
    if not isinstance(raw, dict) or set(raw) != set(TOPK_KEYS):
        raise ConversionError("M6-3 audit TopK report keys differ")
    if case.get("top30_reference") != raw["30"]:
        raise ConversionError("M6-3 audit Top30 reference differs")
    output: dict[str, dict[str, dict[str, pd.DataFrame]]] = {}
    for topk in TOPK_KEYS:
        if set(raw[topk]) != set(WINDOWS):
            raise ConversionError("M6-3 audit window order differs")
        output[topk] = {}
        for window in WINDOWS:
            if set(raw[topk][window]) != set(ARMS):
                raise ConversionError("M6-3 audit arm order differs")
            output[topk][window] = {
                arm: _frame(raw[topk][window][arm], f"{topk}/{window}/{arm}") for arm in ARMS
            }
    for window in WINDOWS:
        reference = output["30"][window][ARMS[0]]
        for topk in TOPK_KEYS:
            for arm in ARMS:
                value = output[topk][window][arm]
                if not reference.index.equals(value.index):
                    raise ConversionError("M6-3 audit paired dates differ")
                if not reference["benchmark_return"].equals(value["benchmark_return"]):
                    raise ConversionError("M6-3 audit paired benchmark differs")
    return output


def _all_stress(case: dict[str, Any]) -> dict[str, dict[str, dict[str, pd.DataFrame]]]:
    raw = case.get("stress_reports")
    if not isinstance(raw, dict) or set(raw) != set(TOPK_KEYS):
        raise ConversionError("M6-3 audit stress TopK keys differ")
    output: dict[str, dict[str, dict[str, pd.DataFrame]]] = {}
    for topk in TOPK_KEYS:
        if set(raw[topk]) != set(STRESS_PERIODS):
            raise ConversionError("M6-3 audit stress periods differ")
        output[topk] = {}
        for period in STRESS_PERIODS:
            if set(raw[topk][period]) != set(ARMS):
                raise ConversionError("M6-3 audit stress arms differ")
            output[topk][period] = {
                arm: _frame(raw[topk][period][arm], f"{topk}/{period}/{arm}") for arm in ARMS
            }
    return output


def _net_active(frame: pd.DataFrame, multiplier: float) -> tuple[pd.Series, pd.Series]:
    net = frame["gross_return"] - multiplier * frame["recorded_cost"]
    active = (1.0 + net) / (1.0 + frame["benchmark_return"]) - 1.0
    if (net <= -1).any() or not np.isfinite(active.to_numpy()).all():
        raise ConversionError("M6-3 audit scenario is invalid")
    return net, active


def _compound(values: pd.Series | list[float]) -> float:
    data = np.asarray(values, dtype=float)
    if data.size == 0 or not np.isfinite(data).all() or (data <= -1).any():
        raise ConversionError("M6-3 audit returns cannot be compounded")
    return float(np.exp(np.log1p(data).sum()) - 1.0)


def _drawdown(values: pd.Series) -> float:
    nav = pd.concat([pd.Series([1.0]), (1.0 + values.reset_index(drop=True)).cumprod()])
    return float((1.0 - nav / nav.cummax()).max())


def _newey_west(values: list[float], lags: int) -> float:
    data = np.asarray(values, dtype=float)
    if data.ndim != 1 or len(data) <= lags or not np.isfinite(data).all():
        raise ConversionError("M6-3 audit HAC input is invalid")
    centered = data - data.mean()
    long_run = float(centered @ centered / len(data))
    for lag in range(1, lags + 1):
        covariance = float(centered[lag:] @ centered[:-lag] / len(data))
        long_run += 2.0 * (1.0 - lag / (lags + 1.0)) * covariance
    variance = long_run / len(data)
    if not math.isfinite(variance) or variance <= 0:
        raise ConversionError("M6-3 audit HAC variance is invalid")
    return float(data.mean() / math.sqrt(variance))


def _holm(raw: dict[str, float]) -> dict[str, float]:
    ordered = sorted(raw.items(), key=lambda item: (item[1], item[0]))
    if len(ordered) != 2:
        raise ConversionError("M6-3 audit Holm family differs")
    output: dict[str, float] = {}
    running = 0.0
    for index, (name, value) in enumerate(ordered):
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ConversionError("M6-3 audit Holm p-value is invalid")
        running = max(running, min(1.0, (2 - index) * value))
        output[name] = running
    return output


def _overlap(case: dict[str, Any], arm: str) -> float:
    schedules = case.get("scheduled_names")
    if not isinstance(schedules, dict) or set(schedules) != set(TOPK_KEYS):
        raise ConversionError("M6-3 audit schedules differ")
    ratios: list[float] = []
    expected_dates: dict[str, tuple[str, ...]] = {}
    for topk in TOPK_KEYS:
        if set(schedules[topk]) != set(WINDOWS):
            raise ConversionError("M6-3 audit schedule windows differ")
        count = int(topk)
        for window in WINDOWS:
            values = schedules[topk][window]
            if set(values) != set(ARMS):
                raise ConversionError("M6-3 audit schedule arms differ")
            date_keys: tuple[str, ...] | None = None
            for schedule in values.values():
                if not isinstance(schedule, dict) or not schedule:
                    raise ConversionError("M6-3 audit schedule date map differs")
                dates = tuple(schedule)
                if dates != tuple(sorted(set(dates))):
                    raise ConversionError("M6-3 audit schedule dates differ")
                if date_keys is None:
                    date_keys = dates
                elif dates != date_keys:
                    raise ConversionError("M6-3 audit schedule arm dates differ")
                for names in schedule.values():
                    if len(names) != count or len(set(names)) != count:
                        raise ConversionError("M6-3 audit schedule size differs")
                    if any(str(name).endswith(".BJ") for name in names):
                        raise ConversionError("M6-3 audit schedule contains .BJ")
            if date_keys is None:
                raise ConversionError("M6-3 audit schedule dates are absent")
            if window in expected_dates and date_keys != expected_dates[window]:
                raise ConversionError("M6-3 audit schedule TopK dates differ")
            expected_dates[window] = date_keys
            if topk == "20":
                ratios.extend(
                    len(set(values[ARMS[0]][day]) & set(values[arm][day])) / 20.0
                    for day in date_keys
                )
    return float(pd.Series(ratios).mean())


def _arm_evidence(
    reports: dict[str, dict[str, dict[str, pd.DataFrame]]],
    stress: dict[str, dict[str, dict[str, pd.DataFrame]]],
    arm: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    did_daily: list[float] = []
    did_windows: dict[str, float] = {}
    direct_windows: dict[str, float] = {}
    drawdowns: dict[str, float] = {}
    for window in WINDOWS:
        _, c20_active = _net_active(reports["20"][window][ARMS[0]], 1.0)
        _, a20_active = _net_active(reports["20"][window][arm], 1.0)
        _, c30_active = _net_active(reports["30"][window][ARMS[0]], 1.0)
        _, a30_active = _net_active(reports["30"][window][arm], 1.0)
        did = (a20_active - c20_active) - (a30_active - c30_active)
        did_windows[window] = float(did.mean())
        did_daily.extend(did.tolist())
        c20_net, _ = _net_active(reports["20"][window][ARMS[0]], 1.0)
        a20_net, _ = _net_active(reports["20"][window][arm], 1.0)
        benchmark_nav = 1.0 + _compound(reports["20"][window][ARMS[0]]["benchmark_return"])
        direct_windows[window] = float(
            (1.0 + _compound(a20_net)) / benchmark_nav
            - (1.0 + _compound(c20_net)) / benchmark_nav
        )
        drawdowns[window] = _drawdown(a20_net)
    pooled: dict[str, float] = {}
    for scenario in SCENARIOS:
        controls: list[float] = []
        alternatives: list[float] = []
        benchmarks: list[float] = []
        for window in WINDOWS:
            control_net, _ = _net_active(reports["20"][window][ARMS[0]], float(scenario))
            arm_net, _ = _net_active(reports["20"][window][arm], float(scenario))
            controls.extend(control_net.tolist())
            alternatives.extend(arm_net.tolist())
            benchmarks.extend(reports["20"][window][ARMS[0]]["benchmark_return"].tolist())
        benchmark_nav = 1.0 + _compound(benchmarks)
        pooled[scenario] = float(
            (1.0 + _compound(alternatives)) / benchmark_nav
            - (1.0 + _compound(controls)) / benchmark_nav
        )
    for period in STRESS_PERIODS:
        stress_net, _ = _net_active(stress["20"][period][arm], 1.0)
        drawdowns[period] = _drawdown(stress_net)
    control_turnover = sum(
        float(reports["20"][window][ARMS[0]]["turnover"].sum()) for window in WINDOWS
    )
    arm_turnover = sum(
        float(reports["20"][window][arm]["turnover"].sum()) for window in WINDOWS
    )
    interaction = {
        "daily_count": len(did_daily),
        "daily_values": did_daily,
        "window_mean": did_windows,
        "positive_windows": sum(value > 0 for value in did_windows.values()),
        "pooled_mean": float(pd.Series(did_daily).mean()),
    }
    direct = {
        "base_window_net_excess_delta": direct_windows,
        "positive_base_delta_windows": sum(value > 0 for value in direct_windows.values()),
        "pooled_cost_delta": pooled,
        "turnover_ratio": float(arm_turnover / control_turnover),
        "maximum_drawdown": max(drawdowns.values()),
        "drawdown_by_window_and_stress": drawdowns,
    }
    return interaction, direct


def independently_evaluate(case: dict[str, Any], protocol: dict[str, Any]) -> dict[str, Any]:
    reports = _all_reports(case)
    stress = _all_stress(case)
    reasons = case.get("preflight_blocked_reasons", [])
    if not isinstance(reasons, list) or any(not isinstance(value, str) for value in reasons):
        raise ConversionError("M6-3 audit blocked reasons differ")
    if reasons:
        return {"blocked": True, "blocked_reasons": reasons, "alternatives": {}, "decision": "BLOCKED"}
    evidence = {arm: _arm_evidence(reports, stress, arm) for arm in ALTERNATIVES}
    t_values = {
        arm: _newey_west(evidence[arm][0]["daily_values"], int(protocol["primary_inference"]["hac_lags"]))
        for arm in ALTERNATIVES
    }
    raw = {arm: float(norm.sf(t_values[arm])) for arm in ALTERNATIVES}
    adjusted = _holm(raw)
    alpha = float(protocol["primary_inference"]["familywise_alpha"])
    interaction_gate = protocol["conversion_gate"]["interaction"]
    direct_gate = protocol["conversion_gate"]["top20_direct_vs_clean_control"]
    alternatives: dict[str, dict[str, Any]] = {}
    for arm in ALTERNATIVES:
        interaction, direct = evidence[arm]
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
            "raw_one_sided_p": raw[arm],
            "holm_adjusted_p": adjusted[arm],
            "interaction_before_primary_inference": before_p,
            "interaction_pass": interaction_pass,
            "direct_top20": direct,
            "direct_pass": direct_pass,
            "scheduled_top20_overlap_vs_clean_control": _overlap(case, arm),
            "conversion_supported": bool(interaction_pass and direct_pass),
        }
    if any(row["conversion_supported"] for row in alternatives.values()):
        decision = "TOPK20_CONVERSION_SUPPORTED"
    elif not any(row["interaction_pass"] for row in alternatives.values()) and not any(
        row["direct_pass"] for row in alternatives.values()
    ):
        decision = "TOPK20_CONVERSION_NOT_SUPPORTED"
    else:
        decision = "MIXED_NOT_CONCLUSIVE"
    return {"blocked": False, "blocked_reasons": [], "alternatives": alternatives, "decision": decision}

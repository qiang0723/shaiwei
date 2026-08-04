"""M4-1 RankIC, corrected execution, multiplicity, and adapted effect gates."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from shaiwei.research.factor_portfolio import daily_rank_ic, icir
from shaiwei.research.g1 import periodic_sharpe
from shaiwei.research.g1_pipeline import _max_library_correlation
from shaiwei.research.star50_residual_effect.contract import ResidualEffectError
from tools.p2_star50_effect_correction.executor import ExecutionResult, execute_period


SCENARIOS = {
    "base": (1.0, 0.0),
    "cost_2x": (2.0, 0.0),
    "extra_10bp_each_side": (1.0, 0.001),
}


def ts_code_to_instrument(value: str) -> str:
    code = str(value)
    if len(code) == 9 and code[:6].isdigit() and code[6:] in {".SH", ".SZ"}:
        return f"{code[7:]}{code[:6]}"
    raise ResidualEffectError(f"unsupported M4-1 source code: {value}")


def as_series(frame: pd.DataFrame, value: str) -> pd.Series:
    required = {"trade_date", "ts_code", value}
    if missing := required - set(frame.columns):
        raise ResidualEffectError(f"M4-1 signal frame lacks {sorted(missing)}")
    selected = frame[["trade_date", "ts_code", value]].dropna().copy()
    if selected.empty or selected.duplicated(["trade_date", "ts_code"]).any():
        raise ResidualEffectError("M4-1 signal is empty or duplicated")
    selected["datetime"] = pd.to_datetime(selected["trade_date"], format="%Y%m%d")
    selected["instrument"] = selected["ts_code"].map(ts_code_to_instrument)
    result = selected.set_index(["datetime", "instrument"])[value]
    result.index = result.index.set_names(["datetime", "instrument"])
    return pd.to_numeric(result, errors="raise").astype(float).sort_index()


def label_series(labels: pd.DataFrame) -> pd.Series:
    return as_series(labels.rename(columns={"label": "value"}), "value").rename("label")


def blend_signal(baseline: pd.Series, factor: pd.Series, *, factor_weight: float) -> pd.Series:
    joined = pd.concat(
        [
            baseline.groupby(level=0).rank(pct=True).rename("baseline"),
            factor.groupby(level=0).rank(pct=True).rename("factor"),
        ],
        axis=1,
        join="inner",
    ).dropna()
    if joined.empty or not 0 < factor_weight < 1:
        raise ResidualEffectError("M4-1 baseline/factor blend is invalid")
    return ((1.0 - factor_weight) * joined["baseline"] + factor_weight * joined["factor"]).sort_index()


def _between(series: pd.Series, start: str, end: str) -> pd.Series:
    dates = series.index.get_level_values("datetime")
    return series.loc[(dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))]


def direction_evidence(
    core_panel: pd.DataFrame,
    labels: pd.DataFrame,
    protocol: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    start, end = protocol["feature_and_label_clock"]["discovery"]
    minimum = int(protocol["evaluation"]["minimum_daily_rank_ic_observations_discovery"])
    target = label_series(labels)
    result: dict[str, dict[str, Any]] = {}
    for spec in protocol["candidates"]:
        candidate = str(spec["candidate_id"])
        factor = as_series(core_panel, candidate)
        values = daily_rank_ic(_between(factor, start, end), _between(target, start, end))
        if len(values) < minimum:
            raise ResidualEffectError(f"{candidate} discovery RankIC observations are insufficient")
        mean = float(values.mean())
        passed = bool(math.isfinite(mean) and int(spec["orientation"]) * mean > 0)
        result[candidate] = {
            "mean_rank_ic": mean,
            "observation_count": int(len(values)),
            "direction_pass": passed,
        }
    return result


def execute_signal(
    signal: pd.Series,
    *,
    start: str,
    end: str,
    scenario: str,
    market: pd.DataFrame,
    members: pd.DataFrame,
    benchmark: pd.DataFrame,
    p2_protocol: dict[str, Any],
) -> ExecutionResult:
    multiplier, extra = SCENARIOS[scenario]
    return execute_period(
        predictions=signal,
        market=market,
        member_days=members,
        benchmark=benchmark,
        start=start,
        end=end,
        cost_multiplier=multiplier,
        extra_slippage_each_side=extra,
        protocol=p2_protocol,
    )


def daily_excess(frame: pd.DataFrame) -> pd.Series:
    strategy = pd.to_numeric(frame["daily_net_return"], errors="raise")
    benchmark = pd.to_numeric(frame["benchmark_return"], errors="raise")
    values = (1.0 + strategy) / (1.0 + benchmark) - 1.0
    if (strategy <= -1).any() or (benchmark <= -1).any() or not np.isfinite(values).all():
        raise ResidualEffectError("M4-1 daily excess return is invalid")
    return pd.Series(values.to_numpy(), index=frame["trade_date"].astype(str), dtype=float)


def compound(values: pd.Series) -> float:
    numeric = pd.to_numeric(values, errors="raise").astype(float)
    if numeric.empty or (numeric <= -1).any() or not np.isfinite(numeric).all():
        raise ResidualEffectError("M4-1 cannot compound invalid returns")
    return float((1.0 + numeric).prod() - 1.0)


def _prediction_for_window(predictions: dict[str, pd.DataFrame], alpha_window: str) -> pd.DataFrame:
    purpose = {"STAR-W1": "test_2023", "STAR-W2": "test_2024", "STAR-W3": "test_2025"}[
        alpha_window
    ]
    return predictions[purpose]


def evaluate_candidate(
    candidate: str,
    *,
    incremental_panel: pd.DataFrame,
    pressure_panels: dict[str, pd.DataFrame],
    labels: pd.DataFrame,
    predictions: dict[str, pd.DataFrame],
    market: pd.DataFrame,
    members: pd.DataFrame,
    benchmark: pd.DataFrame,
    protocol: dict[str, Any],
    p2_protocol: dict[str, Any],
    baseline_cache: dict[str, ExecutionResult],
    factor_library_root: Path,
) -> dict[str, Any]:
    target = label_series(labels)
    factor = as_series(incremental_panel, candidate)
    factor_ic = daily_rank_ic(factor, target)
    window_rank_ic: dict[str, float] = {}
    baseline_ic_parts: list[pd.Series] = []
    candidate_ic_parts: list[pd.Series] = []
    baseline_excess_parts: list[pd.Series] = []
    candidate_excess_parts: list[pd.Series] = []
    cost_2x_parts: list[pd.Series] = []
    extra_parts: list[pd.Series] = []
    baseline_turnover = 0.0
    candidate_turnover = 0.0
    window_rows: list[dict[str, Any]] = []
    return_rows: list[pd.DataFrame] = []
    ic_rows: list[pd.DataFrame] = []
    factor_weight = float(protocol["portfolio"]["candidate_weight"])
    minimum_window = int(protocol["evaluation"]["minimum_daily_rank_ic_observations_each_halfyear"])

    for window in protocol["evaluation"]["oos_windows"]:
        name, start, end = str(window["name"]), str(window["start"]), str(window["end"])
        baseline_frame = _prediction_for_window(predictions, str(window["alpha158_window"]))
        baseline = as_series(baseline_frame, "baseline_score")
        baseline = _between(baseline, start, end)
        window_factor = _between(factor, start, end)
        window_target = _between(target, start, end)
        blend = blend_signal(baseline, window_factor, factor_weight=factor_weight)
        raw_ic = daily_rank_ic(window_factor, window_target)
        baseline_ic = daily_rank_ic(baseline, window_target)
        candidate_ic = daily_rank_ic(blend, window_target)
        if min(len(raw_ic), len(baseline_ic), len(candidate_ic)) < minimum_window:
            raise ResidualEffectError(f"M4-1 {candidate}/{name} has insufficient RankIC days")
        window_rank_ic[name] = float(raw_ic.mean())
        baseline_ic_parts.append(baseline_ic)
        candidate_ic_parts.append(candidate_ic)

        if name not in baseline_cache:
            baseline_cache[name] = execute_signal(
                baseline,
                start=start,
                end=end,
                scenario="base",
                market=market,
                members=members,
                benchmark=benchmark,
                p2_protocol=p2_protocol,
            )
        baseline_execution = baseline_cache[name]
        executions = {
            scenario: execute_signal(
                blend,
                start=start,
                end=end,
                scenario=scenario,
                market=market,
                members=members,
                benchmark=benchmark,
                p2_protocol=p2_protocol,
            )
            for scenario in SCENARIOS
        }
        baseline_excess = daily_excess(baseline_execution.daily)
        candidate_excess = daily_excess(executions["base"].daily)
        baseline_excess_parts.append(baseline_excess)
        candidate_excess_parts.append(candidate_excess)
        cost_2x_parts.append(daily_excess(executions["cost_2x"].daily))
        extra_parts.append(daily_excess(executions["extra_10bp_each_side"].daily))
        baseline_turnover += float(baseline_execution.metrics["turnover_notional"])
        candidate_turnover += float(executions["base"].metrics["turnover_notional"])
        window_rows.append(
            {
                "window": name,
                "factor_rank_ic": window_rank_ic[name],
                "baseline_net_excess": compound(baseline_excess),
                "candidate_net_excess": compound(candidate_excess),
                "candidate_cost_2x_net_excess": compound(cost_2x_parts[-1]),
                "candidate_extra_10bp_net_excess": compound(extra_parts[-1]),
                "baseline_turnover_notional": float(
                    baseline_execution.metrics["turnover_notional"]
                ),
                "candidate_turnover_notional": float(
                    executions["base"].metrics["turnover_notional"]
                ),
            }
        )
        for scenario, execution in executions.items():
            frame = execution.daily.copy()
            frame.insert(0, "scenario", scenario)
            frame.insert(0, "window", name)
            frame.insert(0, "candidate", candidate)
            return_rows.append(frame)
        for series_type, values in (
            ("factor", raw_ic),
            ("baseline", baseline_ic),
            ("augmented", candidate_ic),
        ):
            frame = values.rename("rank_ic").reset_index()
            frame.columns = ["trade_date", "rank_ic"]
            frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.strftime("%Y%m%d")
            frame.insert(0, "series_type", series_type)
            frame.insert(0, "window", name)
            frame.insert(0, "candidate", candidate)
            ic_rows.append(frame)

    stress: dict[str, float] = {}
    for period in protocol["evaluation"]["pressure_periods"]:
        name = str(period["name"])
        pressure_factor = as_series(pressure_panels[name], candidate)
        execution = execute_signal(
            pressure_factor,
            start=str(period["start"]),
            end=str(period["end"]),
            scenario="base",
            market=market,
            members=members,
            benchmark=benchmark,
            p2_protocol=p2_protocol,
        )
        stress[name] = float(execution.metrics["maximum_drawdown"])

    baseline_ic_all = pd.concat(baseline_ic_parts).sort_index()
    candidate_ic_all = pd.concat(candidate_ic_parts).sort_index()
    factor_ic_oos = pd.concat(
        [
            _between(factor_ic, str(window["start"]), str(window["end"]))
            for window in protocol["evaluation"]["oos_windows"]
        ]
    ).sort_index()
    baseline_excess_all = pd.concat(baseline_excess_parts)
    candidate_excess_all = pd.concat(candidate_excess_parts)
    cost_2x_all = pd.concat(cost_2x_parts)
    extra_all = pd.concat(extra_parts)
    return {
        "candidate": candidate,
        "oos_window_rank_ic": window_rank_ic,
        "daily_oos_rank_ic": factor_ic_oos.tolist(),
        "stress_max_drawdown": stress,
        "baseline_turnover": baseline_turnover,
        "candidate_turnover": candidate_turnover,
        "baseline_net_icir": float(icir(baseline_ic_all)),
        "candidate_net_icir": float(icir(candidate_ic_all)),
        "baseline_net_excess": compound(baseline_excess_all),
        "candidate_net_excess": compound(candidate_excess_all),
        "cost_2x_net_excess": compound(cost_2x_all),
        "extra_10bp_net_excess": compound(extra_all),
        "selection_sharpe": periodic_sharpe(candidate_excess_all.tolist(), minimum=252),
        "daily_net_excess_returns": candidate_excess_all.tolist(),
        "max_library_abs_spearman": _max_library_correlation(factor, factor_library_root),
        "window_metrics": window_rows,
        "return_rows": pd.concat(return_rows, ignore_index=True),
        "ic_rows": pd.concat(ic_rows, ignore_index=True),
    }


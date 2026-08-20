"""Primary frozen G0 and diagnostic calculations for production Head30."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from shaiwei.research.production_conversion.contract import ProtocolError


WINDOWS = ("W1", "W2", "W3", "W4", "W5", "W6")
SCENARIOS = ("1", "1.5", "2")


def _compound(values: list[float]) -> float:
    array = np.asarray(values, dtype=float)
    if not len(array) or not np.isfinite(array).all() or (array <= -1).any():
        raise ProtocolError("production-converter return stream is invalid")
    return float(np.prod(1.0 + array) - 1.0)


def _drawdown(values: list[float]) -> float:
    nav = np.cumprod(1.0 + np.asarray(values, dtype=float))
    nav = np.concatenate(([1.0], nav))
    return float(np.max(1.0 - nav / np.maximum.accumulate(nav)))


def _scenario(rows: list[dict[str, Any]], multiplier: float) -> dict[str, Any]:
    gross = [float(row["gross_return"]) for row in rows]
    benchmark = [float(row["benchmark_return"]) for row in rows]
    cost = [float(row["recorded_cost"]) for row in rows]
    net = [value - multiplier * charge for value, charge in zip(gross, cost, strict=True)]
    active = [
        (1.0 + value) / (1.0 + base) - 1.0
        for value, base in zip(net, benchmark, strict=True)
    ]
    return {
        "strategy_return": _compound(net),
        "benchmark_return": _compound(benchmark),
        "cumulative_excess": (1.0 + _compound(net)) / (1.0 + _compound(benchmark)) - 1.0,
        "reported_cost_sum": float(multiplier * sum(cost)),
        "daily_active_return": active,
    }


def evaluate(
    treatments: dict[str, dict[str, Any]], controls: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    if tuple(treatments) != WINDOWS or tuple(controls) != WINDOWS:
        raise ProtocolError("production-converter window set differs")
    windows: dict[str, Any] = {}
    combined: dict[str, float] = {}
    pooled: dict[str, list[float]] = {key: [] for key in SCENARIOS}
    control_delta: list[float] = []
    for window in WINDOWS:
        treatment_rows, control_rows = treatments[window]["daily"], controls[window]
        if [row["date"] for row in treatment_rows] != [row["date"] for row in control_rows]:
            raise ProtocolError("production-converter paired report dates differ")
        scenarios = {
            key: _scenario(treatment_rows, float(key)) for key in SCENARIOS
        }
        control_base = _scenario(control_rows, 1.0)
        control_delta.extend(
            left - right
            for left, right in zip(
                scenarios["1"]["daily_active_return"],
                control_base["daily_active_return"],
                strict=True,
            )
        )
        for key in SCENARIOS:
            pooled[key].append(float(scenarios[key]["cumulative_excess"]))
        positions = treatments[window]["positions"]
        rebalances = treatments[window]["rebalances"]
        net = [
            float(row["gross_return"]) - float(row["recorded_cost"])
            for row in treatment_rows
        ]
        windows[window] = {
            "row_count": len(treatment_rows),
            "cost_scenarios": scenarios,
            "maximum_drawdown": _drawdown(net),
            "turnover_sum": float(sum(float(row["turnover"]) for row in treatment_rows)),
            "recorded_cost_sum": float(
                sum(float(row["recorded_cost"]) for row in treatment_rows)
            ),
            "target_name_replacement_count": int(
                sum(int(row["replacement_count"]) for row in rebalances)
            ),
            "retained_name_reweight_notional": float(
                sum(float(row["retained_reweight_notional"]) for row in rebalances)
            ),
            "realized_position_count_mean": float(
                sum(int(row["position_count"]) for row in positions) / len(positions)
            ),
            "cash_ratio_mean": float(
                sum(float(row["cash_ratio"]) for row in positions) / len(positions)
            ),
        }
    for key in SCENARIOS:
        combined[key] = float(math.prod(1.0 + value for value in pooled[key]) - 1.0)
    positive = sum(
        windows[window]["cost_scenarios"]["1"]["cumulative_excess"] > 0
        for window in WINDOWS
    )
    gate = {
        "window_count": 6,
        "positive_base_cost_excess_windows": positive,
        "combined_cumulative_excess": combined,
        "window_condition_pass": positive >= 4,
        "cost_1_5_condition_pass": combined["1.5"] >= 0,
    }
    gate["pass"] = bool(gate["window_condition_pass"] and gate["cost_1_5_condition_pass"])
    return {
        "windows": windows,
        "g0": gate,
        "control_vs_treatment_daily_active_return_delta": control_delta,
        "decision": "VALIDATED_RESEARCH_SCALE" if gate["pass"] else "REJECTED_RESEARCH_SCALE",
        "production_authorization": "none",
    }


__all__ = ["SCENARIOS", "WINDOWS", "evaluate"]

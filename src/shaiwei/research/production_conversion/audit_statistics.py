"""Independent Head30 reconstruction; deliberately imports no primary calculation code."""

from __future__ import annotations

import math
from typing import Any

import numpy as np


WINDOWS = ("W1", "W2", "W3", "W4", "W5", "W6")
SCENARIOS = ("1", "1.5", "2")


def _compound(values: list[float]) -> float:
    return float(np.prod(1.0 + np.asarray(values, dtype=float)) - 1.0)


def _drawdown(values: list[float]) -> float:
    nav = np.concatenate(([1.0], np.cumprod(1.0 + np.asarray(values, dtype=float))))
    return float(np.max(1.0 - nav / np.maximum.accumulate(nav)))


def independently_evaluate(bundle: dict[str, Any]) -> dict[str, Any]:
    treatments = bundle["treatments"]
    control_active = bundle["control_base_daily_active_return"]
    windows: dict[str, Any] = {}
    pooled: dict[str, list[float]] = {key: [] for key in SCENARIOS}
    delta: list[float] = []
    for window in WINDOWS:
        rows = treatments[window]["daily"]
        scenarios: dict[str, Any] = {}
        for key in SCENARIOS:
            multiplier = float(key)
            net = [float(row["gross_return"]) - multiplier * float(row["recorded_cost"]) for row in rows]
            benchmark = [float(row["benchmark_return"]) for row in rows]
            active = [(1.0 + value) / (1.0 + base) - 1.0 for value, base in zip(net, benchmark, strict=True)]
            excess = (1.0 + _compound(net)) / (1.0 + _compound(benchmark)) - 1.0
            scenarios[key] = {
                "strategy_return": _compound(net), "benchmark_return": _compound(benchmark),
                "cumulative_excess": excess,
                "reported_cost_sum": float(multiplier * sum(float(row["recorded_cost"]) for row in rows)),
                "daily_active_return": active,
            }
            pooled[key].append(excess)
        delta.extend(left - right for left, right in zip(scenarios["1"]["daily_active_return"], control_active[window], strict=True))
        rebalances, positions = treatments[window]["rebalances"], treatments[window]["positions"]
        windows[window] = {
            "row_count": len(rows), "cost_scenarios": scenarios,
            "maximum_drawdown": _drawdown([float(row["gross_return"]) - float(row["recorded_cost"]) for row in rows]),
            "turnover_sum": float(sum(float(row["turnover"]) for row in rows)),
            "recorded_cost_sum": float(sum(float(row["recorded_cost"]) for row in rows)),
            "target_name_replacement_count": int(sum(int(row["replacement_count"]) for row in rebalances)),
            "retained_name_reweight_notional": float(sum(float(row["retained_reweight_notional"]) for row in rebalances)),
            "realized_position_count_mean": float(sum(int(row["position_count"]) for row in positions) / len(positions)),
            "cash_ratio_mean": float(sum(float(row["cash_ratio"]) for row in positions) / len(positions)),
        }
    combined = {key: float(math.prod(1.0 + value for value in pooled[key]) - 1.0) for key in SCENARIOS}
    positive = sum(windows[window]["cost_scenarios"]["1"]["cumulative_excess"] > 0 for window in WINDOWS)
    gate = {
        "window_count": 6, "positive_base_cost_excess_windows": positive,
        "combined_cumulative_excess": combined, "window_condition_pass": positive >= 4,
        "cost_1_5_condition_pass": combined["1.5"] >= 0,
    }
    gate["pass"] = bool(gate["window_condition_pass"] and gate["cost_1_5_condition_pass"])
    return {
        "windows": windows, "g0": gate,
        "control_vs_treatment_daily_active_return_delta": delta,
        "decision": "VALIDATED_RESEARCH_SCALE" if gate["pass"] else "REJECTED_RESEARCH_SCALE",
        "production_authorization": "none",
    }


__all__ = ["independently_evaluate"]

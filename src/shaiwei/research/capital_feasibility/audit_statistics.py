"""Independent artifact-only reconstruction of M6-5B frozen gates."""

from __future__ import annotations

import math
from statistics import median
from typing import Any


WINDOWS = ("W1", "W2", "W3", "W4", "W5", "W6")


def independently_evaluate(bundle: dict[str, Any]) -> dict[str, Any]:
    windows = bundle["windows"]
    if tuple(windows) != WINDOWS:
        raise ValueError("independent M6-5B window set differs")
    rows = [row for window in windows.values() for row in window["rebalances"]]
    positions = [int(row["position_count"]) for row in rows]
    cash = [float(row["cash_ratio"]) for row in rows]
    l1 = [float(row["target_l1_error"]) for row in rows]
    output_windows: dict[str, Any] = {}
    bases: list[float] = []
    costs: list[float] = []
    ideals: list[float] = []
    for name, window in windows.items():
        daily = window["daily"]
        base = float(daily[-1]["normalized_nav"])
        benchmark = float(daily[-1]["benchmark_nav"])
        cost = float(daily[-1]["cost_1_5_nav"])
        ideal = math.prod(
            1.0 + float(row["gross_return"]) - float(row["recorded_cost"])
            for row in window["ideal_daily"]
        )
        output_windows[name] = {
            "row_count": len(daily), "rebalance_count": len(window["rebalances"]),
            "base_final_nav": base, "cost_1_5_final_nav": cost,
            "benchmark_final_nav": benchmark, "base_net_excess": base / benchmark - 1.0,
            "cost_1_5_net_excess": cost / benchmark - 1.0,
            "maximum_drawdown": max(-float(row["drawdown"]) for row in daily),
            "ideal_final_nav": ideal,
        }
        bases.append(base)
        costs.append(cost / benchmark)
        ideals.append(ideal)
    rejected = sum(int(row["minimum_lot_rejection_count"]) for row in rows)
    legs = sum(int(row["target_buy_leg_count"]) for row in rows)
    diagnostics = {
        "median_positions": median(positions), "minimum_positions": min(positions),
        "median_cash_ratio": median(cash), "maximum_cash_ratio": max(cash),
        "median_target_l1": median(l1), "maximum_target_l1": max(l1),
        "minimum_lot_rejection_fraction": rejected / legs,
        "capacity_violation_count": sum(int(row["capacity_violation_count"]) for row in rows),
        "invalid_lot_fill_count": sum(int(row["invalid_lot_fill_count"]) for row in rows),
        "accounting_violation_count": sum(abs(float(row["accounting_difference"])) > 0.01 for row in rows),
        "negative_cash_count": sum(bool(row["negative_cash"]) for row in rows),
        "positive_window_count": sum(row["base_net_excess"] > 0 for row in output_windows.values()),
        "combined_1_5x_net_excess": math.prod(costs) - 1.0,
        "executable_to_ideal_pooled_nav_ratio": math.prod(bases) / math.prod(ideals),
    }
    checks = {
        "all_six_windows_complete": len(output_windows) == 6,
        "accounting": diagnostics["accounting_violation_count"] == 0,
        "nonnegative_cash": diagnostics["negative_cash_count"] == 0,
        "valid_lots": diagnostics["invalid_lot_fill_count"] == 0,
        "capacity": diagnostics["capacity_violation_count"] == 0,
        "median_positions": diagnostics["median_positions"] >= 24,
        "minimum_positions": diagnostics["minimum_positions"] >= 20,
        "median_cash_ratio": diagnostics["median_cash_ratio"] <= 0.20,
        "maximum_cash_ratio": diagnostics["maximum_cash_ratio"] <= 0.35,
        "median_target_l1": diagnostics["median_target_l1"] <= 0.30,
        "maximum_target_l1": diagnostics["maximum_target_l1"] <= 0.50,
        "minimum_lot_rejections": diagnostics["minimum_lot_rejection_fraction"] <= 0.20,
        "positive_windows": diagnostics["positive_window_count"] >= 4,
        "combined_1_5x": diagnostics["combined_1_5x_net_excess"] > 0.0,
        "pooled_nav_ratio": diagnostics["executable_to_ideal_pooled_nav_ratio"] >= 0.95,
    }
    return {
        "windows": output_windows, "diagnostics": diagnostics, "checks": checks,
        "decision": "CAPITAL_FEASIBLE_RESEARCH_ONLY" if all(checks.values()) else "CAPITAL_INFEASIBLE",
        "production_authorization": "none",
    }

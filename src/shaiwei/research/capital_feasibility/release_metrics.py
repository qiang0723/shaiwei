"""Primary frozen M6-5B feasibility and effect-retention calculations."""

from __future__ import annotations

import math
from statistics import median
from typing import Any

from shaiwei.research.production_conversion.contract import ProtocolError


WINDOWS = ("W1", "W2", "W3", "W4", "W5", "W6")


def _ideal_final(rows: list[dict[str, Any]]) -> float:
    return math.prod(
        1.0 + float(row["gross_return"]) - float(row["recorded_cost"])
        for row in rows
    )


def evaluate(pass_bundle: dict[str, Any]) -> dict[str, Any]:
    windows = pass_bundle.get("windows", {})
    if tuple(windows) != WINDOWS:
        raise ProtocolError("M6-5B complete window set is absent")
    rebalances = [row for window in windows.values() for row in window["rebalances"]]
    if not rebalances:
        raise ProtocolError("M6-5B rebalance evidence is absent")
    position_counts = [row["position_count"] for row in rebalances]
    cash_ratios = [row["cash_ratio"] for row in rebalances]
    l1_errors = [row["target_l1_error"] for row in rebalances]
    lot_rejections = sum(row["minimum_lot_rejection_count"] for row in rebalances)
    target_legs = sum(row["target_buy_leg_count"] for row in rebalances)
    window_metrics: dict[str, Any] = {}
    base_finals, cost_finals, ideal_finals = [], [], []
    for name, window in windows.items():
        daily = window["daily"]
        if not daily:
            raise ProtocolError(f"M6-5B window daily path is absent: {name}")
        base, cost, benchmark = daily[-1]["normalized_nav"], daily[-1]["cost_1_5_nav"], daily[-1]["benchmark_nav"]
        ideal = _ideal_final(window["ideal_daily"])
        window_metrics[name] = {
            "row_count": len(daily), "rebalance_count": len(window["rebalances"]),
            "base_final_nav": base, "cost_1_5_final_nav": cost,
            "benchmark_final_nav": benchmark, "base_net_excess": base / benchmark - 1.0,
            "cost_1_5_net_excess": cost / benchmark - 1.0,
            "maximum_drawdown": max(-float(row["drawdown"]) for row in daily),
            "ideal_final_nav": ideal,
        }
        base_finals.append(base)
        cost_finals.append(cost / benchmark)
        ideal_finals.append(ideal)
    diagnostics = {
        "median_positions": median(position_counts), "minimum_positions": min(position_counts),
        "median_cash_ratio": median(cash_ratios), "maximum_cash_ratio": max(cash_ratios),
        "median_target_l1": median(l1_errors), "maximum_target_l1": max(l1_errors),
        "minimum_lot_rejection_fraction": lot_rejections / target_legs,
        "capacity_violation_count": sum(row["capacity_violation_count"] for row in rebalances),
        "invalid_lot_fill_count": sum(row["invalid_lot_fill_count"] for row in rebalances),
        "accounting_violation_count": sum(abs(row["accounting_difference"]) > 0.01 for row in rebalances),
        "negative_cash_count": sum(row["negative_cash"] for row in rebalances),
        "positive_window_count": sum(row["base_net_excess"] > 0 for row in window_metrics.values()),
        "combined_1_5x_net_excess": math.prod(cost_finals) - 1.0,
        "executable_to_ideal_pooled_nav_ratio": math.prod(base_finals) / math.prod(ideal_finals),
    }
    checks = {
        "all_six_windows_complete": len(window_metrics) == 6,
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
        "windows": window_metrics, "diagnostics": diagnostics, "checks": checks,
        "decision": "CAPITAL_FEASIBLE_RESEARCH_ONLY" if all(checks.values()) else "CAPITAL_INFEASIBLE",
        "production_authorization": "none",
    }

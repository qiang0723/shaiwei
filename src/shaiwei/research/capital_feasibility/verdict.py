"""Frozen M6-5A feasibility and effect-retention verdict."""

from __future__ import annotations

from statistics import median
from typing import Any

from .contract import Gates


def evaluate(records: list[dict[str, Any]], effect: dict[str, Any], gates: Gates = Gates()) -> dict:
    if not records:
        return {"decision": "BLOCKED", "checks": {"records_present": False}}
    positions = [row["realized_position_count"] for row in records]
    cash = [row["cash_ratio"] for row in records]
    l1 = [row["target_l1_error"] for row in records]
    rejected = sum(row["minimum_lot_rejection_count"] for row in records)
    legs = sum(row["target_buy_leg_count"] for row in records)
    checks = {
        "accounting": all(abs(float(row["accounting_difference"])) <= 0.01 for row in records),
        "nonnegative_cash": not any(row["negative_cash"] for row in records),
        "valid_lots": sum(row["invalid_lot_fill_count"] for row in records) == 0,
        "capacity": sum(row["capacity_violation_count"] for row in records) == 0,
        "median_positions": median(positions) >= gates.median_positions_minimum,
        "minimum_positions": min(positions) >= gates.minimum_positions,
        "median_cash_ratio": median(cash) <= gates.median_cash_ratio_maximum,
        "maximum_cash_ratio": max(cash) <= gates.maximum_cash_ratio,
        "median_target_l1": median(l1) <= gates.median_l1_maximum,
        "maximum_target_l1": max(l1) <= gates.maximum_l1,
        "minimum_lot_rejections": rejected / legs <= gates.minimum_lot_rejection_fraction_maximum,
        "positive_windows": effect.get("positive_window_count", -1) >= gates.positive_windows_minimum,
        "combined_1_5x": effect.get("combined_1_5x_net_excess", -1.0) > 0.0,
        "pooled_nav_ratio": effect.get("executable_to_ideal_pooled_nav_ratio", -1.0) >= gates.pooled_nav_ratio_minimum,
    }
    return {
        "decision": "CAPITAL_FEASIBLE_RESEARCH_ONLY" if all(checks.values()) else "CAPITAL_INFEASIBLE",
        "checks": checks,
        "diagnostics": {
            "median_positions": median(positions), "minimum_positions": min(positions),
            "median_cash_ratio": median(cash), "maximum_cash_ratio": max(cash),
            "median_target_l1": median(l1), "maximum_target_l1": max(l1),
            "minimum_lot_rejection_fraction": rejected / legs,
        },
        "production_authorization": "none",
    }

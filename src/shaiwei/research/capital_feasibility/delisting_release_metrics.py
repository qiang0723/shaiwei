"""Frozen M6-5B gates plus the M6-5C risk-exit capacity boundary."""

from __future__ import annotations

from typing import Any

from .release_metrics import evaluate as evaluate_capital


def evaluate(bundle: dict[str, Any]) -> dict[str, Any]:
    capital = evaluate_capital(bundle)
    risk_capacity_violations = sum(
        row["violation"]
        for window in bundle["windows"].values()
        for trace in window["risk_trace"]
        for row in trace["risk_capacity"]
    )
    risk_order_count = sum(
        len(trace["risk_orders"])
        for window in bundle["windows"].values()
        for trace in window["risk_trace"]
    )
    risk_fill_count = sum(
        order.get("status") == "FILLED"
        for window in bundle["windows"].values()
        for trace in window["risk_trace"]
        for order in trace["risk_orders"]
    )
    checks = dict(capital["checks"])
    checks["risk_exit_capacity"] = risk_capacity_violations == 0
    passed = all(checks.values())
    return {
        **capital,
        "checks": checks,
        "risk_exit": {
            "order_count": risk_order_count,
            "fill_count": risk_fill_count,
            "capacity_violation_count": risk_capacity_violations,
        },
        "capital_decision": capital["decision"],
        "decision": (
            "RECOVERY_DIAGNOSTIC_PASSES_FROZEN_CAPITAL_GATES"
            if passed
            else "RECOVERY_DIAGNOSTIC_FAILS_FROZEN_CAPITAL_GATES"
        ),
        "strategy_effectiveness_authority": "NOT_FOR_PRODUCTION_VERDICT",
        "production_authorization": "none",
    }

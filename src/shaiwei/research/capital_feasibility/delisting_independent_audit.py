"""Independent artifact-only reconstruction of M6-5C risk decisions and gates."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from shaiwei.research.production_conversion.contract import ProtocolError

from .audit_statistics import independently_evaluate as independently_evaluate_capital


TRIGGER = Decimal("1.0")
SESSIONS = 10
TARGET_WEIGHT = Decimal(1) / Decimal(30)
REASON = "CONSECUTIVE_CLOSES_STRICTLY_BELOW_ONE_YUAN"


def _trigger(
    observations: list[dict[str, object]], code: str, as_of: str
) -> dict[str, object] | None:
    rows = sorted(
        (
            (str(row["trade_date"]), Decimal(str(row["close"])))
            for row in observations
            if row["ts_code"] == code and str(row["trade_date"]) <= as_of
        ),
        key=lambda item: item[0],
    )
    if any(not close.is_finite() or close <= 0 for _, close in rows):
        raise ProtocolError("M6-5C independent risk close is invalid")
    streak: list[tuple[str, Decimal]] = []
    for trade_date, close in rows:
        streak = [*streak, (trade_date, close)] if close < TRIGGER else []
    if len(streak) < SESSIONS:
        return None
    evidence = streak[-SESSIONS:]
    return {
        "ts_code": code,
        "state": "",
        "triggered_as_of": as_of,
        "trade_dates": [day for day, _ in evidence],
        "closes": [str(close) for _, close in evidence],
        "reason_code": REASON,
    }


def _expected_decision(
    *,
    observations: list[dict[str, object]],
    as_of: str,
    targets: list[str],
    held: list[str],
    prior: dict[str, dict[str, object]],
) -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    relevant = set(targets) | set(held) | set(prior)
    active = {
        code: trigger
        for code in sorted(relevant)
        if (trigger := _trigger(observations, code, as_of)) is not None
    }
    held_set = set(held)
    disposed = sorted(set(prior) - held_set)
    latches = {
        code: prior[code] if code in prior else active[code]
        for code in sorted(held_set & (set(prior) | set(active)))
    }
    forced = sorted(latches)
    blocked = [code for code in targets if code in active and code not in held_set]
    excluded = set(blocked) | (set(forced) & set(targets))
    eligible = [code for code in targets if code not in excluded]
    evidence: list[dict[str, object]] = []
    for code in disposed:
        evidence.append({**prior[code], "state": "DISPOSED"})
    for code in sorted(set(blocked) | set(forced)):
        trigger = latches.get(code, active[code])
        evidence.append(
            {
                **trigger,
                "state": "EXIT_LATCHED" if code in latches else "BUY_BLOCKED",
            }
        )
    next_latches = [
        {**latches[code], "state": "EXIT_LATCHED"} for code in sorted(latches)
    ]
    return (
        {
            "as_of": as_of,
            "blocked_buy_codes": blocked,
            "forced_exit_codes": forced,
            "disposed_codes": disposed,
            "eligible_target_codes": eligible,
            "cash_reserve_weight": str(TARGET_WEIGHT * len(excluded)),
            "evidence": evidence,
            "next_state": {"exit_latches": next_latches},
        },
        {code: latches[code] for code in sorted(latches)},
    )


def _audit_window(window: dict[str, Any]) -> dict[str, int]:
    observations = window["risk_observations"]
    keys = [(str(row["ts_code"]), str(row["trade_date"])) for row in observations]
    if (
        len(keys) != len(set(keys))
        or keys != sorted(keys, key=lambda item: (item[1], item[0]))
        or any(code.endswith(".BJ") for code, _ in keys)
    ):
        raise ProtocolError("M6-5C independent risk observations differ")
    open_dates = [str(value) for value in window["official_open_dates"]]
    if open_dates != sorted(set(open_dates)):
        raise ProtocolError("M6-5C independent calendar differs")
    prior: dict[str, dict[str, object]] = {}
    order_count = 0
    fill_count = 0
    capacity_violations = 0
    previous_execution = ""
    for trace in window["risk_trace"]:
        execution = str(trace["execution_date"])
        as_of = str(trace["as_of"])
        expected_as_of = max(day for day in open_dates if day < execution)
        if as_of != expected_as_of or execution <= previous_execution:
            raise ProtocolError("M6-5C independent risk clock differs")
        previous_execution = execution
        expected, prior = _expected_decision(
            observations=observations,
            as_of=as_of,
            targets=[str(code) for code in trace["target_codes"]],
            held=[str(code) for code in trace["held_before"]],
            prior=prior,
        )
        if trace["decision"] != expected:
            raise ProtocolError("M6-5C independent risk decision differs")
        forced = set(expected["forced_exit_codes"])
        orders = trace["risk_orders"]
        if {str(row["ts_code"]) for row in orders} != forced or any(
            row.get("execution_reason") != "DELISTING_PRICE_RISK_EXIT" for row in orders
        ):
            raise ProtocolError("M6-5C independent risk order set differs")
        held_after = set(str(code) for code in trace["held_after"])
        for order in orders:
            code = str(order["ts_code"])
            if (order["status"] == "FILLED") != (code not in held_after):
                raise ProtocolError("M6-5C independent risk exit state differs")
        for row in trace["risk_capacity"]:
            expected_violation = float(row["order_notional_rmb"]) > float(row["limit_rmb"])
            if bool(row["violation"]) != expected_violation:
                raise ProtocolError("M6-5C independent risk capacity differs")
            capacity_violations += int(expected_violation)
        order_count += len(orders)
        fill_count += sum(order["status"] == "FILLED" for order in orders)
    return {
        "order_count": order_count,
        "fill_count": fill_count,
        "capacity_violation_count": capacity_violations,
    }


def independently_evaluate(bundle: dict[str, Any]) -> dict[str, Any]:
    capital = independently_evaluate_capital(bundle)
    risk_rows = [_audit_window(window) for window in bundle["windows"].values()]
    risk = {
        key: sum(row[key] for row in risk_rows)
        for key in ("order_count", "fill_count", "capacity_violation_count")
    }
    checks = dict(capital["checks"])
    checks["risk_exit_capacity"] = risk["capacity_violation_count"] == 0
    passed = all(checks.values())
    return {
        **capital,
        "checks": checks,
        "risk_exit": risk,
        "capital_decision": capital["decision"],
        "decision": (
            "RECOVERY_DIAGNOSTIC_PASSES_FROZEN_CAPITAL_GATES"
            if passed
            else "RECOVERY_DIAGNOSTIC_FAILS_FROZEN_CAPITAL_GATES"
        ),
        "strategy_effectiveness_authority": "NOT_FOR_PRODUCTION_VERDICT",
        "production_authorization": "none",
    }

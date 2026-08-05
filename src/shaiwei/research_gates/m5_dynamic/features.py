"""Eight explicit M5 formulas with frozen missing, sign, denominator, and staleness rules."""

from __future__ import annotations

import math
from collections import Counter
from typing import Any, Callable

import pandas as pd

from .contract import Candidate, M5DataProtocol, M5GateError
from .statements import COMPONENT_PREFIX


PANEL_COLUMNS = (
    "formation_date",
    "effective_date",
    "universe_id",
    "candidate_id",
    "ts_code",
    "current_end_date",
    "predecessor_end_date",
    "candidate_available_date",
    "staleness_days",
    "value",
    "invalid_reason",
)


def _column(component: str) -> str:
    return COMPONENT_PREFIX + component.replace(".", "__")


def _value(row: pd.Series, component: str) -> float:
    return float(row[_column(component)])


def _average_assets(row: pd.Series) -> float:
    return (
        _value(row, "balancesheet.total_assets_t")
        + _value(row, "balancesheet.total_assets_p")
    ) / 2.0


def _gross_margin(row: pd.Series) -> float:
    return (
        (_value(row, "income.total_revenue_t") - _value(row, "income.total_cogs_t"))
        / _value(row, "income.total_revenue_t")
        - (_value(row, "income.total_revenue_p") - _value(row, "income.total_cogs_p"))
        / _value(row, "income.total_revenue_p")
    )


FORMULAS: dict[str, Callable[[pd.Series], float]] = {
    "m5_gross_margin_improvement_v1": _gross_margin,
    "m5_rd_intensity_improvement_v1": lambda row: (
        _value(row, "income.rd_exp_t") / _value(row, "income.total_revenue_t")
        - _value(row, "income.rd_exp_p") / _value(row, "income.total_revenue_p")
    ),
    "m5_receivables_to_revenue_deterioration_v1": lambda row: (
        _value(row, "balancesheet.accounts_receiv_t")
        / _value(row, "income.total_revenue_t")
        - _value(row, "balancesheet.accounts_receiv_p")
        / _value(row, "income.total_revenue_p")
    ),
    "m5_inventory_accumulation_v1": lambda row: (
        _value(row, "balancesheet.inventories_t")
        - _value(row, "balancesheet.inventories_p")
    )
    / _average_assets(row),
    "m5_leverage_change_v1": lambda row: (
        _value(row, "balancesheet.total_liab_t")
        / _value(row, "balancesheet.total_assets_t")
        - _value(row, "balancesheet.total_liab_p")
        / _value(row, "balancesheet.total_assets_p")
    ),
    "m5_current_ratio_improvement_v1": lambda row: (
        _value(row, "balancesheet.total_cur_assets_t")
        / _value(row, "balancesheet.total_cur_liab_t")
        - _value(row, "balancesheet.total_cur_assets_p")
        / _value(row, "balancesheet.total_cur_liab_p")
    ),
    "m5_external_financing_dependence_v1": lambda row: (
        _value(row, "cashflow.n_cash_flows_fnc_act_t") / _average_assets(row)
    ),
    "m5_free_cashflow_margin_improvement_v1": lambda row: (
        _value(row, "cashflow.free_cashflow_t") / _value(row, "income.total_revenue_t")
        - _value(row, "cashflow.free_cashflow_p")
        / _value(row, "income.total_revenue_p")
    ),
}


def _reason(
    row: pd.Series,
    candidate: Candidate,
    nonnegative_fields: set[str],
    staleness_maximum: int,
) -> str | None:
    if pd.isna(row["current_end_date"]) or pd.isna(row["predecessor_end_date"]):
        return "NO_CONSECUTIVE_PAIR"
    if pd.isna(row["candidate_available_date"]):
        return "MISSING_AVAILABILITY"
    if str(row["candidate_available_date"]) > str(row["formation_date"]):
        return "FUTURE_AVAILABILITY"
    if pd.isna(row["staleness_days"]) or int(row["staleness_days"]) > staleness_maximum:
        return "STALE_ANNUAL_PAIR"
    values: dict[str, float] = {}
    for component in candidate.inputs:
        raw = row.get(_column(component))
        if pd.isna(raw):
            return "MISSING_COMPONENT"
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return "NONFINITE_COMPONENT"
        if not math.isfinite(value):
            return "NONFINITE_COMPONENT"
        values[component] = value
        base = component.rsplit("_", 1)[0]
        if base in nonnegative_fields and value < 0:
            return "NEGATIVE_DISALLOWED_COMPONENT"
    for component, value in values.items():
        base = component.rsplit("_", 1)[0]
        if base in {
            "income.total_revenue",
            "balancesheet.total_assets",
            "balancesheet.total_cur_liab",
        } and value <= 0:
            return "INVALID_DENOMINATOR"
    if any(
        component.startswith("balancesheet.total_assets_") for component in candidate.inputs
    ) and _average_assets(row) <= 0:
        return "INVALID_DENOMINATOR"
    return None


def calculate_features(
    protocol: M5DataProtocol,
    components: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if set(FORMULAS) != set(protocol.candidate_ids):
        raise M5GateError("implemented M5 formulas differ from the frozen eight candidates")
    policy = protocol.document["denominator_and_missing_policy"]
    nonnegative = set(policy["nonnegative_required_fields"])
    staleness_maximum = int(policy["current_period_staleness"]["maximum_days_inclusive"])
    candidate_map = {candidate.candidate_id: candidate for candidate in protocol.candidates}
    values: list[float | None] = []
    reasons: list[str | None] = []
    reason_counts: dict[str, Counter[str]] = {
        candidate_id: Counter() for candidate_id in protocol.candidate_ids
    }
    gross_above_one = 0
    for _, row in components.iterrows():
        candidate_id = str(row["candidate_id"])
        candidate = candidate_map.get(candidate_id)
        if candidate is None:
            raise M5GateError("component row contains an unknown candidate")
        reason = _reason(row, candidate, nonnegative, staleness_maximum)
        value: float | None = None
        if reason is None:
            try:
                computed = float(FORMULAS[candidate_id](row))
            except (KeyError, TypeError, ValueError, ZeroDivisionError, OverflowError):
                reason = "FORMULA_ERROR"
            else:
                if math.isfinite(computed):
                    value = computed
                    if candidate_id == "m5_gross_margin_improvement_v1":
                        current_margin = (
                            _value(row, "income.total_revenue_t")
                            - _value(row, "income.total_cogs_t")
                        ) / _value(row, "income.total_revenue_t")
                        predecessor_margin = (
                            _value(row, "income.total_revenue_p")
                            - _value(row, "income.total_cogs_p")
                        ) / _value(row, "income.total_revenue_p")
                        gross_above_one += int(current_margin > 1 or predecessor_margin > 1)
                else:
                    reason = "NONFINITE_OUTPUT"
        values.append(value)
        reasons.append(reason)
        if reason is not None:
            reason_counts[candidate_id][reason] += 1
    result = components.copy()
    result["value"] = pd.array(values, dtype="Float64")
    result["invalid_reason"] = pd.array(reasons, dtype="string")
    if result["value"].dropna().map(math.isfinite).eq(False).any():
        raise M5GateError("M5 formula output contains NaN or infinity")
    diagnostics = {
        "invalid_reason_counts": {
            candidate_id: dict(sorted(counts.items()))
            for candidate_id, counts in reason_counts.items()
        },
        "gross_margin_above_one_rows": gross_above_one,
        "valid_rows": int(result["value"].notna().sum()),
        "invalid_rows": int(result["value"].isna().sum()),
    }
    return result.loc[:, PANEL_COLUMNS].reset_index(drop=True), diagnostics

"""Pure score, ranking, and gate functions for the TS-v6-1 ranking preflight."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_EVEN
from typing import Any, Mapping, Sequence

from shaiwei.research.trend_swing.v6.engine import (
    canonical_json,
    canonical_sha256,
    decimal_value,
    density,
    linear_quantile,
    native,
)

__all__ = [
    "AXES",
    "DIRECTIONS",
    "Q8",
    "canonical_json",
    "canonical_sha256",
    "density",
    "development_gate_report",
    "holdout_gate_report",
    "integration_report",
    "iqr",
    "map_reference_positions",
    "mid_rank_positions",
    "native",
    "score_events",
    "select_by_cut",
    "select_top_k",
]

AXES = (
    "pullback_amount_ratio",
    "recovery_close_location",
    "pre_entry_10d_return_percentile",
)
DIRECTIONS = {
    "pullback_amount_ratio": "lower_is_better",
    "recovery_close_location": "higher_is_better",
    "pre_entry_10d_return_percentile": "lower_is_better",
}
Q8 = Decimal("0.00000001")
EVENT_KEY = ("ts_code", "signal_date", "next_open_date")


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(Q8, rounding=ROUND_HALF_EVEN)


def mid_rank_positions(values: Sequence[Any]) -> tuple[Decimal, ...]:
    """Mid-rank ECDF positions (count_less + 0.5*count_equal)/n, quantized to 8 places."""
    decimals = [decimal_value(value) for value in values]
    n = len(decimals)
    if n == 0:
        raise ValueError("TS-v6-1 ranking input is empty")
    positions = []
    for value in decimals:
        less = sum(1 for other in decimals if other < value)
        equal = sum(1 for other in decimals if other == value)
        positions.append(_quantize((Decimal(less) + Decimal(equal) / 2) / n))
    return tuple(positions)


def map_reference_positions(
    reference: Sequence[Any], queries: Sequence[Any]
) -> tuple[Decimal, ...]:
    """Map query values onto the frozen reference sample's mid-rank ECDF."""
    base = [decimal_value(value) for value in reference]
    n = len(base)
    if n == 0:
        raise ValueError("TS-v6-1 ranking reference sample is empty")
    positions = []
    for raw in queries:
        value = decimal_value(raw)
        less = sum(1 for other in base if other < value)
        equal = sum(1 for other in base if other == value)
        positions.append(_quantize((Decimal(less) + Decimal(equal) / 2) / n))
    return tuple(positions)


def _directed(axis: str, position: Decimal) -> Decimal:
    if DIRECTIONS[axis] == "higher_is_better":
        return position
    return _quantize(Decimal("1") - position)


def score_events(events: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Score events in-sample: per-axis ECDF positions, directed, equal-weight mean."""
    if not events:
        raise ValueError("TS-v6-1 scoring input is empty")
    axis_positions = {
        axis: mid_rank_positions([row[axis] for row in events]) for axis in AXES
    }
    scored = []
    for index, row in enumerate(events):
        directed = {
            axis: _directed(axis, axis_positions[axis][index]) for axis in AXES
        }
        score = _quantize(sum(directed.values()) / Decimal(len(AXES)))
        scored.append({
            "role": str(row["role"]),
            **{key: str(row[key]) for key in EVENT_KEY},
            "axis_positions": directed,
            "score": score,
        })
    return scored


def score_against_reference(
    reference: Sequence[Mapping[str, Any]], events: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Score events against the frozen reference sample's ECDF (holdout mapping)."""
    if not events:
        return []
    axis_positions = {
        axis: map_reference_positions(
            [row[axis] for row in reference], [row[axis] for row in events]
        )
        for axis in AXES
    }
    scored = []
    for index, row in enumerate(events):
        directed = {
            axis: _directed(axis, axis_positions[axis][index]) for axis in AXES
        }
        score = _quantize(sum(directed.values()) / Decimal(len(AXES)))
        scored.append({
            "role": str(row["role"]),
            **{key: str(row[key]) for key in EVENT_KEY},
            "axis_positions": directed,
            "score": score,
        })
    return scored


def _order(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (-row["score"], row["ts_code"], row["signal_date"], row["next_open_date"])


def select_top_k(
    scored: Sequence[Mapping[str, Any]], k: int
) -> tuple[list[dict[str, Any]], Decimal]:
    if k < 1 or k > len(scored):
        raise ValueError("TS-v6-1 top-k is outside the scored population")
    ordered = sorted(scored, key=_order)
    selected = [dict(row) for row in ordered[:k]]
    return selected, ordered[k - 1]["score"]


def select_by_cut(
    scored: Sequence[Mapping[str, Any]], cut_score: Decimal
) -> list[dict[str, Any]]:
    return [dict(row) for row in sorted(scored, key=_order) if row["score"] >= cut_score]


def iqr(values: Sequence[Any]) -> Decimal:
    decimals = [decimal_value(value) for value in values]
    return linear_quantile(decimals, "0.75") - linear_quantile(decimals, "0.25")


def _single_axis_keys(scored: Sequence[Mapping[str, Any]], axis: str, k: int) -> set[tuple[str, ...]]:
    ordered = sorted(
        scored,
        key=lambda row: (
            -row["axis_positions"][axis],
            row["ts_code"],
            row["signal_date"],
            row["next_open_date"],
        ),
    )
    return {tuple(str(row[key]) for key in EVENT_KEY) for row in ordered[:k]}


def integration_report(
    scored: Sequence[Mapping[str, Any]], selected: Sequence[Mapping[str, Any]], k: int
) -> dict[str, bool]:
    """Each axis must change the blended top-k selection for at least one event."""
    blended = {tuple(str(row[key]) for key in EVENT_KEY) for row in selected}
    return {
        axis: _single_axis_keys(scored, axis, k) != blended for axis in AXES
    }


def development_gate_report(
    selected: Sequence[Mapping[str, Any]],
    scored_population: Sequence[Mapping[str, Any]],
    raw_population: Sequence[Mapping[str, Any]],
    gate: Mapping[str, Any],
    k: int,
) -> dict[str, Any]:
    evidence = density(selected, (2021, 2022, 2023))
    yearly = evidence["legal_event_count_by_calendar_year"]
    axis_iqr = {axis: iqr([row[axis] for row in raw_population]) for axis in AXES}
    score_iqr_value = iqr([row["score"] for row in scored_population])
    integration = integration_report(scored_population, selected, k)
    checks = {
        "minimum_legal_events": evidence["legal_event_count"] >= int(gate["minimum_legal_events"]),
        "minimum_distinct_signal_days": evidence["distinct_signal_day_count"]
        >= int(gate["minimum_distinct_signal_days"]),
        "minimum_events_each_calendar_year": min(yearly.values(), default=0)
        >= int(gate["minimum_events_each_calendar_year"]),
        "per_axis_interquartile_range_positive": all(value > 0 for value in axis_iqr.values()),
        "score_interquartile_range_positive": score_iqr_value > 0,
        "each_axis_changes_blended_selection": all(integration.values()),
    }
    return {
        "density": evidence,
        "axis_interquartile_range": {axis: format(value, "f") for axis, value in axis_iqr.items()},
        "score_interquartile_range": format(score_iqr_value, "f"),
        "axis_integration": integration,
        "checks": checks,
        "pass": all(checks.values()),
    }


def holdout_gate_report(
    selected: Sequence[Mapping[str, Any]], gate: Mapping[str, Any]
) -> dict[str, Any]:
    evidence = density(selected, (2024, 2025))
    yearly = evidence["legal_event_count_by_calendar_year"]
    checks = {
        "minimum_distinct_signal_days": evidence["distinct_signal_day_count"]
        >= int(gate["minimum_distinct_signal_days"]),
        "minimum_events_each_calendar_year": min(yearly.values(), default=0)
        >= int(gate["minimum_events_each_calendar_year"]),
    }
    return {"density": evidence, "checks": checks, "pass": all(checks.values())}

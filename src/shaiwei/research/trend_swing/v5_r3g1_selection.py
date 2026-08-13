"""Result-blind density gates and mechanical selection for R3G-1."""

from __future__ import annotations

from decimal import Decimal
import hashlib
import json
import math
from typing import Any, Mapping, Sequence

from shaiwei.research.trend_swing.v5_models import ParameterId
from shaiwei.research.trend_swing.v5_r3g_contract import RegisteredCandidate


SHARED_PARAMETERS = {ParameterId.RECOVERY_CONFIRMATION_DAYS.value, ParameterId.MAXIMUM_WAIT_DAYS.value}


def parameter_hash(point: Mapping[str, str]) -> str:
    payload = json.dumps(dict(sorted(point.items())), separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def density_evidence(events: Sequence[Mapping[str, Any]], years: Sequence[int]) -> dict[str, Any]:
    yearly = {str(year): 0 for year in years}
    days = set()
    for event in events:
        date = str(event["signal_date"])
        if date[:4] in yearly:
            yearly[date[:4]] += 1
            days.add(date)
    return {
        "legal_event_count": sum(yearly.values()),
        "distinct_signal_day_count": len(days),
        "legal_event_count_by_calendar_year": yearly,
    }


def discovery_pass(evidence: Mapping[str, Any], gate: Mapping[str, Any]) -> bool:
    yearly = evidence["legal_event_count_by_calendar_year"]
    return (
        evidence["legal_event_count"] >= gate["per_point_minimum_legal_events"]
        and evidence["distinct_signal_day_count"] >= gate["per_point_minimum_distinct_signal_days"]
        and min(yearly.values(), default=0)
        >= gate["per_point_minimum_events_each_discovery_calendar_year"]
    )


def mechanism_parameter_diversity(
    registered: RegisteredCandidate,
    passing: Sequence[Mapping[str, Any]],
) -> bool:
    specific = {
        slot.parameter_id.value for slot in registered.candidate.parameter_slots
        if slot.parameter_id.value not in SHARED_PARAMETERS
    }
    return all(len({row["parameters"][name] for row in passing}) >= 2 for name in specific)


def _cv(values: Sequence[int]) -> float:
    mean = sum(values) / len(values)
    return 0.0 if mean == 0 else math.sqrt(sum((x - mean) ** 2 for x in values) / len(values)) / mean


def select_anchor(passing: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    return min(
        passing,
        key=lambda row: (
            -min(row["discovery"]["legal_event_count_by_calendar_year"].values()),
            _cv(list(row["discovery"]["legal_event_count_by_calendar_year"].values())),
            abs(row["discovery"]["legal_event_count"] - 60),
            row["point_hash"],
        ),
    )


def normalized_distance(
    registered: RegisteredCandidate,
    left: Mapping[str, str],
    right: Mapping[str, str],
) -> Decimal:
    bounds = {
        slot.parameter_id.value: Decimal(slot.maximum) - Decimal(slot.minimum)
        for slot in registered.candidate.parameter_slots
    }
    return sum(
        (abs(Decimal(left[name]) - Decimal(right[name])) / width for name, width in bounds.items()),
        Decimal("0"),
    )


def select_neighbours(
    registered: RegisteredCandidate,
    anchor: Mapping[str, Any],
    passing: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    choices = [row for row in passing if row["point_hash"] != anchor["point_hash"]]
    return sorted(
        choices,
        key=lambda row: (
            normalized_distance(registered, anchor["parameters"], row["parameters"]),
            row["point_hash"],
        ),
    )[:2]

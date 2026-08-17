"""Pure density design, filtering, and mechanical selection for TS-v6."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_EVEN
import hashlib
import json
import math
from typing import Any, Iterable, Mapping, Sequence


AXES = (
    "MAX_PULLBACK_AMOUNT_RATIO",
    "MIN_RECOVERY_CLOSE_LOCATION",
    "MAX_PRE_ENTRY_10D_RETURN_PERCENTILE",
)
FEATURES = (
    "pullback_amount_ratio",
    "recovery_close_location",
    "pre_entry_10d_return_percentile",
)
L9 = (
    (0, 0, 0), (0, 1, 1), (0, 2, 2),
    (1, 0, 1), (1, 1, 2), (1, 2, 0),
    (2, 0, 2), (2, 1, 0), (2, 2, 1),
)
Q8 = Decimal("0.00000001")


def native(value: Any) -> Any:
    """Normalize library scalar types before canonical JSON serialization."""
    if isinstance(value, dict):
        return {str(key): native(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [native(item) for item in value]
    if isinstance(value, Decimal):
        return format(value, "f")
    if hasattr(value, "item"):
        return native(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("non-finite TS-v6 JSON scalar")
    return value


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        native(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def decimal_value(value: Any) -> Decimal:
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("TS-v6 feature is non-finite")
    return result


def linear_quantile(values: Iterable[Any], position: Any) -> Decimal:
    ordered = sorted(decimal_value(value) for value in values)
    if not ordered:
        raise ValueError("TS-v6 quantile input is empty")
    quantile = decimal_value(position)
    if not Decimal("0") <= quantile <= Decimal("1"):
        raise ValueError("TS-v6 quantile position is outside [0,1]")
    index = Decimal(len(ordered) - 1) * quantile
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = index - lower
    value = ordered[lower] + (ordered[upper] - ordered[lower]) * fraction
    return value.quantize(Q8, rounding=ROUND_HALF_EVEN)


def derive_levels(observations: Sequence[Mapping[str, Any]]) -> dict[str, tuple[Decimal, ...]]:
    positions = {
        AXES[0]: ("0.40", "0.60", "0.80"),
        AXES[1]: ("0.40", "0.60", "0.80"),
        AXES[2]: ("0.60", "0.75", "0.90"),
    }
    levels = {
        axis: tuple(linear_quantile((row[feature] for row in observations), q) for q in positions[axis])
        for axis, feature in zip(AXES, FEATURES, strict=True)
    }
    if any(len(set(values)) != 3 for values in levels.values()):
        raise ValueError("BLOCKED_PARAMETER_LEVEL_COLLAPSE")
    return levels


def design_points(levels: Mapping[str, Sequence[Decimal]]) -> tuple[dict[str, Any], ...]:
    points = []
    for indices in L9:
        parameters = {
            axis: format(levels[axis][index], "f")
            for axis, index in zip(AXES, indices, strict=True)
        }
        points.append({
            "level_indices": list(indices),
            "parameters": parameters,
            "point_hash": canonical_sha256(parameters),
        })
    return tuple(points)


def rejection_reason(row: Mapping[str, Any], parameters: Mapping[str, Any]) -> str:
    if decimal_value(row[FEATURES[0]]) > decimal_value(parameters[AXES[0]]):
        return "PULLBACK_AMOUNT_ABOVE_LIMIT"
    if decimal_value(row[FEATURES[1]]) < decimal_value(parameters[AXES[1]]):
        return "RECOVERY_CLOSE_LOCATION_BELOW_LIMIT"
    if decimal_value(row[FEATURES[2]]) > decimal_value(parameters[AXES[2]]):
        return "PRE_ENTRY_10D_RETURN_PERCENTILE_ABOVE_LIMIT"
    return ""


def filter_events(
    observations: Sequence[Mapping[str, Any]], parameters: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, int], dict[str, int]]:
    accepted, reasons = [], {name: 0 for name in (
        "PULLBACK_AMOUNT_ABOVE_LIMIT", "RECOVERY_CLOSE_LOCATION_BELOW_LIMIT",
        "PRE_ENTRY_10D_RETURN_PERCENTILE_ABOVE_LIMIT",
    )}
    axis_rejected = {axis: 0 for axis in AXES}
    for row in observations:
        values = [decimal_value(row[name]) for name in FEATURES]
        limits = [decimal_value(parameters[name]) for name in AXES]
        failures = (values[0] > limits[0], values[1] < limits[1], values[2] > limits[2])
        for axis, failed in zip(AXES, failures, strict=True):
            axis_rejected[axis] += int(failed)
        reason = rejection_reason(row, parameters)
        if reason:
            reasons[reason] += 1
        else:
            accepted.append(dict(row))
    return accepted, reasons, axis_rejected


def density(events: Sequence[Mapping[str, Any]], years: Sequence[int]) -> dict[str, Any]:
    yearly = {str(year): 0 for year in years}
    days: set[str] = set()
    for event in events:
        day = str(event["signal_date"])
        if day[:4] in yearly:
            yearly[day[:4]] += 1
            days.add(day)
    return {
        "legal_event_count": sum(yearly.values()),
        "distinct_signal_day_count": len(days),
        "legal_event_count_by_calendar_year": yearly,
    }


def development_eligible(
    evidence: Mapping[str, Any], parent_count: int, axis_rejected: Mapping[str, int], gate: Mapping[str, Any]
) -> tuple[bool, float]:
    count = int(evidence["legal_event_count"])
    retention = count / parent_count if parent_count else 0.0
    yearly = evidence["legal_event_count_by_calendar_year"]
    passed = (
        count >= int(gate["minimum_legal_events"])
        and int(evidence["distinct_signal_day_count"]) >= int(gate["minimum_distinct_signal_days"])
        and min(yearly.values(), default=0) >= int(gate["minimum_events_each_calendar_year"])
        and 0 < count < parent_count
        and float(gate["retention_minimum"]) <= retention <= float(gate["retention_maximum"])
        and all(value > 0 for value in axis_rejected.values())
    )
    return passed, retention


def _cv(yearly: Mapping[str, int]) -> float:
    values = list(yearly.values())
    mean = sum(values) / len(values)
    return 0.0 if mean == 0 else math.sqrt(sum((x - mean) ** 2 for x in values) / len(values)) / mean


def select_point(profiles: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    eligible = [row for row in profiles if row["development_pass"]]
    if not eligible:
        return None
    return min(
        eligible,
        key=lambda row: (
            -min(row["development"]["legal_event_count_by_calendar_year"].values()),
            _cv(row["development"]["legal_event_count_by_calendar_year"]),
            abs(row["development"]["legal_event_count"] - 120),
            sum(abs(index - 1) for index in row["level_indices"]),
            row["point_hash"],
        ),
    )

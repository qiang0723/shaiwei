"""Pure IEEE-754 topology diagnostics over already-sealed Top30 rows."""

from __future__ import annotations

from collections import Counter
import math
import struct
from typing import Any

from shaiwei.research.top30_diagnostic.exact import COLUMNS, DiagnosticError


_MASK = (1 << 64) - 1
_SIGN = 1 << 63


def ordered_float_bits(value: float) -> int:
    bits = struct.unpack(">Q", struct.pack(">d", value))[0]
    return (~bits & _MASK) if bits & _SIGN else bits | _SIGN


def ulp_distance(left: float, right: float) -> int:
    if not math.isfinite(left) or not math.isfinite(right):
        raise DiagnosticError("Top30 provenance ULP input is nonfinite")
    return abs(ordered_float_bits(left) - ordered_float_bits(right))


def compare_rows(
    expected: list[dict[str, str]], actual: list[dict[str, str]]
) -> dict[str, Any]:
    if len(expected) != len(actual):
        raise DiagnosticError("Top30 provenance row count differs")
    mismatch_by_field: Counter[str] = Counter()
    ulps: list[int] = []
    absolute: list[float] = []
    first: dict[str, Any] | None = None
    last: dict[str, Any] | None = None
    signs: Counter[str] = Counter()
    for position, (left, right) in enumerate(zip(expected, actual, strict=True)):
        if left.get("date") != right.get("date"):
            raise DiagnosticError("Top30 provenance date identity differs")
        for field in COLUMNS:
            left_hex, right_hex = left.get(field), right.get(field)
            if not isinstance(left_hex, str) or not isinstance(right_hex, str):
                raise DiagnosticError("Top30 provenance row encoding differs")
            if left_hex == right_hex:
                continue
            left_value, right_value = float.fromhex(left_hex), float.fromhex(right_hex)
            distance = ulp_distance(left_value, right_value)
            delta = right_value - left_value
            item = {
                "position": position,
                "date": left["date"],
                "field": field,
                "expected": left_hex,
                "actual": right_hex,
                "ulp_distance": distance,
                "absolute_difference": abs(delta),
            }
            first = first or item
            last = item
            mismatch_by_field[field] += 1
            ulps.append(distance)
            absolute.append(abs(delta))
            signs["positive" if delta > 0 else "negative"] += 1
    ordered = sorted(ulps)
    return {
        "exact_equal": not ulps,
        "row_count": len(expected),
        "mismatch_cell_count": len(ulps),
        "mismatch_by_field": dict(sorted(mismatch_by_field.items())),
        "first_mismatch": first,
        "last_mismatch": last,
        "ulp": {
            "minimum": ordered[0] if ordered else 0,
            "median": ordered[len(ordered) // 2] if ordered else 0,
            "maximum": ordered[-1] if ordered else 0,
            "one_ulp_count": sum(value == 1 for value in ordered),
        },
        "maximum_absolute_difference_diagnostic_only": max(absolute, default=0.0),
        "difference_direction": dict(sorted(signs.items())),
    }


def lane_rows(bundle: dict[str, Any], adapter: str) -> list[dict[str, str]]:
    try:
        first = bundle["adapters"][adapter]["replay_1"]["rows"]
        second = bundle["adapters"][adapter]["replay_2"]["rows"]
    except (KeyError, TypeError) as error:
        raise DiagnosticError("Top30 provenance lane bundle is incomplete") from error
    if not isinstance(first, list) or first != second:
        raise DiagnosticError("Top30 provenance internal replay identity differs")
    return first


__all__ = ["compare_rows", "lane_rows", "ordered_float_bits", "ulp_distance"]

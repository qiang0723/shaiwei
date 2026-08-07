"""Exact, tolerance-free report encoding for Top30 diagnostics."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

import pandas as pd


COLUMNS = ("gross_return", "benchmark_return", "recorded_cost", "turnover")


class DiagnosticError(RuntimeError):
    """Raised when a diagnostic contract cannot be satisfied."""


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def exact_rows(frame: pd.DataFrame) -> list[dict[str, str]]:
    if list(frame.columns) != list(COLUMNS):
        raise DiagnosticError("Top30 diagnostic report columns differ")
    value = frame.copy()
    value.index = pd.to_datetime(value.index)
    if value.empty or value.index.has_duplicates or not value.index.is_monotonic_increasing:
        raise DiagnosticError("Top30 diagnostic report index differs")
    rows: list[dict[str, str]] = []
    for day, row in value.iterrows():
        encoded = {"date": pd.Timestamp(day).strftime("%Y-%m-%d")}
        for column in COLUMNS:
            number = float(row[column])
            if not math.isfinite(number):
                raise DiagnosticError("Top30 diagnostic report contains a nonfinite value")
            encoded[column] = number.hex()
        rows.append(encoded)
    return rows


def exact_diff(expected: list[dict[str, str]], actual: list[dict[str, str]]) -> dict[str, Any]:
    mismatch_count = 0
    first: dict[str, str] | None = None
    maximum_absolute_difference = 0.0
    row_count_equal = len(expected) == len(actual)
    for position in range(max(len(expected), len(actual))):
        if position >= len(expected) or position >= len(actual):
            mismatch_count += 1
            if first is None:
                first = {
                    "position": str(position),
                    "field": "ROW_PRESENCE",
                    "expected": "PRESENT" if position < len(expected) else "ABSENT",
                    "actual": "PRESENT" if position < len(actual) else "ABSENT",
                }
            continue
        left, right = expected[position], actual[position]
        for field in ("date", *COLUMNS):
            if left[field] == right[field]:
                continue
            mismatch_count += 1
            if field != "date":
                maximum_absolute_difference = max(
                    maximum_absolute_difference,
                    abs(float.fromhex(left[field]) - float.fromhex(right[field])),
                )
            if first is None:
                first = {
                    "position": str(position),
                    "field": field,
                    "expected": left[field],
                    "actual": right[field],
                }
    return {
        "exact_equal": mismatch_count == 0,
        "row_count_equal": row_count_equal,
        "expected_row_count": len(expected),
        "actual_row_count": len(actual),
        "mismatch_cell_count": mismatch_count,
        "first_mismatch": first,
        "maximum_absolute_difference_diagnostic_only": maximum_absolute_difference,
    }


__all__ = [
    "COLUMNS",
    "DiagnosticError",
    "canonical_json",
    "canonical_sha256",
    "exact_diff",
    "exact_rows",
]

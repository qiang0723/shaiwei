"""Frozen annual statement row scope shared by M5 lineage adapters."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


ELIGIBLE_END_DATE_SUFFIX = "1231"
ELIGIBLE_REPORT_TYPES = frozenset({"1", "5"})


def is_frozen_annual_statement_row(row: Mapping[str, Any]) -> bool:
    """Match the already-frozen R1 annual statement eligibility domain."""

    end_date = str(row["end_date"]).replace("-", "")
    report_type = str(row["report_type"])
    return end_date.endswith(ELIGIBLE_END_DATE_SUFFIX) and report_type in ELIGIBLE_REPORT_TYPES

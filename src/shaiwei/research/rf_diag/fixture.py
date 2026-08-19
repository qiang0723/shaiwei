"""Synthetic fixtures for the RF gap-lineage diagnostic machinery."""

from __future__ import annotations

from typing import Any

from shaiwei.research.rf_diag.contract import RFDError
from shaiwei.research.rf_diag.diagnose import assign_explanations


def fixture() -> dict[str, Any]:
    cases: list[tuple[dict[str, Any], tuple[str, ...]]] = [
        ({"baostock_status": "0", "suspend_d_record_count": 0, "lifecycle_edge": False,
          "formation_edge": False}, ("SUSPENDED_BY_INDEPENDENT_BAOSTOCK_STATUS",)),
        ({"baostock_status": "1", "suspend_d_record_count": 2, "lifecycle_edge": False,
          "formation_edge": False}, ("SUSPENDED_BY_SUSPEND_D_WITH_TIMING_ANNOTATION",)),
        ({"baostock_status": "", "suspend_d_record_count": 0, "lifecycle_edge": True,
          "formation_edge": False}, ("LIFECYCLE_LIST_OR_DELIST_EDGE",)),
        ({"baostock_status": "", "suspend_d_record_count": 0, "lifecycle_edge": False,
          "formation_edge": True}, ("MEMBERSHIP_FORMATION_EDGE",)),
        ({"baostock_status": "0", "suspend_d_record_count": 1, "lifecycle_edge": True,
          "formation_edge": False},
         ("SUSPENDED_BY_INDEPENDENT_BAOSTOCK_STATUS",
          "SUSPENDED_BY_SUSPEND_D_WITH_TIMING_ANNOTATION",
          "LIFECYCLE_LIST_OR_DELIST_EDGE")),
        ({"baostock_status": "", "suspend_d_record_count": 0, "lifecycle_edge": False,
          "formation_edge": False}, ("UNEXPLAINED_REMAINS",)),
    ]
    for evidence, expected in cases:
        observed = assign_explanations(evidence)
        if observed != expected:
            raise RFDError(f"RF diagnostic fixture differs: {observed} != {expected}")
    return {"fixture_pass": True, "adversarial_cases": len(cases)}

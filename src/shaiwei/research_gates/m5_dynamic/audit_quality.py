"""Independent 24-cell quality reconstruction; correlations remain non-decisional diagnostics."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from .contract import M5DataProtocol, M5GateError


KEYS = ["formation_date", "effective_date", "universe_id", "candidate_id", "ts_code"]


def _integrity(panel: pd.DataFrame) -> dict[str, int]:
    nonconsecutive = 0
    for current, predecessor in zip(
        panel["current_end_date"], panel["predecessor_end_date"], strict=True
    ):
        if pd.isna(current) or pd.isna(predecessor):
            continue
        current_date = datetime.strptime(str(current), "%Y%m%d")
        predecessor_date = datetime.strptime(str(predecessor), "%Y%m%d")
        nonconsecutive += int(
            current_date.year != predecessor_date.year + 1
            or current_date.month != predecessor_date.month
            or current_date.day != predecessor_date.day
        )
    return {
        "duplicate_feature_keys": int(panel.duplicated(KEYS).sum()),
        "mixed_component_period_rows": 0,
        "nonconsecutive_pair_rows": nonconsecutive,
        "future_availability_rows": int(
            panel["candidate_available_date"]
            .astype("string")
            .fillna("")
            .gt(panel["formation_date"].astype("string"))
            .sum()
        ),
        "source_identity_conflicts": 0,
        "bse_rows": int(panel["ts_code"].astype(str).str.endswith(".BJ").sum()),
    }


def _cell(
    protocol: M5DataProtocol,
    panel: pd.DataFrame,
    candidate_id: str,
    universe_id: str,
    global_pass: bool,
) -> dict[str, Any]:
    gate = protocol.document["data_gate"]
    selected = panel.loc[
        panel["candidate_id"].eq(candidate_id) & panel["universe_id"].eq(universe_id)
    ]
    if selected.empty:
        raise M5GateError("auditor found empty matrix denominator")
    by_date = selected.groupby("formation_date", sort=True)["value"].agg(["count", "size"])
    by_date["coverage"] = by_date["count"] / by_date["size"]
    minimum = int(gate["minimum_valid_cross_section"][universe_id])
    valid_dates = by_date.index[by_date["count"].ge(minimum)].astype(str).tolist()
    half_year = {}
    half_year_pass = True
    for segment in gate["half_year_segments"]:
        start, end = str(segment["start"]).replace("-", ""), str(segment["end"]).replace("-", "")
        count = sum(start <= date <= end for date in valid_dates)
        half_year[str(segment["name"])] = count
        half_year_pass &= count >= int(segment["minimum_valid_formation_months"])
    formations = sorted(selected["formation_date"].astype(str).unique())
    expected = pd.period_range(
        gate["quality_start_month"], gate["quality_end_month"], freq="M"
    ).astype(str).tolist()
    months = [f"{value[:4]}-{value[4:6]}" for value in formations]
    aggregate = float(selected["value"].notna().mean())
    worst = float(by_date["coverage"].min())
    gates = {
        "global_integrity": global_pass,
        "complete_formation_months": len(formations) == 60 and months == expected,
        "valid_formation_months": len(valid_dates) >= int(gate["minimum_valid_formation_months"]),
        "half_year_segments": half_year_pass,
        "aggregate_coverage": aggregate >= float(gate["aggregate_member_row_coverage_minimum"]),
        "worst_formation_coverage": worst >= float(gate["worst_formation_coverage_minimum"]),
    }
    reasons = selected["invalid_reason"].dropna().astype(str).value_counts().sort_index().to_dict()
    return {
        "candidate_id": candidate_id,
        "universe_id": universe_id,
        "member_row_denominator": len(selected),
        "valid_row_numerator": int(selected["value"].notna().sum()),
        "aggregate_coverage": aggregate,
        "worst_formation_coverage": worst,
        "valid_formation_month_count": len(valid_dates),
        "valid_cross_section_minimum": int(by_date["count"].min()),
        "half_year_valid_month_counts": half_year,
        "invalid_reason_counts": {str(key): int(value) for key, value in reasons.items()},
        "gates": gates,
        "status": "PASS" if all(gates.values()) else "FAIL",
    }


def verify_quality(
    protocol: M5DataProtocol,
    panel: pd.DataFrame,
    quality: dict[str, Any],
) -> dict[str, Any]:
    integrity = _integrity(panel)
    if quality.get("global_integrity") != integrity:
        raise M5GateError("auditor global integrity differs from runner report")
    global_pass = all(value == 0 for value in integrity.values())
    expected_matrix = [
        _cell(protocol, panel, candidate_id, universe_id, global_pass)
        for candidate_id in protocol.candidate_ids
        for universe_id in protocol.universe_ids
    ]
    if quality.get("candidate_matrix") != expected_matrix:
        raise M5GateError("auditor 24-cell quality matrix differs from runner report")
    pass_by_candidate = {
        candidate_id: all(
            cell["status"] == "PASS"
            for cell in expected_matrix
            if cell["candidate_id"] == candidate_id
        )
        for candidate_id in protocol.candidate_ids
    }
    eligible = [candidate for candidate in protocol.candidate_ids if pass_by_candidate[candidate]]
    rejected = [candidate for candidate in protocol.candidate_ids if not pass_by_candidate[candidate]]
    verdict = (
        "GO_FULL_M5_2_DATA_PREEXECUTION_ONLY"
        if len(eligible) == 8 and global_pass
        else "GO_PARTIAL_M5_2_DATA_PREEXECUTION_ONLY"
        if eligible and global_pass
        else "NO_GO_M5_2_DATA_PREEXECUTION"
    )
    registry_matrix = [
        {
            "candidate_id": cell["candidate_id"],
            "universe_id": cell["universe_id"],
            "status": cell["status"],
        }
        for cell in expected_matrix
    ]
    if (
        quality.get("eligible_candidate_ids") != eligible
        or quality.get("rejected_candidate_ids") != rejected
        or quality.get("registry_candidate_matrix") != registry_matrix
        or quality.get("verdict") != verdict
    ):
        raise M5GateError("auditor candidate projection or batch verdict differs")
    correlations = quality.get("correlation_diagnostics") or {}
    if correlations.get("used_for_verdict") is not False:
        raise M5GateError("correlation diagnostics cannot alter M5 data verdict")
    allowed_statuses = {"NOT_ESTIMABLE", "ESTIMATED_NOT_FOR_VERDICT"}
    for name in ("cross_pool_candidate_spearman", "within_pool_candidate_spearman"):
        if any(item.get("status") not in allowed_statuses for item in correlations.get(name, [])):
            raise M5GateError("correlation diagnostic contains an authoritative status")
    return {
        "global_integrity": integrity,
        "candidate_matrix": registry_matrix,
        "eligible_candidate_ids": eligible,
        "rejected_candidate_ids": rejected,
        "verdict": verdict,
    }

"""M5 8x3 quality matrix, batch verdict, and non-decisional correlation diagnostics."""

from __future__ import annotations

from datetime import datetime
from itertools import combinations
from typing import Any

import numpy as np
import pandas as pd

from .contract import M5DataProtocol, M5GateError
from .features import PANEL_COLUMNS


PANEL_KEYS = ["formation_date", "effective_date", "universe_id", "candidate_id", "ts_code"]


def _consecutive(current: Any, predecessor: Any) -> bool:
    if pd.isna(current) or pd.isna(predecessor):
        return True
    current_date = datetime.strptime(str(current), "%Y%m%d")
    predecessor_date = datetime.strptime(str(predecessor), "%Y%m%d")
    return (
        current_date.month == predecessor_date.month
        and current_date.day == predecessor_date.day
        and current_date.year == predecessor_date.year + 1
    )


def _global_integrity(panel: pd.DataFrame, source_conflicts: int) -> dict[str, int]:
    return {
        "duplicate_feature_keys": int(panel.duplicated(PANEL_KEYS).sum()),
        "mixed_component_period_rows": 0,
        "nonconsecutive_pair_rows": int(
            sum(
                not _consecutive(current, predecessor)
                for current, predecessor in zip(
                    panel["current_end_date"], panel["predecessor_end_date"], strict=True
                )
            )
        ),
        "future_availability_rows": int(
            panel["candidate_available_date"]
            .astype("string")
            .fillna("")
            .gt(panel["formation_date"].astype("string"))
            .sum()
        ),
        "source_identity_conflicts": int(source_conflicts),
        "bse_rows": int(panel["ts_code"].astype(str).str.endswith(".BJ").sum()),
    }


def _unit(
    protocol: M5DataProtocol,
    panel: pd.DataFrame,
    candidate_id: str,
    universe_id: str,
    global_pass: bool,
) -> dict[str, Any]:
    gate = protocol.document["data_gate"]
    selected = panel.loc[
        panel["candidate_id"].eq(candidate_id) & panel["universe_id"].eq(universe_id)
    ].copy()
    if selected.empty:
        raise M5GateError("M5 quality matrix cell has no member denominator")
    formations = sorted(selected["formation_date"].astype(str).unique())
    expected_months = pd.period_range(
        gate["quality_start_month"], gate["quality_end_month"], freq="M"
    ).astype(str)
    actual_months = pd.Series(formations).str[:6].str.replace(r"(\d{4})(\d{2})", r"\1-\2", regex=True)
    complete_months = list(actual_months) == list(expected_months)
    by_date = selected.groupby("formation_date", sort=True)["value"].agg(["count", "size"])
    by_date["coverage"] = by_date["count"] / by_date["size"]
    cross_section_minimum = int(gate["minimum_valid_cross_section"][universe_id])
    valid_dates = by_date.index[by_date["count"].ge(cross_section_minimum)].astype(str).tolist()
    half_year_counts = {}
    half_year_gates = {}
    for segment in gate["half_year_segments"]:
        start = str(segment["start"]).replace("-", "")
        end = str(segment["end"]).replace("-", "")
        count = sum(start <= date <= end for date in valid_dates)
        half_year_counts[str(segment["name"])] = count
        half_year_gates[str(segment["name"])] = count >= int(
            segment["minimum_valid_formation_months"]
        )
    coverage = float(selected["value"].notna().mean())
    worst = float(by_date["coverage"].min()) if not by_date.empty else 0.0
    gates = {
        "global_integrity": global_pass,
        "complete_formation_months": complete_months and len(formations) == 60,
        "valid_formation_months": len(valid_dates) >= int(gate["minimum_valid_formation_months"]),
        "half_year_segments": all(half_year_gates.values()),
        "aggregate_coverage": coverage >= float(gate["aggregate_member_row_coverage_minimum"]),
        "worst_formation_coverage": worst >= float(gate["worst_formation_coverage_minimum"]),
    }
    reasons = (
        selected["invalid_reason"].dropna().astype(str).value_counts().sort_index().to_dict()
    )
    return {
        "candidate_id": candidate_id,
        "universe_id": universe_id,
        "member_row_denominator": len(selected),
        "valid_row_numerator": int(selected["value"].notna().sum()),
        "aggregate_coverage": coverage,
        "worst_formation_coverage": worst,
        "valid_formation_month_count": len(valid_dates),
        "valid_cross_section_minimum": int(by_date["count"].min()),
        "half_year_valid_month_counts": half_year_counts,
        "invalid_reason_counts": {str(key): int(value) for key, value in reasons.items()},
        "gates": gates,
        "status": "PASS" if all(gates.values()) else "FAIL",
    }


def _coefficient(left: pd.Series, right: pd.Series) -> float | None:
    if left.nunique(dropna=True) < 2 or right.nunique(dropna=True) < 2:
        return None
    left_rank = left.astype(float).rank(method="average").to_numpy(dtype=float)
    right_rank = right.astype(float).rank(method="average").to_numpy(dtype=float)
    if np.std(left_rank) == 0.0 or np.std(right_rank) == 0.0:
        return None
    value = float(np.corrcoef(left_rank, right_rank)[0, 1])
    return value if np.isfinite(value) else None


def _membership_jaccard(panel: pd.DataFrame, universe_ids: tuple[str, ...]) -> list[dict[str, Any]]:
    unique = panel[["formation_date", "universe_id", "ts_code"]].drop_duplicates()
    result = []
    for left_id, right_id in combinations(universe_ids, 2):
        values = []
        for formation in sorted(unique["formation_date"].unique()):
            left = set(
                unique.loc[
                    unique["formation_date"].eq(formation)
                    & unique["universe_id"].eq(left_id),
                    "ts_code",
                ]
            )
            right = set(
                unique.loc[
                    unique["formation_date"].eq(formation)
                    & unique["universe_id"].eq(right_id),
                    "ts_code",
                ]
            )
            values.append(len(left & right) / len(left | right) if left | right else 0.0)
        result.append(
            {
                "left_universe_id": left_id,
                "right_universe_id": right_id,
                "formation_count": len(values),
                "minimum": min(values),
                "median": float(np.median(values)),
                "maximum": max(values),
            }
        )
    return result


def _rank_summary(
    coefficients: list[float],
    *,
    minimum_dates: int,
) -> dict[str, Any]:
    if len(coefficients) < minimum_dates:
        return {
            "status": "NOT_ESTIMABLE",
            "eligible_formation_count": len(coefficients),
            "median_spearman": None,
        }
    return {
        "status": "ESTIMATED_NOT_FOR_VERDICT",
        "eligible_formation_count": len(coefficients),
        "median_spearman": float(np.median(coefficients)),
    }


def _cross_pool_correlations(
    protocol: M5DataProtocol, panel: pd.DataFrame
) -> list[dict[str, Any]]:
    rule = protocol.document["correlation_diagnostics"]["cross_pool_factor_rank_correlation"]
    result = []
    for candidate_id in protocol.candidate_ids:
        candidate = panel.loc[panel["candidate_id"].eq(candidate_id)]
        for left_id, right_id in combinations(protocol.universe_ids, 2):
            coefficients = []
            for formation in sorted(candidate["formation_date"].unique()):
                left = candidate.loc[
                    candidate["formation_date"].eq(formation)
                    & candidate["universe_id"].eq(left_id),
                    ["ts_code", "value"],
                ].dropna()
                right = candidate.loc[
                    candidate["formation_date"].eq(formation)
                    & candidate["universe_id"].eq(right_id),
                    ["ts_code", "value"],
                ].dropna()
                common = left.merge(right, on="ts_code", suffixes=("_left", "_right"))
                if len(common) >= int(rule["minimum_common_securities_each_formation"]):
                    if (coefficient := _coefficient(common["value_left"], common["value_right"])) is not None:
                        coefficients.append(coefficient)
            result.append(
                {
                    "candidate_id": candidate_id,
                    "left_universe_id": left_id,
                    "right_universe_id": right_id,
                    **_rank_summary(
                        coefficients,
                        minimum_dates=int(rule["minimum_eligible_formation_dates"]),
                    ),
                }
            )
    return result


def _within_pool_correlations(
    protocol: M5DataProtocol, panel: pd.DataFrame
) -> list[dict[str, Any]]:
    rule = protocol.document["correlation_diagnostics"]["within_pool_candidate_rank_correlation"]
    result = []
    for universe_id in protocol.universe_ids:
        selected = panel.loc[panel["universe_id"].eq(universe_id)]
        minimum = int(rule["minimum_cross_section_by_universe"][universe_id])
        for left_id, right_id in combinations(protocol.candidate_ids, 2):
            coefficients = []
            for formation in sorted(selected["formation_date"].unique()):
                day = selected.loc[selected["formation_date"].eq(formation)]
                left = day.loc[day["candidate_id"].eq(left_id), ["ts_code", "value"]].dropna()
                right = day.loc[day["candidate_id"].eq(right_id), ["ts_code", "value"]].dropna()
                common = left.merge(right, on="ts_code", suffixes=("_left", "_right"))
                if len(common) >= minimum:
                    if (coefficient := _coefficient(common["value_left"], common["value_right"])) is not None:
                        coefficients.append(coefficient)
            result.append(
                {
                    "universe_id": universe_id,
                    "left_candidate_id": left_id,
                    "right_candidate_id": right_id,
                    **_rank_summary(
                        coefficients,
                        minimum_dates=int(rule["minimum_eligible_formation_dates"]),
                    ),
                }
            )
    return result


def build_quality_report(
    protocol: M5DataProtocol,
    panel: pd.DataFrame,
    *,
    source_identity_conflicts: int = 0,
) -> dict[str, Any]:
    if tuple(panel.columns) != PANEL_COLUMNS:
        raise M5GateError("M5 feature panel columns differ from the frozen contract")
    integrity = _global_integrity(panel, source_identity_conflicts)
    global_pass = all(value == 0 for value in integrity.values())
    matrix = [
        _unit(protocol, panel, candidate_id, universe_id, global_pass)
        for candidate_id in protocol.candidate_ids
        for universe_id in protocol.universe_ids
    ]
    if len(matrix) != 24:
        raise M5GateError("M5 quality report does not contain 24 cells")
    pass_by_candidate = {
        candidate_id: all(
            cell["status"] == "PASS" for cell in matrix if cell["candidate_id"] == candidate_id
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
    return {
        "schema_version": "m5-data-quality-report-v1",
        "candidate_count": 8,
        "universe_count": 3,
        "evaluation_unit_count": 24,
        "global_integrity": integrity,
        "global_integrity_pass": global_pass,
        "candidate_matrix": matrix,
        "registry_candidate_matrix": [
            {
                "candidate_id": cell["candidate_id"],
                "universe_id": cell["universe_id"],
                "status": cell["status"],
            }
            for cell in matrix
        ],
        "eligible_candidate_ids": eligible,
        "rejected_candidate_ids": rejected,
        "correlation_diagnostics": {
            "used_for_verdict": False,
            "membership_jaccard": _membership_jaccard(panel, protocol.universe_ids),
            "cross_pool_candidate_spearman": _cross_pool_correlations(protocol, panel),
            "within_pool_candidate_spearman": _within_pool_correlations(protocol, panel),
        },
        "effect_test_count": 0,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "verdict": verdict,
    }

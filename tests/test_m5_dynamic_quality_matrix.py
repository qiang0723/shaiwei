from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from shaiwei.research_gates.m5_dynamic.contract import M5DataProtocol
from shaiwei.research_gates.m5_dynamic.fixture import synthetic_feature_panel
from shaiwei.research_gates.m5_dynamic.matrix import _coefficient, build_quality_report


ROOT = Path(__file__).parents[1]


def test_spearman_diagnostic_uses_average_ranks_without_scipy() -> None:
    assert _coefficient(
        pd.Series([1.0, 2.0, 2.0, 4.0]),
        pd.Series([10.0, 20.0, 20.0, 30.0]),
    ) == pytest.approx(1.0)
    assert _coefficient(pd.Series([1.0, 1.0]), pd.Series([1.0, 2.0])) is None


def _protocol() -> M5DataProtocol:
    return M5DataProtocol.load(
        ROOT / "config/m5_dynamic_fundamental_cross_pool_v1.yaml",
        build_path=ROOT / "config/m5_dynamic_fundamental_data_gate_build_v1.yaml",
        project_root=ROOT,
    )


def test_complete_synthetic_matrix_is_full_go_without_effect_authority() -> None:
    protocol = _protocol()
    panel, _ = synthetic_feature_panel(protocol)
    report = build_quality_report(protocol, panel)

    assert report["candidate_count"] == 8
    assert report["universe_count"] == 3
    assert report["evaluation_unit_count"] == len(report["candidate_matrix"]) == 24
    assert len(
        {
            (cell["candidate_id"], cell["universe_id"])
            for cell in report["candidate_matrix"]
        }
    ) == 24
    assert {cell["status"] for cell in report["candidate_matrix"]} == {"PASS"}
    assert report["eligible_candidate_ids"] == list(protocol.candidate_ids)
    assert report["rejected_candidate_ids"] == []
    assert report["verdict"] == "GO_FULL_M5_2_DATA_PREEXECUTION_ONLY"
    assert report["effect_test_count"] == 0
    assert report["strategy_effective"] == "NOT_EVALUATED"
    assert report["production_authorization"] == "none"
    assert report["correlation_diagnostics"]["used_for_verdict"] is False
    assert all(
        item["status"] == "NOT_ESTIMABLE"
        for item in report["correlation_diagnostics"]["cross_pool_candidate_spearman"]
    )


def test_one_pool_failure_rejects_whole_candidate_but_keeps_24_cells() -> None:
    protocol = _protocol()
    panel, _ = synthetic_feature_panel(protocol)
    candidate = protocol.candidate_ids[0]
    mask = panel["candidate_id"].eq(candidate) & panel["universe_id"].eq(
        "star-board-midcap-pit-v1"
    )
    panel.loc[mask, "value"] = pd.NA
    panel.loc[mask, "invalid_reason"] = "SYNTHETIC_MISSING"
    report = build_quality_report(protocol, panel)

    assert len(report["candidate_matrix"]) == 24
    assert report["eligible_candidate_ids"] == list(protocol.candidate_ids[1:])
    assert report["rejected_candidate_ids"] == [candidate]
    assert report["verdict"] == "GO_PARTIAL_M5_2_DATA_PREEXECUTION_ONLY"
    cells = [cell for cell in report["candidate_matrix"] if cell["candidate_id"] == candidate]
    assert [cell["status"] for cell in cells] == ["PASS", "FAIL", "PASS"]


def test_valid_month_54_and_half_year_five_are_inclusive_boundaries() -> None:
    protocol = _protocol()
    panel, _ = synthetic_feature_panel(protocol, pool_sizes=(38, 25, 25))
    candidate = protocol.candidate_ids[0]
    universe = "star50-official-pit-v2"
    dates = sorted(
        panel.loc[
            panel["candidate_id"].eq(candidate) & panel["universe_id"].eq(universe),
            "formation_date",
        ].unique()
    )
    invalid_dates = [dates[index] for index in (0, 6, 12, 18, 24, 30)]
    for formation_date in invalid_dates:
        day_mask = (
            panel["candidate_id"].eq(candidate)
            & panel["universe_id"].eq(universe)
            & panel["formation_date"].eq(formation_date)
        )
        indices = panel.index[day_mask][:9]
        panel.loc[indices, "value"] = pd.NA
        panel.loc[indices, "invalid_reason"] = "SYNTHETIC_COVERAGE_BOUNDARY"
    report = build_quality_report(protocol, panel)
    cell = next(
        item
        for item in report["candidate_matrix"]
        if item["candidate_id"] == candidate and item["universe_id"] == universe
    )

    assert cell["valid_formation_month_count"] == 54
    assert min(cell["half_year_valid_month_counts"].values()) == 5
    assert cell["worst_formation_coverage"] == 29 / 38
    assert cell["status"] == "PASS"

    seventh = dates[36]
    day_mask = (
        panel["candidate_id"].eq(candidate)
        & panel["universe_id"].eq(universe)
        & panel["formation_date"].eq(seventh)
    )
    indices = panel.index[day_mask][:9]
    panel.loc[indices, "value"] = pd.NA
    panel.loc[indices, "invalid_reason"] = "SYNTHETIC_COVERAGE_BOUNDARY"
    failed = build_quality_report(protocol, panel)
    failed_cell = next(
        item
        for item in failed["candidate_matrix"]
        if item["candidate_id"] == candidate and item["universe_id"] == universe
    )
    assert failed_cell["valid_formation_month_count"] == 53
    assert failed_cell["gates"]["valid_formation_months"] is False
    assert failed_cell["status"] == "FAIL"

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from shaiwei.research_gates.m5_dynamic.audit_source_conflicts import (
    audit_statement_sources,
)
from shaiwei.research_gates.m5_dynamic.contract import M5DataProtocol
from shaiwei.research_gates.m5_dynamic.failure_projection import (
    build_global_failure_reports,
)
from shaiwei.research_gates.m5_dynamic.fixture import synthetic_inputs
from shaiwei.research_gates.m5_dynamic.source_conflicts import (
    CATEGORIES,
    assess_all_statement_sources,
    assess_statement_sources,
)


ROOT = Path(__file__).parents[1]


def _protocol() -> M5DataProtocol:
    return M5DataProtocol.load(
        ROOT / "config/m5_dynamic_fundamental_cross_pool_v1.yaml",
        build_path=ROOT / "config/m5_dynamic_fundamental_data_gate_build_v2.yaml",
        project_root=ROOT,
    )


def _rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ts_code": "990001.SH",
                "f_ann_date": "20250315",
                "end_date": "20241231",
                "report_type": "1",
                "update_flag": "1",
                "total_revenue": 100,
                "total_cogs": 60,
                "rd_exp": None,
            }
        ]
    )


@pytest.mark.parametrize(
    ("ordinary_copies", "vip_copies", "mutate_source", "expected"),
    [
        (2, 0, None, "EXACT_DUPLICATE_WITHIN_STANDARD"),
        (0, 2, None, "EXACT_DUPLICATE_WITHIN_VIP"),
        (1, 1, None, "CONSISTENT_OVERLAP_STANDARD_VIP"),
        (2, 0, "standard", "CONFLICT_WITHIN_STANDARD"),
        (0, 2, "vip", "CONFLICT_WITHIN_VIP"),
        (1, 1, "vip", "CONFLICT_STANDARD_VIP"),
    ],
)
def test_six_source_categories_are_exact_and_independently_reproduced(
    ordinary_copies: int,
    vip_copies: int,
    mutate_source: str | None,
    expected: str,
) -> None:
    base = _rows()
    ordinary = (
        pd.concat([base.copy(deep=True)] * ordinary_copies, ignore_index=True).copy(
            deep=True
        )
        if ordinary_copies
        else base.iloc[0:0].copy()
    )
    vip = (
        pd.concat([base.copy(deep=True)] * vip_copies, ignore_index=True).copy(deep=True)
        if vip_copies
        else base.iloc[0:0].copy()
    )
    target = ordinary if mutate_source == "standard" else vip
    if mutate_source is not None:
        target.loc[target.index[-1], "total_revenue"] = 101

    primary = assess_statement_sources("income", ordinary, vip).report
    independent = audit_statement_sources("income", ordinary, vip)

    assert primary["category_counts"] == independent["category_counts"]
    assert primary["conflict_field_counts"] == independent["conflict_field_counts"]
    assert primary["conflict_set_sha256"] == independent["conflict_set_sha256"]
    assert primary["category_counts"][expected] == 1
    assert sum(primary["category_counts"].values()) == 1


def test_numeric_and_null_normalization_is_exact_without_rounding() -> None:
    ordinary = _rows()
    vip = _rows().astype({"total_revenue": "float64"})
    vip.loc[0, "total_revenue"] = 100.0
    assessment = assess_statement_sources("income", ordinary, vip)
    assert assessment.report["category_counts"]["CONSISTENT_OVERLAP_STANDARD_VIP"] == 1
    assert assessment.conflict_count == 0

    vip.loc[0, "total_revenue"] = 100.0000000000001
    assessment = assess_statement_sources("income", ordinary, vip)
    assert assessment.report["category_counts"]["CONFLICT_STANDARD_VIP"] == 1
    assert assessment.report["conflict_field_counts"]["total_revenue"] == 1


def test_global_failure_projection_is_complete_and_row_level_free() -> None:
    protocol = _protocol()
    frames, _ = synthetic_inputs(protocol)
    vip = frames["tushare.balancesheet_vip"].copy()
    vip.loc[0, "total_assets"] = float(vip.loc[0, "total_assets"]) + 1
    frames["tushare.balancesheet_vip"] = vip
    assessment = assess_all_statement_sources(frames)
    conflict, report = build_global_failure_reports(
        protocol,
        assessment,
        input_manifest_sha256="1" * 64,
        release_scope_sha256="2" * 64,
        code_bundle_sha256="3" * 64,
        approval_event_sha256="4" * 64,
        source_evidence={"sources": {}, "memberships": {}},
        semantic_rows_read=False,
    )

    assert assessment.has_conflicts is True
    assert len(report["quality"]["candidate_matrix"]) == 24
    assert {cell["status"] for cell in report["quality"]["candidate_matrix"]} == {
        "FAIL"
    }
    assert report["quality"]["eligible_candidate_ids"] == []
    assert report["quality"]["rejected_candidate_ids"] == list(
        protocol.candidate_ids
    )
    assert report["feature_panel"] == {"status": "NOT_CREATED_GLOBAL_FAILURE"}
    serialized = str(conflict)
    for forbidden in (
        "990001.SH",
        "20250315",
        "20241231",
        "raw_value",
        "normalized_value",
        "candidate_value",
        "absolute_path",
    ):
        assert forbidden not in serialized
    assert set(conflict["table_category_counts"][0]["category_counts"]) == set(
        CATEGORIES
    )

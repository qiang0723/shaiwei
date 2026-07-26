from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from tools.p4_star100.contract import (
    FIELDS,
    INDEX_CODE,
    Request,
    Star100CollectionError,
    build_plan,
    canonical_frame_sha256,
    validate_response,
)


def test_plan_is_bounded_and_index_specific() -> None:
    plan = build_plan(date(2023, 8, 7), date(2026, 7, 24))
    assert len(plan) == 40
    assert [item.partition_name for item in plan if item.api_name == "index_daily"] == [
        "2023",
        "2024",
        "2025",
        "2026",
    ]
    weights = [item for item in plan if item.api_name == "index_weight"]
    assert len(weights) == 36
    assert weights[0].start_date == "20230807"
    assert weights[-1].end_date == "20260724"
    assert all(INDEX_CODE in item.params.values() for item in plan)


def test_invalid_range_fails() -> None:
    with pytest.raises(ValueError, match="start must not exceed"):
        build_plan(date(2026, 1, 2), date(2026, 1, 1))


def test_response_schema_code_dates_and_bse_fail_closed() -> None:
    request = Request("index_weight", "20260101", "20260131", "2026-01")
    valid = pd.DataFrame(
        [[INDEX_CODE, "688001.SH", "20260130", 1.0]],
        columns=FIELDS["index_weight"],
    )
    assert len(validate_response(request, valid, 1000)) == 1
    bad_bse = valid.copy()
    bad_bse.loc[0, "con_code"] = "920001.BJ"
    with pytest.raises(Star100CollectionError, match="forbidden .BJ"):
        validate_response(request, bad_bse, 1000)
    bad_code = valid.copy()
    bad_code.loc[0, "index_code"] = "000688.SH"
    with pytest.raises(Star100CollectionError, match="code mismatch"):
        validate_response(request, bad_code, 1000)
    bad_date = valid.copy()
    bad_date.loc[0, "trade_date"] = "20260201"
    with pytest.raises(Star100CollectionError, match="out-of-window"):
        validate_response(request, bad_date, 1000)


def test_canonical_hash_ignores_row_order() -> None:
    frame = pd.DataFrame(
        [
            [INDEX_CODE, "688002.SH", "20260130", 1.0],
            [INDEX_CODE, "688001.SH", "20260130", 1.0],
        ],
        columns=FIELDS["index_weight"],
    )
    assert canonical_frame_sha256("index_weight", frame) == canonical_frame_sha256(
        "index_weight", frame.iloc[::-1]
    )

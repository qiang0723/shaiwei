from __future__ import annotations

import pandas as pd

from tools.official_index_lineage.audit import _build_membership
from tools.official_index_lineage.discovery import announcement_rows, is_candidate
from tools.official_index_lineage.quality import daily_quality, months, open_dates, weight_quality


def test_archive_parser_and_candidate_policy() -> None:
    content = b'<a href="/market/sseindex/diclosure/c/c_20240720_10760020.shtml" title="x">x</a>'
    rows = announcement_rows(content)
    assert rows[0]["announcement_date"] == "20240720"
    assert is_candidate(rows[0], {rows[0]["source_url"]}) is True
    assert is_candidate(
        {"source_url": "https://www.sse.com.cn/x", "title": "关于某指数样本调整的公告"},
        set(),
    ) is True


def test_calendar_and_daily_quality() -> None:
    calendar = pd.DataFrame(
        [
            {"exchange": "SSE", "cal_date": "20240820", "is_open": 1},
            {"exchange": "SSE", "cal_date": "20240821", "is_open": 0},
        ]
    )
    expected = open_dates(calendar, "20240820", "20240821")
    daily = pd.DataFrame(
        [
            {
                "ts_code": "000699.SH", "trade_date": "20240820", "open": 1000,
                "high": 1005, "low": 995, "close": 1001, "pre_close": 1000,
                "change": 1, "pct_chg": 0.1, "vol": 1, "amount": 1,
            }
        ]
    )
    quality = daily_quality(daily, expected)
    assert quality["coverage"] == 1.0
    assert quality["ohlc_or_nonnegative_violation_count"] == 0


def test_weight_quality_detects_missing_month_even_with_same_total_snapshots() -> None:
    codes = [f"688{number:03d}.SH" for number in range(200)]
    rows = [
        {"index_code": "000699.SH", "con_code": code, "trade_date": day, "weight": 0.5}
        for day in ("20240830", "20240829")
        for code in codes
    ]
    quality, usable = weight_quality(
        pd.DataFrame(rows), ["2024-08", "2024-09"], set(codes)
    )
    assert quality["missing_months"] == ["2024-09"]
    assert quality["multi_snapshot_months"] == ["2024-08"]
    assert usable == {}


def test_membership_applies_event_before_snapshot() -> None:
    initial = {f"688{number:03d}.SH" for number in range(200)}
    events = [
        {"effective_date": "20240916", "out_code": "688000.SH", "in_code": "688900.SH"}
    ]
    daily, errors = _build_membership(initial, events, ["20240913", "20240916"])
    assert errors == []
    assert "688000.SH" in daily["20240913"]
    assert "688900.SH" in daily["20240916"]


def test_month_range_is_inclusive() -> None:
    assert len(months("2024-08", "2026-07")) == 24

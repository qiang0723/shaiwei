import json
from pathlib import Path

import pandas as pd
import pytest

from shaiwei.research.trend_swing.benchmark_lineage import (
    BenchmarkLineageError,
    CalendarEvidence,
    evaluate_quality,
    parse_history,
    validate_identity_text,
)


def _raw(rows: list[list[object]]) -> bytes:
    return json.dumps({"data": rows}, ensure_ascii=False).encode()


def _row(day: str, close: float = 100.0, code: str = "H00906") -> list[object]:
    return [
        day,
        code,
        "中证800全收益指数",
        "中证800全收益",
        "CSI 800 Total Return Index",
        "CSI 800 TR",
        close - 1,
        close + 1,
        close - 2,
        close,
        1.0,
        1.0,
        None,
        None,
        800,
        None,
    ]


def _calendar(*days: str) -> CalendarEvidence:
    return CalendarEvidence(frozenset(days), "a" * 64, 1, "b" * 64)


def test_parse_and_evaluate_complete_official_history() -> None:
    frame = parse_history(_raw([_row("2019-01-02"), _row("2019-01-03", 101.0)]))
    report = evaluate_quality(
        frame,
        frame.copy(),
        identity_text="000906价格指数 N00906净收益指数 H00906全收益指数",
        calendar=_calendar("20190102", "20190103"),
        start_date="20190101",
        end_date="20260811",
    )
    assert report["verdict"] == "GO_H00906_LINEAGE_DATA_GATE_ONLY"
    assert report["row_count"] == 2
    assert report["missing_official_open_date_count"] == 0
    assert report["strategy_effect_attempt_count"] == 0


@pytest.mark.parametrize(
    ("first", "second", "calendar", "identity"),
    [
        ([_row("2019-01-02", code="000906")], None, ("20190102",), "000906 N00906 H00906全收益"),
        ([_row("2019-01-02")], None, ("20190102", "20190103"), "000906 N00906 H00906全收益"),
        ([_row("2019-01-02")], [_row("2019-01-02", 101.0)], ("20190102",), "000906 N00906 H00906全收益"),
        ([_row("2019-01-02")], None, ("20190102",), "000906 H00906"),
    ],
)
def test_quality_gate_fails_closed(
    first: list[list[object]],
    second: list[list[object]] | None,
    calendar: tuple[str, ...],
    identity: str,
) -> None:
    left = parse_history(_raw(first))
    right = parse_history(_raw(second or first))
    with pytest.raises(BenchmarkLineageError):
        evaluate_quality(
            left,
            right,
            identity_text=identity,
            calendar=_calendar(*calendar),
            start_date="20190101",
            end_date="20260811",
        )


def test_invalid_history_shape_and_identity_fail_closed() -> None:
    with pytest.raises(BenchmarkLineageError):
        parse_history(json.dumps({"data": [["2019-01-02", "H00906"]]}).encode())
    with pytest.raises(BenchmarkLineageError):
        validate_identity_text("000906 H00906 total return")


def test_optional_ohlc_allows_official_close_only_rows() -> None:
    row = _row("2019-01-02")
    row[6:9] = [None, None, None]
    frame = parse_history(_raw([row]))
    report = evaluate_quality(
        frame,
        frame.copy(),
        identity_text="000906 N00906 H00906 Total Return",
        calendar=_calendar("20190102"),
        start_date="20190101",
        end_date="20260811",
    )
    assert report["complete_ohlc_row_count"] == 0
    assert report["checks"]["optional_ohlc_consistency_pass"]


def test_daily_frame_can_roundtrip_parquet(tmp_path: Path) -> None:
    frame = parse_history(_raw([_row("2019-01-02")]))
    target = tmp_path / "daily.parquet"
    frame.to_parquet(target, index=False)
    assert pd.read_parquet(target).equals(frame)

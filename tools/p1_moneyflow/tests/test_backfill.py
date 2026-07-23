from pathlib import Path

import pandas as pd
import pytest

from tools.p1_moneyflow.backfill import open_trade_dates, parse_args


def _calendar() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"exchange": "SSE", "cal_date": "20260722", "is_open": 1},
            {"exchange": "SSE", "cal_date": "20260723", "is_open": 1},
            {"exchange": "SSE", "cal_date": "20260724", "is_open": 1},
            {"exchange": "SSE", "cal_date": "20260725", "is_open": 0},
            {"exchange": "SZSE", "cal_date": "20260723", "is_open": 1},
        ]
    )


def test_open_dates_use_official_sse_calendar_and_range():
    assert open_trade_dates(
        _calendar(), start_date="20260723", end_date="20260725"
    ) == ["20260723", "20260724"]


def test_open_dates_refuse_invalid_or_empty_range():
    with pytest.raises(ValueError, match="must not exceed"):
        open_trade_dates(_calendar(), start_date="20260725", end_date="20260723")
    with pytest.raises(ValueError, match="no official"):
        open_trade_dates(_calendar(), start_date="20260726", end_date="20260727")


def test_backfill_execution_requires_report():
    with pytest.raises(SystemExit):
        parse_args(["--end-date", "20260723"])
    args = parse_args(
        [
            "--start-date",
            "20160101",
            "--end-date",
            "20260723",
            "--report",
            str(Path("logs/moneyflow/report.json")),
        ]
    )
    assert args.start_date == "20160101"

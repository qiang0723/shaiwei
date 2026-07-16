import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from shaiwei.config import load
from shaiwei.ingest.tushare import public_request_params
from shaiwei.pipeline.daily import (
    DailyPipelineError,
    bootstrap_watermark,
    build_market_requests,
    build_plan,
    current_watermark,
    _next_month_end,
    validate_trade_date,
)


INGEST_HEADER = [
    "batch_id",
    "ingest_time",
    "source_api",
    "params_json",
    "row_count",
    "parquet_path",
    "content_sha256",
    "operator",
]
DAILY_HEADER = [
    "run_id",
    "started_at",
    "finished_at",
    "target_trade_date",
    "status",
    "batch_count",
    "row_count",
    "data_snapshot_sha256",
    "error_type",
    "operator",
]


def _ledgers(tmp_path: Path, bootstrap_end: str = "20260710") -> tuple[Path, Path]:
    ingest = tmp_path / "ingest.csv"
    with ingest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=INGEST_HEADER)
        writer.writeheader()
        for index, api in enumerate(("daily", "adj_factor", "daily_basic", "index_daily")):
            writer.writerow(
                {
                    "batch_id": str(index),
                    "ingest_time": "2026-07-10T12:00:00+00:00",
                    "source_api": f"tushare.{api}",
                    "params_json": json.dumps({"end_date": bootstrap_end}),
                    "row_count": "1",
                    "parquet_path": "unused",
                    "content_sha256": "unused",
                    "operator": "test",
                }
            )
    daily = tmp_path / "daily.csv"
    with daily.open("w", newline="", encoding="utf-8") as handle:
        csv.DictWriter(handle, fieldnames=DAILY_HEADER).writeheader()
    return ingest, daily


def _append_daily(path: Path, trade_date: str, status: str) -> None:
    with path.open("a", newline="", encoding="utf-8") as handle:
        csv.DictWriter(handle, fieldnames=DAILY_HEADER).writerow(
            {
                "run_id": f"{trade_date}-{status}",
                "started_at": "2026-07-14T00:00:00+00:00",
                "finished_at": "2026-07-14T00:01:00+00:00",
                "target_trade_date": trade_date,
                "status": status,
                "batch_count": "5",
                "row_count": "1",
                "data_snapshot_sha256": "hash" if status == "PASS" else "",
                "error_type": "" if status == "PASS" else "RuntimeError",
                "operator": "test",
            }
        )


def test_plan_catches_up_after_sleep_and_respects_ready_cutoff(tmp_path: Path):
    ingest, daily = _ledgers(tmp_path)
    _append_daily(daily, "20260713", "FAIL")
    calendar = pd.DataFrame(
        {"cal_date": ["20260711", "20260712", "20260713", "20260714"], "is_open": [0, 0, 1, 1]}
    )
    settings = load()

    before = build_plan(
        now=datetime(2026, 7, 14, 11, 0, tzinfo=timezone.utc),  # 19:00 Shanghai
        settings=settings,
        trade_cal=calendar,
        ingest_ledger_path=ingest,
        daily_ledger_path=daily,
    )
    after = build_plan(
        now=datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc),  # 20:00 Shanghai
        settings=settings,
        trade_cal=calendar,
        ingest_ledger_path=ingest,
        daily_ledger_path=daily,
    )

    assert before.missing_trade_dates == ("20260713",)
    assert after.missing_trade_dates == ("20260713", "20260714")


def test_passed_date_advances_watermark_and_is_idempotent(tmp_path: Path):
    ingest, daily = _ledgers(tmp_path)
    _append_daily(daily, "20260713", "PASS")
    _append_daily(daily, "20260714", "PASS")
    assert bootstrap_watermark(ingest) == "20260710"
    assert current_watermark(ingest_ledger_path=ingest, daily_ledger_path=daily) == "20260714"

    plan = build_plan(
        now=datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc),
        settings=load(),
        trade_cal=pd.DataFrame({"cal_date": ["20260713", "20260714"], "is_open": [1, 1]}),
        ingest_ledger_path=ingest,
        daily_ledger_path=daily,
    )
    assert plan.missing_trade_dates == ()


def test_out_of_order_pass_does_not_hide_an_earlier_hole(tmp_path: Path):
    ingest, daily = _ledgers(tmp_path)
    _append_daily(daily, "20260714", "PASS")
    plan = build_plan(
        now=datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc),
        settings=load(),
        trade_cal=pd.DataFrame({"cal_date": ["20260713", "20260714"], "is_open": [1, 1]}),
        ingest_ledger_path=ingest,
        daily_ledger_path=daily,
    )
    assert plan.watermark == "20260710"
    assert plan.missing_trade_dates == ("20260713",)


def test_market_plan_uses_exact_trade_date_and_one_benchmark():
    settings = load()
    requests = build_market_requests(settings, "20260715")
    assert [request.api_name for request in requests] == [
        "daily",
        "adj_factor",
        "daily_basic",
        "suspend_d",
        "index_daily",
    ]
    assert all(request.params["trade_date"] == "20260715" for request in requests)
    assert requests[-1].params["ts_code"] == settings.universe.index_code
    assert all("fields" in public_request_params(request) for request in requests)


def test_calendar_refresh_horizon_is_end_of_next_month():
    assert _next_month_end(datetime(2026, 7, 16).date()).isoformat() == "2026-08-31"
    assert _next_month_end(datetime(2026, 12, 16).date()).isoformat() == "2027-01-31"


def _frame(codes: list[str], trade_date: str) -> pd.DataFrame:
    return pd.DataFrame({"ts_code": codes, "trade_date": [trade_date] * len(codes)})


def test_trade_date_validation_checks_cross_api_sets_and_bse():
    settings = load()
    settings.daily.min_market_rows = 2
    codes = ["000001.SZ", "600000.SH"]
    frames = {
        "daily": _frame(codes, "20260715"),
        "adj_factor": _frame(codes, "20260715"),
        "daily_basic": _frame(codes, "20260715"),
        "suspend_d": _frame([], "20260715"),
        "index_daily": _frame([settings.universe.index_code], "20260715"),
    }
    assert validate_trade_date(settings=settings, trade_date="20260715", request_frames=frames) == 7

    frames["daily"] = _frame(["000001.SZ", "920001.BJ"], "20260715")
    with pytest.raises(DailyPipelineError, match="BSE"):
        validate_trade_date(settings=settings, trade_date="20260715", request_frames=frames)

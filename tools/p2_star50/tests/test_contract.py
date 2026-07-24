from datetime import date

import pandas as pd
import pytest

from tools.p2_star50.contract import (
    INDEX_CODE,
    Request,
    StableCollector,
    Star50CollectionError,
    build_plan,
    canonical_frame_sha256,
    validate_response,
)
from tools.p2_star50.audit import _completed_month_end


def _daily() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ts_code": INDEX_CODE,
                "trade_date": "20200102",
                "open": 1000,
                "high": 1010,
                "low": 990,
                "close": 1005,
                "pre_close": 1000,
                "change": 5,
                "pct_chg": 0.5,
                "vol": 1,
                "amount": 2,
            }
        ]
    )


def test_build_plan_uses_year_and_month_bounded_requests():
    plan = build_plan(date(2019, 12, 31), date(2020, 2, 1))
    assert [item.api_name for item in plan] == [
        "index_daily",
        "index_daily",
        "index_weight",
        "index_weight",
        "index_weight",
    ]
    assert plan[0].start_date == "20191231"
    assert plan[-1].end_date == "20200201"
    assert all(item.params.get("ts_code", item.params.get("index_code")) == INDEX_CODE for item in plan)


def test_only_completed_weight_months_are_due():
    assert _completed_month_end("20260724") == "2026-06-30"
    assert _completed_month_end("20260731") == "2026-07-31"


def test_canonical_hash_ignores_provider_row_order():
    frame = pd.concat([_daily(), _daily().assign(trade_date="20200103")], ignore_index=True)
    assert canonical_frame_sha256("index_daily", frame) == canonical_frame_sha256(
        "index_daily", frame.iloc[::-1]
    )


def test_validate_response_rejects_bse_and_source_limit():
    request = Request("index_weight", "20200101", "20200131", "2020-01")
    frame = pd.DataFrame(
        [{"index_code": INDEX_CODE, "con_code": "920001.BJ", "trade_date": "20200102", "weight": 100}]
    )
    with pytest.raises(Star50CollectionError, match=r"\.BJ"):
        validate_response(request, frame, 6000)
    daily_request = Request("index_daily", "20200101", "20200131", "2020")
    with pytest.raises(Star50CollectionError, match="at/above"):
        validate_response(daily_request, pd.concat([_daily()] * 2), 2)


class _Client:
    def __init__(self, frames):
        self.frames = iter(frames)

    def query(self, api_name, **kwargs):
        return next(self.frames)


class _Writer:
    def write(self, **kwargs):
        return type(
            "Batch",
            (),
            {
                "batch_id": "x",
                "source_api": kwargs["source_api"],
                "row_count": len(kwargs["frame"]),
                "parquet_path": None,
                "content_sha256": "x",
            },
        )()


class _Ingest:
    min_request_interval_seconds = 0
    max_attempts = 1
    retry_base_seconds = 0
    source_row_limit = 6000


class _Settings:
    ingest = _Ingest()


def test_stability_probe_fails_before_writer_on_revision():
    changed = _daily().assign(close=1006)
    collector = StableCollector(
        client=_Client([_daily(), changed]),
        writer=_Writer(),
        settings=_Settings(),
    )
    request = Request("index_daily", "20200101", "20200131", "2020")
    with pytest.raises(Star50CollectionError, match="revision mismatch"):
        collector.collect(request)

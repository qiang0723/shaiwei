from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from shaiwei.config import load
from shaiwei.ingest.core import RawBatchWriter
from shaiwei.ingest.tushare import (
    FIELDS,
    IngestError,
    Request,
    TushareIngestor,
    build_bootstrap_plan,
    build_corporate_action_plan,
    build_financial_plan,
    build_industry_membership_plan,
    build_market_plan,
    build_namechange_plan,
    build_suspension_plan,
)


class FakeClient:
    def __init__(self, rows: int = 1):
        self.calls = []
        self.rows = rows

    def query(self, api_name: str, **kwargs):
        self.calls.append((api_name, kwargs))
        fields = kwargs["fields"].split(",")
        return pd.DataFrame({field: [None] * self.rows for field in fields})


def test_bootstrap_plan_partitions_monthly_and_defers_namechange(tmp_path: Path):
    settings = load()
    plan = build_bootstrap_plan(settings, date(2016, 2, 10))

    assert sum(request.api_name == "stock_basic" for request in plan) == 3
    assert sum(request.api_name == "index_weight" for request in plan) == 6
    assert any(request.partitions.get("period") == "2015-12" for request in plan)
    assert {
        request.params["index_code"] for request in plan if request.api_name == "index_weight"
    } == {"000906.SH", "000300.SH"}
    assert not any(request.api_name == "suspend_d" for request in plan)
    assert sum(request.api_name == "index_daily" for request in plan) == 1
    assert not any(request.api_name == "namechange" for request in plan)
    february = [request for request in plan if request.partitions.get("period") == "2016-02"]
    assert {request.params["end_date"] for request in february} == {"20160210"}


def test_ingestor_uses_explicit_fields_and_records_each_response(tmp_path: Path):
    settings = load()
    settings.ingest.min_request_interval_seconds = 0
    client = FakeClient()
    recorded = []
    writer = RawBatchWriter(tmp_path, recorder=lambda **kw: recorded.append(kw) or "id")
    request = Request("namechange", {}, {"scope": "all"})

    batches = TushareIngestor(client=client, writer=writer, settings=settings).run([request])

    assert len(batches) == 1
    assert client.calls[0][1]["fields"] == ",".join(FIELDS["namechange"])
    assert "start_date" not in client.calls[0][1]
    assert recorded[0]["params"]["fields"] == ",".join(FIELDS["namechange"])


def test_ingestor_rejects_namechange_date_filters(tmp_path: Path):
    settings = load()
    writer = RawBatchWriter(tmp_path, recorder=lambda **_: "id")
    request = Request("namechange", {"start_date": "20200101"}, {})
    with pytest.raises(IngestError, match="without date filters"):
        TushareIngestor(client=FakeClient(), writer=writer, settings=settings).run([request])


def test_ingestor_rejects_possible_source_truncation(tmp_path: Path):
    settings = load()
    settings.ingest.min_request_interval_seconds = 0
    settings.ingest.source_row_limit = 2
    writer = RawBatchWriter(tmp_path, recorder=lambda **_: "id")
    with pytest.raises(IngestError, match="possible truncation"):
        TushareIngestor(client=FakeClient(rows=2), writer=writer, settings=settings).run(
            [Request("trade_cal", {}, {})]
        )


def test_ingestor_rejects_missing_response_field(tmp_path: Path):
    class BrokenClient(FakeClient):
        def query(self, api_name: str, **kwargs):
            return pd.DataFrame({"ts_code": ["000001.SZ"]})

    settings = load()
    settings.ingest.min_request_interval_seconds = 0
    writer = RawBatchWriter(tmp_path, recorder=lambda **_: "id")
    with pytest.raises(IngestError, match="missing fields"):
        TushareIngestor(client=BrokenClient(), writer=writer, settings=settings).run(
            [Request("namechange", {}, {})]
        )


def test_ingestor_preserves_schema_for_legitimate_empty_response(tmp_path: Path):
    class EmptyClient(FakeClient):
        def query(self, api_name: str, **kwargs):
            return pd.DataFrame()

    settings = load()
    settings.ingest.min_request_interval_seconds = 0
    recorded = []
    writer = RawBatchWriter(tmp_path, recorder=lambda **kw: recorded.append(kw) or "id")
    batches = TushareIngestor(client=EmptyClient(), writer=writer, settings=settings).run(
        [Request("suspend_d", {"trade_date": "20171214"}, {"trade_date": "20171214"})]
    )
    stored = pd.read_parquet(batches[0].parquet_path)
    assert stored.empty
    assert stored.columns.tolist() == list(FIELDS["suspend_d"])
    assert recorded[0]["row_count"] == 0


def test_market_plan_is_per_stock_windowed_and_excludes_bse():
    settings = load()
    settings.ingest.history_window_years = 2
    stocks = pd.DataFrame(
        [
            {"ts_code": "600001.SH", "list_date": "20160101", "delist_date": None},
            {"ts_code": "920001.BJ", "list_date": "20160101", "delist_date": None},
        ]
    )
    plan = build_market_plan(settings, date(2020, 2, 1), stocks)
    assert {request.params["ts_code"] for request in plan} == {"600001.SH"}
    assert [request.api_name for request in plan].count("daily") == 3
    assert [request.api_name for request in plan].count("adj_factor") == 3
    assert [request.api_name for request in plan].count("daily_basic") == 3
    assert all({"ts_code", "start_date", "end_date"} == request.params.keys() for request in plan)


def test_financial_plan_explicitly_covers_three_statements():
    settings = load()
    stocks = pd.DataFrame([{"ts_code": "600001.SH", "list_date": "20160101", "delist_date": None}])
    plan = build_financial_plan(settings, date(2020, 2, 1), stocks)
    assert {request.api_name for request in plan} == {"income", "balancesheet", "cashflow"}
    for api in ("income", "balancesheet", "cashflow"):
        assert {"f_ann_date", "report_type", "update_flag"} <= set(FIELDS[api])


def test_namechange_plan_splits_by_stock_without_date_filters():
    settings = load()
    stocks = pd.DataFrame(
        [
            {"ts_code": "600001.SH", "list_date": "20160101", "delist_date": None},
            {"ts_code": "600002.SH", "list_date": "20160101", "delist_date": None},
        ]
    )
    plan = build_namechange_plan(settings, date(2020, 2, 1), stocks)
    assert [request.params for request in plan] == [
        {"ts_code": "600001.SH"},
        {"ts_code": "600002.SH"},
    ]
    assert all(not ({"start_date", "end_date"} & request.params.keys()) for request in plan)


def test_suspension_plan_is_split_by_authoritative_open_day():
    settings = load()
    calendar = pd.DataFrame(
        {"cal_date": ["20160101", "20160104", "20160105"], "is_open": [0, 1, 1]}
    )
    plan = build_suspension_plan(settings, date(2016, 1, 5), calendar)
    assert [request.params for request in plan] == [
        {"trade_date": "20160104"},
        {"trade_date": "20160105"},
    ]


def test_corporate_action_plan_is_per_stock_without_unsupported_dates():
    settings = load()
    stocks = pd.DataFrame([{"ts_code": "600001.SH", "list_date": "20160101", "delist_date": None}])
    plan = build_corporate_action_plan(settings, date(2020, 2, 1), stocks)
    assert plan == [Request("dividend", {"ts_code": "600001.SH"}, {"symbol": "600001.SH"})]
    assert {"ex_date", "div_proc", "stk_div"} <= set(FIELDS["dividend"])


def test_industry_membership_plan_requests_current_and_historical_rows():
    settings = load()
    stocks = pd.DataFrame([{"ts_code": "600001.SH", "list_date": "20160101", "delist_date": None}])
    plan = build_industry_membership_plan(settings, date(2020, 2, 1), stocks)
    assert [request.params for request in plan] == [
        {"ts_code": "600001.SH", "is_new": "Y"},
        {"ts_code": "600001.SH", "is_new": "N"},
    ]
    assert {"l1_code", "in_date", "out_date"} <= set(FIELDS["index_member_all"])

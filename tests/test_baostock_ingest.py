from pathlib import Path

import pandas as pd
import pytest

from shaiwei.ingest.baostock import BaostockStatusIngestor, request_params
from shaiwei.ingest.core import RawBatchWriter
from shaiwei.transform.availability import StatusWindow


class Result:
    error_code = "0"
    error_msg = "success"

    def __init__(self, rows=None):
        self.fields = ["date", "code", "tradestatus"]
        self.rows = rows or []
        self.index = 0

    def next(self):
        return self.index < len(self.rows)

    def get_row_data(self):
        row = self.rows[self.index]
        self.index += 1
        return row


class Client:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def login(self):
        return Result()

    def logout(self):
        return Result()

    def query_history_k_data_plus(self, **kwargs):
        self.calls.append(kwargs)
        return Result(self.rows)


def test_baostock_status_is_normalized_validated_and_recorded(tmp_path: Path):
    client = Client([
        ["2020-01-02", "sz.000001", "0"],
        ["2020-01-03", "sz.000001", "1"],
    ])
    recorded = []
    writer = RawBatchWriter(tmp_path, recorder=lambda **kwargs: recorded.append(kwargs) or "id")
    request = StatusWindow("000001.SZ", "20200102", "20200103", ("20200102", "20200103"))

    batch = BaostockStatusIngestor(writer, client).run([request])[0]
    stored = pd.read_parquet(batch.parquet_path)

    assert stored.to_dict("records") == [
        {"ts_code": "000001.SZ", "trade_date": "20200102", "trade_status": "0"},
        {"ts_code": "000001.SZ", "trade_date": "20200103", "trade_status": "1"},
    ]
    assert recorded[0]["source_api"] == "baostock.history_k_data_plus"
    assert recorded[0]["params"] == request_params(request)


def test_baostock_status_fails_closed_when_a_required_day_is_omitted(tmp_path: Path):
    client = Client([["2020-01-02", "sz.000001", "0"]])
    request = StatusWindow("000001.SZ", "20200102", "20200103", ("20200102", "20200103"))
    with pytest.raises(ValueError, match="omitted 1 required dates"):
        BaostockStatusIngestor(
            RawBatchWriter(tmp_path, recorder=lambda **_: "id"), client
        ).run([request])

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from shaiwei.ingest.core import RawBatchWriter


def test_raw_batch_is_new_file_and_recorded(tmp_path: Path):
    calls = []

    def record(**kwargs):
        calls.append(kwargs)
        return "batch-1"

    writer = RawBatchWriter(
        tmp_path,
        recorder=record,
        now=lambda: datetime(2026, 7, 15, 1, 2, 3, tzinfo=timezone.utc),
        id_factory=lambda: "nonce1",
    )
    batch = writer.write(
        source_api="tushare.trade_cal",
        params={"exchange": "SSE"},
        frame=pd.DataFrame({"cal_date": ["20260715"], "is_open": [1]}),
        partitions={"exchange": "SSE"},
    )

    assert batch.batch_id == "batch-1"
    assert batch.parquet_path.is_file()
    assert "source=tushare/api=trade_cal/exchange=SSE" in str(batch.parquet_path)
    assert pd.read_parquet(batch.parquet_path).to_dict("records") == [{"cal_date": "20260715", "is_open": 1}]
    assert calls[0]["row_count"] == 1
    assert calls[0]["content_sha256"] == batch.content_sha256


def test_raw_batch_never_overwrites_existing_file(tmp_path: Path):
    writer = RawBatchWriter(
        tmp_path,
        recorder=lambda **_: "batch",
        now=lambda: datetime(2026, 7, 15, tzinfo=timezone.utc),
        id_factory=lambda: "same",
    )
    kwargs = {
        "source_api": "tushare.trade_cal",
        "params": {},
        "frame": pd.DataFrame({"x": [1]}),
    }
    first = writer.write(**kwargs)
    with pytest.raises(FileExistsError):
        writer.write(**kwargs)
    assert pd.read_parquet(first.parquet_path)["x"].tolist() == [1]


def test_raw_batch_rolls_back_file_when_ledger_fails(tmp_path: Path):
    def fail(**_):
        raise RuntimeError("ledger unavailable")

    writer = RawBatchWriter(tmp_path, recorder=fail, id_factory=lambda: "rollback")
    with pytest.raises(RuntimeError, match="ledger unavailable"):
        writer.write(source_api="tushare.trade_cal", params={}, frame=pd.DataFrame({"x": [1]}))
    assert list(tmp_path.rglob("*.parquet")) == []

import csv
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from shaiwei import ledger as ledger_module
from shaiwei.ingest.catalog import CatalogError, canonical_params_key, committed_params_keys, load_latest_api
from shaiwei.ledger import sha256_file


HEADER = [
    "batch_id", "ingest_time", "source_api", "params_json", "row_count", "parquet_path",
    "content_sha256", "operator",
]


def _entry(path: Path, *, batch: str, ingest_time: str, value: int) -> dict[str, object]:
    pd.DataFrame({"x": [value]}).to_parquet(path)
    return {
        "batch_id": batch,
        "ingest_time": ingest_time,
        "source_api": "tushare.stock_basic",
        "params_json": '{"list_status":"L"}',
        "row_count": 1,
        "parquet_path": str(path),
        "content_sha256": sha256_file(path),
        "operator": "test",
    }


def test_catalog_uses_latest_committed_batch_per_request(tmp_path: Path):
    ledger = tmp_path / "ledger.csv"
    old = _entry(tmp_path / "old.parquet", batch="old", ingest_time="2026-01-01T00:00:00Z", value=1)
    new = _entry(tmp_path / "new.parquet", batch="new", ingest_time="2026-01-02T00:00:00Z", value=2)
    with ledger.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADER)
        writer.writeheader()
        writer.writerows([old, new])
    assert load_latest_api("tushare.stock_basic", ledger_path=ledger)["x"].tolist() == [2]


def test_catalog_resolves_legacy_path_after_project_move(monkeypatch, tmp_path: Path):
    project = tmp_path / "new-project"
    path = project / "data/raw/source=tushare/api=stock_basic/batch.parquet"
    path.parent.mkdir(parents=True)
    entry = _entry(path, batch="old-path", ingest_time="2026-01-01T00:00:00Z", value=7)
    entry["parquet_path"] = "/old/mac/shaiwei_init/data/raw/source=tushare/api=stock_basic/batch.parquet"
    ledger = tmp_path / "ledger.csv"
    with ledger.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADER)
        writer.writeheader()
        writer.writerow(entry)
    monkeypatch.setattr(ledger_module, "PROJECT_ROOT", project)

    assert load_latest_api("tushare.stock_basic", ledger_path=ledger)["x"].tolist() == [7]


def test_catalog_detects_tampered_committed_batch(tmp_path: Path):
    ledger = tmp_path / "ledger.csv"
    entry = _entry(
        tmp_path / "batch.parquet",
        batch="id",
        ingest_time=datetime.now(timezone.utc).isoformat(),
        value=1,
    )
    entry["content_sha256"] = "0" * 64
    with ledger.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADER)
        writer.writeheader()
        writer.writerow(entry)
    with pytest.raises(CatalogError, match="hash mismatch"):
        load_latest_api("tushare.stock_basic", ledger_path=ledger)


def test_resume_keys_only_include_intact_latest_batches(tmp_path: Path):
    ledger = tmp_path / "ledger.csv"
    good = _entry(
        tmp_path / "good.parquet", batch="good", ingest_time="2026-01-01T00:00:00Z", value=1
    )
    bad = _entry(
        tmp_path / "bad.parquet", batch="bad", ingest_time="2026-01-01T00:00:01Z", value=2
    )
    bad["params_json"] = '{"list_status":"D"}'
    bad["content_sha256"] = "0" * 64
    with ledger.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADER)
        writer.writeheader()
        writer.writerows([good, bad])

    assert committed_params_keys("tushare.stock_basic", ledger_path=ledger) == {
        canonical_params_key({"list_status": "L"})
    }


def test_catalog_does_not_hide_duplicate_source_rows(tmp_path: Path):
    ledger = tmp_path / "ledger.csv"
    path = tmp_path / "duplicates.parquet"
    pd.DataFrame({"x": [1, 1]}).to_parquet(path)
    entry = {
        "batch_id": "dup",
        "ingest_time": "2026-01-01T00:00:00Z",
        "source_api": "tushare.stock_basic",
        "params_json": '{"list_status":"L"}',
        "row_count": 2,
        "parquet_path": str(path),
        "content_sha256": sha256_file(path),
        "operator": "test",
    }
    with ledger.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADER)
        writer.writeheader()
        writer.writerow(entry)

    assert load_latest_api("tushare.stock_basic", ledger_path=ledger)["x"].tolist() == [1, 1]


def test_catalog_uses_payload_schema_instead_of_hive_partition_inference(tmp_path: Path):
    ledger = tmp_path / "ledger.csv"
    path = (
        tmp_path / "raw/source=tushare/api=suspend_d/trade_date=20160104"
        / "ingest_date=2026-07-15/batch.parquet"
    )
    path.parent.mkdir(parents=True)
    pd.DataFrame(
        {
            "ts_code": ["000002.SZ"],
            "trade_date": ["20160104"],
            "suspend_type": ["S"],
        }
    ).to_parquet(path)
    entry = {
        "batch_id": "partition-collision",
        "ingest_time": "2026-07-15T00:00:00Z",
        "source_api": "tushare.suspend_d",
        "params_json": '{"trade_date":"20160104"}',
        "row_count": 1,
        "parquet_path": str(path),
        "content_sha256": sha256_file(path),
        "operator": "test",
    }
    with ledger.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADER)
        writer.writeheader()
        writer.writerow(entry)

    loaded = load_latest_api("tushare.suspend_d", ledger_path=ledger)
    assert loaded.columns.tolist() == ["ts_code", "trade_date", "suspend_type"]
    assert loaded["trade_date"].tolist() == ["20160104"]

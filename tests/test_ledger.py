from pathlib import Path

import pandas as pd
import pytest

from shaiwei import ledger


def test_sha256_file_is_deterministic(tmp_path: Path):
    artifact = tmp_path / "batch.parquet"
    artifact.write_bytes(b"frozen-batch")
    assert ledger.sha256_file(artifact) == ledger.sha256_file(artifact)


def test_append_rejects_missing_fields(tmp_path: Path):
    path = tmp_path / "ledger.csv"
    path.write_text("a,b\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing fields"):
        ledger._append(path, {"a": "1"})


def test_append_rejects_unknown_fields(tmp_path: Path):
    path = tmp_path / "ledger.csv"
    path.write_text("a,b\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unknown fields"):
        ledger._append(path, {"a": "1", "b": "2", "c": "3"})


def test_ingest_ledger_rejects_sensitive_params(tmp_path: Path):
    artifact = tmp_path / "batch.parquet"
    pd.DataFrame({"x": [1]}).to_parquet(artifact)
    with pytest.raises(ValueError, match="sensitive field"):
        ledger.append_ingest_batch("tushare.daily", {"TUSHARE_TOKEN": "secret"}, 1, str(artifact))


def test_ingest_ledger_rejects_false_row_count(tmp_path: Path):
    artifact = tmp_path / "batch.parquet"
    pd.DataFrame({"x": [1]}).to_parquet(artifact)
    with pytest.raises(ValueError, match="does not match"):
        ledger.append_ingest_batch("tushare.daily", {}, 2, str(artifact))


def test_empty_ingest_snapshot_is_stable(tmp_path: Path):
    path = tmp_path / "ingest.csv"
    path.write_text(
        "batch_id,ingest_time,source_api,params_json,row_count,parquet_path,content_sha256,operator\n",
        encoding="utf-8",
    )
    assert ledger.ingest_snapshot_sha256(path) == ledger.ingest_snapshot_sha256(path)

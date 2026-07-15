from pathlib import Path

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

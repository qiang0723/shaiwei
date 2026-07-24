import csv
from pathlib import Path

import pandas as pd
import pytest

from shaiwei import ledger


def test_sha256_file_is_deterministic(tmp_path: Path):
    artifact = tmp_path / "batch.parquet"
    artifact.write_bytes(b"frozen-batch")
    assert ledger.sha256_file(artifact) == ledger.sha256_file(artifact)


def test_project_artifact_path_is_portable(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(ledger, "PROJECT_ROOT", tmp_path)
    artifact = tmp_path / "data/raw/source=tushare/batch.parquet"
    artifact.parent.mkdir(parents=True)
    artifact.touch()

    assert ledger.portable_artifact_path(artifact) == "data/raw/source=tushare/batch.parquet"
    assert ledger.resolve_artifact_path("data/raw/source=tushare/batch.parquet") == artifact


def test_legacy_absolute_raw_path_survives_project_move(monkeypatch, tmp_path: Path):
    project = tmp_path / "new-project"
    artifact = project / "data/raw/source=tushare/batch.parquet"
    artifact.parent.mkdir(parents=True)
    artifact.touch()
    monkeypatch.setattr(ledger, "PROJECT_ROOT", project)

    legacy = "/old/mac/shaiwei_init/data/raw/source=tushare/batch.parquet"
    assert ledger.resolve_artifact_path(legacy) == artifact


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


def test_append_uses_lf_line_endings(tmp_path: Path):
    path = tmp_path / "ledger.csv"
    path.write_bytes(b"a,b\n")
    ledger._append(path, {"a": "1", "b": "2"})
    assert path.read_bytes() == b"a,b\n1,2\n"


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


def test_verify_ingest_batches_rehashes_every_committed_file(tmp_path: Path):
    artifact = tmp_path / "batch.parquet"
    pd.DataFrame({"x": [1, 2]}).to_parquet(artifact)
    path = tmp_path / "ingest.csv"
    header = [
        "batch_id", "ingest_time", "source_api", "params_json", "row_count",
        "parquet_path", "content_sha256", "operator",
    ]
    row = {
        "batch_id": "batch1",
        "ingest_time": "2026-01-01T00:00:00Z",
        "source_api": "tushare.daily",
        "params_json": "{}",
        "row_count": 2,
        "parquet_path": str(artifact),
        "content_sha256": ledger.sha256_file(artifact),
        "operator": "test",
    }
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        writer.writerow(row)
    assert ledger.verify_ingest_batches(path)["row_count"] == 2
    artifact.write_bytes(b"tampered")
    with pytest.raises((ValueError, OSError)):
        ledger.verify_ingest_batches(path)


def test_p2_engineering_ledger_is_idempotent_and_fail_closed_on_collision(tmp_path: Path):
    path = tmp_path / "p2_runs.csv"
    path.write_text("run_id,status,finished_at,operator\n", encoding="utf-8")
    row = {
        "run_id": "p2-1",
        "status": "GO",
        "finished_at": "2026-07-25T00:00:00+08:00",
        "operator": "test",
    }
    assert ledger.append_p2_star50_engineering_run(path=path, **row)
    assert not ledger.append_p2_star50_engineering_run(path=path, **row)
    with pytest.raises(ValueError, match="collision"):
        ledger.append_p2_star50_engineering_run(
            path=path,
            run_id="p2-1",
            status="NO_GO",
            finished_at="2026-07-25T00:00:00+08:00",
            operator="test",
        )


def test_p2_effect_ledger_separates_protocol_and_real_runtime_timestamps(tmp_path: Path):
    path = tmp_path / "p2_effect_runs.csv"
    path.write_text(
        "run_id,protocol_frozen_at,run_finished_at,status,operator\n",
        encoding="utf-8",
    )
    row = {
        "run_id": "p2-2-one",
        "protocol_frozen_at": "2026-07-25T00:50:00+08:00",
        "run_finished_at": "2026-07-24T18:30:00+00:00",
        "status": "NO_GO",
        "operator": "test",
    }
    assert row["protocol_frozen_at"] != row["run_finished_at"]
    assert ledger.append_p2_star50_effect_run(path=path, **row)
    assert not ledger.append_p2_star50_effect_run(path=path, **row)

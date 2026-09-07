"""Secret-free release planning and white-listed paper provenance projections."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import yaml

from shaiwei.config import PROJECT_ROOT, DailyPipeline


class MetadataError(ValueError):
    """Only non-sensitive, stable error messages cross the release boundary."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def confined(root: Path, relative: str) -> Path:
    value = Path(relative)
    if value.is_absolute() or ".." in value.parts or not value.parts:
        raise MetadataError("metadata path is outside the project")
    path = root / value
    if any((root / Path(*value.parts[:i])).is_symlink()
           for i in range(1, len(value.parts) + 1)):
        raise MetadataError("symlink metadata paths are forbidden")
    if not path.resolve().is_relative_to(root.resolve()):
        raise MetadataError("metadata path escaped the project")
    return path


def load_plan(now: datetime, project_root: Path = PROJECT_ROOT):
    """Reuse the authoritative daily planner without config.load or os.environ."""
    from shaiwei.ingest.catalog import load_latest_api
    from shaiwei.pipeline.daily import build_plan

    path = confined(project_root, "config/settings.yaml")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    daily = DailyPipeline.model_validate(raw["daily"])
    ingest = confined(project_root, "ledger/ingest_batches.csv")
    with ingest.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if row.get("source_api") != "tushare.trade_cal":
                continue
            value = Path(row.get("parquet_path", ""))
            if value.is_absolute():
                try:
                    value = value.relative_to(project_root)
                except ValueError as error:
                    raise MetadataError("calendar path escaped the project") from error
            if value.parts[:2] != ("data", "raw") or value.suffix != ".parquet":
                raise MetadataError("calendar path is outside raw-data metadata")
            confined(project_root, value.as_posix())
    calendar = load_latest_api("tushare.trade_cal", ledger_path=ingest)
    return build_plan(
        now=now, settings=SimpleNamespace(daily=daily), trade_cal=calendar,
        ingest_ledger_path=ingest,
        daily_ledger_path=confined(project_root, "ledger/daily_runs.csv"),
    )


FORWARD_FIELDS = (
    "account_id", "run_id", "execution_trade_date", "signal_trade_date",
    "code_snapshot_sha256", "data_snapshot_sha256", "policy_sha256",
    "signal_sha256", "reconciliation_sha256", "artifact_sha256", "artifact_path",
    "finished_at", "operator", "freshness_status", "status",
)


def latest_forward(account: str, project_root: Path = PROJECT_ROOT) -> dict[str, str]:
    ledger = confined(project_root, "ledger/paper_runs.csv")
    with ledger.open(newline="", encoding="utf-8") as stream:
        rows = [
            {key: row.get(key, "") for key in FORWARD_FIELDS}
            for row in csv.DictReader(stream)
            if row.get("account_id") == account and row.get("status") == "PASS"
        ]
    if not rows:
        raise MetadataError("FORWARD ledger evidence is missing")
    # Never fall back to an older FORWARD if the latest PASS is BACKFILL.
    row = max(rows, key=lambda item: (item["execution_trade_date"], item["finished_at"]))
    if row["operator"] != "docker-scheduler" or row["freshness_status"] != "PASS":
        raise MetadataError("FORWARD operator or freshness differs")
    if not all(row[field] for field in FORWARD_FIELDS[:9]):
        raise MetadataError("FORWARD identity is incomplete")
    relative = Path(row["artifact_path"])
    if relative.parts[:4] != ("data", "paper", account, "runs") or relative.suffix != ".json":
        raise MetadataError("FORWARD artifact is outside the account run boundary")
    artifact = confined(project_root, row["artifact_path"])
    payload = artifact.read_bytes()
    if hashlib.sha256(payload).hexdigest() != row["artifact_sha256"]:
        raise MetadataError("FORWARD artifact hash differs")
    try:
        document = json.loads(payload)
    except (ValueError, UnicodeError) as error:
        raise MetadataError("FORWARD artifact is invalid") from error
    if not isinstance(document, dict) or document.get("mode") != "FORWARD":
        raise MetadataError("latest PASS artifact is not FORWARD")
    for field in FORWARD_FIELDS[:9]:
        if str(document.get(field, "")) != row[field]:
            raise MetadataError("FORWARD artifact identity differs")
    return {**row, "mode": "FORWARD", "artifact_verified": "true"}

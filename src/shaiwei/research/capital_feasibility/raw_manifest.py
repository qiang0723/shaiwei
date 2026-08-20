"""Metadata-only immutable raw-batch manifest for the M6-5B release."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from shaiwei.config import PROJECT_ROOT
from shaiwei.ledger import sha256_file
from shaiwei.research.model_attribution.contract import canonical_sha256
from shaiwei.research.model_attribution.effect_contract import write_once_document
from shaiwei.research.production_conversion.contract import ProtocolError


REQUIRED_APIS = (
    "tushare.daily", "tushare.index_daily", "tushare.stock_basic",
    "tushare.namechange", "tushare.suspend_d", "tushare.dividend",
    "tushare.trade_cal",
)


def _relative_raw_path(value: str, project_root: Path) -> str:
    path = (project_root / value).resolve()
    raw = (project_root / "data/raw").resolve()
    if path == raw or raw not in path.parents or path.is_symlink():
        raise ProtocolError("M6-5B raw batch path escapes immutable raw root")
    return path.relative_to(project_root).as_posix()


def build_manifest_document(
    ledger_path: Path,
    *,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    rows = pd.read_csv(ledger_path, dtype=str, keep_default_na=False)
    required = {"source_api", "params_json", "ingest_time", "parquet_path", "row_count", "content_sha256"}
    if required - set(rows):
        raise ProtocolError("M6-5B ingest ledger schema differs")
    rows = rows.loc[rows["source_api"].isin(REQUIRED_APIS)].copy()
    if set(rows["source_api"]) != set(REQUIRED_APIS):
        raise ProtocolError("M6-5B required raw source is absent")
    rows["_time"] = pd.to_datetime(rows["ingest_time"], utc=True, errors="raise")
    rows["_params"] = rows["params_json"].map(
        lambda value: json.dumps(json.loads(value), sort_keys=True, separators=(",", ":"))
    )
    latest = rows.sort_values("_time").drop_duplicates(["source_api", "_params"], keep="last")
    entries: list[dict[str, Any]] = []
    for row in latest.sort_values(["source_api", "parquet_path"]).itertuples(index=False):
        path = _relative_raw_path(str(row.parquet_path), project_root)
        if len(str(row.content_sha256)) != 64 or int(row.row_count) < 0:
            raise ProtocolError("M6-5B raw batch metadata is invalid")
        entries.append({
            "source_api": str(row.source_api),
            "path": path,
            "sha256": str(row.content_sha256),
            "row_count": int(row.row_count),
            "ingest_time": str(row.ingest_time),
            "params_sha256": canonical_sha256(json.loads(str(row.params_json))),
        })
    counts = {api: sum(entry["source_api"] == api for entry in entries) for api in REQUIRED_APIS}
    return {
        "schema_version": "m6-head30-500k-raw-batch-manifest-v1",
        "required_source_apis": list(REQUIRED_APIS),
        "entry_count": len(entries),
        "api_entry_counts": counts,
        "entries_sha256": canonical_sha256(entries),
        "entries": entries,
        "semantic_values_read": False,
    }


def write_manifest(ledger_path: Path, output: Path) -> tuple[dict[str, Any], str, bool]:
    document = build_manifest_document(ledger_path)
    digest, reused = write_once_document(output, document)
    return document, digest, reused


def load_and_verify_manifest(path: Path, *, project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ProtocolError("M6-5B raw manifest is invalid") from error
    entries = document.get("entries") if isinstance(document, dict) else None
    if (
        document.get("schema_version") != "m6-head30-500k-raw-batch-manifest-v1"
        or document.get("required_source_apis") != list(REQUIRED_APIS)
        or not isinstance(entries, list)
        or document.get("entry_count") != len(entries)
        or document.get("entries_sha256") != canonical_sha256(entries)
    ):
        raise ProtocolError("M6-5B raw manifest contract differs")
    for entry in entries:
        path_value = _relative_raw_path(str(entry.get("path", "")), project_root)
        payload = project_root / path_value
        if not payload.is_file() or sha256_file(payload) != entry.get("sha256"):
            raise ProtocolError(f"M6-5B raw batch hash differs: {path_value}")
        if pq.read_metadata(payload).num_rows != int(entry.get("row_count", -1)):
            raise ProtocolError(f"M6-5B raw batch row count differs: {path_value}")
    return document

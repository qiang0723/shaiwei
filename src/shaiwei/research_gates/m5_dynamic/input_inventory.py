"""Metadata-only, content-addressed inventory for a future approved M5 data release."""

from __future__ import annotations

import csv
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from .contract import (
    API_FIELDS,
    PROTOCOL_SCOPE_SHA256,
    REQUIRED_APIS,
    M5DataProtocol,
    M5GateError,
    canonical_json,
    sha256_file,
    sha256_json,
)


LEDGER_COLUMNS = {
    "batch_id",
    "ingest_time",
    "source_api",
    "params_json",
    "row_count",
    "parquet_path",
    "content_sha256",
    "operator",
}


def _canonical_params(value: str) -> str:
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise M5GateError("ingest ledger params_json must contain an object")
    return canonical_json(parsed)


def _relative_file(project_root: Path, raw_path: str) -> tuple[Path, str]:
    path = Path(raw_path)
    if not path.is_absolute():
        path = project_root / path
    if path.is_symlink():
        raise M5GateError("M5 input inventory forbids symlinked artifacts")
    try:
        resolved = path.resolve(strict=True)
        relative = resolved.relative_to(project_root.resolve(strict=True)).as_posix()
    except (FileNotFoundError, ValueError) as exc:
        raise M5GateError("M5 input artifact is missing or outside project root") from exc
    if not resolved.is_file():
        raise M5GateError("M5 input artifact is not a regular file")
    return resolved, relative


def _parquet_metadata(path: Path) -> tuple[int, list[str]]:
    metadata = pq.read_metadata(path)
    return int(metadata.num_rows), list(metadata.schema.names)


def _latest_rows(ledger_path: Path) -> dict[str, list[dict[str, str]]]:
    with ledger_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if set(reader.fieldnames or ()) != LEDGER_COLUMNS:
            raise M5GateError("ingest ledger header differs from the frozen inventory contract")
        rows = [dict(row) for row in reader if row["source_api"] in REQUIRED_APIS]
    grouped: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        params = _canonical_params(row["params_json"])
        try:
            recorded = datetime.fromisoformat(row["ingest_time"])
        except ValueError as exc:
            raise M5GateError("ingest ledger time is invalid") from exc
        if recorded.tzinfo is None:
            raise M5GateError("ingest ledger time lacks timezone")
        key = (row["source_api"], params)
        current = grouped.get(key)
        if current is None or datetime.fromisoformat(current["ingest_time"]) < recorded:
            grouped[key] = {**row, "params_json": params}
    result = {api: [] for api in REQUIRED_APIS}
    for (api, _), row in sorted(grouped.items()):
        result[api].append(row)
    if any(not rows for rows in result.values()):
        missing = [api for api, rows in result.items() if not rows]
        raise M5GateError(f"M5 input inventory lacks committed APIs: {missing}")
    return result


def build_input_manifest(
    protocol: M5DataProtocol,
    *,
    project_root: Path,
    ledger_path: Path,
    created_at: str,
) -> dict[str, Any]:
    selected = _latest_rows(ledger_path)
    sources = []
    seen_batch_ids: set[str] = set()
    for api in REQUIRED_APIS:
        batches = []
        for row in selected[api]:
            path, relative = _relative_file(project_root, row["parquet_path"])
            row_count, fields = _parquet_metadata(path)
            if row_count != int(row["row_count"]):
                raise M5GateError("M5 input batch row count differs from ledger")
            content_sha = sha256_file(path)
            if content_sha != row["content_sha256"]:
                raise M5GateError("M5 input batch content hash differs from ledger")
            if not set(API_FIELDS[api]) <= set(fields):
                raise M5GateError("M5 input batch schema lacks required allowlisted fields")
            batch_id = row["batch_id"]
            if not batch_id or batch_id in seen_batch_ids:
                raise M5GateError("M5 input batch identity is empty or duplicated")
            seen_batch_ids.add(batch_id)
            identity = {
                "batch_id": batch_id,
                "source_api": api,
                "params_json": row["params_json"],
                "ingest_time": row["ingest_time"],
                "relative_path": relative,
                "row_count": row_count,
                "bytes": os.stat(path).st_size,
                "content_sha256": content_sha,
                "operator": row["operator"],
            }
            batches.append(
                {
                    "batch_id": batch_id,
                    "batch_identity_sha256": sha256_json(identity),
                    "relative_path": relative,
                    "content_sha256": content_sha,
                    "request_params_sha256": sha256_json(json.loads(row["params_json"])),
                    "row_count": row_count,
                    "bytes": os.stat(path).st_size,
                    "schema_fields": fields,
                    "ingest_time": row["ingest_time"],
                }
            )
        sources.append(
            {
                "source_api": api,
                "selection_sha256": sha256_json(batches),
                "batches": batches,
            }
        )
    memberships = []
    seen_paths: dict[str, tuple[int, int, str, list[str]]] = {}
    for universe in protocol.universes:
        path, relative = _relative_file(project_root, universe.membership_relative_path)
        if relative not in seen_paths:
            row_count, fields = _parquet_metadata(path)
            seen_paths[relative] = (
                row_count,
                os.stat(path).st_size,
                sha256_file(path),
                fields,
            )
        row_count, size, content_sha, fields = seen_paths[relative]
        if content_sha != universe.membership_sha256:
            raise M5GateError("M5 membership hash differs from frozen protocol")
        memberships.append(
            {
                "universe_id": universe.universe_id,
                "relative_path": relative,
                "content_sha256": content_sha,
                "row_count": row_count,
                "bytes": size,
                "schema_fields": fields,
                "filter": (
                    None
                    if universe.filter_column is None
                    else {"column": universe.filter_column, "value": universe.filter_value}
                ),
            }
        )
    document = {
        "schema_version": "m5-data-input-v1",
        "created_at": created_at,
        "protocol_scope_sha256": PROTOCOL_SCOPE_SHA256,
        "protocol_sha256": protocol.sha256,
        "semantic_rows_read": False,
        "ledger_selection_scope": list(REQUIRED_APIS),
        "sources": sources,
        "memberships": memberships,
    }
    if _latest_rows(ledger_path) != selected:
        raise M5GateError("M5 relevant ledger selection changed while inventory was built")
    return document


def write_manifest_once(path: Path, document: dict[str, Any]) -> str:
    payload = (canonical_json(document) + "\n").encode("utf-8")
    if path.exists():
        if path.read_bytes() != payload:
            raise M5GateError("existing M5 input manifest differs")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    return sha256_file(path)

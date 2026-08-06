"""Metadata-only inventory for a future approved M5 source-lineage gate."""

from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from .contract import API_FIELDS, M5GateError, canonical_json, sha256_file, sha256_json
from .lineage_contract import LineageProtocol, SOURCE_APIS


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


def _utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise M5GateError("M5 lineage inventory time is invalid") from exc
    if parsed.tzinfo is None:
        raise M5GateError("M5 lineage inventory time lacks timezone")
    return parsed.astimezone(timezone.utc)


def _params(value: str) -> tuple[str, str]:
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise M5GateError("M5 lineage ledger params must be an object")
    return canonical_json(parsed), sha256_json(parsed)


def _project_file(project_root: Path, raw_path: str) -> tuple[Path, str]:
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = project_root / candidate
    if candidate.is_symlink():
        raise M5GateError("M5 lineage inventory forbids symlinks")
    try:
        path = candidate.resolve(strict=True)
        relative = path.relative_to(project_root.resolve(strict=True)).as_posix()
    except (FileNotFoundError, ValueError) as exc:
        raise M5GateError("M5 lineage batch is missing or outside project") from exc
    if not path.is_file():
        raise M5GateError("M5 lineage batch is not a regular file")
    return path, relative


def _batch(project_root: Path, row: dict[str, str]) -> dict[str, Any]:
    path, relative = _project_file(project_root, row["parquet_path"])
    metadata = pq.read_metadata(path)
    fields = list(metadata.schema.names)
    api = row["source_api"]
    if not set(API_FIELDS[api]) <= set(fields):
        raise M5GateError("M5 lineage batch schema lacks frozen statement fields")
    content_sha = sha256_file(path)
    row_count = int(metadata.num_rows)
    if content_sha != row["content_sha256"] or row_count != int(row["row_count"]):
        raise M5GateError("M5 lineage batch differs from ingest ledger")
    params_json, params_sha = _params(row["params_json"])
    identity = {
        "batch_id": row["batch_id"],
        "source_api": api,
        "params_json": params_json,
        "ingest_time": row["ingest_time"],
        "relative_path": relative,
        "row_count": row_count,
        "bytes": os.stat(path).st_size,
        "content_sha256": content_sha,
        "operator": row["operator"],
    }
    return {
        "batch_id": row["batch_id"],
        "batch_identity_sha256": sha256_json(identity),
        "relative_path": relative,
        "content_sha256": content_sha,
        "request_params_sha256": params_sha,
        "row_count": row_count,
        "bytes": os.stat(path).st_size,
        "schema_fields": fields,
        "ingest_time": _utc(row["ingest_time"]).isoformat(),
    }


def _ledger_rows(ledger_path: Path, *, created_at: str) -> list[dict[str, str]]:
    cutoff = _utc(created_at)
    with ledger_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if set(reader.fieldnames or ()) != LEDGER_COLUMNS:
            raise M5GateError("M5 lineage ingest ledger header differs")
        rows = [
            dict(row)
            for row in reader
            if row["source_api"] in SOURCE_APIS and _utc(row["ingest_time"]) <= cutoff
        ]
    identities = [row["batch_id"] for row in rows]
    if not rows or any(not item for item in identities) or len(identities) != len(set(identities)):
        raise M5GateError("M5 lineage history batch identities are empty or duplicated")
    return sorted(
        rows,
        key=lambda row: (SOURCE_APIS.index(row["source_api"]), _utc(row["ingest_time"]), row["batch_id"]),
    )


def _group_batches(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = []
    for api in SOURCE_APIS:
        batches = [item for item in rows if item["source_api"] == api]
        if not batches:
            raise M5GateError(f"M5 lineage inventory lacks {api}")
        public = [{key: value for key, value in item.items() if key != "source_api"} for item in batches]
        grouped.append(
            {
                "source_api": api,
                "selection_sha256": sha256_json(public),
                "batches": public,
            }
        )
    return grouped


def _anchor_sources(
    project_root: Path,
    *,
    prior_manifest_path: Path,
    prior_release_path: Path,
) -> list[dict[str, Any]]:
    prior_release = json.loads(prior_release_path.read_text(encoding="utf-8"))
    prior_manifest = json.loads(prior_manifest_path.read_text(encoding="utf-8"))
    scope = prior_release.get("scope") or {}
    if (
        scope.get("input_manifest_sha256") != sha256_json(prior_manifest)
        or prior_manifest.get("semantic_rows_read") is not False
    ):
        raise M5GateError("M5 lineage anchor manifest differs from prior release")
    rows = []
    for source in prior_manifest.get("sources", []):
        api = source.get("source_api")
        if api not in SOURCE_APIS:
            continue
        for item in source.get("batches", []):
            path, relative = _project_file(project_root, item["relative_path"])
            metadata = pq.read_metadata(path)
            if (
                sha256_file(path) != item["content_sha256"]
                or int(metadata.num_rows) != int(item["row_count"])
                or list(metadata.schema.names) != list(item["schema_fields"])
            ):
                raise M5GateError("M5 lineage anchor batch differs")
            rows.append({"source_api": api, **item, "relative_path": relative})
    return _group_batches(rows)


def build_lineage_input_manifest(
    protocol: LineageProtocol,
    *,
    project_root: Path,
    ledger_path: Path,
    prior_manifest_path: Path,
    prior_release_path: Path,
    created_at: str,
) -> dict[str, Any]:
    selected = _ledger_rows(ledger_path, created_at=created_at)
    history = [_batch(project_root, row) | {"source_api": row["source_api"]} for row in selected]
    prior = protocol.document["prior_authoritative_data_no_go"]
    document = {
        "schema_version": "m5-source-lineage-input-v1",
        "created_at": _utc(created_at).isoformat(),
        "protocol_scope_sha256": protocol.scope_document["protocol_scope_sha256"],
        "semantic_rows_read": False,
        "prior_conflict_identity": {
            "case_id": prior["case_id"],
            "release_scope_sha256": prior["release_scope_sha256"],
            "conflict_group_count": prior["conflict_group_count"],
            "conflict_groups_by_table": prior["conflict_groups_by_table"],
        },
        "ledger_selection_scope": list(SOURCE_APIS),
        "anchor_sources": _anchor_sources(
            project_root,
            prior_manifest_path=prior_manifest_path,
            prior_release_path=prior_release_path,
        ),
        "history_sources": _group_batches(history),
        "authoritative_evidence": [],
    }
    if _ledger_rows(ledger_path, created_at=created_at) != selected:
        raise M5GateError("M5 lineage ledger selection changed during inventory")
    return document


def write_manifest_once(path: Path, document: dict[str, Any]) -> str:
    payload = (canonical_json(document) + "\n").encode("utf-8")
    if path.exists():
        if path.read_bytes() != payload:
            raise M5GateError("existing M5 lineage input manifest differs")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    return sha256_file(path)

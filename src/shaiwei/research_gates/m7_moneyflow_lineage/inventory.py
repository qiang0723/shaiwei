"""Metadata-only inventory for one future approved M7 lineage read."""

from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from shaiwei.research_gates.m7_moneyflow.contract import canonical_json, sha256_file, sha256_json

from .contract import LineageError, LineageProtocol, SOURCE_COLUMNS, safe_relative


LEDGER_FIELDS = {
    "batch_id",
    "ingest_time",
    "source_api",
    "params_json",
    "row_count",
    "parquet_path",
    "content_sha256",
    "operator",
}


def _params(value: str) -> tuple[str, dict[str, Any]]:
    item = json.loads(value)
    if not isinstance(item, dict):
        raise LineageError("lineage request parameters must be an object")
    return canonical_json(item), item


def _latest_rows(ledger: Path, *, cutoff: datetime) -> dict[str, list[dict[str, Any]]]:
    with ledger.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if set(reader.fieldnames or ()) != LEDGER_FIELDS:
            raise LineageError("lineage ingest ledger header differs")
        rows = [dict(row) for row in reader if row["source_api"] in SOURCE_COLUMNS]
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        try:
            recorded = datetime.fromisoformat(row["ingest_time"])
        except ValueError as exc:
            raise LineageError("lineage ingest timestamp is invalid") from exc
        if recorded.tzinfo is None or recorded > cutoff:
            continue
        key, params = _params(row["params_json"])
        identity = (row["source_api"], key)
        current = latest.get(identity)
        if current is not None and current["_recorded"] == recorded:
            tied = (row["row_count"], row["content_sha256"], row["parquet_path"])
            prior = (current["row_count"], current["content_sha256"], current["parquet_path"])
            if tied != prior:
                raise LineageError("lineage latest request has a conflicting timestamp tie")
        if current is None or current["_recorded"] < recorded:
            latest[identity] = {**row, "_key": key, "_params": params, "_recorded": recorded}
    grouped = {source: [] for source in SOURCE_COLUMNS}
    for row in latest.values():
        grouped[row["source_api"]].append(row)
    for rows_for_source in grouped.values():
        rows_for_source.sort(key=lambda item: item["_key"])
    return grouped


def _overlaps(params: dict[str, Any], start: str, end: str) -> bool:
    if "trade_date" in params:
        return start <= str(params["trade_date"]) <= end
    request_start = str(params.get("start_date", ""))
    request_end = str(params.get("end_date", ""))
    return bool(request_start and request_end and request_start <= end and request_end >= start)


def _bound(root: Path, value: str) -> tuple[Path, str]:
    path = Path(value)
    if not path.is_absolute():
        path = root / safe_relative(value, "lineage raw path")
    if path.is_symlink():
        raise LineageError("lineage inventory forbids symlinks")
    try:
        resolved = path.resolve(strict=True)
        relative = resolved.relative_to(root.resolve(strict=True)).as_posix()
    except (FileNotFoundError, ValueError) as exc:
        if path.is_absolute() and "data/raw/" in path.as_posix():
            return _bound(root, "data/raw/" + path.as_posix().split("data/raw/", 1)[1])
        raise LineageError("lineage raw file is missing or outside project root") from exc
    if not resolved.is_file():
        raise LineageError("lineage raw input is not a regular file")
    return resolved, relative


def _batch(root: Path, row: dict[str, Any], source_api: str, index: int) -> dict[str, Any]:
    path, relative = _bound(root, row["parquet_path"])
    metadata = pq.read_metadata(path)
    fields = list(metadata.schema.names)
    projected = SOURCE_COLUMNS[source_api]
    if metadata.num_rows != int(row["row_count"]) or not set(projected) <= set(fields):
        raise LineageError("lineage footer row count or schema differs")
    content_sha = sha256_file(path)
    if content_sha != row["content_sha256"]:
        raise LineageError("lineage source content hash differs")
    return {
        "request_params_sha256": sha256_json(row["_params"]),
        "relative_path": relative,
        "bundle_relative_path": f"sources/{source_api}/{index:05d}.parquet",
        "row_count": int(row["row_count"]),
        "bytes": path.stat().st_size,
        "content_sha256": content_sha,
        "schema_fields": fields,
    }


def _predecessor(root: Path, protocol: LineageProtocol) -> dict[str, Any]:
    relative = protocol.document["input_contract"]["predecessor_bundle"]["path"]
    bundle = root / safe_relative(relative, "predecessor bundle")
    if bundle.is_symlink() or not bundle.is_dir():
        raise LineageError("lineage predecessor bundle is unavailable")
    manifest_path = bundle / "bundle_manifest.json"
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise LineageError("lineage predecessor bundle manifest differs")
    expected = protocol.document["predecessor"]
    if (
        sha256_file(manifest_path) != expected["input_bundle_manifest_sha256"]
        or document.get("input_manifest_sha256") != expected["input_manifest_sha256"]
    ):
        raise LineageError("lineage predecessor bundle identity differs")
    return {
        "relative_path": relative,
        "input_manifest_sha256": document["input_manifest_sha256"],
        "bundle_manifest_sha256": sha256_file(manifest_path),
        "file_count": int(document["file_count"]),
    }


def build_manifest(
    protocol: LineageProtocol,
    *,
    project_root: Path,
    ledger_path: Path,
    created_at: str,
) -> dict[str, Any]:
    cutoff = datetime.fromisoformat(protocol.document["input_contract"]["metadata_inventory_cutoff_utc"])
    if cutoff.tzinfo is None:
        raise LineageError("lineage metadata cutoff lacks timezone")
    grouped = _latest_rows(ledger_path, cutoff=cutoff)
    start = protocol.document["scope"]["source_date_start"]
    end = protocol.document["scope"]["source_date_end"]
    sources: dict[str, Any] = {}
    for source_api, rows in grouped.items():
        selected = [row for row in rows if _overlaps(row["_params"], start, end)]
        if not selected:
            raise LineageError(f"lineage inventory has no {source_api} batches")
        batches = [_batch(project_root, row, source_api, index) for index, row in enumerate(selected)]
        sources[source_api] = {
            "projected_columns": list(SOURCE_COLUMNS[source_api]),
            "selected_batch_count": len(batches),
            "selected_row_count": sum(item["row_count"] for item in batches),
            "selected_bytes": sum(item["bytes"] for item in batches),
            "catalog_sha256": sha256_json(batches),
            "batches": batches,
        }
    document = {
        "schema_version": "m7-moneyflow-gap-lineage-input-v1",
        "created_at": created_at,
        "metadata_cutoff_utc": cutoff.isoformat(),
        "protocol_sha256": protocol.sha256,
        "semantic_rows_read": False,
        "predecessor_bundle": _predecessor(project_root, protocol),
        "sources": sources,
    }
    repeated = _latest_rows(ledger_path, cutoff=cutoff)
    for source_api in SOURCE_COLUMNS:
        first = [(row["_key"], row["row_count"], row["content_sha256"]) for row in grouped[source_api]]
        second = [(row["_key"], row["row_count"], row["content_sha256"]) for row in repeated[source_api]]
        if first != second:
            raise LineageError("lineage ledger changed while inventory was built")
    return document


def write_once(path: Path, document: dict[str, Any]) -> str:
    payload = (canonical_json(document) + "\n").encode()
    if path.exists():
        if path.read_bytes() != payload:
            raise LineageError("existing lineage manifest differs")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    return sha256_file(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        protocol = LineageProtocol.load(args.protocol, project_root=args.project_root)
        document = build_manifest(
            protocol,
            project_root=args.project_root,
            ledger_path=args.ledger,
            created_at=args.created_at,
        )
        physical = write_once(args.output, document)
    except (LineageError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(canonical_json({"status": "FAIL", "error_class": type(error).__name__, "message": str(error)}))
        return 2
    print(
        canonical_json(
            {
                "status": "PASS",
                "input_manifest_sha256": sha256_json(document),
                "input_manifest_physical_sha256": physical,
                "semantic_rows_read": False,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

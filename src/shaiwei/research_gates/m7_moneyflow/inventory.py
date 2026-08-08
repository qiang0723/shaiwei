"""Metadata-only inventory for the future approved M7 real key read."""

from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from .contract import (
    MEMBERSHIP_COLUMNS,
    PROJECTED_SOURCE_COLUMNS,
    SOURCE_API,
    M7GateError,
    M7Protocol,
    canonical_json,
    safe_relative,
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


def _canonical_params(value: str) -> tuple[str, dict[str, Any]]:
    document = json.loads(value)
    if not isinstance(document, dict):
        raise M7GateError("M7 ledger params_json must contain an object")
    return canonical_json(document), document


def _latest_rows(ledger_path: Path) -> list[dict[str, Any]]:
    with ledger_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if set(reader.fieldnames or ()) != LEDGER_COLUMNS:
            raise M7GateError("M7 ingest ledger header differs")
        candidates = [dict(row) for row in reader if row["source_api"] == SOURCE_API]
    latest: dict[str, dict[str, Any]] = {}
    for row in candidates:
        params_key, params = _canonical_params(row["params_json"])
        try:
            recorded = datetime.fromisoformat(row["ingest_time"])
        except ValueError as exc:
            raise M7GateError("M7 ingest ledger timestamp is invalid") from exc
        if recorded.tzinfo is None:
            raise M7GateError("M7 ingest ledger timestamp lacks timezone")
        current = latest.get(params_key)
        if current is None or current["_recorded"] < recorded:
            latest[params_key] = {
                **row,
                "_params_key": params_key,
                "_params": params,
                "_recorded": recorded,
            }
    return sorted(latest.values(), key=lambda item: item["_params_key"])


def catalog_sha256(rows: list[dict[str, Any]]) -> str:
    digest = __import__("hashlib").sha256()
    for row in sorted(rows, key=lambda item: (item["source_api"], item["_params_key"])):
        identity = {
            "source_api": row["source_api"],
            "params_key": row["_params_key"],
            "row_count": int(row["row_count"]),
            "content_sha256": row["content_sha256"],
            "parquet_path": row["parquet_path"],
        }
        digest.update(canonical_json(identity).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _bound_file(project_root: Path, raw_path: str) -> tuple[Path, str]:
    path = Path(raw_path)
    if not path.is_absolute():
        path = project_root / safe_relative(raw_path, "input artifact")
    if path.is_symlink():
        raise M7GateError("M7 input inventory forbids symlinked artifacts")
    try:
        resolved = path.resolve(strict=True)
        relative = resolved.relative_to(project_root.resolve(strict=True)).as_posix()
    except (FileNotFoundError, ValueError) as exc:
        if path.is_absolute() and "data/raw" in path.as_posix():
            suffix = path.as_posix().split("data/raw/", 1)[1]
            return _bound_file(project_root, f"data/raw/{suffix}")
        raise M7GateError("M7 input artifact is missing or outside project root") from exc
    if not resolved.is_file():
        raise M7GateError("M7 input artifact is not a regular file")
    return resolved, relative


def _json_evidence(path: Path, expected_sha: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or sha256_file(path) != expected_sha:
        raise M7GateError("M7 frozen JSON evidence identity differs")
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise M7GateError("M7 frozen JSON evidence must contain an object")
    return document


def _calendar_and_quarantine(
    protocol: M7Protocol, project_root: Path
) -> tuple[list[str], list[str], dict[str, dict[str, Any]]]:
    source = protocol.document["moneyflow_input"]
    quality_path = project_root / safe_relative(source["full_quality_report_path"], "quality report")
    quarantine_path = project_root / safe_relative(source["quarantine_report_path"], "quarantine report")
    quality = _json_evidence(quality_path, source["full_quality_report_sha256"])
    quarantine = _json_evidence(quarantine_path, source["quarantine_report_sha256"])
    dates = [str(item["trade_date"]) for item in quality.get("per_trade_date", [])]
    if dates != sorted(set(dates)):
        raise M7GateError("M7 P1 quality calendar is duplicated or unordered")
    source_summary = quality.get("source") or {}
    if (
        source_summary.get("latest_catalog_sha256") != source["audited_catalog_sha256"]
        or source_summary.get("latest_batch_count") != source["audited_trade_date_count"]
        or source_summary.get("latest_row_count") != source["audited_row_count"]
        or source_summary.get("revision_observed_count") != 0
        or source_summary.get("saturated_response_count") != 0
    ):
        raise M7GateError("M7 P1 source audit summary differs")
    quarantine_dates = [
        str(item["trade_date"])
        for item in (quarantine.get("evaluation") or {}).get("quarantined_source_dates", [])
    ]
    if len(quarantine_dates) != source["quarantined_source_date_count"]:
        raise M7GateError("M7 quarantine count differs")
    evidence = {
        "full_quality_report": _file_identity(project_root, quality_path),
        "quarantine_report": _file_identity(project_root, quarantine_path),
    }
    return dates, quarantine_dates, evidence


def _file_identity(project_root: Path, path: Path) -> dict[str, Any]:
    resolved, relative = _bound_file(project_root, str(path))
    return {"relative_path": relative, "bytes": resolved.stat().st_size, "sha256": sha256_file(resolved)}


def _source_batch(project_root: Path, row: dict[str, Any], trade_date: str) -> dict[str, Any]:
    params = row["_params"]
    if set(params) != {"fields", "trade_date"} or str(params["trade_date"]) != trade_date:
        raise M7GateError("M7 source request parameters differ")
    path, relative = _bound_file(project_root, row["parquet_path"])
    metadata = pq.read_metadata(path)
    fields = list(metadata.schema.names)
    if metadata.num_rows != int(row["row_count"]) or not set(PROJECTED_SOURCE_COLUMNS) <= set(fields):
        raise M7GateError("M7 source footer row count or schema differs")
    content_sha = sha256_file(path)
    if content_sha != row["content_sha256"]:
        raise M7GateError("M7 source batch content hash differs")
    return {
        "trade_date": trade_date,
        "batch_id": row["batch_id"],
        "request_params_sha256": sha256_json(params),
        "relative_path": relative,
        "row_count": int(row["row_count"]),
        "bytes": path.stat().st_size,
        "content_sha256": content_sha,
        "schema_fields": fields,
    }


def build_input_manifest(
    protocol: M7Protocol,
    *,
    project_root: Path,
    ledger_path: Path,
    created_at: str,
) -> dict[str, Any]:
    latest = _latest_rows(ledger_path)
    source_config = protocol.document["moneyflow_input"]
    if (
        len(latest) != source_config["audited_trade_date_count"]
        or sum(int(row["row_count"]) for row in latest) != source_config["audited_row_count"]
        or catalog_sha256(latest) != source_config["audited_catalog_sha256"]
    ):
        raise M7GateError("M7 current latest catalog differs from frozen P1 audit")
    calendar, quarantine_dates, evidence = _calendar_and_quarantine(protocol, project_root)
    pit = protocol.pit
    source_dates = [date for date in calendar if pit["source_start_date"] <= date <= pit["source_end_date"]]
    feature_dates = [date for date in calendar if pit["feature_start_date"] <= date <= pit["feature_end_date"]]
    if not source_dates or len(source_dates) != len(feature_dates):
        raise M7GateError("M7 source and feature date domains do not form a one-day PIT mapping")
    calendar_positions = {date: index for index, date in enumerate(calendar)}
    if any(calendar[calendar_positions[feature] - 1] != source for source, feature in zip(source_dates, feature_dates)):
        raise M7GateError("M7 source dates are not the prior official dates for features")
    by_date = {str(row["_params"].get("trade_date", "")): row for row in latest}
    if set(source_dates) - set(by_date):
        raise M7GateError("M7 audited source catalog misses a required source date")
    batches = [_source_batch(project_root, by_date[date], date) for date in source_dates]
    membership_config = protocol.document["membership_input"]
    membership_path, membership_relative = _bound_file(
        project_root, membership_config["daily_membership_path"]
    )
    membership_metadata = pq.read_metadata(membership_path)
    membership_fields = list(membership_metadata.schema.names)
    if (
        membership_metadata.num_rows != membership_config["daily_membership_row_count"]
        or membership_fields != list(MEMBERSHIP_COLUMNS)
        or sha256_file(membership_path) != membership_config["daily_membership_sha256"]
    ):
        raise M7GateError("M7 M3 membership footer or content identity differs")
    document = {
        "schema_version": "m7-moneyflow-data-input-manifest-v1",
        "created_at": created_at,
        "protocol_scope_sha256": protocol.build_document["protocol_scope_sha256"],
        "protocol_sha256": protocol.sha256,
        "build_contract_sha256": protocol.build_sha256,
        "semantic_rows_read": False,
        "source_audit": {
            "source_api": SOURCE_API,
            "full_catalog_sha256": catalog_sha256(latest),
            "full_catalog_batch_count": len(latest),
            "full_catalog_row_count": sum(int(row["row_count"]) for row in latest),
            "selected_catalog_sha256": sha256_json(batches),
            "selected_source_date_count": len(source_dates),
            "selected_source_start_date": source_dates[0],
            "selected_source_end_date": source_dates[-1],
            "feature_date_count": len(feature_dates),
            "feature_start_date": feature_dates[0],
            "feature_end_date": feature_dates[-1],
            "quarantined_source_dates_in_scope": sum(date in set(quarantine_dates) for date in source_dates),
            "revision_observed_count": 0,
            "saturated_response_count": 0,
        },
        "source_batches": batches,
        "membership": {
            "relative_path": membership_relative,
            "content_sha256": sha256_file(membership_path),
            "row_count": membership_metadata.num_rows,
            "bytes": membership_path.stat().st_size,
            "schema_fields": membership_fields,
        },
        "evidence_files": evidence,
    }
    if catalog_sha256(_latest_rows(ledger_path)) != catalog_sha256(latest):
        raise M7GateError("M7 source catalog changed while metadata inventory was built")
    return document


def write_manifest_once(path: Path, document: dict[str, Any]) -> str:
    payload = (canonical_json(document) + "\n").encode("utf-8")
    if path.exists():
        if path.read_bytes() != payload:
            raise M7GateError("existing M7 input manifest differs")
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
    parser.add_argument("--build-contract", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        protocol = M7Protocol.load(
            args.protocol, build_path=args.build_contract, project_root=args.project_root
        )
        document = build_input_manifest(
            protocol,
            project_root=args.project_root,
            ledger_path=args.ledger,
            created_at=args.created_at,
        )
        physical_sha = write_manifest_once(args.output, document)
    except (M7GateError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(canonical_json({"status": "FAIL", "error_class": type(error).__name__, "message": str(error)}))
        return 2
    print(canonical_json({"status": "PASS", "manifest_sha256": sha256_json(document), "physical_sha256": physical_sha}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

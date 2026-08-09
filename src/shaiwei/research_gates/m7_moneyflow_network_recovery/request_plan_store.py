"""Write-once storage and verification for exact M7 recovery request plans."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path, PurePosixPath
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from shaiwei.research_gates.m7_moneyflow.contract import sha256_json

from shaiwei.research_gates.m7_moneyflow_recovery.contract import RecoveryError

from .request_plan import (
    FULL_MARKET_COLUMNS,
    STATUS_COLUMNS,
    TARGETED_COLUMNS,
    RequestPlanData,
    aggregate_summary,
    frame_logical_sha256,
    full_market_frame,
    parse_full_market_frame,
    parse_status_frame,
    parse_targeted_frame,
    status_frame,
    targeted_frame,
)
from .sealing import read_canonical, sha256_file, write_canonical_once


FILES = {
    "status": ("status_requests.parquet", STATUS_COLUMNS),
    "full_market": ("moneyflow_full_market_requests.parquet", FULL_MARKET_COLUMNS),
    "targeted": ("moneyflow_targeted_requests.parquet", TARGETED_COLUMNS),
}


def _payload(frame: pd.DataFrame, columns: tuple[str, ...]) -> bytes:
    normalized = frame.loc[:, columns].astype("string")
    sink = pa.BufferOutputStream()
    pq.write_table(pa.Table.from_pandas(normalized, preserve_index=False), sink, compression="zstd")
    return sink.getvalue().to_pybytes()


def _write_once(path: Path, payload: bytes) -> None:
    try:
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as error:
        raise RecoveryError("recovery request plan path was already consumed") from error


def _item(path: Path, frame: pd.DataFrame, columns: tuple[str, ...]) -> dict[str, Any]:
    payload = _payload(frame, columns)
    _write_once(path, payload)
    return {
        "relative_name": path.name,
        "row_count": len(frame),
        "schema_fields": list(columns),
        "bytes": len(payload),
        "physical_sha256": hashlib.sha256(payload).hexdigest(),
        "logical_sha256": frame_logical_sha256(frame, columns),
    }


def request_plan_id(
    *,
    protocol_sha256: str,
    target_a_logical_sha256: str,
    target_b_logical_sha256: str,
    official_dates: tuple[str, ...],
) -> str:
    return sha256_json(
        {
            "schema_version": "m7-moneyflow-recovery-request-plan-v1",
            "protocol_sha256": protocol_sha256,
            "target_a_logical_sha256": target_a_logical_sha256,
            "target_b_logical_sha256": target_b_logical_sha256,
            "official_dates_sha256": sha256_json(list(official_dates)),
        }
    )


def write_request_plan_once(
    output_root: Path,
    data: RequestPlanData,
    *,
    protocol_sha256: str,
    tracked_root_relative: str,
    target_identity: dict[str, dict[str, Any]],
    calendar_identity: dict[str, Any],
) -> tuple[Path, dict[str, Any], str]:
    plan_id = request_plan_id(
        protocol_sha256=protocol_sha256,
        target_a_logical_sha256=str(target_identity["track_a"]["logical_sha256"]),
        target_b_logical_sha256=str(target_identity["track_b"]["logical_sha256"]),
        official_dates=data.official_dates,
    )
    root = output_root / plan_id
    if root.exists():
        raise RecoveryError("recovery request plan already exists")
    root.mkdir(parents=True, mode=0o700)
    frames = {
        "status": status_frame(data.status_requests),
        "full_market": full_market_frame(data.full_market_requests),
        "targeted": targeted_frame(data.targeted_requests),
    }
    files = {
        name: _item(root / FILES[name][0], frames[name], FILES[name][1])
        for name in FILES
    }
    dates_document = {
        "schema_version": "m7-moneyflow-recovery-official-dates-v1",
        "official_dates": list(data.official_dates),
    }
    dates_sha = write_canonical_once(root / "official_dates.json", dates_document)
    relative = PurePosixPath(tracked_root_relative) / plan_id
    if relative.is_absolute() or ".." in relative.parts:
        raise RecoveryError("recovery request plan tracked root is unsafe")
    manifest = {
        "schema_version": "m7-moneyflow-recovery-request-plan-manifest-v1",
        "plan_id": plan_id,
        "protocol_sha256": protocol_sha256,
        "plan_root_relative_path": relative.as_posix(),
        "target_identity": target_identity,
        "calendar_identity": calendar_identity,
        "request_summary": aggregate_summary(data),
        "plan_files": files,
        "official_dates_file": {
            "relative_name": "official_dates.json",
            "physical_sha256": dates_sha,
            "date_count": len(data.official_dates),
        },
        "security_codes_in_manifest": False,
        "moneyflow_numeric_value_columns_read": 0,
        "provider_call_count": 0,
        "external_network_used": False,
        "production_authorization": "none",
    }
    manifest_sha = write_canonical_once(root / "request_plan_manifest.json", manifest)
    return root, manifest, manifest_sha


def _read_frame(root: Path, item: dict[str, Any], columns: tuple[str, ...]) -> pd.DataFrame:
    name = str(item.get("relative_name", ""))
    if name != PurePosixPath(name).name:
        raise RecoveryError("recovery request plan path is unsafe")
    path = root / name
    if path.is_symlink() or not path.is_file():
        raise RecoveryError("recovery request plan file is missing")
    try:
        metadata = pq.read_metadata(path)
    except (OSError, pa.ArrowException) as error:
        raise RecoveryError("recovery request plan file integrity differs") from error
    if (
        path.stat().st_size != int(item.get("bytes", -1))
        or metadata.num_rows != int(item.get("row_count", -1))
        or list(metadata.schema.names) != list(columns)
        or sha256_file(path) != item.get("physical_sha256")
    ):
        raise RecoveryError("recovery request plan file integrity differs")
    try:
        frame = pq.read_table(path).to_pandas()
    except (OSError, pa.ArrowException) as error:
        raise RecoveryError("recovery request plan file integrity differs") from error
    if frame_logical_sha256(frame, columns) != item.get("logical_sha256"):
        raise RecoveryError("recovery request plan logical identity differs")
    return frame


def read_request_plan(root: Path, *, expected_manifest_sha256: str) -> tuple[RequestPlanData, dict[str, Any]]:
    manifest_path = root / "request_plan_manifest.json"
    if manifest_path.is_symlink() or sha256_file(manifest_path) != expected_manifest_sha256:
        raise RecoveryError("recovery request plan manifest identity differs")
    manifest = read_canonical(manifest_path)
    frames = {
        name: _read_frame(root, manifest["plan_files"][name], FILES[name][1])
        for name in FILES
    }
    dates_path = root / str(manifest["official_dates_file"]["relative_name"])
    if sha256_file(dates_path) != manifest["official_dates_file"]["physical_sha256"]:
        raise RecoveryError("recovery official dates file identity differs")
    dates_document = read_canonical(dates_path)
    dates = tuple(map(str, dates_document.get("official_dates", ())))
    data = RequestPlanData(
        parse_status_frame(frames["status"]),
        parse_full_market_frame(frames["full_market"]),
        parse_targeted_frame(frames["targeted"]),
        dates,
    )
    if aggregate_summary(data) != manifest.get("request_summary"):
        raise RecoveryError("recovery request plan aggregate summary differs")
    expected_id = request_plan_id(
        protocol_sha256=str(manifest["protocol_sha256"]),
        target_a_logical_sha256=str(manifest["target_identity"]["track_a"]["logical_sha256"]),
        target_b_logical_sha256=str(manifest["target_identity"]["track_b"]["logical_sha256"]),
        official_dates=dates,
    )
    if expected_id != manifest.get("plan_id") or root.name != expected_id:
        raise RecoveryError("recovery request plan ID differs")
    return data, manifest

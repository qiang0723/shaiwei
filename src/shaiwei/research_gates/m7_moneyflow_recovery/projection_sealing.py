"""Deterministic target hashing and write-once projection evidence sealing."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from shaiwei.research_gates.m7_moneyflow.contract import sha256_json

from .contract import RecoveryError
from .sealing import write_canonical_once
from .target_projection import OUTPUT_COLUMNS


def logical_target_sha256(frame: pd.DataFrame) -> str:
    normalized = frame.loc[:, OUTPUT_COLUMNS].astype("string").sort_values(list(OUTPUT_COLUMNS))
    return sha256_json(normalized.to_dict("records"))


def _parquet_payload(frame: pd.DataFrame) -> bytes:
    normalized = frame.loc[:, OUTPUT_COLUMNS].astype("string").sort_values(list(OUTPUT_COLUMNS))
    sink = pa.BufferOutputStream()
    pq.write_table(pa.Table.from_pandas(normalized, preserve_index=False), sink, compression="zstd")
    return sink.getvalue().to_pybytes()


def write_target_once(path: Path, frame: pd.DataFrame) -> dict[str, Any]:
    payload = _parquet_payload(frame)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as error:
        raise RecoveryError("recovery target projection output already exists") from error
    return {
        "relative_name": path.name,
        "row_count": len(frame),
        "schema_fields": list(OUTPUT_COLUMNS),
        "bytes": len(payload),
        "parquet_sha256": hashlib.sha256(payload).hexdigest(),
        "logical_content_sha256": logical_target_sha256(frame),
    }


def write_projection_run_once(
    output_root: Path,
    *,
    run_id: str,
    track_a: pd.DataFrame,
    track_b: pd.DataFrame,
    report: dict[str, Any],
) -> dict[str, Any]:
    target = output_root / run_id
    if target.exists():
        raise RecoveryError("recovery target projection run already exists")
    target.mkdir(parents=True, mode=0o700)
    a_item = write_target_once(target / "track_a_targets.parquet", track_a)
    b_item = write_target_once(target / "track_b_targets.parquet", track_b)
    report_sha = write_canonical_once(target / "target_projection_report.json", report)
    manifest = {
        "schema_version": "m7-moneyflow-recovery-target-projection-manifest-v1",
        "run_id": run_id,
        "protocol_sha256": report["protocol_sha256"],
        "release_scope_sha256": report["release_scope_sha256"],
        "approval_sha256": report["approval_sha256"],
        "lineage_core_sha256": report["lineage_core_sha256"],
        "track_a": a_item,
        "track_b": b_item,
        "report_sha256": report_sha,
        "security_codes_in_manifest": False,
        "numeric_moneyflow_value_columns_read": 0,
        "provider_call_count": 0,
        "production_authorization": "none",
    }
    manifest_sha = write_canonical_once(target / "target_projection_manifest.json", manifest)
    return {**manifest, "manifest_sha256": manifest_sha}

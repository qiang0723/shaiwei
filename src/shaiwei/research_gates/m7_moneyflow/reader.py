"""Approved key-only Parquet reader; it cannot project money-flow values."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from .contract import (
    MEMBERSHIP_COLUMNS,
    PROJECTED_SOURCE_COLUMNS,
    InputManifest,
    M7GateError,
    M7Protocol,
    sha256_file,
)


@dataclass(frozen=True)
class KeyInputs:
    membership: pd.DataFrame
    source_keys: pd.DataFrame
    official_dates: tuple[str, ...]
    quarantined_source_dates: frozenset[str]
    evidence: dict[str, Any]


def _bound_path(input_root: Path, relative: str) -> Path:
    path = input_root / relative
    if path.is_symlink():
        raise M7GateError("M7 approved reader forbids symlinked inputs")
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(input_root.resolve(strict=True))
    except (FileNotFoundError, ValueError) as exc:
        raise M7GateError("M7 approved input is missing or outside input root") from exc
    if not resolved.is_file():
        raise M7GateError("M7 approved input is not a regular file")
    return resolved


def _verify(path: Path, item: dict[str, Any]) -> None:
    if path.stat().st_size != int(item["bytes"]) or sha256_file(path) != item["content_sha256"]:
        raise M7GateError("M7 approved input physical identity differs")
    metadata = pq.read_metadata(path)
    if metadata.num_rows != int(item["row_count"]) or list(metadata.schema.names) != item["schema_fields"]:
        raise M7GateError("M7 approved Parquet footer identity differs")


def _evidence_json(input_root: Path, item: dict[str, Any]) -> dict[str, Any]:
    path = _bound_path(input_root, str(item["relative_path"]))
    if path.stat().st_size != int(item["bytes"]) or sha256_file(path) != item["sha256"]:
        raise M7GateError("M7 approved evidence file identity differs")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise M7GateError("M7 approved evidence file must be an object")
    return value


def load_key_inputs(
    protocol: M7Protocol,
    manifest: InputManifest,
    *,
    input_root: Path,
) -> KeyInputs:
    membership_item = manifest.document["membership"]
    membership_path = _bound_path(input_root, membership_item["relative_path"])
    _verify(membership_path, membership_item)
    membership = pq.ParquetFile(membership_path).read(columns=list(MEMBERSHIP_COLUMNS)).to_pandas()
    source_parts = []
    total_rows = 0
    total_bytes = 0
    for item in manifest.document["source_batches"]:
        path = _bound_path(input_root, item["relative_path"])
        _verify(path, item)
        frame = pq.ParquetFile(path).read(columns=list(PROJECTED_SOURCE_COLUMNS)).to_pandas()
        frame["request_trade_date"] = item["trade_date"]
        source_parts.append(frame)
        total_rows += len(frame)
        total_bytes += path.stat().st_size
    source_keys = pd.concat(source_parts, ignore_index=True)
    quality = _evidence_json(input_root, manifest.document["evidence_files"]["full_quality_report"])
    quarantine = _evidence_json(input_root, manifest.document["evidence_files"]["quarantine_report"])
    official_dates = tuple(str(item["trade_date"]) for item in quality.get("per_trade_date", []))
    quarantined = frozenset(
        str(item["trade_date"])
        for item in (quarantine.get("evaluation") or {}).get("quarantined_source_dates", [])
    )
    source = quality.get("source") or {}
    if (
        source.get("revision_observed_count") != 0
        or source.get("saturated_response_count") != 0
        or source.get("latest_catalog_sha256")
        != protocol.document["moneyflow_input"]["audited_catalog_sha256"]
    ):
        raise M7GateError("M7 approved P1 audit status differs")
    return KeyInputs(
        membership=membership,
        source_keys=source_keys,
        official_dates=official_dates,
        quarantined_source_dates=quarantined,
        evidence={
            "source_batch_count": len(source_parts),
            "source_row_count": total_rows,
            "source_bytes": total_bytes,
            "raw_projected_columns": list(PROJECTED_SOURCE_COLUMNS),
            "numeric_moneyflow_value_columns_read": 0,
            "membership_projected_columns": list(MEMBERSHIP_COLUMNS),
        },
    )

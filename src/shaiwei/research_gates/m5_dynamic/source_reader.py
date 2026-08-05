"""Read only exact manifest-listed Parquet columns after a release is separately approved."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from .contract import (
    API_FIELDS,
    MEMBERSHIP_CODE_FIELDS,
    InputManifest,
    M5DataProtocol,
    M5GateError,
    sha256_file,
)


def _bound_path(root: Path, relative: str) -> Path:
    path = root / relative
    if path.is_symlink():
        raise M5GateError("manifest-listed input cannot be a symlink")
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(root.resolve(strict=True))
    except (FileNotFoundError, ValueError) as exc:
        raise M5GateError("manifest-listed input is missing or escapes input root") from exc
    if not resolved.is_file():
        raise M5GateError("manifest-listed input is not a regular file")
    return resolved


def _verify_file(path: Path, item: dict[str, Any]) -> None:
    metadata = pq.read_metadata(path)
    if (
        int(metadata.num_rows) != int(item["row_count"])
        or os.stat(path).st_size != int(item["bytes"])
        or sha256_file(path) != item["content_sha256"]
        or list(metadata.schema.names) != list(item["schema_fields"])
    ):
        raise M5GateError("manifest-listed Parquet identity differs")


def load_allowed_inputs(
    protocol: M5DataProtocol,
    manifest: InputManifest,
    *,
    input_root: Path,
) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame], dict[str, Any]]:
    frames: dict[str, pd.DataFrame] = {}
    source_evidence: dict[str, Any] = {}
    for source in manifest.document["sources"]:
        api = source["source_api"]
        pieces = []
        for batch in source["batches"]:
            path = _bound_path(input_root, batch["relative_path"])
            _verify_file(path, batch)
            pieces.append(pd.read_parquet(path, columns=list(API_FIELDS[api])))
        frames[api] = pd.concat(pieces, ignore_index=True) if pieces else pd.DataFrame()
        source_evidence[api] = {
            "selection_sha256": source["selection_sha256"],
            "batch_count": len(source["batches"]),
            "loaded_row_count": len(frames[api]),
        }
    memberships: dict[str, pd.DataFrame] = {}
    membership_evidence: dict[str, Any] = {}
    universe_map = {item.universe_id: item for item in protocol.universes}
    for item in manifest.document["memberships"]:
        universe = universe_map[item["universe_id"]]
        path = _bound_path(input_root, item["relative_path"])
        _verify_file(path, item)
        code_field = MEMBERSHIP_CODE_FIELDS[universe.universe_id]
        columns = ["trade_date", code_field]
        if universe.filter_column:
            columns.extend(["formation_date", universe.filter_column])
        frame = pd.read_parquet(path, columns=columns)
        if code_field != "ts_code":
            frame = frame.rename(columns={code_field: "ts_code"})
        if universe.filter_column:
            frame = frame.loc[
                frame[universe.filter_column].astype(str).eq(str(universe.filter_value))
            ].copy()
        memberships[universe.universe_id] = frame
        membership_evidence[universe.universe_id] = {
            "content_sha256": item["content_sha256"],
            "source_row_count": int(item["row_count"]),
            "loaded_row_count_after_filter": len(frame),
        }
    if set(frames) != {source["source_api"] for source in manifest.document["sources"]}:
        raise M5GateError("M5 source reader did not materialize the exact API allowlist")
    if set(memberships) != set(protocol.universe_ids):
        raise M5GateError("M5 source reader did not materialize the exact three pools")
    return frames, memberships, {
        "sources": source_evidence,
        "memberships": membership_evidence,
    }

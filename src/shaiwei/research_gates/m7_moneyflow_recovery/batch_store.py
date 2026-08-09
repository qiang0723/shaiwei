"""Write-once Parquet batches and canonical receipts in an isolated recovery root."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from shaiwei.research_gates.m7_moneyflow.contract import canonical_json, require_sha256, sha256_json

from .contract import RecoveryError


SOURCE_RE = re.compile(r"^[a-z0-9_.-]+$")


@dataclass(frozen=True)
class BatchIdentity:
    release_scope_sha256: str
    request_sha256: str
    source_api: str
    request_shape: str


def _parquet_bytes(frame: pd.DataFrame) -> bytes:
    sink = pa.BufferOutputStream()
    pq.write_table(pa.Table.from_pandas(frame, preserve_index=False), sink, compression="zstd")
    return sink.getvalue().to_pybytes()


def _write_once(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as error:
        raise RecoveryError("recovery isolated batch path was already consumed") from error


def write_batch(root: Path, identity: BatchIdentity, frame: pd.DataFrame) -> dict[str, Any]:
    scope = require_sha256(identity.release_scope_sha256, "release scope SHA")
    request = require_sha256(identity.request_sha256, "request SHA")
    if SOURCE_RE.fullmatch(identity.source_api) is None or SOURCE_RE.fullmatch(identity.request_shape) is None:
        raise RecoveryError("recovery isolated batch identity contains unsafe text")
    relative = Path(identity.source_api) / identity.request_shape / request / "batch.parquet"
    payload = _parquet_bytes(frame)
    content_sha = hashlib.sha256(payload).hexdigest()
    document = {
        "schema_version": "m7-moneyflow-recovery-batch-receipt-v1",
        "release_scope_sha256": scope,
        "request_sha256": request,
        "source_api": identity.source_api,
        "request_shape": identity.request_shape,
        "batch_relative_path": relative.as_posix(),
        "row_count": len(frame),
        "schema_fields": list(frame.columns),
        "content_sha256": content_sha,
        "append_only": True,
        "production_ledger_written": False,
    }
    receipt = {**document, "receipt_sha256": sha256_json(document)}
    _write_once(root / relative, payload)
    _write_once(root / relative.with_name("receipt.json"), (canonical_json(receipt) + "\n").encode())
    return receipt

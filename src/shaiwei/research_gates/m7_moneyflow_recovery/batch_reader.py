"""Verify isolated recovery receipts and assemble the frozen in-memory input."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

import pandas as pd
import pyarrow.parquet as pq

from shaiwei.research_gates.m7_moneyflow.contract import canonical_json, sha256_json

from .contract import RecoveryError, RecoveryProtocol
from .inputs import RecoveryInputs


def _safe_batch(root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or not pure.parts:
        raise RecoveryError("recovery batch receipt contains unsafe path")
    path = root / pure.as_posix()
    if path.is_symlink():
        raise RecoveryError("recovery batch cannot be a symlink")
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(root.resolve(strict=True))
    except (FileNotFoundError, ValueError) as error:
        raise RecoveryError("recovery batch is missing or outside isolated root") from error
    return resolved


def read_receipt(root: Path, receipt_path: Path) -> tuple[dict[str, Any], pd.DataFrame]:
    serialized = receipt_path.read_text(encoding="utf-8")
    receipt = json.loads(serialized)
    if not isinstance(receipt, dict) or serialized != canonical_json(receipt) + "\n":
        raise RecoveryError("recovery batch receipt is not canonical")
    claimed = dict(receipt)
    receipt_sha = claimed.pop("receipt_sha256", None)
    if receipt_sha != sha256_json(claimed):
        raise RecoveryError("recovery batch receipt identity differs")
    batch = _safe_batch(root, str(receipt.get("batch_relative_path", "")))
    payload_sha = hashlib.sha256(batch.read_bytes()).hexdigest()
    if payload_sha != receipt.get("content_sha256"):
        raise RecoveryError("recovery isolated batch integrity differs")
    metadata = pq.read_metadata(batch)
    if (
        metadata.num_rows != int(receipt.get("row_count", -1))
        or list(metadata.schema.names) != receipt.get("schema_fields")
    ):
        raise RecoveryError("recovery isolated batch integrity differs")
    return receipt, pq.read_table(batch).to_pandas()


def _load_shape(
    root: Path,
    receipts: Iterable[Path],
    *,
    release_scope_sha256: str,
    expected_request_sha256s: frozenset[str],
    source_api: str,
    shape: str,
) -> tuple[pd.DataFrame, tuple[int, ...]]:
    frames: list[pd.DataFrame] = []
    counts: list[int] = []
    observed: list[str] = []
    for path in sorted(receipts):
        receipt, frame = read_receipt(root, path)
        if (
            receipt.get("release_scope_sha256") != release_scope_sha256
            or receipt.get("source_api") != source_api
            or receipt.get("request_shape") != shape
        ):
            raise RecoveryError("recovery batch source or shape differs")
        frames.append(frame)
        counts.append(len(frame))
        observed.append(str(receipt["request_sha256"]))
    if len(observed) != len(set(observed)) or set(observed) != expected_request_sha256s:
        raise RecoveryError("recovery batch request identities differ")
    return (pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()), tuple(counts)


def assemble_inputs(
    protocol: RecoveryProtocol,
    *,
    release_scope_sha256: str,
    status_root: Path,
    moneyflow_root: Path,
    track_a: pd.DataFrame,
    track_b: pd.DataFrame,
    daily_keys: pd.DataFrame,
    official_dates: tuple[str, ...],
    status_receipts: Iterable[Path],
    full_market_receipts: Iterable[Path],
    targeted_receipts: Iterable[Path],
    status_request_sha256s: frozenset[str],
    full_market_request_sha256s: frozenset[str],
    targeted_request_sha256s: frozenset[str],
) -> RecoveryInputs:
    status, _ = _load_shape(
        status_root,
        status_receipts,
        release_scope_sha256=release_scope_sha256,
        expected_request_sha256s=status_request_sha256s,
        source_api="baostock.history_k_data_plus",
        shape="exact_status_window",
    )
    full, counts = _load_shape(
        moneyflow_root,
        full_market_receipts,
        release_scope_sha256=release_scope_sha256,
        expected_request_sha256s=full_market_request_sha256s,
        source_api="tushare.moneyflow",
        shape="full_market_by_trade_date",
    )
    targeted, _ = _load_shape(
        moneyflow_root,
        targeted_receipts,
        release_scope_sha256=release_scope_sha256,
        expected_request_sha256s=targeted_request_sha256s,
        source_api="tushare.moneyflow",
        shape="one_security_one_date",
    )
    target_keys = set(track_b[["ts_code", "trade_date"]].itertuples(index=False, name=None))
    if {"ts_code", "trade_date"} <= set(full.columns):
        mask = [(str(row.ts_code), str(row.trade_date)) in target_keys for row in full.itertuples()]
        full = full.loc[mask, list(protocol.moneyflow_fields)].reset_index(drop=True)
    return RecoveryInputs(
        track_a_targets=track_a,
        track_b_targets=track_b,
        daily_keys=daily_keys,
        independent_status=status,
        full_market_target_rows=full,
        targeted_rows=targeted,
        official_dates=official_dates,
        full_market_response_row_counts=counts,
        immutable_batch_integrity=True,
    )

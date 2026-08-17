"""Canonical write-once Parquet and manifest sealing for R3G-2 effect."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from shaiwei.research.trend_swing.r3g2.contract import R3G2Error, sha256_file
from shaiwei.research.trend_swing.r3g2.evidence import canonical_json, write_once_bytes, write_once_json
from shaiwei.research.trend_swing.r3g2.effect_models import SimulationResult


NAV_COLUMNS = (
    "trade_date", "nav", "daily_return", "benchmark_return", "active_return",
    "cash_ratio", "gross_weight", "maximum_security_weight", "maximum_industry_weight",
    "position_count", "corporate_action_overlap_count",
)
ORDER_COLUMNS = (
    "trade_date", "ts_code", "side", "batch", "reason", "status", "filled_notional",
    "capacity_limited",
)
TRADE_COLUMNS = (
    "trade_date", "episode_id", "ts_code", "industry", "side", "batch", "reason",
    "gross_notional", "fees", "closed_trade", "closed_trade_pnl",
)


def _frame(rows: tuple[dict[str, Any], ...], columns: tuple[str, ...]) -> pd.DataFrame:
    return pd.DataFrame(list(rows), columns=list(columns))


def _parquet_bytes(frame: pd.DataFrame) -> bytes:
    table = pa.Table.from_pandas(frame, preserve_index=False)
    sink = pa.BufferOutputStream()
    pq.write_table(
        table, sink, compression="zstd", use_dictionary=False,
        write_statistics=True, data_page_version="1.0",
    )
    return sink.getvalue().to_pybytes()


def write_once_frame(path: Path, frame: pd.DataFrame) -> str:
    payload = _parquet_bytes(frame)
    digest, _ = write_once_bytes(path, payload)
    return digest


def save_simulation(
    root: Path,
    result: SimulationResult,
    summary: Mapping[str, Any],
) -> dict[str, Any]:
    files = {
        "nav.parquet": write_once_frame(root / "nav.parquet", _frame(result.nav_rows, NAV_COLUMNS)),
        "orders.parquet": write_once_frame(
            root / "orders.parquet", _frame(result.order_rows, ORDER_COLUMNS)
        ),
        "trades.parquet": write_once_frame(
            root / "trades.parquet", _frame(result.trade_rows, TRADE_COLUMNS)
        ),
    }
    summary_sha, _ = write_once_json(root / "summary.json", dict(summary))
    files["summary.json"] = summary_sha
    return {"files": files, "bundle_sha256": _bundle(files)}


def _bundle(files: Mapping[str, str]) -> str:
    return hashlib.sha256(canonical_json(dict(sorted(files.items())))).hexdigest()


def tree_manifest(root: Path) -> dict[str, Any]:
    files = {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    }
    return {
        "schema_version": "ts-v5-r3g2-effect-pass-manifest-v1",
        "file_count": len(files),
        "files": files,
        "bundle_sha256": _bundle(files),
    }


def seal_pass(root: Path, summary: Mapping[str, Any]) -> dict[str, Any]:
    summary_sha, _ = write_once_json(root / "pass_summary.json", dict(summary))
    manifest = tree_manifest(root)
    manifest_sha, _ = write_once_json(root / "manifest.json", manifest)
    return {
        "summary_sha256": summary_sha,
        "manifest_sha256": manifest_sha,
        "bundle_sha256": manifest["bundle_sha256"],
        "file_count": manifest["file_count"],
    }


def verify_manifest(root: Path) -> dict[str, Any]:
    path = root / "manifest.json"
    if not path.is_file():
        raise R3G2Error("R3G-2 pass manifest is absent")
    import json

    document = json.loads(path.read_text(encoding="utf-8"))
    observed = tree_manifest(root)
    if document != observed:
        raise R3G2Error("R3G-2 pass artifact hash differs")
    return document

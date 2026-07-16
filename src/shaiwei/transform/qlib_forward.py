"""Versioned forward qlib snapshots; the frozen Stage-0 cache is never mutated."""

from __future__ import annotations

import gc
import json
import os
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from shaiwei.config import PROJECT_ROOT, Settings
from shaiwei.ingest.catalog import load_latest_api
from shaiwei.ledger import ingest_snapshot_sha256, portable_artifact_path
from shaiwei.provenance import code_snapshot_sha256
from shaiwei.transform.market import attach_trade_limit_flags, sanitize_adj_factors, transform_market_data
from shaiwei.transform.qlib_bin import (
    QLIB_MANIFEST,
    build_qlib_bin,
    qlib_tree_integrity,
    verify_qlib_tree_manifest,
)

CURRENT_POINTER = "current.json"


class ForwardQlibError(RuntimeError):
    pass


@dataclass(frozen=True)
class ForwardSnapshot:
    provider_uri: Path
    data_snapshot_sha256: str
    code_snapshot_sha256: str
    artifact_sha256: str
    sentinel_report_path: Path


def _forward_root(settings: Settings) -> Path:
    return settings.runtime.data_root / "qlib_forward"


def _matching_sentinel_report(data_hash: str, code_hash: str) -> tuple[Path, dict[str, object]] | None:
    report_dir = PROJECT_ROOT / "logs" / "sentinels"
    for path in sorted(report_dir.glob("*.json"), reverse=True):
        report = json.loads(path.read_text(encoding="utf-8"))
        if (
            report.get("data_snapshot_sha256") == data_hash
            and report.get("code_snapshot_sha256") == code_hash
        ):
            return path, report
    return None


def ensure_matching_sentinels(data_hash: str, code_hash: str) -> Path:
    matched = _matching_sentinel_report(data_hash, code_hash)
    if matched is None:
        completed = subprocess.run([sys.executable, "-m", "shaiwei.sentinel"], check=False)
        if completed.returncode != 0:
            raise ForwardQlibError("full sentinel gate failed; forward qlib build is blocked")
        matched = _matching_sentinel_report(data_hash, code_hash)
    if matched is None:
        raise ForwardQlibError("sentinel run did not produce a matching snapshot report")
    path, report = matched
    if report.get("required_failures"):
        raise ForwardQlibError("matching sentinel report contains required failures")
    return path


def _build_version(
    settings: Settings,
    output: Path,
    *,
    data_hash: str,
    code_hash: str,
) -> dict[str, int | str]:
    daily = load_latest_api("tushare.daily")
    adj_factor = sanitize_adj_factors(
        daily,
        load_latest_api("tushare.adj_factor"),
        load_latest_api("tushare.dividend"),
    )
    stock_basic = load_latest_api("tushare.stock_basic")
    market = attach_trade_limit_flags(
        transform_market_data(daily, adj_factor),
        stock_basic,
        load_latest_api("tushare.namechange"),
        settings.limit_rules.model_dump(),
        copy=False,
    )
    staging = output.with_name(f".{output.name}.building.{uuid.uuid4().hex}")
    try:
        build_qlib_bin(
            staging,
            market,
            load_latest_api("tushare.trade_cal"),
            stock_basic,
            load_latest_api("tushare.index_weight"),
            load_latest_api("tushare.index_daily"),
            {
                settings.baseline.instrument: settings.universe.index_code,
                settings.alphagen_benchmark.instrument: settings.alphagen_benchmark.index_code,
            },
        )
        integrity = qlib_tree_integrity(staging)
        (staging / QLIB_MANIFEST).write_text(
            json.dumps(
                {
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "purpose": "forward-shadow",
                    "code_snapshot_sha256": code_hash,
                    "data_snapshot_sha256": data_hash,
                    **integrity,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        os.replace(staging, output)
        return integrity
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    finally:
        del daily, adj_factor, stock_basic, market
        gc.collect()


def _write_pointer(root: Path, snapshot: ForwardSnapshot) -> None:
    root.mkdir(parents=True, exist_ok=True)
    pointer = root / CURRENT_POINTER
    temporary = root / f".{CURRENT_POINTER}.{uuid.uuid4().hex}.tmp"
    payload = {
        "activated_at": datetime.now(timezone.utc).isoformat(),
        "provider_uri": snapshot.provider_uri.relative_to(root).as_posix(),
        "data_snapshot_sha256": snapshot.data_snapshot_sha256,
        "code_snapshot_sha256": snapshot.code_snapshot_sha256,
        "artifact_sha256": snapshot.artifact_sha256,
        "sentinel_report_path": portable_artifact_path(snapshot.sentinel_report_path),
    }
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    with temporary.open("rb") as handle:
        os.fsync(handle.fileno())
    os.replace(temporary, pointer)


def _prune_versions(root: Path, *, current: Path, keep: int) -> None:
    versions = root / "versions"
    candidates = sorted(
        (path for path in versions.iterdir() if path.is_dir() and not path.name.startswith(".")),
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )
    protected = {current.resolve(), *(path.resolve() for path in candidates[:keep])}
    for path in candidates:
        if path.resolve() not in protected:
            shutil.rmtree(path)


def ensure_forward_snapshot(settings: Settings) -> ForwardSnapshot:
    data_hash = ingest_snapshot_sha256()
    code_hash = code_snapshot_sha256()
    sentinel_path = ensure_matching_sentinels(data_hash, code_hash)
    root = _forward_root(settings)
    versions = root / "versions"
    versions.mkdir(parents=True, exist_ok=True)
    version = f"{code_hash[:12]}-{data_hash[:12]}"
    output = versions / version
    if output.is_dir():
        integrity = verify_qlib_tree_manifest(output, data_hash=data_hash, code_hash=code_hash)
    elif output.exists():
        raise ForwardQlibError(f"forward qlib version path is not a directory: {output}")
    else:
        integrity = _build_version(
            settings,
            output,
            data_hash=data_hash,
            code_hash=code_hash,
        )
    snapshot = ForwardSnapshot(
        provider_uri=output,
        data_snapshot_sha256=data_hash,
        code_snapshot_sha256=code_hash,
        artifact_sha256=str(integrity["artifact_sha256"]),
        sentinel_report_path=sentinel_path,
    )
    _write_pointer(root, snapshot)
    _prune_versions(
        root,
        current=output,
        keep=settings.shadow_pipeline.qlib_versions_to_keep,
    )
    return snapshot


def current_forward_snapshot(settings: Settings) -> ForwardSnapshot:
    root = _forward_root(settings)
    pointer = root / CURRENT_POINTER
    if not pointer.is_file():
        raise ForwardQlibError("forward qlib pointer is missing")
    payload = json.loads(pointer.read_text(encoding="utf-8"))
    provider = root / str(payload["provider_uri"])
    integrity = verify_qlib_tree_manifest(
        provider,
        data_hash=str(payload["data_snapshot_sha256"]),
        code_hash=str(payload["code_snapshot_sha256"]),
    )
    if integrity["artifact_sha256"] != payload["artifact_sha256"]:
        raise ForwardQlibError("forward pointer artifact hash differs from version manifest")
    sentinel = Path(str(payload["sentinel_report_path"]))
    if not sentinel.is_absolute():
        sentinel = PROJECT_ROOT / sentinel
    if not sentinel.is_file():
        raise ForwardQlibError("forward pointer sentinel report is missing")
    return ForwardSnapshot(
        provider_uri=provider,
        data_snapshot_sha256=str(payload["data_snapshot_sha256"]),
        code_snapshot_sha256=str(payload["code_snapshot_sha256"]),
        artifact_sha256=str(payload["artifact_sha256"]),
        sentinel_report_path=sentinel,
    )

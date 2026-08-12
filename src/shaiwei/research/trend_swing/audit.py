"""Independent read-only audit for the one-shot TS-1A profile."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb
import pyarrow.parquet as pq

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.trend_swing.contract import (
    AUDIT_PATH,
    FORBIDDEN_RESULT_TERMS,
    MANIFEST_PATH,
    PROTOCOL_PATH,
    REPORT_PATH,
    TrendSwingError,
    canonical_sha256,
    sha256_file,
    write_once_json,
)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TrendSwingError(f"TS audit expected mapping: {path.name}")
    return value


def _walk_keys(value: Any) -> list[str]:
    keys = []
    if isinstance(value, dict):
        for key, child in value.items():
            keys.append(str(key).lower())
            keys.extend(_walk_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.extend(_walk_keys(child))
    return keys


def _artifact(record: dict[str, Any]) -> Path:
    path = (PROJECT_ROOT / str(record["path"])).resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()):
        raise TrendSwingError("TS audit artifact escapes the project root")
    return path


def _verify_artifacts(manifest: dict[str, Any]) -> tuple[int, int]:
    artifact_count = 0
    row_count = 0
    for source in manifest["sources"].values():
        for record in source["artifacts"]:
            path = _artifact(record)
            metadata = pq.read_metadata(path)
            if metadata.num_rows != int(record["row_count"]):
                raise TrendSwingError(f"TS audit row count differs: {path.name}")
            if sha256_file(path) != record["content_sha256"]:
                raise TrendSwingError(f"TS audit hash differs: {path.name}")
            artifact_count += 1
            row_count += metadata.num_rows
    return artifact_count, row_count


def _recompute_index_codes(manifest: dict[str, Any]) -> list[str]:
    records = manifest["sources"]["tushare.index_daily"]["artifacts"]
    paths = [str(_artifact(record)) for record in records]
    connection = duckdb.connect(":memory:")
    try:
        rows = connection.execute(
            """
            SELECT DISTINCT CAST(ts_code AS VARCHAR) AS ts_code
            FROM read_parquet(?, union_by_name = true, hive_partitioning = false)
            ORDER BY ts_code
            """,
            [paths],
        ).fetchall()
    finally:
        connection.close()
    return [row[0] for row in rows]


def _recompute_source_rows(manifest: dict[str, Any]) -> dict[str, int]:
    return {
        source_api: sum(int(record["row_count"]) for record in source["artifacts"])
        for source_api, source in manifest["sources"].items()
    }


def audit_once() -> dict[str, Any]:
    if AUDIT_PATH.exists():
        raise TrendSwingError("TS-1A independent audit already exists; rerun is forbidden")
    manifest = _load_json(MANIFEST_PATH)
    report = _load_json(REPORT_PATH)
    checks = {
        "protocol_hash_matches": report["protocol_sha256"] == sha256_file(PROTOCOL_PATH),
        "manifest_binding_matches": report["input_manifest_sha256"] == canonical_sha256(manifest),
        "manifest_file_hash_matches": report["input_manifest_file_sha256"] == sha256_file(MANIFEST_PATH),
        "result_blind": report["authority"]["result_blind"] is True,
        "zero_effect_attempts": report["authority"]["strategy_effect_attempt_count"] == 0,
        "zero_network_requests": report["authority"]["network_request_count"] == 0,
        "no_forbidden_result_keys": not (set(_walk_keys(report)) & FORBIDDEN_RESULT_TERMS),
        "missing_chinext_recomputed": "399006.SZ" not in _recompute_index_codes(manifest),
        "blocked_market_rule": "BLOCKED_MARKET_RULE" in report["blocking_verdicts"],
        "source_row_summaries_match": _recompute_source_rows(manifest)
        == {key: int(value["row_count"]) for key, value in report["source_summary"].items()},
    }
    artifact_count, row_count = _verify_artifacts(manifest)
    if not all(checks.values()):
        raise TrendSwingError(f"TS-1A independent audit failed: {checks}")
    audit = {
        "schema_version": "ts-v3-data-gate-independent-audit-v1",
        "report_path": REPORT_PATH.relative_to(PROJECT_ROOT).as_posix(),
        "report_sha256": sha256_file(REPORT_PATH),
        "manifest_path": MANIFEST_PATH.relative_to(PROJECT_ROOT).as_posix(),
        "manifest_sha256": sha256_file(MANIFEST_PATH),
        "verified_artifact_count": artifact_count,
        "verified_source_row_count": row_count,
        "checks": checks,
        "verdict": "PASS",
    }
    write_once_json(AUDIT_PATH, audit)
    return audit

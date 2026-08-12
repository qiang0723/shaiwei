"""Project-local immutable input discovery for TS-1A."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import pyarrow.parquet as pq

from shaiwei.config import PROJECT_ROOT
from shaiwei.ingest.catalog import canonical_params_key
from shaiwei.ledger import INGEST
from shaiwei.research.trend_swing.contract import (
    ALPHA158_PATH,
    TrendSwingError,
    TrendSwingProtocol,
    canonical_sha256,
    sha256_file,
)


def _artifact_path(value: str, root: Path) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    elif not candidate.is_relative_to(root):
        parts = candidate.parts
        markers = [index for index in range(len(parts) - 1) if parts[index : index + 2] == ("data", "raw")]
        if not markers:
            raise TrendSwingError("TS source artifact escapes the project root")
        candidate = root.joinpath(*parts[markers[-1] :])
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise TrendSwingError("TS source artifact escapes the project root")
    return resolved


def latest_source_entries(ledger: pd.DataFrame, source_api: str) -> pd.DataFrame:
    required = {
        "batch_id",
        "ingest_time",
        "source_api",
        "params_json",
        "row_count",
        "parquet_path",
        "content_sha256",
    }
    if missing := required - set(ledger.columns):
        raise TrendSwingError(f"TS ingest ledger missing columns: {sorted(missing)}")
    entries = ledger.loc[ledger["source_api"].eq(source_api)].copy()
    if entries.empty:
        return entries
    entries["_params_key"] = entries["params_json"].map(
        lambda value: canonical_params_key(json.loads(value))
    )
    entries["_time"] = pd.to_datetime(entries["ingest_time"], utc=True, errors="raise")
    return entries.sort_values("_time").drop_duplicates("_params_key", keep="last")


def _evidence_record(row: Any, root: Path) -> dict[str, Any]:
    path = _artifact_path(str(row.parquet_path), root)
    if not path.is_file():
        raise TrendSwingError(f"TS committed batch missing: {path.name}")
    metadata = pq.read_metadata(path)
    if metadata.num_rows != int(row.row_count):
        raise TrendSwingError(f"TS committed batch row count differs: {path.name}")
    digest = sha256_file(path)
    if digest != str(row.content_sha256):
        raise TrendSwingError(f"TS committed batch hash differs: {path.name}")
    params = json.loads(row.params_json)
    return {
        "batch_id": str(row.batch_id),
        "params": params,
        "row_count": int(row.row_count),
        "path": path.relative_to(root).as_posix(),
        "content_sha256": digest,
    }


def collect_input_manifest(
    protocol: TrendSwingProtocol,
    *,
    ledger_path: Path = INGEST,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    before = sha256_file(ledger_path)
    ledger = pd.read_csv(ledger_path, dtype=str, keep_default_na=False)
    sources: dict[str, Any] = {}
    missing = []
    for source_api in protocol.required_sources:
        latest = latest_source_entries(ledger, source_api)
        if latest.empty:
            missing.append(source_api)
            sources[source_api] = {"batch_count": 0, "row_count": 0, "artifacts": []}
            continue
        artifacts = [_evidence_record(row, project_root) for row in latest.itertuples(index=False)]
        sources[source_api] = {
            "batch_count": len(artifacts),
            "row_count": sum(record["row_count"] for record in artifacts),
            "artifact_bundle_sha256": canonical_sha256(artifacts),
            "artifacts": artifacts,
        }
    if sha256_file(ledger_path) != before:
        raise TrendSwingError("ingest ledger changed while TS manifest was collected")
    alpha_path = ALPHA158_PATH.resolve()
    alpha: dict[str, Any]
    if not alpha_path.is_file():
        alpha = {"present": False}
    else:
        metadata = pq.read_metadata(alpha_path)
        alpha = {
            "present": True,
            "path": alpha_path.relative_to(project_root).as_posix(),
            "row_count": metadata.num_rows,
            "content_sha256": sha256_file(alpha_path),
            "columns": metadata.schema.names,
        }
    return {
        "schema_version": "ts-v3-data-gate-input-manifest-v1",
        "protocol_id": protocol.document["protocol_id"],
        "protocol_sha256": protocol.sha256,
        "ingest_ledger_path": ledger_path.relative_to(project_root).as_posix(),
        "ingest_ledger_sha256": before,
        "required_sources_missing": missing,
        "sources": sources,
        "alpha158": alpha,
    }


def source_paths(manifest: dict[str, Any], source_api: str, root: Path = PROJECT_ROOT) -> list[str]:
    records = manifest.get("sources", {}).get(source_api, {}).get("artifacts", [])
    return [str(_artifact_path(str(record["path"]), root)) for record in records]


def index_coverage(manifest: dict[str, Any], root: Path = PROJECT_ROOT) -> list[dict[str, Any]]:
    paths = source_paths(manifest, "tushare.index_daily", root)
    if not paths:
        return []
    connection = duckdb.connect(":memory:")
    try:
        result = connection.execute(
            """
            SELECT CAST(ts_code AS VARCHAR) AS ts_code,
                   min(CAST(trade_date AS VARCHAR)) AS first_date,
                   max(CAST(trade_date AS VARCHAR)) AS last_date,
                   count(*) AS row_count,
                   count(DISTINCT CAST(trade_date AS VARCHAR)) AS unique_date_count
            FROM read_parquet(?, union_by_name = true, hive_partitioning = false)
            GROUP BY ts_code ORDER BY ts_code
            """,
            [paths],
        ).df()
    finally:
        connection.close()
    result["duplicate_date_count"] = result["row_count"] - result["unique_date_count"]
    return result.to_dict(orient="records")


def calendar_coverage(manifest: dict[str, Any], root: Path = PROJECT_ROOT) -> dict[str, Any]:
    paths = source_paths(manifest, "tushare.trade_cal", root)
    if not paths:
        return {"open_day_count": 0, "first_open_day": None, "last_open_day": None}
    connection = duckdb.connect(":memory:")
    try:
        row = connection.execute(
            """
            SELECT count(DISTINCT CAST(cal_date AS VARCHAR)),
                   min(CAST(cal_date AS VARCHAR)), max(CAST(cal_date AS VARCHAR))
            FROM read_parquet(?, union_by_name = true, hive_partitioning = false)
            WHERE CAST(exchange AS VARCHAR) = 'SSE' AND CAST(is_open AS VARCHAR) IN ('1', '1.0')
              AND CAST(cal_date AS VARCHAR) BETWEEN ? AND ?
            """,
            [paths, "20160101", "20260811"],
        ).fetchone()
    finally:
        connection.close()
    return {"open_day_count": int(row[0]), "first_open_day": row[1], "last_open_day": row[2]}


def alpha158_coverage(manifest: dict[str, Any], root: Path = PROJECT_ROOT) -> dict[str, Any]:
    alpha = manifest.get("alpha158", {})
    if not alpha.get("present"):
        return {"present": False, "event_key_coverage": "NOT_EVALUATED_UPSTREAM_BLOCKED"}
    path = _artifact_path(str(alpha["path"]), root)
    connection = duckdb.connect(":memory:")
    try:
        row = connection.execute(
            """
            SELECT min(CAST(trade_date AS VARCHAR)), max(CAST(trade_date AS VARCHAR)),
                   count(*), count(DISTINCT CAST(trade_date AS VARCHAR)),
                   count(DISTINCT CAST(ts_code AS VARCHAR))
            FROM read_parquet(?, hive_partitioning = false)
            """,
            [str(path)],
        ).fetchone()
    finally:
        connection.close()
    return {
        "present": True,
        "first_date": row[0],
        "last_date": row[1],
        "row_count": int(row[2]),
        "date_count": int(row[3]),
        "security_count": int(row[4]),
        "event_key_coverage": "NOT_EVALUATED_UPSTREAM_BLOCKED",
    }

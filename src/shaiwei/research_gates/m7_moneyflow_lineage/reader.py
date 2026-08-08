"""Approved lineage reader; all semantic projections are key/status only."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import pyarrow.parquet as pq

from shaiwei.research_gates.m7_moneyflow.contract import InputManifest, M7Protocol, sha256_file
from shaiwei.research_gates.m7_moneyflow.reader import load_key_inputs

from .contract import (
    OLD_BUILD_PATH,
    OLD_INPUT_MANIFEST_PATH,
    OLD_PROTOCOL_PATH,
    LineageError,
    LineageInputManifest,
    LineageProtocol,
    SOURCE_COLUMNS,
)


@dataclass(frozen=True)
class LineageInputs:
    membership: pd.DataFrame
    moneyflow_keys: pd.DataFrame
    daily_keys: pd.DataFrame
    suspension: pd.DataFrame
    independent_status: pd.DataFrame
    official_dates: tuple[str, ...]
    quarantined_source_dates: frozenset[str]
    evidence: dict[str, Any]


def _bound(root: Path, relative: str) -> Path:
    path = root / relative
    if path.is_symlink():
        raise LineageError("lineage approved reader forbids symlinks")
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(root.resolve(strict=True))
    except (FileNotFoundError, ValueError) as exc:
        raise LineageError("lineage approved input is missing or outside input root") from exc
    if not resolved.is_file():
        raise LineageError("lineage approved input is not a regular file")
    return resolved


def _verified_paths(root: Path, manifest: LineageInputManifest, source_api: str) -> list[str]:
    paths = []
    projected = set(SOURCE_COLUMNS[source_api])
    for item in manifest.document["sources"][source_api]["batches"]:
        path = _bound(root, str(item["bundle_relative_path"]))
        metadata = pq.read_metadata(path)
        if (
            path.stat().st_size != int(item["bytes"])
            or metadata.num_rows != int(item["row_count"])
            or list(metadata.schema.names) != item["schema_fields"]
            or not projected <= set(metadata.schema.names)
            or sha256_file(path) != item["content_sha256"]
        ):
            raise LineageError("lineage approved source identity differs")
        paths.append(str(path))
    return paths


def _query_sources(
    manifest: LineageInputManifest,
    *,
    input_root: Path,
    membership: pd.DataFrame,
    start: str,
    end: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, int]]:
    paths = {source: _verified_paths(input_root, manifest, source) for source in SOURCE_COLUMNS}
    needed = membership[["ts_code"]].drop_duplicates().copy()
    connection = duckdb.connect(":memory:")
    try:
        connection.register("needed", needed)
        daily = connection.execute(
            """
            SELECT DISTINCT CAST(ts_code AS VARCHAR) ts_code,
                            CAST(trade_date AS VARCHAR) trade_date
            FROM read_parquet(?, union_by_name=true)
            SEMI JOIN needed USING (ts_code)
            WHERE CAST(trade_date AS VARCHAR) BETWEEN ? AND ?
            """,
            [paths["tushare.daily"], start, end],
        ).fetchdf()
        suspension = connection.execute(
            """
            SELECT CAST(ts_code AS VARCHAR) ts_code,
                   CAST(trade_date AS VARCHAR) trade_date,
                   max(CASE WHEN coalesce(trim(CAST(suspend_timing AS VARCHAR)), '') = ''
                            THEN 1 ELSE 0 END)::INT primary_full_day,
                   max(CASE WHEN coalesce(trim(CAST(suspend_timing AS VARCHAR)), '') <> ''
                            THEN 1 ELSE 0 END)::INT primary_intraday
            FROM read_parquet(?, union_by_name=true)
            SEMI JOIN needed USING (ts_code)
            WHERE CAST(trade_date AS VARCHAR) BETWEEN ? AND ?
            GROUP BY 1,2
            """,
            [paths["tushare.suspend_d"], start, end],
        ).fetchdf()
        independent = connection.execute(
            """
            SELECT CAST(ts_code AS VARCHAR) ts_code,
                   CAST(trade_date AS VARCHAR) trade_date,
                   max(CASE WHEN CAST(trade_status AS VARCHAR) = '0' THEN 1 ELSE 0 END)::INT independent_nontrading,
                   max(CASE WHEN CAST(trade_status AS VARCHAR) = '1' THEN 1 ELSE 0 END)::INT independent_trading,
                   sum(CASE WHEN CAST(trade_status AS VARCHAR) NOT IN ('0','1')
                            OR trade_status IS NULL THEN 1 ELSE 0 END)::BIGINT invalid_status_rows
            FROM read_parquet(?, union_by_name=true)
            SEMI JOIN needed USING (ts_code)
            WHERE CAST(trade_date AS VARCHAR) BETWEEN ? AND ?
            GROUP BY 1,2
            """,
            [paths["baostock.history_k_data_plus"], start, end],
        ).fetchdf()
    finally:
        connection.close()
    evidence = {
        "daily_selected_batch_count": len(paths["tushare.daily"]),
        "suspend_selected_batch_count": len(paths["tushare.suspend_d"]),
        "independent_selected_batch_count": len(paths["baostock.history_k_data_plus"]),
        "numeric_moneyflow_value_columns_read": 0,
        "numeric_daily_value_columns_read": 0,
    }
    return daily, suspension, independent, evidence


def load_lineage_inputs(
    protocol: LineageProtocol,
    manifest: LineageInputManifest,
    *,
    input_root: Path,
) -> LineageInputs:
    predecessor_root = input_root / "predecessor"
    old = M7Protocol.load(
        predecessor_root / OLD_PROTOCOL_PATH,
        build_path=predecessor_root / OLD_BUILD_PATH,
        project_root=predecessor_root,
    )
    old_manifest = InputManifest.load(
        predecessor_root / OLD_INPUT_MANIFEST_PATH,
        old,
    )
    prior = load_key_inputs(old, old_manifest, input_root=predecessor_root)
    scope = protocol.document["scope"]
    daily, suspension, independent, evidence = _query_sources(
        manifest,
        input_root=input_root,
        membership=prior.membership,
        start=scope["source_date_start"],
        end=scope["source_date_end"],
    )
    return LineageInputs(
        membership=prior.membership,
        moneyflow_keys=prior.source_keys,
        daily_keys=daily,
        suspension=suspension,
        independent_status=independent,
        official_dates=prior.official_dates,
        quarantined_source_dates=prior.quarantined_source_dates,
        evidence={
            **evidence,
            "moneyflow_projected_columns": ["ts_code", "trade_date"],
            "membership_projected_columns": [
                "trade_date",
                "formation_date",
                "universe_id",
                "ts_code",
                "segment",
            ],
            "daily_projected_columns": ["ts_code", "trade_date"],
            "suspend_projected_columns": list(SOURCE_COLUMNS["tushare.suspend_d"]),
            "independent_projected_columns": list(SOURCE_COLUMNS["baostock.history_k_data_plus"]),
        },
    )

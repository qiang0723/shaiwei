"""以 ingest ledger 为唯一索引读取已提交的原始批次。"""

import json
from pathlib import Path

import duckdb
import pandas as pd
import pyarrow.parquet as pq

from shaiwei.ledger import INGEST, resolve_artifact_path, sha256_file


class CatalogError(RuntimeError):
    pass


def canonical_params_key(params: dict[str, object]) -> str:
    return json.dumps(params, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def committed_params_keys(
    source_api: str,
    *,
    ledger_path: Path = INGEST,
    verify: bool = True,
) -> set[str]:
    """Return resumable request keys whose latest committed batch is intact."""
    entries = pd.read_csv(ledger_path, dtype=str, keep_default_na=False)
    entries = entries.loc[entries["source_api"].eq(source_api)].copy()
    if entries.empty:
        return set()
    entries["params_key"] = entries["params_json"].map(lambda value: canonical_params_key(json.loads(value)))
    entries["ingest_order"] = pd.to_datetime(entries["ingest_time"], utc=True, errors="raise")
    latest = entries.sort_values("ingest_order").drop_duplicates("params_key", keep="last")
    valid = set()
    for entry in latest.itertuples(index=False):
        path = resolve_artifact_path(entry.parquet_path)
        if not path.is_file():
            continue
        metadata = pq.read_metadata(path)
        if metadata.num_rows != int(entry.row_count):
            continue
        if verify and sha256_file(path) != entry.content_sha256:
            continue
        valid.add(entry.params_key)
    return valid


def load_latest_api(source_api: str, *, ledger_path: Path = INGEST, verify: bool = True) -> pd.DataFrame:
    entries = pd.read_csv(ledger_path, dtype=str, keep_default_na=False)
    entries = entries.loc[entries["source_api"].eq(source_api)].copy()
    if entries.empty:
        raise CatalogError(f"no committed batches for {source_api}")
    entries["_params_key"] = entries["params_json"].map(lambda value: canonical_params_key(json.loads(value)))
    entries["_time"] = pd.to_datetime(entries["ingest_time"], utc=True, errors="raise")
    latest = entries.sort_values("_time").drop_duplicates("_params_key", keep="last")

    paths = []
    for entry in latest.itertuples(index=False):
        path = resolve_artifact_path(entry.parquet_path)
        if not path.is_file():
            raise CatalogError(f"committed batch file is missing: {path}")
        metadata = pq.read_metadata(path)
        if verify and sha256_file(path) != entry.content_sha256:
            raise CatalogError(f"content hash mismatch: {path}")
        if metadata.num_rows != int(entry.row_count):
            raise CatalogError(f"row count mismatch: {path}")
        paths.append(str(path))
    if not paths:
        return pd.DataFrame()
    # DuckDB streams the Parquet fragments into one result and avoids retaining
    # thousands of per-request pandas frames plus a second full concat copy.
    # Do not silently drop duplicates: downstream key assertions must see and
    # reject duplicate source rows rather than having the catalog hide them.
    connection = duckdb.connect(":memory:")
    try:
        # Ledger paths identify exact immutable payloads.  Never let DuckDB
        # infer Hive columns from directory names: a partition such as
        # trade_date=20160104 is inferred as INTEGER and can override the
        # payload's canonical string column, silently breaking PIT joins.
        return connection.execute(
            "SELECT * FROM read_parquet(?, union_by_name = true, hive_partitioning = false)",
            [paths],
        ).df()
    finally:
        connection.close()


def load_latest_request(
    source_api: str,
    params: dict[str, object],
    *,
    ledger_path: Path = INGEST,
    verify: bool = True,
) -> pd.DataFrame:
    """Load the latest intact payload for one exact, canonical request."""
    entries = pd.read_csv(ledger_path, dtype=str, keep_default_na=False)
    entries = entries.loc[entries["source_api"].eq(source_api)].copy()
    wanted = canonical_params_key(params)
    entries = entries.loc[
        entries["params_json"].map(lambda value: canonical_params_key(json.loads(value))).eq(wanted)
    ]
    if entries.empty:
        raise CatalogError(f"no committed batch for {source_api} params={wanted}")
    entries["_time"] = pd.to_datetime(entries["ingest_time"], utc=True, errors="raise")
    entry = entries.sort_values("_time").iloc[-1]
    path = resolve_artifact_path(entry["parquet_path"])
    if not path.is_file():
        raise CatalogError(f"committed batch file is missing: {path}")
    metadata = pq.read_metadata(path)
    if metadata.num_rows != int(entry["row_count"]):
        raise CatalogError(f"row count mismatch: {path}")
    if verify and sha256_file(path) != entry["content_sha256"]:
        raise CatalogError(f"content hash mismatch: {path}")
    return pd.read_parquet(path)


def latest_request_evidence(
    source_api: str,
    params: dict[str, object],
    *,
    ledger_path: Path = INGEST,
) -> dict[str, str | int]:
    """Return and verify the immutable ledger identity for one exact request."""
    entries = pd.read_csv(ledger_path, dtype=str, keep_default_na=False)
    entries = entries.loc[entries["source_api"].eq(source_api)].copy()
    wanted = canonical_params_key(params)
    entries = entries.loc[
        entries["params_json"].map(
            lambda value: canonical_params_key(json.loads(value))
        ).eq(wanted)
    ]
    if entries.empty:
        raise CatalogError(f"no committed evidence for {source_api} params={wanted}")
    entries["_time"] = pd.to_datetime(entries["ingest_time"], utc=True, errors="raise")
    entry = entries.sort_values("_time").iloc[-1]
    path = resolve_artifact_path(entry["parquet_path"])
    if not path.is_file():
        raise CatalogError(f"committed batch file is missing: {path}")
    metadata = pq.read_metadata(path)
    if metadata.num_rows != int(entry["row_count"]):
        raise CatalogError(f"row count mismatch: {path}")
    if sha256_file(path) != entry["content_sha256"]:
        raise CatalogError(f"content hash mismatch: {path}")
    return {
        "batch_id": str(entry["batch_id"]),
        "source_api": source_api,
        "params_json": str(entry["params_json"]),
        "row_count": int(entry["row_count"]),
        "content_sha256": str(entry["content_sha256"]),
        "path": str(entry["parquet_path"]),
    }

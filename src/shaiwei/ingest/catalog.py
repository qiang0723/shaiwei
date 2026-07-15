"""以 ingest ledger 为唯一索引读取已提交的原始批次。"""

import json
from pathlib import Path

import duckdb
import pandas as pd
import pyarrow.parquet as pq

from shaiwei.ledger import INGEST, sha256_file


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
        path = Path(entry.parquet_path)
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
        path = Path(entry.parquet_path)
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
        return connection.execute(
            "SELECT * FROM read_parquet(?, union_by_name = true)", [paths]
        ).df()
    finally:
        connection.close()

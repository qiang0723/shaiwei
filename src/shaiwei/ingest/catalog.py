"""以 ingest ledger 为唯一索引读取已提交的原始批次。"""

import json
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from shaiwei.ledger import INGEST, sha256_file


class CatalogError(RuntimeError):
    pass


def load_latest_api(source_api: str, *, ledger_path: Path = INGEST, verify: bool = True) -> pd.DataFrame:
    entries = pd.read_csv(ledger_path, dtype=str, keep_default_na=False)
    entries = entries.loc[entries["source_api"].eq(source_api)].copy()
    if entries.empty:
        raise CatalogError(f"no committed batches for {source_api}")
    entries["_params_key"] = entries["params_json"].map(
        lambda value: json.dumps(json.loads(value), ensure_ascii=False, sort_keys=True)
    )
    entries["_time"] = pd.to_datetime(entries["ingest_time"], utc=True, errors="raise")
    latest = entries.sort_values("_time").drop_duplicates("_params_key", keep="last")

    frames = []
    for entry in latest.itertuples(index=False):
        path = Path(entry.parquet_path)
        if not path.is_file():
            raise CatalogError(f"committed batch file is missing: {path}")
        metadata = pq.read_metadata(path)
        if verify and sha256_file(path) != entry.content_sha256:
            raise CatalogError(f"content hash mismatch: {path}")
        if metadata.num_rows != int(entry.row_count):
            raise CatalogError(f"row count mismatch: {path}")
        frames.append(pd.read_parquet(path))
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).drop_duplicates().reset_index(drop=True)

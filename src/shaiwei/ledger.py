"""账本唯一写入口。任何代码禁止直接 open/pandas 重写 ledger/*.csv —— 只准调用这里的 append_*。"""
import csv
import fcntl
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LEDGER_DIR = PROJECT_ROOT / "ledger"
EXPERIMENTS = LEDGER_DIR / "experiments.csv"
INGEST = LEDGER_DIR / "ingest_batches.csv"

def _append(path: Path, row: dict) -> None:
    with path.open("r+", newline="", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        header = f.readline().strip().split(",")
        missing = set(header) - set(row)
        if missing:
            raise ValueError(f"ledger row missing fields: {missing}")
        extra = set(row) - set(header)
        if extra:
            raise ValueError(f"ledger row has unknown fields: {extra}")
        f.seek(0, os.SEEK_END)
        csv.DictWriter(f, fieldnames=header).writerow(row)
        f.flush()
        os.fsync(f.fileno())


def _reject_sensitive_params(value: object, path: str = "params") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_")
            if any(marker in normalized for marker in ("token", "secret", "password", "api_key")):
                raise ValueError(f"sensitive field is forbidden in ledger: {path}.{key}")
            _reject_sensitive_params(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _reject_sensitive_params(child, f"{path}[{index}]")

def sha256_file(p: str | Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def append_ingest_batch(source_api: str, params: dict, row_count: int,
                        parquet_path: str, content_sha256: str | None = None,
                        operator: str = "automation") -> str:
    import pyarrow.parquet as pq

    _reject_sensitive_params(params)
    parquet_file = Path(parquet_path)
    if not parquet_file.is_file():
        raise FileNotFoundError(parquet_file)
    actual_row_count = pq.read_metadata(parquet_file).num_rows
    if row_count != actual_row_count:
        raise ValueError(f"row_count={row_count} does not match parquet rows={actual_row_count}")
    actual_sha256 = sha256_file(parquet_file)
    if content_sha256 is not None and content_sha256 != actual_sha256:
        raise ValueError("provided content_sha256 does not match parquet file")
    batch_id = uuid.uuid4().hex[:12]
    _append(INGEST, {
        "batch_id": batch_id,
        "ingest_time": datetime.now(timezone.utc).isoformat(),
        "source_api": source_api,
        "params_json": json.dumps(params, ensure_ascii=False, sort_keys=True),
        "row_count": row_count,
        "parquet_path": str(parquet_file),
        "content_sha256": actual_sha256,
        "operator": operator,
    })
    return batch_id

def append_experiment(**kw) -> str:
    kw.setdefault("experiment_id", uuid.uuid4().hex[:12])
    kw.setdefault("parent_experiment_id", "")
    kw.setdefault("ts", datetime.now(timezone.utc).isoformat())
    for field in ("params_json", "result_json"):
        if isinstance(kw.get(field), (dict, list)):
            kw[field] = json.dumps(kw[field], ensure_ascii=False, sort_keys=True)
    if isinstance(kw.get("admitted"), bool):
        kw["admitted"] = str(kw["admitted"]).lower()
    _append(EXPERIMENTS, kw)
    return kw["experiment_id"]

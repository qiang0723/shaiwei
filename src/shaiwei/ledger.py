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
DAILY_RUNS = LEDGER_DIR / "daily_runs.csv"
SHADOW_RUNS = LEDGER_DIR / "shadow_runs.csv"
SHADOW_RECONCILIATIONS = LEDGER_DIR / "shadow_reconciliations.csv"
FACTOR_ADMISSIONS = LEDGER_DIR / "factor_admissions.csv"
PAPER_ACCOUNTS = LEDGER_DIR / "paper_accounts.csv"
PAPER_EVENTS = LEDGER_DIR / "paper_events.csv"
PAPER_RUNS = LEDGER_DIR / "paper_runs.csv"
P2_STAR50_ENGINEERING_RUNS = LEDGER_DIR / "p2_star50_engineering_runs.csv"
P2_STAR50_ENGINEERING_ADMISSIONS = LEDGER_DIR / "p2_star50_engineering_admissions.csv"
P2_STAR50_EFFECT_RUNS = LEDGER_DIR / "p2_star50_effect_runs.csv"
P2_STAR50_EFFECT_ADMISSIONS = LEDGER_DIR / "p2_star50_effect_admissions.csv"
P2_STAR50_EFFECT_CORRECTION_RUNS = LEDGER_DIR / "p2_star50_effect_correction_runs.csv"
P2_STAR50_EFFECT_CORRECTION_ADMISSIONS = LEDGER_DIR / "p2_star50_effect_correction_admissions.csv"
LLM_FACTOR_ATTEMPTS = LEDGER_DIR / "llm_factor_attempts.csv"
LLM_FACTOR_TRANSPORTS = LEDGER_DIR / "llm_factor_transports.csv"
LLM_FACTOR_ATTEMPTS_V2 = LEDGER_DIR / "llm_factor_attempts_v2.csv"
LLM_FACTOR_TRANSPORTS_V2 = LEDGER_DIR / "llm_factor_transports_v2.csv"


def portable_artifact_path(path: str | Path) -> str:
    """Store project artifacts relative to the repository when possible."""
    artifact = Path(path)
    try:
        return artifact.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return str(artifact)


def resolve_artifact_path(path: str | Path) -> Path:
    """Resolve portable paths and legacy absolute raw-data paths after a move."""
    artifact = Path(path)
    if artifact.is_file():
        return artifact
    if not artifact.is_absolute():
        return PROJECT_ROOT / artifact

    # Historical ledger rows used machine-specific absolute paths. Preserve
    # those immutable rows, but recover the project-owned data/raw suffix so a
    # clone mounted at /workspace (or moved to another machine) remains usable.
    parts = artifact.parts
    raw_markers = [
        index
        for index in range(len(parts) - 1)
        if parts[index : index + 2] == ("data", "raw")
    ]
    if raw_markers:
        return PROJECT_ROOT.joinpath(*parts[raw_markers[-1] :])
    return artifact

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
        csv.DictWriter(f, fieldnames=header, lineterminator="\n").writerow(row)
        f.flush()
        os.fsync(f.fileno())


def _append_idempotent(path: Path, row: dict, *, key: str) -> bool:
    """Append once by a deterministic key; an existing row must be byte-equivalent."""
    with path.open("r+", newline="", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        reader = csv.DictReader(handle)
        header = reader.fieldnames or []
        missing = set(header) - set(row)
        extra = set(row) - set(header)
        if missing or extra:
            raise ValueError(f"ledger row schema mismatch: missing={missing}, extra={extra}")
        normalized = {field: str(row[field]) for field in header}
        for existing in reader:
            if existing[key] != normalized[key]:
                continue
            if existing != normalized:
                raise ValueError(f"ledger key collision with different content: {path.name}:{normalized[key]}")
            return False
        handle.seek(0, os.SEEK_END)
        csv.DictWriter(handle, fieldnames=header, lineterminator="\n").writerow(normalized)
        handle.flush()
        os.fsync(handle.fileno())
        return True


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


def verify_ingest_batches(path: Path = INGEST) -> dict[str, int]:
    """Re-hash every immutable raw batch referenced by the append-only ledger."""
    import pyarrow.parquet as pq

    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    batch_ids = [row["batch_id"] for row in rows]
    if len(batch_ids) != len(set(batch_ids)):
        raise ValueError("ingest ledger contains duplicate batch_id values")
    total_rows = 0
    total_bytes = 0
    for row in rows:
        parquet_path = resolve_artifact_path(row["parquet_path"])
        if not parquet_path.is_file():
            raise FileNotFoundError(parquet_path)
        metadata = pq.read_metadata(parquet_path)
        expected_rows = int(row["row_count"])
        if metadata.num_rows != expected_rows:
            raise ValueError(f"row count mismatch: {parquet_path}")
        if sha256_file(parquet_path) != row["content_sha256"]:
            raise ValueError(f"content hash mismatch: {parquet_path}")
        total_rows += expected_rows
        total_bytes += parquet_path.stat().st_size
    return {"batch_count": len(rows), "row_count": total_rows, "byte_count": total_bytes}


def ingest_snapshot_sha256(path: Path = INGEST) -> str:
    """Hash the ordered committed batch identities without hashing multi-GB data again."""
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    canonical = [
        {
            "batch_id": row["batch_id"],
            "source_api": row["source_api"],
            "params_json": json.loads(row["params_json"]),
            "row_count": int(row["row_count"]),
            "content_sha256": row["content_sha256"],
        }
        for row in rows
    ]
    payload = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()

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
        "parquet_path": portable_artifact_path(parquet_file),
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


def append_daily_run(**kw: object) -> str:
    """Append one terminal daily-run outcome; never store credentials or URLs."""
    kw.setdefault("run_id", uuid.uuid4().hex[:12])
    kw.setdefault("finished_at", datetime.now(timezone.utc).isoformat())
    kw.setdefault("operator", "docker-scheduler")
    _append(DAILY_RUNS, kw)
    return str(kw["run_id"])


def append_shadow_run(**kw: object) -> str:
    kw.setdefault("run_id", uuid.uuid4().hex[:12])
    kw.setdefault("finished_at", datetime.now(timezone.utc).isoformat())
    kw.setdefault("operator", "docker-scheduler")
    for field in ("rebalance_due", "on_time"):
        if isinstance(kw.get(field), bool):
            kw[field] = str(kw[field]).lower()
    _append(SHADOW_RUNS, kw)
    return str(kw["run_id"])


def append_shadow_reconciliation(**kw: object) -> str:
    kw.setdefault("reconciliation_id", uuid.uuid4().hex[:12])
    kw.setdefault("finished_at", datetime.now(timezone.utc).isoformat())
    kw.setdefault("operator", "docker-scheduler")
    _append(SHADOW_RECONCILIATIONS, kw)
    return str(kw["reconciliation_id"])


def append_factor_admission(*, path: Path | None = None, **kw: object) -> str:
    """Append one immutable G1 decision without inflating experiment trial N."""
    kw.setdefault("decision_id", uuid.uuid4().hex[:12])
    kw.setdefault("evaluated_at", datetime.now(timezone.utc).isoformat())
    if isinstance(kw.get("admitted"), bool):
        kw["admitted"] = str(kw["admitted"]).lower()
    _append(path or FACTOR_ADMISSIONS, kw)
    return str(kw["decision_id"])


def append_llm_factor_attempt(*, path: Path | None = None, **kw: object) -> bool:
    """Append one terminal D1 attempt; raw prompts/responses never belong in this ledger."""
    kw.setdefault("operator", "docker-d1-research")
    return _append_idempotent(path or LLM_FACTOR_ATTEMPTS, kw, key="attempt_id")


def append_llm_factor_transport(*, path: Path | None = None, **kw: object) -> bool:
    """Append one immutable D1 provider-transport event without request or response content."""
    kw.setdefault("operator", "docker-d1-research")
    return _append_idempotent(path or LLM_FACTOR_TRANSPORTS, kw, key="event_id")


def append_llm_factor_experiment(*, path: Path | None = None, **kw: object) -> bool:
    """Append the deterministic experiment-ledger counterpart of one D1 attempt."""
    for field in ("params_json", "result_json"):
        if isinstance(kw.get(field), (dict, list)):
            _reject_sensitive_params(kw[field], path=field)
            kw[field] = json.dumps(
                kw[field], ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
    if isinstance(kw.get("admitted"), bool):
        kw["admitted"] = str(kw["admitted"]).lower()
    return _append_idempotent(path or EXPERIMENTS, kw, key="experiment_id")


def append_paper_account(*, path: Path | None = None, **kw: object) -> bool:
    kw.setdefault("created_at", datetime.now(timezone.utc).isoformat())
    kw.setdefault("operator", "docker-scheduler")
    return _append_idempotent(path or PAPER_ACCOUNTS, kw, key="account_id")


def append_paper_event(*, path: Path | None = None, **kw: object) -> bool:
    kw.setdefault("recorded_at", datetime.now(timezone.utc).isoformat())
    kw.setdefault("operator", "docker-scheduler")
    if isinstance(kw.get("payload_json"), (dict, list)):
        kw["payload_json"] = json.dumps(
            kw["payload_json"], ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
    return _append_idempotent(path or PAPER_EVENTS, kw, key="event_id")


def append_paper_run(*, path: Path | None = None, **kw: object) -> bool:
    kw.setdefault("finished_at", datetime.now(timezone.utc).isoformat())
    kw.setdefault("operator", "docker-scheduler")
    return _append_idempotent(path or PAPER_RUNS, kw, key="run_id")


def append_p2_star50_engineering_run(*, path: Path | None = None, **kw: object) -> bool:
    """Append one sanitized P2-1 engineering-only outcome."""
    kw.setdefault("finished_at", datetime.now(timezone.utc).isoformat())
    kw.setdefault("operator", "p2-star50-engineering")
    return _append_idempotent(path or P2_STAR50_ENGINEERING_RUNS, kw, key="run_id")


def append_p2_star50_engineering_admission(*, path: Path | None = None, **kw: object) -> bool:
    """Append one P2-1 boundary decision; this never authorizes production."""
    kw.setdefault("evaluated_at", datetime.now(timezone.utc).isoformat())
    kw.setdefault("operator", "p2-star50-engineering")
    return _append_idempotent(
        path or P2_STAR50_ENGINEERING_ADMISSIONS,
        kw,
        key="decision_id",
    )


def append_p2_star50_effect_run(*, path: Path | None = None, **kw: object) -> bool:
    """Append one sanitized P2-2 result with a real runtime UTC timestamp."""
    kw.setdefault("run_finished_at", datetime.now(timezone.utc).isoformat())
    kw.setdefault("operator", "p2-star50-effect")
    return _append_idempotent(path or P2_STAR50_EFFECT_RUNS, kw, key="run_id")


def append_p2_star50_effect_admission(*, path: Path | None = None, **kw: object) -> bool:
    """Append one P2-2 historical decision; this never authorizes production."""
    kw.setdefault("evaluated_at", datetime.now(timezone.utc).isoformat())
    kw.setdefault("operator", "p2-star50-effect")
    return _append_idempotent(path or P2_STAR50_EFFECT_ADMISSIONS, kw, key="decision_id")


def append_p2_star50_effect_correction_run(*, path: Path | None = None, **kw: object) -> bool:
    """Append one P2-2C run with distinct protocol and real-runtime timestamps."""
    kw.setdefault("run_finished_at", datetime.now(timezone.utc).isoformat())
    kw.setdefault("operator", "p2-star50-effect-correction")
    return _append_idempotent(path or P2_STAR50_EFFECT_CORRECTION_RUNS, kw, key="run_id")


def append_p2_star50_effect_correction_admission(
    *, path: Path | None = None, **kw: object
) -> bool:
    """Append the authoritative corrected historical decision; never authorize production."""
    kw.setdefault("evaluated_at", datetime.now(timezone.utc).isoformat())
    kw.setdefault("operator", "p2-star50-effect-correction")
    return _append_idempotent(
        path or P2_STAR50_EFFECT_CORRECTION_ADMISSIONS,
        kw,
        key="decision_id",
    )

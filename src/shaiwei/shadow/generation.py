"""Deterministic forward shadow training with model- and data-bound signals."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from dateutil.relativedelta import relativedelta
from qlib.contrib.data.handler import Alpha158
from qlib.data.dataset import DatasetH
from qlib.workflow import R

from shaiwei.backtest.baseline import FORWARD_LABEL, _model
from shaiwei.backtest.qlib_runtime import initialize_qlib
from shaiwei.config import PROJECT_ROOT, Settings
from shaiwei.ledger import append_experiment, portable_artifact_path, sha256_file
from shaiwei.provenance import git_head
from shaiwei.shadow.manifest import verify_signal_manifest, write_signal_manifest
from shaiwei.transform.qlib_forward import ForwardSnapshot


class ShadowGenerationError(RuntimeError):
    pass


@dataclass(frozen=True)
class GeneratedSignal:
    signal_date: str
    manifest_path: Path
    signal_sha256: str
    model_spec_sha256: str
    model_artifact_sha256: str
    model_artifact_path: Path
    score_rows: int
    rebalance_due: bool


def signal_segments(settings: Settings, signal_date: date) -> dict[str, tuple[str, str]]:
    train_start = signal_date - relativedelta(years=3)
    valid_start = signal_date - relativedelta(months=settings.baseline.validation_months)
    train_end = valid_start - timedelta(days=1)
    return {
        "train": (train_start.isoformat(), train_end.isoformat()),
        "valid": (valid_start.isoformat(), signal_date.isoformat()),
        "test": (signal_date.isoformat(), signal_date.isoformat()),
    }


def model_spec_sha256(settings: Settings, signal_date: date) -> str:
    payload = {
        "engine": "Alpha158+LightGBM",
        "engine_version": "4.6.0",
        "instrument": settings.baseline.instrument,
        "forward_label": FORWARD_LABEL,
        "segments": signal_segments(settings, signal_date),
        "baseline": settings.baseline.model_dump(mode="json"),
        "joblib_max_procs": settings.compute.joblib_max_procs,
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


def _train_scores(
    settings: Settings,
    signal_date: date,
) -> tuple[pd.DataFrame, dict[str, tuple[str, str]], bytes]:
    segments = signal_segments(settings, signal_date)
    handler = Alpha158(
        instruments=settings.baseline.instrument,
        start_time=segments["train"][0],
        end_time=signal_date.isoformat(),
        fit_start_time=segments["train"][0],
        fit_end_time=segments["train"][1],
        infer_processors=[
            {"class": "RobustZScoreNorm", "kwargs": {"fields_group": "feature", "clip_outlier": True}},
            {"class": "Fillna", "kwargs": {"fields_group": "feature"}},
        ],
        learn_processors=[
            {"class": "DropnaLabel"},
            {"class": "CSRankNorm", "kwargs": {"fields_group": "label"}},
        ],
        label=([FORWARD_LABEL], ["LABEL0"]),
    )
    dataset = DatasetH(handler=handler, segments=segments)
    model = _model(settings)
    with R.start(experiment_name="forward_shadow_alpha158"):
        model.fit(dataset, verbose_eval=50)
        predictions = model.predict(dataset, segment="test")
    scores = predictions.rename("score").reset_index()
    if "instrument" not in scores.columns:
        raise ShadowGenerationError(
            f"qlib predictions missing instrument index: {scores.columns.tolist()}"
        )
    if model.model is None:
        raise ShadowGenerationError("LightGBM model artifact is missing after fit")
    model_bytes = model.model.model_to_string().encode("utf-8")
    return scores.loc[:, ["instrument", "score"]], segments, model_bytes


def _persist_model(output_root: Path, signal_date: date, spec_hash: str, model_bytes: bytes) -> Path:
    model_hash = hashlib.sha256(model_bytes).hexdigest()
    path = output_root / "models" / f"{signal_date:%Y%m%d}-{spec_hash[:12]}-{model_hash[:12]}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        if sha256_file(path) != model_hash:
            raise ShadowGenerationError(f"existing model artifact hash mismatch: {path}")
        return path
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_bytes(model_bytes)
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        os.link(temporary, path)
    except FileExistsError:
        if not path.is_file() or sha256_file(path) != model_hash:
            raise ShadowGenerationError(f"concurrent model artifact differs: {path}")
    finally:
        temporary.unlink(missing_ok=True)
    if sha256_file(path) != model_hash:
        raise ShadowGenerationError("persisted model artifact failed hash verification")
    return path


def _reuse_existing(
    path: Path,
    *,
    signal_date: date,
    snapshot: ForwardSnapshot,
    spec_hash: str,
    rebalance_due: bool,
    previous_signal_sha256: str,
) -> GeneratedSignal | None:
    if not path.is_file():
        return None
    signal_hash = verify_signal_manifest(path)
    document = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "signal_date": signal_date.isoformat(),
        "data_snapshot_sha256": snapshot.data_snapshot_sha256,
        "code_snapshot_sha256": snapshot.code_snapshot_sha256,
        "qlib_artifact_sha256": snapshot.artifact_sha256,
        "model_spec_sha256": spec_hash,
        "rebalance_due": rebalance_due,
        "previous_signal_sha256": previous_signal_sha256,
    }
    differences = {key for key, value in expected.items() if document.get(key) != value}
    if differences:
        raise ShadowGenerationError(f"existing signal binding differs: {sorted(differences)}")
    model_path = Path(str(document.get("model_artifact_path", "")))
    if not model_path.is_absolute():
        model_path = PROJECT_ROOT / model_path
    claimed_model_hash = str(document.get("model_artifact_sha256", ""))
    if not model_path.is_file() or sha256_file(model_path) != claimed_model_hash:
        raise ShadowGenerationError("existing signal model artifact is missing or corrupt")
    return GeneratedSignal(
        signal_date=signal_date.isoformat(),
        manifest_path=path,
        signal_sha256=signal_hash,
        model_spec_sha256=spec_hash,
        model_artifact_sha256=claimed_model_hash,
        model_artifact_path=model_path,
        score_rows=int(document.get("score_rows", len(document.get("orders", [])))),
        rebalance_due=bool(document["rebalance_due"]),
    )


def generate_forward_signal(
    settings: Settings,
    *,
    signal_date: date,
    snapshot: ForwardSnapshot,
    data_complete_at: datetime,
    output_root: Path | None = None,
    previous_manifest_path: Path | None = None,
    rebalance_due: bool = True,
) -> GeneratedSignal:
    output_root = output_root or settings.runtime.data_root / "shadow"
    signal_dir = output_root / "signals"
    spec_hash = model_spec_sha256(settings, signal_date)
    previous_signal_sha256 = ""
    carried_targets: list[str] | None = None
    if previous_manifest_path is not None:
        previous_signal_sha256 = verify_signal_manifest(previous_manifest_path)
        previous = json.loads(previous_manifest_path.read_text(encoding="utf-8"))
        if not rebalance_due:
            carried_targets = [str(order["instrument"]) for order in previous["orders"]]
    manifest_path = signal_dir / (
        f"{signal_date:%Y%m%d}-{snapshot.code_snapshot_sha256[:12]}-"
        f"{snapshot.data_snapshot_sha256[:12]}.json"
    )
    if existing := _reuse_existing(
        manifest_path,
        signal_date=signal_date,
        snapshot=snapshot,
        spec_hash=spec_hash,
        rebalance_due=rebalance_due,
        previous_signal_sha256=previous_signal_sha256,
    ):
        return existing

    sentinel = json.loads(snapshot.sentinel_report_path.read_text(encoding="utf-8"))
    if sentinel.get("required_failures"):
        raise ShadowGenerationError("signal generation blocked by sentinel failures")
    initialize_qlib(settings, provider_uri=snapshot.provider_uri)
    scores, segments, model_bytes = _train_scores(settings, signal_date)
    model_path = _persist_model(output_root, signal_date, spec_hash, model_bytes)
    model_hash = sha256_file(model_path)
    generated_at = datetime.now(timezone.utc)
    path, signal_hash = write_signal_manifest(
        scores,
        signal_date=signal_date,
        topk=settings.backtest.topk,
        sentinel_results=list(sentinel["results"]),
        data_complete_at=data_complete_at,
        generated_at=generated_at,
        data_snapshot_sha256=snapshot.data_snapshot_sha256,
        code_commit=git_head(),
        code_snapshot_sha256=snapshot.code_snapshot_sha256,
        output_dir=signal_dir,
        environment=settings.runtime.environment,
        qlib_artifact_sha256=snapshot.artifact_sha256,
        model_spec_sha256=spec_hash,
        model_artifact_sha256=model_hash,
        model_artifact_path=portable_artifact_path(model_path),
        target_instruments=carried_targets,
        rebalance_due=rebalance_due,
        previous_signal_sha256=previous_signal_sha256,
        rebalance_days=settings.backtest.rebalance_days,
    )
    # score_rows is execution evidence rather than part of the signed signal
    # payload; it remains in the append-only experiment ledger.
    append_experiment(
        candidate_source="Alpha158-forward-shadow",
        model_or_engine="LightGBM",
        engine_version="4.6.0",
        seed=settings.baseline.seed,
        prompt_hash="",
        code_sha256=snapshot.code_snapshot_sha256,
        data_snapshot_sha256=snapshot.data_snapshot_sha256,
        feature_or_formula=f"Alpha158; label={FORWARD_LABEL}",
        params_json={"segments": segments, "topk": settings.backtest.topk, "model_spec": spec_hash},
        train_period=f"{segments['train'][0]}~{segments['train'][1]}",
        valid_period=f"{segments['valid'][0]}~{segments['valid'][1]}; signal={signal_date}",
        result_json={
            "signal_sha256": signal_hash,
            "manifest_path": portable_artifact_path(path),
            "score_rows": len(scores),
            "model_artifact_sha256": model_hash,
            "rebalance_due": rebalance_due,
        },
        admitted=False,
        reject_reason="forward shadow signal; not a factor-admission experiment",
    )
    return GeneratedSignal(
        signal_date=signal_date.isoformat(),
        manifest_path=path,
        signal_sha256=signal_hash,
        model_spec_sha256=spec_hash,
        model_artifact_sha256=model_hash,
        model_artifact_path=model_path,
        score_rows=len(scores),
        rebalance_due=rebalance_due,
    )

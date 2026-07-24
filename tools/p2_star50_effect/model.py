"""Frozen Alpha158/LightGBM training and prediction for P2-2."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import resource
import time
from typing import Any
from unittest.mock import patch

import lightgbm
import pandas as pd
import qlib
from qlib.config import REG_CN
from qlib.contrib.data.handler import Alpha158
from qlib.contrib.model.gbdt import LGBModel
from qlib.data.dataset import DatasetH
from qlib.workflow import R

from shaiwei.config import PROJECT_ROOT
from shaiwei.ledger import sha256_file

from tools.p2_star50_effect.contract import EffectGateFailure, canonical_sha256


def _iso(value: str) -> str:
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def _model(protocol: dict[str, Any]) -> LGBModel:
    spec = protocol["model"]
    seed = int(spec["seed"])
    return LGBModel(
        loss="mse",
        learning_rate=float(spec["learning_rate"]),
        num_leaves=int(spec["num_leaves"]),
        max_depth=int(spec["max_depth"]),
        colsample_bytree=float(spec["colsample_bytree"]),
        subsample=float(spec["subsample"]),
        reg_alpha=float(spec["reg_alpha"]),
        reg_lambda=float(spec["reg_lambda"]),
        num_threads=int(spec["num_threads"]),
        seed=seed,
        feature_fraction_seed=seed,
        bagging_seed=seed,
        data_random_seed=seed,
        deterministic=bool(spec["deterministic"]),
        force_col_wise=bool(spec["force_col_wise"]),
        verbosity=-1,
        num_boost_round=int(spec["num_boost_round"]),
        early_stopping_rounds=int(spec["early_stopping_rounds"]),
    )


def _prediction_hash(prediction: pd.Series) -> str:
    frame = prediction.rename("score").reset_index()
    frame.columns = ["datetime", "instrument", "score"]
    frame["datetime"] = pd.to_datetime(frame["datetime"]).dt.strftime("%Y-%m-%d")
    frame["instrument"] = frame["instrument"].astype(str)
    frame["score"] = pd.to_numeric(frame["score"], errors="raise").map(lambda value: float(value).hex())
    frame = frame.sort_values(["datetime", "instrument"]).reset_index(drop=True)
    return canonical_sha256(frame.to_dict("records"))


def train_window(
    *,
    protocol: dict[str, Any],
    window: dict[str, Any],
    pressure: dict[str, Any],
    pass_root: Path,
) -> dict[str, Any]:
    provider = PROJECT_ROOT / protocol["identity"]["qlib_provider"]
    qlib.init(provider_uri=str(provider), region=REG_CN)
    segments = {
        "train": tuple(map(_iso, window["train"])),
        "valid": tuple(map(_iso, window["valid"])),
        "test": tuple(map(_iso, window["test"])),
        "pressure": (_iso(pressure["start"]), _iso(pressure["end"])),
    }
    handler_end = max(segments["test"][1], segments["pressure"][1])
    handler = Alpha158(
        instruments=protocol["identity"]["instrument_id"],
        start_time=segments["train"][0],
        end_time=handler_end,
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
        label=([protocol["model"]["label"]], ["LABEL0"]),
    )
    dataset = DatasetH(handler=handler, segments=segments)
    segment_rows = {
        name: int(len(dataset.prepare(name, col_set="feature")))
        for name in ("train", "valid", "test", "pressure")
    }
    if not all(segment_rows.values()):
        raise EffectGateFailure(f"Alpha158 produced an empty segment for {window['name']}")
    model = _model(protocol)
    started_at = datetime.now(timezone.utc).isoformat()
    started = time.monotonic()
    with patch.object(R, "log_metrics", return_value=None):
        model.fit(dataset, verbose_eval=False)
    elapsed = time.monotonic() - started
    test_prediction = model.predict(dataset, segment="test")
    pressure_prediction = model.predict(dataset, segment="pressure")
    if test_prediction.empty or pressure_prediction.empty:
        raise EffectGateFailure(f"empty prediction output for {window['name']}")
    if test_prediction.isna().all() or pressure_prediction.isna().all():
        raise EffectGateFailure(f"all-null prediction output for {window['name']}")

    booster = getattr(model, "model", None)
    if booster is None or not hasattr(booster, "model_to_string"):
        raise EffectGateFailure("LightGBM model text is unavailable for hashing")
    model_text = booster.model_to_string()
    window_root = pass_root / str(window["name"])
    window_root.mkdir(parents=True, exist_ok=True)
    model_path = window_root / "model.txt"
    model_path.write_text(model_text, encoding="utf-8")
    model_sha = sha256_file(model_path)

    prediction_hashes: dict[str, str] = {}
    predictions: dict[str, pd.Series] = {}
    for name, prediction in (("test", test_prediction), ("pressure", pressure_prediction)):
        prediction = prediction.sort_index()
        predictions[name] = prediction
        path = window_root / f"{name}_predictions.parquet"
        prediction.rename("score").to_frame().reset_index().to_parquet(path, index=False, compression="zstd")
        prediction_hashes[name] = _prediction_hash(prediction)

    metadata = {
        "window": window["name"],
        "segments": segments,
        "segment_rows": segment_rows,
        "started_at": started_at,
        "run_finished_at": datetime.now(timezone.utc).isoformat(),
        "wall_seconds": elapsed,
        "maximum_resident_set_size": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
        "python_version": __import__("platform").python_version(),
        "qlib_version": getattr(qlib, "__version__", "unknown"),
        "lightgbm_version": lightgbm.__version__,
        "model_sha256": model_sha,
        "prediction_canonical_sha256": prediction_hashes,
    }
    metadata_path = window_root / "training_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "window": window["name"],
        "predictions": predictions,
        "model_sha256": model_sha,
        "prediction_hashes": prediction_hashes,
        "metadata": metadata,
        "metadata_sha256": sha256_file(metadata_path),
    }

"""Purged Alpha158/LightGBM training for the single P2-2C correction."""

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
from qlib.data.dataset.handler import DataHandlerLP
from qlib.workflow import R

from shaiwei.config import PROJECT_ROOT
from shaiwei.ledger import sha256_file

from tools.p2_star50_effect_correction.calendar import purged_window_segments
from tools.p2_star50_effect_correction.contract import CorrectionGateFailure, canonical_sha256


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


def prediction_hash(prediction: pd.Series) -> str:
    frame = prediction.rename("score").reset_index()
    frame.columns = ["datetime", "instrument", "score"]
    frame["datetime"] = pd.to_datetime(frame["datetime"]).dt.strftime("%Y-%m-%d")
    frame["instrument"] = frame["instrument"].astype(str)
    frame["score"] = pd.to_numeric(frame["score"], errors="raise").map(lambda value: float(value).hex())
    frame = frame.sort_values(["datetime", "instrument"]).reset_index(drop=True)
    return canonical_sha256(frame.to_dict("records"))


def training_time_contract(
    protocol: dict[str, Any],
    window: dict[str, Any],
    pressure: dict[str, Any],
    calendar: list[str],
) -> dict[str, Any]:
    """Return the only permitted handler/segment clock for corrected training."""
    required = protocol["model"]["required_purged_last_signal_dates"][window["name"]]
    segments, maturity = purged_window_segments(window, calendar, required)
    segments["pressure"] = (_iso(pressure["start"]), _iso(pressure["end"]))
    return {
        "segments": segments,
        "maturity": maturity,
        "handler_start_time": _iso(window["train"][0]),
        "handler_end_time": max(segments["test"][1], segments["pressure"][1]),
        "fit_start_time": _iso(window["train"][0]),
        "fit_end_time": segments["train"][1],
    }


def train_window(
    *,
    protocol: dict[str, Any],
    window: dict[str, Any],
    pressure: dict[str, Any],
    calendar: list[str],
    pass_root: Path,
) -> dict[str, Any]:
    """Train once with purged train/valid endpoints and unchanged test/pressure periods."""
    time_contract = training_time_contract(protocol, window, pressure, calendar)
    segments = time_contract["segments"]
    maturity = time_contract["maturity"]
    provider = PROJECT_ROOT / protocol["identity"]["qlib_provider"]
    qlib.init(provider_uri=str(provider), region=REG_CN)
    handler = Alpha158(
        instruments=protocol["identity"]["instrument_id"],
        start_time=time_contract["handler_start_time"],
        end_time=time_contract["handler_end_time"],
        fit_start_time=time_contract["fit_start_time"],
        fit_end_time=time_contract["fit_end_time"],
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
    feature_rows = {
        name: int(len(dataset.prepare(name, col_set="feature")))
        for name in ("train", "valid", "test", "pressure")
    }
    learning_frames = {
        name: dataset.prepare(
            name,
            col_set=["feature", "label"],
            data_key=DataHandlerLP.DK_L,
        )
        for name in ("train", "valid")
    }
    learning_rows = {name: int(len(frame)) for name, frame in learning_frames.items()}
    if not all(feature_rows.values()) or not all(learning_rows.values()):
        raise CorrectionGateFailure(f"Alpha158 produced an empty segment for {window['name']}")
    for name, frame in learning_frames.items():
        last_observation = pd.Timestamp(frame.index.get_level_values("datetime").max()).strftime("%Y-%m-%d")
        if last_observation != segments[name][1]:
            raise CorrectionGateFailure(
                f"actual {name} last learning observation is not the purged endpoint: {last_observation}"
            )
        if frame["label"].isna().any().any():
            raise CorrectionGateFailure(f"purged {name} learning frame still contains null labels")

    model = _model(protocol)
    started_at = datetime.now(timezone.utc).isoformat()
    started = time.monotonic()
    with patch.object(R, "log_metrics", return_value=None):
        model.fit(dataset, verbose_eval=False)
    elapsed = time.monotonic() - started
    predictions: dict[str, pd.Series] = {
        "test": model.predict(dataset, segment="test").sort_index(),
        "pressure": model.predict(dataset, segment="pressure").sort_index(),
    }
    if any(prediction.empty or prediction.isna().all() for prediction in predictions.values()):
        raise CorrectionGateFailure(f"empty/all-null prediction output for {window['name']}")

    booster = getattr(model, "model", None)
    if booster is None or not hasattr(booster, "model_to_string"):
        raise CorrectionGateFailure("LightGBM model text is unavailable for hashing")
    window_root = pass_root / str(window["name"])
    window_root.mkdir(parents=True, exist_ok=True)
    model_path = window_root / "model.txt"
    model_path.write_text(booster.model_to_string(), encoding="utf-8")
    model_sha = sha256_file(model_path)

    prediction_hashes: dict[str, str] = {}
    prediction_file_hashes: dict[str, str] = {}
    for name, prediction in predictions.items():
        path = window_root / f"{name}_predictions.parquet"
        prediction.rename("score").to_frame().reset_index().to_parquet(
            path,
            index=False,
            compression="zstd",
        )
        prediction_hashes[name] = prediction_hash(prediction)
        prediction_file_hashes[name] = sha256_file(path)

    metadata = {
        "window": window["name"],
        "original_segments": {
            name: tuple(map(_iso, window[name])) for name in ("train", "valid", "test")
        },
        "effective_segments": segments,
        "handler_fit_end_time": time_contract["fit_end_time"],
        "label_maturity_audit": maturity,
        "feature_rows": feature_rows,
        "learning_rows": learning_rows,
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
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "window": window["name"],
        "predictions": predictions,
        "model_sha256": model_sha,
        "prediction_hashes": prediction_hashes,
        "prediction_file_hashes": prediction_file_hashes,
        "metadata": metadata,
        "metadata_sha256": sha256_file(metadata_path),
    }

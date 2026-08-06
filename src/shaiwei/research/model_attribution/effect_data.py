"""Qlib dataset and two-model execution boundary for an approved M6-2 release."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import qlib
from qlib.config import REG_CN
from qlib.contrib.data.handler import Alpha158
from qlib.data.dataset import DatasetH
from qlib.data.dataset.handler import DataHandlerLP
from qlib.workflow import R

from shaiwei.research.model_attribution.contract import AttributionError
from shaiwei.research.model_attribution.models import build_models
from shaiwei.research.model_attribution.scoring import rank_blend


@dataclass(frozen=True)
class WindowModelOutput:
    window: str
    segments: dict[str, tuple[str, str]]
    mature_predictions: dict[str, pd.Series]
    test_predictions: dict[str, pd.Series]
    mature_labels: pd.Series
    stress_predictions: dict[str, pd.Series]
    model_artifacts: dict[str, bytes]


def initialize_effect_qlib(provider_root: Path) -> None:
    if not provider_root.is_dir():
        raise AttributionError("M6 Qlib provider root is absent")
    qlib.init(
        provider_uri=str(provider_root.resolve()),
        region=REG_CN,
        exp_manager={
            "class": "MLflowExpManager",
            "module_path": "qlib.workflow.expm",
            "kwargs": {
                "uri": "sqlite:////tmp/m6-mlflow.db",
                "default_exp_name": "m6-model-attribution",
            },
        },
    )


def _segments(window: dict[str, Any], *, include_stress: bool) -> dict[str, tuple[str, str]]:
    result = {
        "train": (str(window["train"][0]), str(window["purged_train_last_signal"])),
        "valid": (str(window["valid"][0]), str(window["purged_valid_last_signal"])),
        "test": (str(window["test"][0]), str(window["test"][1])),
    }
    if include_stress:
        result["stress_2026h1"] = ("2026-01-01", "2026-06-30")
    return result


def build_window_dataset(protocol: dict[str, Any], window: dict[str, Any]) -> DatasetH:
    include_stress = str(window["name"]) == "W6"
    segments = _segments(window, include_stress=include_stress)
    end_time = "2026-06-30" if include_stress else str(window["test"][1])
    handler_spec = protocol["shared_handler"]
    handler = Alpha158(
        instruments=str(protocol["scope"]["qlib_instrument"]),
        start_time=str(window["train"][0]),
        end_time=end_time,
        fit_start_time=segments["train"][0],
        fit_end_time=segments["train"][1],
        infer_processors=[
            {"class": row["class"], "kwargs": {key: value for key, value in row.items() if key != "class"}}
            for row in handler_spec["infer_processors"]
        ],
        learn_processors=[
            {"class": row["class"], "kwargs": {key: value for key, value in row.items() if key != "class"}}
            if len(row) > 1
            else {"class": row["class"]}
            for row in handler_spec["learn_processors"]
        ],
        label=([str(protocol["clock_and_label"]["label_expression"])], ["LABEL0"]),
    )
    return DatasetH(handler=handler, segments=segments)


def _member_series(value: pd.Series, name: str) -> pd.Series:
    if not isinstance(value, pd.Series) or not isinstance(value.index, pd.MultiIndex):
        raise AttributionError(f"M6 {name} is not a member-day Series")
    if value.index.nlevels != 2:
        raise AttributionError(f"M6 {name} index shape differs")
    result = pd.to_numeric(value, errors="raise").astype(float).sort_index()
    result.index = result.index.set_names(["datetime", "instrument"])
    if result.index.has_duplicates or result.empty or not np.isfinite(result.to_numpy()).all():
        raise AttributionError(f"M6 {name} is empty, duplicated, or nonfinite")
    codes = result.index.get_level_values("instrument").astype(str)
    if codes.str.startswith("BJ").any() or codes.str.endswith("BJ").any() or codes.str.endswith(".BJ").any():
        raise AttributionError("M6 .BJ returned in real model data")
    return result


def _labels(dataset: DatasetH, window: dict[str, Any]) -> pd.Series:
    prepared = dataset.prepare("test", col_set="label", data_key=DataHandlerLP.DK_L)
    if isinstance(prepared, pd.DataFrame):
        if prepared.shape[1] != 1:
            raise AttributionError("M6 expected one processed label column")
        label = prepared.iloc[:, 0]
    elif isinstance(prepared, pd.Series):
        label = prepared
    else:
        raise AttributionError("M6 processed labels have unexpected type")
    cutoff = pd.Timestamp(str(window["score_last_signal"]))
    dates = pd.to_datetime(label.index.get_level_values(0))
    return _member_series(label.loc[dates <= cutoff].dropna().rename("label"), "mature label")


def _prediction(model: Any, dataset: DatasetH, segment: str, name: str) -> pd.Series:
    value = model.predict(dataset, segment=segment)
    if not isinstance(value, pd.Series):
        raise AttributionError(f"M6 {name} prediction is not a Series")
    return _member_series(value.rename("score"), name)


def _mature(prediction: pd.Series, labels: pd.Series, name: str) -> pd.Series:
    missing = labels.index.difference(prediction.index)
    if len(missing):
        raise AttributionError(f"M6 {name} lacks mature label keys")
    selected = prediction.reindex(labels.index)
    return _member_series(selected.rename("score"), f"{name} mature prediction")


def _model_artifacts(lgbm: Any, ridge: Any) -> dict[str, bytes]:
    if getattr(lgbm, "model", None) is None:
        raise AttributionError("M6 LightGBM model artifact is absent")
    lgbm_text = lgbm.model.model_to_string().encode("utf-8")
    coefficients = np.asarray(getattr(ridge, "coef_", None), dtype=float)
    if coefficients.ndim != 1 or not np.isfinite(coefficients).all():
        raise AttributionError("M6 Ridge coefficients are absent or invalid")
    intercept = float(getattr(ridge, "intercept_", float("nan")))
    if not np.isfinite(intercept):
        raise AttributionError("M6 Ridge intercept is invalid")
    import json

    ridge_payload = (
        json.dumps(
            {"coef": coefficients.tolist(), "intercept": intercept},
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )
    return {"clean_lgbm_control_v1.txt": lgbm_text, "ridge_alpha1_v1.json": ridge_payload}


def fit_window(protocol: dict[str, Any], window: dict[str, Any]) -> WindowModelOutput:
    dataset = build_window_dataset(protocol, window)
    lgbm, ridge = build_models(protocol)
    with R.start(experiment_name=f"m6-{window['name']}"):
        lgbm.fit(dataset, verbose_eval=0)
        ridge.fit(dataset)
    control_test = _prediction(lgbm, dataset, "test", "LightGBM test")
    ridge_test = _prediction(ridge, dataset, "test", "Ridge test")
    if not control_test.index.equals(ridge_test.index):
        raise AttributionError("M6 full test prediction keys differ")
    blend_test = rank_blend(control_test, ridge_test)
    labels = _labels(dataset, window)
    test_predictions = {
        "clean_lgbm_control_v1": control_test,
        "ridge_alpha1_v1": ridge_test,
        "lgbm_ridge_rank_blend_50_50_v1": blend_test,
    }
    mature_predictions = {name: _mature(value, labels, name) for name, value in test_predictions.items()}
    stress_predictions: dict[str, pd.Series] = {}
    if str(window["name"]) == "W6":
        control_stress = _prediction(lgbm, dataset, "stress_2026h1", "LightGBM stress")
        ridge_stress = _prediction(ridge, dataset, "stress_2026h1", "Ridge stress")
        if not control_stress.index.equals(ridge_stress.index):
            raise AttributionError("M6 stress prediction keys differ")
        stress_predictions = {
            "clean_lgbm_control_v1": control_stress,
            "ridge_alpha1_v1": ridge_stress,
            "lgbm_ridge_rank_blend_50_50_v1": rank_blend(control_stress, ridge_stress),
        }
    return WindowModelOutput(
        window=str(window["name"]),
        segments={key: tuple(value) for key, value in dataset.segments.items()},
        mature_predictions=mature_predictions,
        test_predictions=test_predictions,
        mature_labels=labels,
        stress_predictions=stress_predictions,
        model_artifacts=_model_artifacts(lgbm, ridge),
    )

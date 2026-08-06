"""Narrow Qlib model factories and injected training adapter for M6."""

from __future__ import annotations

from typing import Any, Callable

import pandas as pd
from qlib.contrib.model.gbdt import LGBModel
from qlib.contrib.model.linear import LinearModel

from shaiwei.research.model_attribution.contract import AttributionError


def build_models(protocol: dict[str, Any]) -> tuple[LGBModel, LinearModel]:
    specs = {row["arm_id"]: row for row in protocol["arms"]}
    control = dict(specs["clean_lgbm_control_v1"]["parameters"])
    ridge = dict(specs["ridge_alpha1_v1"]["parameters"])
    lgbm = LGBModel(**control)
    linear = LinearModel(**ridge)
    return lgbm, linear


def model_factory_smoke(protocol: dict[str, Any]) -> dict[str, Any]:
    lgbm, ridge = build_models(protocol)
    if not isinstance(lgbm, LGBModel) or not isinstance(ridge, LinearModel):
        raise AttributionError("M6 qlib model factory returned unexpected types")
    if ridge.estimator != "ridge" or float(ridge.alpha) != 1.0:
        raise AttributionError("M6 Ridge parameters differ")
    return {
        "control_class": f"{type(lgbm).__module__}.{type(lgbm).__name__}",
        "ridge_class": f"{type(ridge).__module__}.{type(ridge).__name__}",
        "ridge_estimator": ridge.estimator,
        "ridge_alpha": float(ridge.alpha),
        "fit_called": False,
    }


def fit_predict_with_injected_models(
    dataset: Any,
    *,
    model_factory: Callable[[], tuple[Any, Any]],
) -> tuple[pd.Series, pd.Series]:
    """Fit two injected models; the M6-1 CLI deliberately never calls this adapter."""
    control, ridge = model_factory()
    control.fit(dataset)
    ridge.fit(dataset)
    control_prediction = control.predict(dataset, segment="test")
    ridge_prediction = ridge.predict(dataset, segment="test")
    if not isinstance(control_prediction, pd.Series) or not isinstance(ridge_prediction, pd.Series):
        raise AttributionError("M6 injected model prediction is not a Series")
    return control_prediction.sort_index(), ridge_prediction.sort_index()

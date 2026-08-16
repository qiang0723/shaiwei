"""W7 clean Alpha158/LightGBM prediction lineage without effect inspection."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from qlib.workflow import R

from shaiwei.research.model_attribution.effect_data import (
    build_window_dataset,
    initialize_effect_qlib,
)
from shaiwei.research.model_attribution.models import build_models
from shaiwei.research.trend_swing.contract import canonical_sha256
from shaiwei.research.trend_swing.r3g2.contract import EffectProtocol, R3G2Error
from shaiwei.research.trend_swing.r3g2.evidence import canonical_json, write_once_bytes


@dataclass(frozen=True)
class W7Output:
    predictions: pd.Series
    model_bytes: bytes


def _predictions(value: object) -> pd.Series:
    if not isinstance(value, pd.Series) or not isinstance(value.index, pd.MultiIndex):
        raise R3G2Error("R3G-2 W7 prediction is not a member-day Series")
    if value.index.nlevels != 2:
        raise R3G2Error("R3G-2 W7 prediction index shape differs")
    result = pd.to_numeric(value, errors="raise").astype(float).sort_index().rename("score")
    result.index = result.index.set_names(["datetime", "instrument"])
    dates = pd.to_datetime(result.index.get_level_values("datetime"))
    codes = result.index.get_level_values("instrument").astype(str)
    if (
        result.empty
        or result.index.has_duplicates
        or not np.isfinite(result.to_numpy()).all()
        or dates.min() < pd.Timestamp("2025-01-01")
        or dates.max() > pd.Timestamp("2025-12-31")
        or codes.str.startswith("BJ").any()
        or codes.str.endswith(".BJ").any()
    ):
        raise R3G2Error("R3G-2 W7 prediction failed its result-blind quality gate")
    return result


def fit_w7(
    protocol: EffectProtocol, provider_root: Path, *, initialize: bool = True
) -> W7Output:
    """Fit exactly the frozen clean control and return scores, never labels or metrics."""
    m6 = protocol.m6_document()
    window = protocol.w7_window()
    if initialize:
        initialize_effect_qlib(provider_root)
    dataset = build_window_dataset(m6, window)
    model, _unused_ridge = build_models(m6)
    with R.start(experiment_name="ts-v5-r3g2-w7-lineage"):
        model.fit(dataset, verbose_eval=0)
    prediction = _predictions(model.predict(dataset, segment="test"))
    fitted = getattr(model, "model", None)
    if fitted is None:
        raise R3G2Error("R3G-2 W7 LightGBM artifact is absent")
    model_bytes = fitted.model_to_string().encode("utf-8")
    if not model_bytes:
        raise R3G2Error("R3G-2 W7 LightGBM artifact is empty")
    return W7Output(predictions=prediction, model_bytes=model_bytes)


def _prediction_bytes(predictions: pd.Series) -> tuple[bytes, pd.DataFrame]:
    frame = _predictions(predictions).reset_index()
    frame["datetime"] = pd.to_datetime(frame["datetime"]).dt.strftime("%Y-%m-%d")
    frame["instrument"] = frame["instrument"].astype(str)
    frame = frame.sort_values(["datetime", "instrument"]).reset_index(drop=True)
    buffer = BytesIO()
    frame.to_parquet(buffer, index=False, compression="zstd", engine="pyarrow")
    return buffer.getvalue(), frame


def save_pass(root: Path, output: W7Output, protocol: EffectProtocol) -> dict[str, Any]:
    predictions, frame = _prediction_bytes(output.predictions)
    artifacts: dict[str, dict[str, Any]] = {}
    for relative, payload, rows in (
        ("predictions.parquet", predictions, len(frame)),
        ("model.txt", output.model_bytes, None),
    ):
        path = root / relative
        digest, reused = write_once_bytes(path, payload)
        metadata: dict[str, Any] = {
            "sha256": digest,
            "byte_count": path.stat().st_size,
            "reused": reused,
        }
        if rows is not None:
            metadata["row_count"] = rows
        artifacts[relative] = metadata
    summary = {
        "schema_version": "ts-v5-r3g2-w7-lineage-pass-summary-v1",
        "protocol_sha256": protocol.sha256,
        "window": protocol.w7_window(),
        "prediction_row_count": len(frame),
        "prediction_date_min": str(frame["datetime"].min()),
        "prediction_date_max": str(frame["datetime"].max()),
        "contains_label_rankic_return_or_portfolio_metric": False,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
    }
    summary_payload = canonical_json(summary) + b"\n"
    summary_sha, summary_reused = write_once_bytes(root / "summary.json", summary_payload)
    artifacts["summary.json"] = {
        "sha256": summary_sha,
        "byte_count": (root / "summary.json").stat().st_size,
        "reused": summary_reused,
    }
    canonical_artifacts = {
        name: {key: value for key, value in metadata.items() if key != "reused"}
        for name, metadata in artifacts.items()
    }
    manifest = {
        "schema_version": "ts-v5-r3g2-w7-lineage-pass-manifest-v1",
        "artifacts": canonical_artifacts,
        "bundle_sha256": canonical_sha256(canonical_artifacts),
    }
    manifest_payload = canonical_json(manifest) + b"\n"
    manifest_sha, manifest_reused = write_once_bytes(root / "manifest.json", manifest_payload)
    return {
        "manifest_sha256": manifest_sha,
        "bundle_sha256": manifest["bundle_sha256"],
        "all_reused": manifest_reused and all(row["reused"] for row in artifacts.values()),
    }

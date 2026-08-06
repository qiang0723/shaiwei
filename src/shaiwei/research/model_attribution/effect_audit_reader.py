"""Strict M6-2 artifact reader used only by the independent auditor."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from shaiwei.research.model_attribution.contract import (
    AttributionError,
    canonical_sha256,
    sha256_file,
)
from shaiwei.research.model_attribution.effect_schema import ARMS, WINDOWS


def _series(path: Path, value_name: str) -> pd.Series:
    frame = pd.read_parquet(path)
    if list(frame.columns) != ["datetime", "instrument", value_name]:
        raise AttributionError("M6 audit member-day schema differs")
    frame["datetime"] = pd.to_datetime(frame["datetime"])
    value = frame.set_index(["datetime", "instrument"])[value_name].sort_index()
    if value.empty or value.index.has_duplicates:
        raise AttributionError("M6 audit member-day keys are empty or duplicated")
    codes = value.index.get_level_values("instrument").astype(str)
    if codes.str.startswith("BJ").any() or codes.str.endswith("BJ").any():
        raise AttributionError("M6 audit found .BJ in member-day evidence")
    return value


def _report(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    expected = ["datetime", "gross_return", "benchmark_return", "recorded_cost", "turnover"]
    if list(frame.columns) != expected:
        raise AttributionError("M6 audit backtest schema differs")
    frame["datetime"] = pd.to_datetime(frame["datetime"])
    result = frame.set_index("datetime").sort_index()
    if result.empty or result.index.has_duplicates:
        raise AttributionError("M6 audit backtest dates are empty or duplicated")
    return result


def _document(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AttributionError(f"M6 audit document is invalid: {path.name}") from error
    if not isinstance(value, dict):
        raise AttributionError(f"M6 audit document is not a mapping: {path.name}")
    return value


def read_pass(root: Path) -> dict[str, Any]:
    manifest = _document(root / "manifest.json")
    if manifest.get("schema_version") != "m6-model-attribution-pass-manifest-v1":
        raise AttributionError("M6 audit pass manifest schema differs")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or not artifacts:
        raise AttributionError("M6 audit pass manifest artifacts are absent")
    if manifest.get("bundle_sha256") != canonical_sha256(artifacts):
        raise AttributionError("M6 audit pass bundle hash differs")
    declared = set(artifacts)
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    if actual != declared:
        raise AttributionError("M6 audit pass file set differs from manifest")
    for relative, metadata in artifacts.items():
        if not isinstance(metadata, dict) or metadata.get("sha256") != sha256_file(root / relative):
            raise AttributionError(f"M6 audit artifact hash differs: {relative}")
    predictions: dict[str, dict[str, pd.Series]] = {}
    test_predictions: dict[str, dict[str, pd.Series]] = {}
    labels: dict[str, pd.Series] = {}
    reports: dict[str, dict[str, pd.DataFrame]] = {}
    top30: dict[str, dict[str, dict[str, list[str]]]] = {}
    for window in WINDOWS:
        labels[window] = _series(root / window / "mature_labels.parquet", "label")
        predictions[window] = {
            arm: _series(root / window / "mature_predictions" / f"{arm}.parquet", "score") for arm in ARMS
        }
        test_predictions[window] = {
            arm: _series(root / window / "test_predictions" / f"{arm}.parquet", "score") for arm in ARMS
        }
        reports[window] = {arm: _report(root / window / "backtest" / f"{arm}.parquet") for arm in ARMS}
        top30[window] = {arm: _document(root / window / "top30" / f"{arm}.json") for arm in ARMS}
    stress_reports = {arm: _report(root / "W6" / "stress_backtest" / f"{arm}.parquet") for arm in ARMS}
    return {
        "manifest": manifest,
        "predictions": predictions,
        "test_predictions": test_predictions,
        "labels": labels,
        "reports": reports,
        "stress_reports": stress_reports,
        "top30": top30,
        "summary": _document(root / "summary.json"),
    }

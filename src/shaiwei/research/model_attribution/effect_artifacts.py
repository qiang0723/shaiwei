"""Canonical write-once M6-2 model, prediction, and backtest artifacts."""

from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
from typing import Any

import pandas as pd

from shaiwei.research.model_attribution.contract import AttributionError, canonical_sha256
from shaiwei.research.model_attribution.effect_contract import (
    write_once_bytes,
    write_once_document,
)
from shaiwei.research.model_attribution.effect_data import WindowModelOutput
from shaiwei.research.model_attribution.effect_schema import ARMS, WINDOWS


def _series_frame(series: pd.Series, value_name: str) -> pd.DataFrame:
    frame = series.rename(value_name).reset_index()
    if list(frame.columns[:2]) != ["datetime", "instrument"]:
        raise AttributionError("M6 member-day artifact columns differ")
    frame["datetime"] = pd.to_datetime(frame["datetime"]).dt.strftime("%Y-%m-%d")
    frame["instrument"] = frame["instrument"].astype(str)
    return frame.sort_values(["datetime", "instrument"]).reset_index(drop=True)


def _report_frame(report: pd.DataFrame) -> pd.DataFrame:
    frame = report.copy().reset_index()
    frame = frame.rename(columns={frame.columns[0]: "datetime"})
    expected = ["datetime", "gross_return", "benchmark_return", "recorded_cost", "turnover"]
    if list(frame.columns) != expected:
        raise AttributionError("M6 backtest artifact columns differ")
    frame["datetime"] = pd.to_datetime(frame["datetime"]).dt.strftime("%Y-%m-%d")
    return frame.sort_values("datetime").reset_index(drop=True)


def _parquet_bytes(frame: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    frame.to_parquet(buffer, index=False, compression="zstd", engine="pyarrow")
    return buffer.getvalue()


def _save_frame(path: Path, frame: pd.DataFrame) -> dict[str, Any]:
    digest, reused = write_once_bytes(path, _parquet_bytes(frame))
    return {"sha256": digest, "row_count": len(frame), "byte_count": path.stat().st_size, "reused": reused}


def _save_bytes(path: Path, payload: bytes) -> dict[str, Any]:
    digest, reused = write_once_bytes(path, payload)
    return {"sha256": digest, "byte_count": path.stat().st_size, "reused": reused}


def save_pass(
    root: Path,
    outputs: dict[str, WindowModelOutput],
    reports: dict[str, dict[str, pd.DataFrame]],
    stress_reports: dict[str, pd.DataFrame],
    top30: dict[str, dict[str, dict[str, list[str]]]],
    summary: dict[str, Any],
) -> dict[str, Any]:
    if tuple(outputs) != WINDOWS or tuple(reports) != WINDOWS:
        raise AttributionError("M6 pass window order differs")
    artifacts: dict[str, dict[str, Any]] = {}
    for window in WINDOWS:
        output = outputs[window]
        prefix = Path(window)
        for name, payload in sorted(output.model_artifacts.items()):
            relative = (prefix / "models" / name).as_posix()
            artifacts[relative] = _save_bytes(root / relative, payload)
        label_relative = (prefix / "mature_labels.parquet").as_posix()
        artifacts[label_relative] = _save_frame(
            root / label_relative, _series_frame(output.mature_labels, "label")
        )
        for arm in ARMS:
            mature_relative = (prefix / "mature_predictions" / f"{arm}.parquet").as_posix()
            test_relative = (prefix / "test_predictions" / f"{arm}.parquet").as_posix()
            report_relative = (prefix / "backtest" / f"{arm}.parquet").as_posix()
            top_relative = (prefix / "top30" / f"{arm}.json").as_posix()
            artifacts[mature_relative] = _save_frame(
                root / mature_relative,
                _series_frame(output.mature_predictions[arm], "score"),
            )
            artifacts[test_relative] = _save_frame(
                root / test_relative,
                _series_frame(output.test_predictions[arm], "score"),
            )
            artifacts[report_relative] = _save_frame(
                root / report_relative,
                _report_frame(reports[window][arm]),
            )
            top_payload = (
                json.dumps(top30[window][arm], sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
            )
            artifacts[top_relative] = _save_bytes(root / top_relative, top_payload)
        if window == "W6":
            for arm in ARMS:
                prediction_relative = (prefix / "stress_predictions" / f"{arm}.parquet").as_posix()
                report_relative = (prefix / "stress_backtest" / f"{arm}.parquet").as_posix()
                artifacts[prediction_relative] = _save_frame(
                    root / prediction_relative,
                    _series_frame(output.stress_predictions[arm], "score"),
                )
                artifacts[report_relative] = _save_frame(
                    root / report_relative,
                    _report_frame(stress_reports[arm]),
                )
    summary_sha, summary_reused = write_once_document(root / "summary.json", summary)
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
        "schema_version": "m6-model-attribution-pass-manifest-v1",
        "artifacts": canonical_artifacts,
        "bundle_sha256": canonical_sha256(canonical_artifacts),
    }
    manifest_sha, manifest_reused = write_once_document(root / "manifest.json", manifest)
    return {
        "manifest_sha256": manifest_sha,
        "bundle_sha256": manifest["bundle_sha256"],
        "artifact_count": len(artifacts),
        "all_reused": manifest_reused and all(row["reused"] for row in artifacts.values()),
    }


def _read_series(path: Path, value_name: str) -> pd.Series:
    frame = pd.read_parquet(path)
    if list(frame.columns) != ["datetime", "instrument", value_name]:
        raise AttributionError("M6 stored member-day artifact schema differs")
    frame["datetime"] = pd.to_datetime(frame["datetime"])
    return frame.set_index(["datetime", "instrument"])[value_name].sort_index()


def _read_report(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    expected = ["datetime", "gross_return", "benchmark_return", "recorded_cost", "turnover"]
    if list(frame.columns) != expected:
        raise AttributionError("M6 stored backtest schema differs")
    frame["datetime"] = pd.to_datetime(frame["datetime"])
    return frame.set_index("datetime").sort_index()


def load_pass(root: Path) -> dict[str, Any]:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    artifacts = manifest.get("artifacts", {})
    if manifest.get("bundle_sha256") != canonical_sha256(artifacts):
        raise AttributionError("M6 pass manifest bundle hash differs")
    from shaiwei.research.model_attribution.contract import sha256_file

    for relative, metadata in artifacts.items():
        path = root / relative
        if sha256_file(path) != metadata["sha256"]:
            raise AttributionError(f"M6 pass artifact hash differs: {relative}")
    predictions: dict[str, dict[str, pd.Series]] = {}
    labels: dict[str, pd.Series] = {}
    reports: dict[str, dict[str, pd.DataFrame]] = {}
    for window in WINDOWS:
        labels[window] = _read_series(root / window / "mature_labels.parquet", "label")
        predictions[window] = {
            arm: _read_series(root / window / "mature_predictions" / f"{arm}.parquet", "score")
            for arm in ARMS
        }
        reports[window] = {arm: _read_report(root / window / "backtest" / f"{arm}.parquet") for arm in ARMS}
    stress_reports = {arm: _read_report(root / "W6" / "stress_backtest" / f"{arm}.parquet") for arm in ARMS}
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    return {
        "manifest": manifest,
        "predictions": predictions,
        "labels": labels,
        "reports": reports,
        "stress_reports": stress_reports,
        "summary": summary,
    }

"""Strict identity-first reader for the single frozen M6 control score surface."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import qlib
from qlib.config import REG_CN

from shaiwei.research.model_attribution.audit_recovery_contract import effect_tree_identity
from shaiwei.research.model_attribution.contract import ProtocolBundle, canonical_sha256, sha256_file
from shaiwei.research.production_conversion.contract import ProtocolError
from shaiwei.research.production_conversion.real_contract import ReleaseProtocol, ReleaseScope, mapping


WINDOWS = ("W1", "W2", "W3", "W4", "W5", "W6")
ARM = "clean_lgbm_control_v1"


def _manifest(root: Path, expected_bundle: str) -> dict[str, Any]:
    document = mapping(root / "manifest.json")
    artifacts = document.get("artifacts")
    if document.get("schema_version") != "m6-model-attribution-pass-manifest-v1" or not isinstance(artifacts, dict):
        raise ProtocolError("production-converter sealed manifest differs")
    if document.get("bundle_sha256") != canonical_sha256(artifacts) or document.get("bundle_sha256") != expected_bundle:
        raise ProtocolError("production-converter sealed pass bundle differs")
    for relative, metadata in artifacts.items():
        path = root / relative
        if path.is_symlink() or sha256_file(path) != metadata.get("sha256") or path.stat().st_size != metadata.get("byte_count"):
            raise ProtocolError(f"production-converter sealed artifact differs: {relative}")
    return document


def _prediction(path: Path) -> pd.Series:
    frame = pd.read_parquet(path)
    if list(frame.columns) != ["datetime", "instrument", "score"]:
        raise ProtocolError("production-converter prediction schema differs")
    frame["datetime"] = pd.to_datetime(frame["datetime"])
    frame["instrument"] = frame["instrument"].astype(str)
    value = frame.set_index(["datetime", "instrument"])["score"].sort_index()
    value = pd.to_numeric(value, errors="raise").astype(float)
    codes = value.index.get_level_values("instrument").astype(str)
    if value.empty or value.index.has_duplicates or not np.isfinite(value.to_numpy()).all():
        raise ProtocolError("production-converter prediction is invalid")
    if codes.str.startswith("BJ").any() or codes.str.endswith(".BJ").any():
        raise ProtocolError("production-converter prediction contains .BJ")
    return value


def _report(path: Path) -> list[dict[str, float | str]]:
    frame = pd.read_parquet(path)
    expected = ["datetime", "gross_return", "benchmark_return", "recorded_cost", "turnover"]
    if list(frame.columns) != expected:
        raise ProtocolError("production-converter control report schema differs")
    if frame.empty or frame["datetime"].duplicated().any():
        raise ProtocolError("production-converter control report is empty or duplicated")
    return [
        {
            "date": pd.Timestamp(row["datetime"]).strftime("%Y-%m-%d"),
            **{name: float(row[name]) for name in expected[1:]},
        }
        for _, row in frame.sort_values("datetime").iterrows()
    ]


def read_pass(root: Path, expected_bundle: str) -> dict[str, Any]:
    _manifest(root, expected_bundle)
    return {
        "predictions": {
            window: _prediction(root / window / "test_predictions" / f"{ARM}.parquet")
            for window in WINDOWS
        },
        "controls": {
            window: _report(root / window / "backtest" / f"{ARM}.parquet")
            for window in WINDOWS
        },
    }


def load_sealed_passes(root: Path, release: ReleaseScope) -> dict[str, dict[str, Any]]:
    expected = release.scope["inputs"]["sealed_m6_effect"]
    return {
        name: read_pass(root / name, expected[f"{name}_bundle_sha256"])
        for name in ("first_pass", "replay")
    }


def verify_input_identities(
    provider_root: Path,
    effect_root: Path,
    audit_path: Path,
    protocol: ReleaseProtocol,
    release: ReleaseScope,
) -> dict[str, Any]:
    metadata = ProtocolBundle.load().verify_metadata_inputs(
        provider_root / "_shaiwei_manifest.json", provider_root / "calendars/day.txt"
    )
    qlib_identity = {
        "qlib_manifest_sha256": metadata["qlib_manifest_sha256"],
        "qlib_tree_sha256": metadata["qlib_tree_sha256"],
        "qlib_file_count": metadata["qlib_file_count"],
        "calendar_sha256": sha256_file(provider_root / "calendars/day.txt"),
        "calendar_row_count": metadata["calendar_row_count"],
    }
    if qlib_identity != release.scope["inputs"]["qlib"]:
        raise ProtocolError("production-converter Qlib input identity differs")
    observed = effect_tree_identity(effect_root)
    expected = release.scope["inputs"]["sealed_m6_effect"]
    if observed != {key: expected[key] for key in ("file_count", "total_bytes", "tree_sha256")}:
        raise ProtocolError("production-converter sealed effect tree differs")
    if sha256_file(audit_path) != release.scope["inputs"]["sealed_m6_audit"]["sha256"]:
        raise ProtocolError("production-converter sealed audit differs")
    return {"qlib": qlib_identity, "sealed_m6_effect": expected, "sealed_m6_audit": release.scope["inputs"]["sealed_m6_audit"]}


def initialize_qlib(provider_root: Path) -> None:
    if not provider_root.is_dir():
        raise ProtocolError("production-converter Qlib provider root is absent")
    qlib.init(provider_uri=str(provider_root.resolve()), region=REG_CN)


__all__ = ["ARM", "WINDOWS", "initialize_qlib", "load_sealed_passes", "verify_input_identities"]

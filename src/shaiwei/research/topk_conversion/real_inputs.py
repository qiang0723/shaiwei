"""Strict sealed M6 input reader and metadata identity gates for M6-3C."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import qlib
from qlib.config import REG_CN

from shaiwei.research.model_attribution.audit_recovery_contract import effect_tree_identity
from shaiwei.research.model_attribution.contract import ProtocolBundle as M6ProtocolBundle
from shaiwei.research.model_attribution.contract import canonical_sha256, sha256_file
from shaiwei.research.topk_conversion.contract import ConversionError
from shaiwei.research.topk_conversion.real_contract import RealProtocol, ReleaseScope, mapping
from shaiwei.research.topk_conversion.schema import ARMS, WINDOWS


def _series(path: Path) -> pd.Series:
    frame = pd.read_parquet(path)
    if list(frame.columns) != ["datetime", "instrument", "score"]:
        raise ConversionError(f"M6-3C prediction schema differs: {path.name}")
    frame["datetime"] = pd.to_datetime(frame["datetime"])
    frame["instrument"] = frame["instrument"].astype(str)
    value = frame.set_index(["datetime", "instrument"])["score"].sort_index()
    value = pd.to_numeric(value, errors="raise").astype(float)
    if value.empty or value.index.has_duplicates or not np.isfinite(value.to_numpy()).all():
        raise ConversionError("M6-3C prediction is empty, duplicated, or nonfinite")
    codes = value.index.get_level_values("instrument").astype(str)
    if codes.str.startswith("BJ").any() or codes.str.endswith(".BJ").any():
        raise ConversionError("M6-3C sealed prediction contains .BJ")
    return value


def _report(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    expected = ["datetime", "gross_return", "benchmark_return", "recorded_cost", "turnover"]
    if list(frame.columns) != expected:
        raise ConversionError(f"M6-3C report schema differs: {path.name}")
    frame["datetime"] = pd.to_datetime(frame["datetime"])
    result = frame.set_index("datetime").sort_index()
    for column in result:
        result[column] = pd.to_numeric(result[column], errors="raise").astype(float)
    if result.empty or result.index.has_duplicates or not np.isfinite(result.to_numpy()).all():
        raise ConversionError("M6-3C sealed report is empty, duplicated, or nonfinite")
    return result


def _validate_manifest(root: Path, expected_bundle_sha256: str) -> dict[str, Any]:
    manifest = mapping(root / "manifest.json")
    if manifest.get("schema_version") != "m6-model-attribution-pass-manifest-v1":
        raise ConversionError("M6-3C sealed pass manifest schema differs")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or not artifacts:
        raise ConversionError("M6-3C sealed pass artifacts are absent")
    if manifest.get("bundle_sha256") != canonical_sha256(artifacts):
        raise ConversionError("M6-3C sealed pass bundle self hash differs")
    if manifest.get("bundle_sha256") != expected_bundle_sha256:
        raise ConversionError("M6-3C sealed pass bundle differs from the frozen identity")
    declared = set(artifacts)
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    if actual != declared:
        raise ConversionError("M6-3C sealed pass file set differs")
    for relative, metadata in artifacts.items():
        path = root / relative
        if path.is_symlink() or not isinstance(metadata, dict):
            raise ConversionError("M6-3C sealed pass metadata differs")
        if (
            metadata.get("sha256") != sha256_file(path)
            or metadata.get("byte_count") != path.stat().st_size
        ):
            raise ConversionError(f"M6-3C sealed artifact identity differs: {relative}")
    return manifest


def read_pass(root: Path, *, expected_bundle_sha256: str) -> dict[str, Any]:
    manifest = _validate_manifest(root, expected_bundle_sha256)
    predictions: dict[str, dict[str, pd.Series]] = {}
    reports: dict[str, dict[str, pd.DataFrame]] = {}
    top30: dict[str, dict[str, dict[str, list[str]]]] = {}
    for window in WINDOWS:
        predictions[window] = {
            arm: _series(root / window / "test_predictions" / f"{arm}.parquet") for arm in ARMS
        }
        reports[window] = {
            arm: _report(root / window / "backtest" / f"{arm}.parquet") for arm in ARMS
        }
        top30[window] = {
            arm: mapping(root / window / "top30" / f"{arm}.json") for arm in ARMS
        }
    stress_predictions = {
        arm: _series(root / "W6" / "stress_predictions" / f"{arm}.parquet") for arm in ARMS
    }
    stress_reports = {
        arm: _report(root / "W6" / "stress_backtest" / f"{arm}.parquet") for arm in ARMS
    }
    return {
        "manifest": manifest,
        "predictions": predictions,
        "reports": reports,
        "top30": top30,
        "stress_predictions": stress_predictions,
        "stress_reports": stress_reports,
    }


def load_sealed_passes(root: Path, protocol: RealProtocol) -> dict[str, dict[str, Any]]:
    expected = protocol.document["predecessors"]["authoritative_m6_effect"]
    first = read_pass(root / "first_pass", expected_bundle_sha256=expected["first_pass_bundle_sha256"])
    replay = read_pass(root / "replay", expected_bundle_sha256=expected["replay_bundle_sha256"])
    if first["manifest"]["artifacts"] != replay["manifest"]["artifacts"]:
        raise ConversionError("M6-3C sealed first-pass and replay artifacts differ")
    return {"first_pass": first, "replay": replay}


def verify_input_identities(
    provider_root: Path,
    effect_root: Path,
    audit_path: Path,
    protocol: RealProtocol,
    release: ReleaseScope,
) -> dict[str, Any]:
    m6_bundle = M6ProtocolBundle.load()
    metadata = m6_bundle.verify_metadata_inputs(
        provider_root / "_shaiwei_manifest.json", provider_root / "calendars/day.txt"
    )
    observed_qlib = {
        "qlib_manifest_sha256": metadata["qlib_manifest_sha256"],
        "qlib_tree_sha256": metadata["qlib_tree_sha256"],
        "qlib_file_count": metadata["qlib_file_count"],
        "calendar_sha256": sha256_file(provider_root / "calendars/day.txt"),
        "calendar_row_count": metadata["calendar_row_count"],
    }
    if observed_qlib != release.scope["inputs"]["qlib"]:
        raise ConversionError("M6-3C Qlib input identity differs")
    observed_effect = effect_tree_identity(effect_root)
    expected_effect = release.scope["inputs"]["sealed_m6_effect"]
    if observed_effect != {
        "file_count": expected_effect["file_count"],
        "total_bytes": expected_effect["total_bytes"],
        "tree_sha256": expected_effect["tree_sha256"],
    }:
        raise ConversionError("M6-3C sealed effect tree differs")
    if sha256_file(effect_root / "report.json") != expected_effect["report_sha256"]:
        raise ConversionError("M6-3C sealed effect report differs")
    if sha256_file(audit_path) != release.scope["inputs"]["sealed_m6_audit"]["sha256"]:
        raise ConversionError("M6-3C sealed independent audit differs")
    return {
        "qlib": observed_qlib,
        "sealed_m6_effect": expected_effect,
        "sealed_m6_audit": release.scope["inputs"]["sealed_m6_audit"],
    }


def initialize_qlib(provider_root: Path) -> None:
    if not provider_root.is_dir():
        raise ConversionError("M6-3C Qlib provider root is absent")
    qlib.init(provider_uri=str(provider_root.resolve()), region=REG_CN)


__all__ = ["initialize_qlib", "load_sealed_passes", "read_pass", "verify_input_identities"]

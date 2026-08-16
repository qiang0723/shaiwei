"""Independent W7 artifact audit without Qlib, labels, or effect computation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from shaiwei.research.trend_swing.contract import canonical_sha256
from shaiwei.research.trend_swing.r3g2.contract import EffectProtocol, R3G2Error


EXPECTED_FILES = {"manifest.json", "model.txt", "predictions.parquet", "summary.json"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise R3G2Error(f"R3G-2 audit document is invalid: {path.name}") from error
    if not isinstance(value, dict):
        raise R3G2Error(f"R3G-2 audit document is not a mapping: {path.name}")
    return value


def audit_pass(root: Path, protocol: EffectProtocol) -> dict[str, Any]:
    if {path.name for path in root.iterdir() if path.is_file()} != EXPECTED_FILES:
        raise R3G2Error("R3G-2 W7 pass file set differs")
    manifest = _json(root / "manifest.json")
    if manifest.get("schema_version") != "ts-v5-r3g2-w7-lineage-pass-manifest-v1":
        raise R3G2Error("R3G-2 W7 manifest schema differs")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != EXPECTED_FILES - {"manifest.json"}:
        raise R3G2Error("R3G-2 W7 manifest artifact set differs")
    if manifest.get("bundle_sha256") != canonical_sha256(artifacts):
        raise R3G2Error("R3G-2 W7 manifest bundle hash differs")
    for relative, metadata in artifacts.items():
        path = root / relative
        if _sha256(path) != metadata.get("sha256") or path.stat().st_size != metadata.get(
            "byte_count"
        ):
            raise R3G2Error(f"R3G-2 W7 artifact identity differs: {relative}")
    frame = pd.read_parquet(root / "predictions.parquet")
    if list(frame.columns) != ["datetime", "instrument", "score"]:
        raise R3G2Error("R3G-2 W7 prediction schema differs")
    dates = pd.to_datetime(frame["datetime"], errors="raise")
    scores = pd.to_numeric(frame["score"], errors="raise").astype(float)
    codes = frame["instrument"].astype(str)
    if (
        frame.empty
        or frame.duplicated(["datetime", "instrument"]).any()
        or not np.isfinite(scores.to_numpy()).all()
        or dates.min() < pd.Timestamp("2025-01-01")
        or dates.max() > pd.Timestamp("2025-12-31")
        or codes.str.startswith("BJ").any()
        or codes.str.endswith(".BJ").any()
    ):
        raise R3G2Error("R3G-2 W7 prediction content gate failed")
    summary = _json(root / "summary.json")
    checks = {
        "protocol_binding": summary.get("protocol_sha256") == protocol.sha256,
        "window_binding": summary.get("window") == protocol.w7_window(),
        "row_count": summary.get("prediction_row_count") == len(frame),
        "date_min": summary.get("prediction_date_min") == dates.min().strftime("%Y-%m-%d"),
        "date_max": summary.get("prediction_date_max") == dates.max().strftime("%Y-%m-%d"),
        "no_effect_fields": summary.get(
            "contains_label_rankic_return_or_portfolio_metric"
        )
        is False,
        "strategy_not_evaluated": summary.get("strategy_effective") == "NOT_EVALUATED",
        "production_none": summary.get("production_authorization") == "none",
        "model_nonempty": (root / "model.txt").stat().st_size > 0,
    }
    if not all(checks.values()):
        raise R3G2Error("R3G-2 W7 independent pass audit failed")
    return {
        "manifest_sha256": _sha256(root / "manifest.json"),
        "bundle_sha256": manifest["bundle_sha256"],
        "artifact_sha256": {name: metadata["sha256"] for name, metadata in artifacts.items()},
        "checks": checks,
    }


def audit_pair(first: Path, replay: Path, protocol: EffectProtocol) -> dict[str, Any]:
    first_audit = audit_pass(first, protocol)
    replay_audit = audit_pass(replay, protocol)
    deterministic = (
        first_audit["bundle_sha256"] == replay_audit["bundle_sha256"]
        and first_audit["artifact_sha256"] == replay_audit["artifact_sha256"]
    )
    if not deterministic:
        raise R3G2Error("R3G-2 W7 first pass and replay differ")
    return {
        "schema_version": "ts-v5-r3g2-w7-lineage-independent-audit-v1",
        "protocol_sha256": protocol.sha256,
        "first_pass": first_audit,
        "replay": replay_audit,
        "deterministic_replay": True,
        "label_rankic_return_or_effect_read": False,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "verdict": "GO_W7_LINEAGE_ENGINEERING_FIXTURE_ONLY",
    }

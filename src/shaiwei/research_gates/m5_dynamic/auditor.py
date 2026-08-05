"""Independent M5 auditor: re-read inputs, rederive PIT/formulas/matrix, and rehash artifacts."""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .audit_quality import verify_quality
from .audit_recompute import OUTPUT_COLUMNS, recompute_panel
from .contract import (
    InputManifest,
    M5DataProtocol,
    M5GateError,
    canonical_json,
    sha256_file,
    sha256_json,
)
from .release import ApprovalEnvelope, DataReleaseScope
from .source_reader import load_allowed_inputs


def _canonical_file(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or path.read_text(encoding="utf-8") != canonical_json(value) + "\n":
        raise M5GateError("M5 evidence JSON is not a canonical object")
    return value


def _scalar(value: Any) -> Any:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        converted = float(value)
        if not math.isfinite(converted):
            raise M5GateError("M5 panel contains nonfinite serialized value")
        return converted
    return str(value)


def canonical_panel_sha256(frame: pd.DataFrame) -> str:
    ordered = frame.loc[:, OUTPUT_COLUMNS].sort_values(
        ["formation_date", "effective_date", "universe_id", "candidate_id", "ts_code"],
        kind="stable",
    )
    return sha256_json(
        [[_scalar(value) for value in row] for row in ordered.itertuples(index=False, name=None)]
    )


def _compare_panels(sealed: pd.DataFrame, recomputed: pd.DataFrame) -> None:
    if tuple(sealed.columns) != OUTPUT_COLUMNS or tuple(recomputed.columns) != OUTPUT_COLUMNS:
        raise M5GateError("M5 sealed or recomputed panel schema differs")
    if len(sealed) != len(recomputed):
        raise M5GateError("M5 sealed and recomputed panel row counts differ")
    left = sealed.sort_values(
        ["formation_date", "effective_date", "universe_id", "candidate_id", "ts_code"],
        kind="stable",
    ).reset_index(drop=True)
    right = recomputed.sort_values(
        ["formation_date", "effective_date", "universe_id", "candidate_id", "ts_code"],
        kind="stable",
    ).reset_index(drop=True)
    for column in OUTPUT_COLUMNS:
        if column == "value":
            left_values = pd.to_numeric(left[column], errors="coerce").to_numpy(dtype=float, na_value=np.nan)
            right_values = pd.to_numeric(right[column], errors="coerce").to_numpy(dtype=float, na_value=np.nan)
            if not np.array_equal(left_values, right_values, equal_nan=True):
                raise M5GateError("M5 sealed factor values differ from independent recomputation")
        else:
            left_values = left[column].astype("string").fillna("<NULL>").tolist()
            right_values = right[column].astype("string").fillna("<NULL>").tolist()
            if left_values != right_values:
                raise M5GateError(f"M5 sealed {column} differs from independent recomputation")


def audit_run(
    protocol: M5DataProtocol,
    frames: dict[str, pd.DataFrame],
    membership_frames: dict[str, pd.DataFrame],
    *,
    run_root: Path,
    expected_input_manifest_sha256: str,
    expected_release_scope_sha256: str,
    expected_approval_event_sha256: str,
) -> dict[str, Any]:
    manifest_path = run_root / "run_manifest.json"
    report_path = run_root / "data_gate_report.json"
    panel_path = run_root / "feature_panel.parquet"
    if any(not path.is_file() for path in (manifest_path, report_path, panel_path)):
        raise M5GateError("M5 run root is incomplete")
    manifest = _canonical_file(manifest_path)
    report = _canonical_file(report_path)
    identity = {
        "input_manifest_sha256": expected_input_manifest_sha256,
        "release_scope_sha256": expected_release_scope_sha256,
        "approval_event_sha256": expected_approval_event_sha256,
    }
    if any(manifest.get(key) != value or report.get(key) != value for key, value in identity.items()):
        raise M5GateError("M5 run identity differs from approved release")
    artifacts = manifest.get("artifacts") or {}
    if (
        artifacts.get("feature_panel", {}).get("sha256") != sha256_file(panel_path)
        or artifacts.get("data_gate_report", {}).get("sha256") != sha256_file(report_path)
        or report.get("feature_panel", {}).get("sha256") != sha256_file(panel_path)
    ):
        raise M5GateError("M5 run artifact physical hash differs")
    if (
        manifest.get("runner_self_reported_only") is not True
        or manifest.get("independent_audit_status") != "NOT_RUN"
        or report.get("label_read") is not False
        or report.get("effect_read") is not False
        or report.get("model_training_run") is not False
        or report.get("backtest_run") is not False
        or report.get("provider_call_count") != 0
        or report.get("production_authorization") != "none"
    ):
        raise M5GateError("M5 runner claims unauthorized result or authority")
    sealed = pd.read_parquet(panel_path)
    if len(sealed) != int(report["feature_panel"]["row_count"]):
        raise M5GateError("M5 sealed panel row count differs")
    recomputed = recompute_panel(protocol, frames, membership_frames)
    _compare_panels(sealed, recomputed)
    quality = verify_quality(protocol, recomputed, report["quality"])
    if manifest.get("verdict") != quality["verdict"] or report.get("verdict") != quality["verdict"]:
        raise M5GateError("M5 manifest/report verdict differs from independent quality verdict")
    return {
        "schema_version": "m5-data-gate-independent-audit-v1",
        "status": "PASS",
        "run_id": manifest["run_id"],
        "run_manifest_sha256": sha256_file(manifest_path),
        "report_sha256": sha256_file(report_path),
        "feature_panel_physical_sha256": sha256_file(panel_path),
        "feature_panel_canonical_sha256": canonical_panel_sha256(sealed),
        "independent_recomputed_panel_sha256": canonical_panel_sha256(recomputed),
        "input_manifest_sha256": expected_input_manifest_sha256,
        "release_scope_sha256": expected_release_scope_sha256,
        "approval_event_sha256": expected_approval_event_sha256,
        "candidate_matrix": quality["candidate_matrix"],
        "eligible_candidate_ids": quality["eligible_candidate_ids"],
        "rejected_candidate_ids": quality["rejected_candidate_ids"],
        "verdict": quality["verdict"],
        "effect_test_count": 0,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
    }


def seal_audit(audit_root: Path, audit: dict[str, Any]) -> dict[str, Any]:
    target = audit_root / audit["run_id"] / "audit_report.json"
    payload = (canonical_json(audit) + "\n").encode("utf-8")
    if target.exists():
        if target.read_bytes() != payload:
            raise M5GateError("existing M5 audit report differs")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    return {**audit, "audit_report_sha256": sha256_file(target)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--build-contract", type=Path, required=True)
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--release-scope", type=Path, required=True)
    parser.add_argument("--approval-envelope", type=Path, required=True)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--audit-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        protocol = M5DataProtocol.load(
            args.protocol, build_path=args.build_contract, project_root=Path("/inputs")
        )
        input_manifest = InputManifest.load(args.input_manifest, protocol)
        release = DataReleaseScope.load(args.release_scope, protocol, input_manifest)
        approval = ApprovalEnvelope.load(args.approval_envelope, release)
        frames, memberships, _ = load_allowed_inputs(
            protocol, input_manifest, input_root=args.input_root
        )
        result = seal_audit(
            args.audit_root,
            audit_run(
                protocol,
                frames,
                memberships,
                run_root=args.run_root,
                expected_input_manifest_sha256=input_manifest.sha256,
                expected_release_scope_sha256=release.sha256,
                expected_approval_event_sha256=approval.document["approval_event_sha256"],
            ),
        )
    except (M5GateError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(canonical_json({"status": "FAIL", "error_class": type(error).__name__, "message": str(error)}))
        return 2
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

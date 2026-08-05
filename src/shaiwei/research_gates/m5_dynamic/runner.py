"""Thin write-once M5 data-gate runner; real mode requires an exact approval envelope."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .contract import (
    InputManifest,
    M5DataProtocol,
    M5GateError,
    canonical_json,
    sha256_file,
    sha256_json,
)
from .features import calculate_features
from .matrix import build_quality_report
from .membership import build_membership_panel
from .release import ApprovalEnvelope, DataReleaseScope
from .source_reader import load_allowed_inputs
from .statements import build_candidate_components


OUTPUT_FILES = ("feature_panel.parquet", "data_gate_report.json", "run_manifest.json")


def _json_bytes(value: Any) -> bytes:
    return (canonical_json(value) + "\n").encode("utf-8")


def _write_json(path: Path, value: Any) -> None:
    payload = _json_bytes(value)
    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def _write_panel(path: Path, panel: pd.DataFrame) -> None:
    ordered = panel.sort_values(
        ["formation_date", "effective_date", "universe_id", "candidate_id", "ts_code"],
        kind="stable",
    ).reset_index(drop=True)
    table = pa.Table.from_pandas(ordered, preserve_index=False)
    pq.write_table(
        table,
        path,
        compression="zstd",
        compression_level=9,
        use_dictionary=False,
        write_statistics=True,
        data_page_version="1.0",
    )
    with path.open("rb") as handle:
        os.fsync(handle.fileno())


def _verify_existing(run_root: Path, expected_identity: dict[str, str]) -> dict[str, Any]:
    if not run_root.is_dir() or any(not (run_root / name).is_file() for name in OUTPUT_FILES):
        raise M5GateError("existing M5 run directory is partial")
    manifest_path = run_root / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if canonical_json(manifest) + "\n" != manifest_path.read_text(encoding="utf-8"):
        raise M5GateError("existing M5 run manifest is not canonical")
    if any(manifest.get(key) != value for key, value in expected_identity.items()):
        raise M5GateError("existing M5 run identity differs")
    artifacts = manifest.get("artifacts") or {}
    for name in ("feature_panel", "data_gate_report"):
        item = artifacts.get(name) or {}
        path = run_root / str(item.get("file", ""))
        if not path.is_file() or sha256_file(path) != item.get("sha256"):
            raise M5GateError("existing M5 run artifact hash differs")
    return manifest


def build_gate_result(
    protocol: M5DataProtocol,
    frames: dict[str, pd.DataFrame],
    membership_frames: dict[str, pd.DataFrame],
    *,
    input_manifest_sha256: str,
    release_scope_sha256: str,
    code_bundle_sha256: str,
    approval_event_sha256: str,
    semantic_rows_read: bool,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    members, membership_diagnostics = build_membership_panel(
        protocol, frames["tushare.trade_cal"], membership_frames
    )
    components, statement_diagnostics = build_candidate_components(protocol, members, frames)
    panel, feature_diagnostics = calculate_features(protocol, components)
    source_conflicts = sum(
        int(item["source_identity_conflicts"])
        for item in statement_diagnostics["source"].values()
    )
    quality = build_quality_report(
        protocol,
        panel,
        source_identity_conflicts=source_conflicts,
    )
    report = {
        "schema_version": "m5-data-gate-report-v1",
        "protocol_id": protocol.document["protocol_id"],
        "protocol_sha256": protocol.sha256,
        "input_manifest_sha256": input_manifest_sha256,
        "release_scope_sha256": release_scope_sha256,
        "code_bundle_sha256": code_bundle_sha256,
        "approval_event_sha256": approval_event_sha256,
        "execution_kind": (
            "REAL_APPROVED_DATA_GATE" if semantic_rows_read else "SYNTHETIC_FIXTURE"
        ),
        "semantic_rows_read": semantic_rows_read,
        "membership_diagnostics": membership_diagnostics,
        "statement_diagnostics": statement_diagnostics,
        "feature_diagnostics": feature_diagnostics,
        "quality": quality,
        "label_read": False,
        "effect_read": False,
        "model_training_run": False,
        "backtest_run": False,
        "provider_call_count": 0,
        "provider_cost_usd": "0.00",
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "verdict": quality["verdict"],
    }
    return panel, report


def seal_run(
    output_root: Path,
    panel: pd.DataFrame,
    report: dict[str, Any],
) -> dict[str, Any]:
    identity = {
        key: report[key]
        for key in (
            "protocol_sha256",
            "input_manifest_sha256",
            "release_scope_sha256",
            "code_bundle_sha256",
            "approval_event_sha256",
        )
    }
    run_id = sha256_json(identity)
    run_root = output_root / run_id
    if run_root.exists():
        return _verify_existing(run_root, {"run_id": run_id, **identity})
    output_root.mkdir(parents=True, exist_ok=True)
    temporary = output_root / f".{run_id}.{os.getpid()}.tmp"
    if temporary.exists():
        raise M5GateError("M5 temporary run directory already exists")
    temporary.mkdir(mode=0o700)
    try:
        panel_path = temporary / "feature_panel.parquet"
        report_path = temporary / "data_gate_report.json"
        _write_panel(panel_path, panel)
        report_with_panel = {
            **report,
            "feature_panel": {
                "file": panel_path.name,
                "row_count": len(panel),
                "sha256": sha256_file(panel_path),
            },
        }
        _write_json(report_path, report_with_panel)
        manifest = {
            "schema_version": "m5-data-gate-run-manifest-v1",
            "run_id": run_id,
            **identity,
            "execution_kind": report["execution_kind"],
            "artifacts": {
                "feature_panel": report_with_panel["feature_panel"],
                "data_gate_report": {
                    "file": report_path.name,
                    "sha256": sha256_file(report_path),
                },
            },
            "candidate_count": report["quality"]["candidate_count"],
            "universe_count": report["quality"]["universe_count"],
            "evaluation_unit_count": report["quality"]["evaluation_unit_count"],
            "verdict": report["verdict"],
            "runner_self_reported_only": True,
            "independent_audit_status": "NOT_RUN",
            "effect_test_count": 0,
            "strategy_effective": "NOT_EVALUATED",
            "production_authorization": "none",
        }
        _write_json(temporary / "run_manifest.json", manifest)
        directory_fd = os.open(temporary, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        os.replace(temporary, run_root)
        parent_fd = os.open(output_root, os.O_RDONLY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    return _verify_existing(run_root, {"run_id": run_id, **identity})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--build-contract", type=Path, required=True)
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--release-scope", type=Path, required=True)
    parser.add_argument("--approval-envelope", type=Path, required=True)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        protocol = M5DataProtocol.load(
            args.protocol,
            build_path=args.build_contract,
            project_root=Path("/inputs"),
        )
        input_manifest = InputManifest.load(args.input_manifest, protocol)
        release = DataReleaseScope.load(args.release_scope, protocol, input_manifest)
        approval = ApprovalEnvelope.load(args.approval_envelope, release)
        frames, memberships, source_evidence = load_allowed_inputs(
            protocol, input_manifest, input_root=args.input_root
        )
        panel, report = build_gate_result(
            protocol,
            frames,
            memberships,
            input_manifest_sha256=input_manifest.sha256,
            release_scope_sha256=release.sha256,
            code_bundle_sha256=release.scope["implementation"]["code_bundle_sha256"],
            approval_event_sha256=approval.document["approval_event_sha256"],
            semantic_rows_read=True,
        )
        report["source_evidence"] = source_evidence
        result = seal_run(args.output_root, panel, report)
    except (M5GateError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(canonical_json({"status": "FAIL", "error_class": type(error).__name__, "message": str(error)}))
        return 2
    print(canonical_json(result))
    return 0 if result["verdict"].startswith("GO_") else 3


if __name__ == "__main__":
    raise SystemExit(main())

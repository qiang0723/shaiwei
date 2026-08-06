"""Write-once physical sealing for normal and global-failure M5 runs."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .contract import M5GateError, canonical_json, sha256_file, sha256_json


NORMAL_OUTPUT_FILES = {
    "feature_panel.parquet",
    "data_gate_report.json",
    "run_manifest.json",
}
GLOBAL_FAILURE_OUTPUT_FILES = {
    "source_conflict_report.json",
    "data_gate_report.json",
    "run_manifest.json",
}


def _write_json(path: Path, value: Any) -> None:
    payload = (canonical_json(value) + "\n").encode("utf-8")
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


def _run_identity(report: dict[str, Any]) -> dict[str, str]:
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
    if report.get("schema_version") == "m5-data-gate-report-v2":
        identity.update(
            {
                "protocol_scope_sha256": report["protocol_scope_sha256"],
                "outcome_kind": report["outcome_kind"],
            }
        )
    return identity


def _verify_existing(run_root: Path, expected_identity: dict[str, str]) -> dict[str, Any]:
    if not run_root.is_dir() or not (run_root / "run_manifest.json").is_file():
        raise M5GateError("existing M5 run directory is partial")
    manifest_path = run_root / "run_manifest.json"
    serialized = manifest_path.read_text(encoding="utf-8")
    manifest = json.loads(serialized)
    if canonical_json(manifest) + "\n" != serialized:
        raise M5GateError("existing M5 run manifest is not canonical")
    if any(manifest.get(key) != value for key, value in expected_identity.items()):
        raise M5GateError("existing M5 run identity differs")
    artifacts = manifest.get("artifacts") or {}
    outcome = manifest.get("outcome_kind", "NORMAL_DATA_MATRIX")
    expected_files = (
        GLOBAL_FAILURE_OUTPUT_FILES
        if outcome == "GLOBAL_DATA_FAILURE"
        else NORMAL_OUTPUT_FILES
    )
    if {path.name for path in run_root.iterdir()} != expected_files:
        raise M5GateError("existing M5 run artifact set differs")
    expected_artifacts = (
        {"source_conflict_report", "data_gate_report"}
        if outcome == "GLOBAL_DATA_FAILURE"
        else {"feature_panel", "data_gate_report"}
    )
    if set(artifacts) != expected_artifacts:
        raise M5GateError("existing M5 run manifest artifact set differs")
    for name in expected_artifacts:
        item = artifacts.get(name) or {}
        path = run_root / str(item.get("file", ""))
        if not path.is_file() or sha256_file(path) != item.get("sha256"):
            raise M5GateError("existing M5 run artifact hash differs")
    return manifest


def _publish_directory(output_root: Path, temporary: Path, run_root: Path) -> None:
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


def _manifest(
    report: dict[str, Any],
    *,
    run_id: str,
    identity: dict[str, str],
    artifacts: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": (
            "m5-data-gate-run-manifest-v2"
            if report.get("schema_version") == "m5-data-gate-report-v2"
            else "m5-data-gate-run-manifest-v1"
        ),
        "run_id": run_id,
        **identity,
        "execution_kind": report["execution_kind"],
        "artifacts": artifacts,
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


def seal_run(
    output_root: Path,
    panel: pd.DataFrame,
    report: dict[str, Any],
) -> dict[str, Any]:
    identity = _run_identity(report)
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
        manifest = _manifest(
            report,
            run_id=run_id,
            identity=identity,
            artifacts={
                "feature_panel": report_with_panel["feature_panel"],
                "data_gate_report": {
                    "file": report_path.name,
                    "sha256": sha256_file(report_path),
                },
            },
        )
        _write_json(temporary / "run_manifest.json", manifest)
        _publish_directory(output_root, temporary, run_root)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    return _verify_existing(run_root, {"run_id": run_id, **identity})


def seal_global_failure(
    output_root: Path,
    conflict_report: dict[str, Any],
    report: dict[str, Any],
) -> dict[str, Any]:
    identity = _run_identity(report)
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
        conflict_path = temporary / "source_conflict_report.json"
        report_path = temporary / "data_gate_report.json"
        _write_json(conflict_path, conflict_report)
        sealed_conflict = {
            "file": conflict_path.name,
            "sha256": sha256_file(conflict_path),
        }
        report_with_conflict = {**report, "source_conflict_report": sealed_conflict}
        _write_json(report_path, report_with_conflict)
        manifest = _manifest(
            report,
            run_id=run_id,
            identity=identity,
            artifacts={
                "source_conflict_report": sealed_conflict,
                "data_gate_report": {
                    "file": report_path.name,
                    "sha256": sha256_file(report_path),
                },
            },
        )
        _write_json(temporary / "run_manifest.json", manifest)
        _publish_directory(output_root, temporary, run_root)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    return _verify_existing(run_root, {"run_id": run_id, **identity})

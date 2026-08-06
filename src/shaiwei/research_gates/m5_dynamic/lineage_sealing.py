"""Write-once sealing for aggregate M5 source-lineage gate evidence."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from .contract import M5GateError, canonical_json, sha256_file, sha256_json


OUTPUT_FILES = {
    "source_lineage_report.json",
    "lineage_gate_report.json",
    "run_manifest.json",
}


def _write_json(path: Path, value: dict[str, Any]) -> None:
    payload = (canonical_json(value) + "\n").encode("utf-8")
    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def _identity(report: dict[str, Any]) -> dict[str, str]:
    return {
        key: str(report[key])
        for key in (
            "protocol_scope_sha256",
            "input_manifest_sha256",
            "release_scope_sha256",
            "code_bundle_sha256",
            "approval_event_sha256",
            "outcome_kind",
        )
    }


def _verify_existing(run_root: Path, expected: dict[str, str]) -> dict[str, Any]:
    if not run_root.is_dir() or {path.name for path in run_root.iterdir()} != OUTPUT_FILES:
        raise M5GateError("existing M5 lineage run directory is partial")
    manifest_path = run_root / "run_manifest.json"
    serialized = manifest_path.read_text(encoding="utf-8")
    manifest = json.loads(serialized)
    if serialized != canonical_json(manifest) + "\n":
        raise M5GateError("existing M5 lineage manifest is not canonical")
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise M5GateError("existing M5 lineage identity differs")
    artifacts = manifest.get("artifacts") or {}
    if set(artifacts) != {"source_lineage_report", "lineage_gate_report"}:
        raise M5GateError("existing M5 lineage artifact set differs")
    for item in artifacts.values():
        path = run_root / str(item.get("file", ""))
        if not path.is_file() or sha256_file(path) != item.get("sha256"):
            raise M5GateError("existing M5 lineage artifact hash differs")
    return manifest


def seal_lineage_run(
    output_root: Path,
    lineage_report: dict[str, Any],
    gate_report: dict[str, Any],
) -> dict[str, Any]:
    identity = _identity(gate_report)
    run_id = sha256_json(identity)
    run_root = output_root / run_id
    if run_root.exists():
        return _verify_existing(run_root, {"run_id": run_id, **identity})
    output_root.mkdir(parents=True, exist_ok=True)
    temporary = output_root / f".{run_id}.{os.getpid()}.tmp"
    if temporary.exists():
        raise M5GateError("M5 lineage temporary directory already exists")
    temporary.mkdir(mode=0o700)
    try:
        lineage_path = temporary / "source_lineage_report.json"
        gate_path = temporary / "lineage_gate_report.json"
        _write_json(lineage_path, lineage_report)
        sealed_lineage = {
            "file": lineage_path.name,
            "sha256": sha256_file(lineage_path),
        }
        sealed_gate = {**gate_report, "source_lineage_report": sealed_lineage}
        _write_json(gate_path, sealed_gate)
        manifest = {
            "schema_version": "m5-source-lineage-run-manifest-v1",
            "run_id": run_id,
            **identity,
            "execution_kind": gate_report["execution_kind"],
            "artifacts": {
                "source_lineage_report": sealed_lineage,
                "lineage_gate_report": {
                    "file": gate_path.name,
                    "sha256": sha256_file(gate_path),
                },
            },
            "verdict": gate_report["verdict"],
            "runner_self_reported_only": True,
            "independent_audit_status": "NOT_RUN",
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

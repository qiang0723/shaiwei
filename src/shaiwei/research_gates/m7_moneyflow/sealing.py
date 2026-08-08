"""Write-once canonical evidence sealing for the M7 runner and auditor."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from .contract import M7GateError, canonical_json, sha256_file


def canonical_object(path: Path) -> dict[str, Any]:
    serialized = path.read_text(encoding="utf-8")
    document = json.loads(serialized)
    if not isinstance(document, dict) or serialized != canonical_json(document) + "\n":
        raise M7GateError("M7 evidence JSON is not a canonical object")
    return document


def _write(path: Path, document: dict[str, Any]) -> None:
    path.write_text(canonical_json(document) + "\n", encoding="utf-8")
    with path.open("rb") as handle:
        os.fsync(handle.fileno())


def seal_run(output_root: Path, report: dict[str, Any]) -> dict[str, Any]:
    run_id = str(report["run_id"])
    target = output_root / run_id
    report_payload = (canonical_json(report) + "\n").encode("utf-8")
    if target.exists():
        manifest = canonical_object(target / "run_manifest.json")
        if (target / "data_gate_report.json").read_bytes() != report_payload:
            raise M7GateError("existing M7 run report differs")
        return manifest
    output_root.mkdir(parents=True, exist_ok=True)
    temporary = output_root / f".{run_id}.{os.getpid()}.tmp"
    if temporary.exists():
        raise M7GateError("M7 run temporary directory already exists")
    temporary.mkdir(mode=0o700)
    try:
        report_path = temporary / "data_gate_report.json"
        _write(report_path, report)
        manifest = {
            "schema_version": "m7-moneyflow-data-gate-run-manifest-v1",
            "run_id": run_id,
            "protocol_sha256": report["protocol_sha256"],
            "input_manifest_sha256": report["input_manifest_sha256"],
            "release_scope_sha256": report["release_scope_sha256"],
            "approval_sha256": report["approval_sha256"],
            "code_bundle_sha256": report["code_bundle_sha256"],
            "report_sha256": sha256_file(report_path),
            "report_bytes": report_path.stat().st_size,
            "verdict": report["verdict"],
            "runner_internal_replay_status": "PASS",
            "independent_audit_status": "NOT_RUN",
            "production_authorization": "none",
        }
        _write(temporary / "run_manifest.json", manifest)
        os.replace(temporary, target)
        return manifest
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise


def seal_audit(audit_root: Path, audit: dict[str, Any]) -> dict[str, Any]:
    target = audit_root / str(audit["run_id"]) / "audit_report.json"
    payload = (canonical_json(audit) + "\n").encode("utf-8")
    if target.exists():
        if target.read_bytes() != payload:
            raise M7GateError("existing M7 audit report differs")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    return {**audit, "audit_report_sha256": sha256_file(target)}

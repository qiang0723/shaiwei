"""Write-once canonical report, run manifest, and independent audit."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from shaiwei.research_gates.m7_moneyflow.contract import canonical_json, sha256_file

from .contract import LineageError


def _write_once(path: Path, document: dict[str, Any]) -> None:
    payload = (canonical_json(document) + "\n").encode()
    if path.exists():
        if path.read_bytes() != payload:
            raise LineageError("existing lineage sealed artifact differs")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def canonical_object(path: Path) -> dict[str, Any]:
    serialized = path.read_text(encoding="utf-8")
    value = json.loads(serialized)
    if not isinstance(value, dict) or serialized != canonical_json(value) + "\n":
        raise LineageError("lineage artifact is not canonical JSON")
    return value


def seal_run(root: Path, report: dict[str, Any]) -> dict[str, Any]:
    run_root = root / str(report["run_id"])
    report_path = run_root / "lineage_report.json"
    _write_once(report_path, report)
    manifest = {
        "schema_version": "m7-moneyflow-gap-lineage-run-manifest-v1",
        "run_id": report["run_id"],
        "protocol_sha256": report["protocol_sha256"],
        "input_manifest_sha256": report["input_manifest_sha256"],
        "release_scope_sha256": report["release_scope_sha256"],
        "approval_sha256": report["approval_sha256"],
        "code_bundle_sha256": report["code_bundle_sha256"],
        "report_sha256": sha256_file(report_path),
        "verdict": report["verdict"],
    }
    manifest_path = run_root / "run_manifest.json"
    _write_once(manifest_path, manifest)
    return {
        "run_id": report["run_id"],
        "report_sha256": sha256_file(report_path),
        "run_manifest_sha256": sha256_file(manifest_path),
        "verdict": report["verdict"],
    }


def seal_audit(root: Path, audit: dict[str, Any]) -> dict[str, Any]:
    path = root / str(audit["run_id"]) / "audit_report.json"
    _write_once(path, audit)
    return {**audit, "audit_report_sha256": sha256_file(path)}

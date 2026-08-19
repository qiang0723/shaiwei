"""One-shot RF gap-lineage diagnostic orchestration."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Any, Mapping

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.trend_swing.r4_contract import load_r3_manifest
from shaiwei.research.trend_swing.v6.engine import canonical_json, canonical_sha256, native
from shaiwei.research.rf_diag.contract import (
    AUDIT_PATH,
    MANIFEST_PATH,
    MARKER_PATH,
    OUTPUT_ROOT,
    REPORT_PATH,
    RFDError,
    RFDScope,
    runtime_identity,
    validate_bound_inputs,
)
from shaiwei.research.rf_diag.diagnose import run_diagnostic


def _write_json_once(path: Path, document: Mapping[str, Any]) -> str:
    if path.exists():
        raise RFDError(f"RF diagnostic write-once output already exists: {path.name}")
    payload = canonical_json(document) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def _relative(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def run_once() -> dict[str, Any]:
    if any(path.exists() for path in (MARKER_PATH, REPORT_PATH, MANIFEST_PATH, AUDIT_PATH)):
        raise RFDError("RF diagnostic output exists; same-scope rerun is forbidden")
    scope = RFDScope.load()
    validate_bound_inputs(scope)
    identity = runtime_identity()
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    marker_sha = _write_json_once(
        MARKER_PATH,
        {
            "schema_version": "rf-0b-gap-diagnostic-marker-v1",
            "semantic_read_started": True,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "protocol_sha256": scope.sha256,
            "release_identity": identity,
        },
    )
    manifest_path = PROJECT_ROOT / scope.document["frozen_inputs"]["raw_market_store"][
        "r3_frozen_input_manifest"
    ]["path"]
    manifest = load_r3_manifest(manifest_path)
    first = native(run_diagnostic(scope, OUTPUT_ROOT / "duckdb-tmp", manifest))
    second = native(run_diagnostic(scope, OUTPUT_ROOT / "duckdb-tmp-replay", manifest))
    if canonical_json(first) != canonical_json(second):
        raise RFDError("RF diagnostic internal deterministic replay differs")
    artifacts = {
        "semantic_read_marker": {"path": _relative(MARKER_PATH), "sha256": marker_sha},
    }
    first["machine_artifacts"] = artifacts
    first["internal_deterministic_replay_pass"] = True
    first["canonical_payload_sha256"] = canonical_sha256(first)
    report_sha = _write_json_once(REPORT_PATH, first)
    manifest_doc = {
        "schema_version": "rf-0b-gap-lineage-diagnostic-manifest-v1",
        "protocol_sha256": scope.sha256,
        "release_identity": identity,
        "artifacts": {**artifacts, "report": {"path": _relative(REPORT_PATH), "sha256": report_sha}},
        "contains_outcome": False,
        "contains_security_identifiers": True,
        "production_authorization": "none",
    }
    _write_json_once(MANIFEST_PATH, manifest_doc)
    return first

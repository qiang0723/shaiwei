"""Independent physical and semantic audit of sealed M5 global failure."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from .audit_failure_projection import expected_global_failure
from .audit_source_conflicts import audit_all_statement_sources
from .contract import (
    M5DataProtocol,
    M5GateError,
    canonical_json,
    sha256_file,
    sha256_json,
)


FORBIDDEN_CONFLICT_KEYS = {
    "ts_code",
    "f_ann_date",
    "end_date",
    "report_type",
    "update_flag",
    "raw_value",
    "normalized_value",
    "candidate_value",
    "absolute_path",
}


def _canonical_file(path: Path) -> dict[str, Any]:
    serialized = path.read_text(encoding="utf-8")
    value = json.loads(serialized)
    if not isinstance(value, dict) or serialized != canonical_json(value) + "\n":
        raise M5GateError("M5 conflict evidence JSON is not canonical")
    return value


def _scan_forbidden_keys(value: Any) -> None:
    if isinstance(value, dict):
        if forbidden := set(value) & FORBIDDEN_CONFLICT_KEYS:
            raise M5GateError(
                f"M5 conflict evidence contains forbidden fields: {sorted(forbidden)}"
            )
        for child in value.values():
            _scan_forbidden_keys(child)
    elif isinstance(value, list):
        for child in value:
            _scan_forbidden_keys(child)


def audit_global_failure(
    protocol: M5DataProtocol,
    frames: dict[str, pd.DataFrame],
    *,
    run_root: Path,
    manifest: dict[str, Any],
    report: dict[str, Any],
    expected_input_manifest_sha256: str,
    expected_release_scope_sha256: str,
    expected_approval_event_sha256: str,
) -> dict[str, Any]:
    conflict_path = run_root / "source_conflict_report.json"
    if (
        not conflict_path.is_file()
        or (run_root / "feature_panel.parquet").exists()
        or {path.name for path in run_root.iterdir()}
        != {
            "source_conflict_report.json",
            "data_gate_report.json",
            "run_manifest.json",
        }
    ):
        raise M5GateError("M5 global-failure artifact set differs")
    conflict = _canonical_file(conflict_path)
    _scan_forbidden_keys(conflict)
    artifacts = manifest.get("artifacts") or {}
    conflict_artifact = artifacts.get("source_conflict_report") or {}
    report_artifact = artifacts.get("data_gate_report") or {}
    if (
        set(artifacts) != {"source_conflict_report", "data_gate_report"}
        or conflict_artifact.get("file") != conflict_path.name
        or conflict_artifact.get("sha256") != sha256_file(conflict_path)
        or report_artifact.get("file") != "data_gate_report.json"
        or report_artifact.get("sha256")
        != sha256_file(run_root / "data_gate_report.json")
        or report.get("source_conflict_report") != conflict_artifact
    ):
        raise M5GateError("M5 global-failure artifact physical hash differs")
    approved_identity = {
        key: report.get(key)
        for key in (
            "protocol_sha256",
            "protocol_scope_sha256",
            "input_manifest_sha256",
            "release_scope_sha256",
            "code_bundle_sha256",
            "approval_event_sha256",
        )
    }
    audited = audit_all_statement_sources(frames)
    expected_conflict, expected_quality = expected_global_failure(
        protocol,
        audited,
        approved_identity=approved_identity,
        semantic_rows_read=report.get("semantic_rows_read") is True,
    )
    if conflict != expected_conflict:
        raise M5GateError("M5 source conflict report differs from independent audit")
    if report.get("quality") != expected_quality:
        raise M5GateError("M5 global-failure matrix differs from independent audit")
    if (
        manifest.get("schema_version") != "m5-data-gate-run-manifest-v2"
        or report.get("schema_version") != "m5-data-gate-report-v2"
        or manifest.get("outcome_kind") != "GLOBAL_DATA_FAILURE"
        or report.get("outcome_kind") != "GLOBAL_DATA_FAILURE"
        or report.get("feature_panel") != {"status": "NOT_CREATED_GLOBAL_FAILURE"}
        or report.get("verdict") != expected_quality["verdict"]
        or manifest.get("verdict") != expected_quality["verdict"]
        or manifest.get("runner_self_reported_only") is not True
        or manifest.get("independent_audit_status") != "NOT_RUN"
        or report.get("label_read") is not False
        or report.get("effect_read") is not False
        or report.get("model_training_run") is not False
        or report.get("backtest_run") is not False
        or report.get("provider_call_count") != 0
        or report.get("production_authorization") != "none"
    ):
        raise M5GateError("M5 global-failure evidence claims unauthorized state")
    return {
        "schema_version": "m5-data-gate-independent-audit-v2",
        "status": "PASS",
        "outcome_kind": "GLOBAL_DATA_FAILURE",
        "run_id": manifest["run_id"],
        "run_manifest_sha256": sha256_file(run_root / "run_manifest.json"),
        "report_sha256": sha256_file(run_root / "data_gate_report.json"),
        "source_conflict_report_physical_sha256": sha256_file(conflict_path),
        "source_conflict_report_canonical_sha256": sha256_json(conflict),
        "global_conflict_set_sha256": audited["global_conflict_set_sha256"],
        "input_manifest_sha256": expected_input_manifest_sha256,
        "release_scope_sha256": expected_release_scope_sha256,
        "approval_event_sha256": expected_approval_event_sha256,
        "candidate_matrix": expected_quality["registry_candidate_matrix"],
        "eligible_candidate_ids": [],
        "rejected_candidate_ids": list(protocol.candidate_ids),
        "verdict": expected_quality["verdict"],
        "effect_test_count": 0,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
    }

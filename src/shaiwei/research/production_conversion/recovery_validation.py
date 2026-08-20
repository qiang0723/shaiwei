"""Fail-closed validation for the result-blind Head30 entrypoint recovery."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shaiwei.research.model_attribution.contract import sha256_file
from shaiwei.research.production_conversion.contract import ProtocolError


def _project_file(project_root: Path, relative: object) -> Path:
    if not isinstance(relative, str) or not relative:
        raise ProtocolError("production-converter recovery predecessor path is invalid")
    root = project_root.resolve()
    path = (root / relative).resolve(strict=True)
    if root not in path.parents or path.is_symlink():
        raise ProtocolError("production-converter recovery predecessor is outside project")
    return path


def _json_mapping(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ProtocolError("production-converter recovery predecessor is invalid") from error
    if not isinstance(value, dict):
        raise ProtocolError("production-converter recovery predecessor is not a mapping")
    return value


def validate_entrypoint_recovery_protocol(
    document: dict[str, Any], project_root: Path
) -> None:
    predecessors = document.get("predecessors", {})
    original = predecessors.get("original_release_protocol", {})
    original_path = _project_file(project_root, original.get("path"))
    if original.get("sha256") != sha256_file(original_path):
        raise ProtocolError("production-converter recovery protocol predecessor differs")

    failed = predecessors.get("failed_release_scope", {})
    failed_path = _project_file(project_root, failed.get("path"))
    failed_document = _json_mapping(failed_path)
    if (
        failed.get("file_sha256") != sha256_file(failed_path)
        or failed.get("release_scope_sha256")
        != failed_document.get("release_scope_sha256")
    ):
        raise ProtocolError("production-converter failed release predecessor differs")

    evidence = predecessors.get("entrypoint_failure_evidence", {})
    evidence_path = _project_file(project_root, evidence.get("path"))
    evidence_document = _json_mapping(evidence_path)
    if evidence.get("sha256") != sha256_file(evidence_path):
        raise ProtocolError("production-converter entrypoint failure evidence differs")
    required = {
        "container_created": False,
        "treatment_effect_started": False,
        "real_effect_read": False,
        "portfolio_attempts_consumed": 0,
        "same_scope_retry_authorized": False,
        "production_authorization": "none",
    }
    if any(evidence_document.get(key) != value for key, value in required.items()):
        raise ProtocolError("production-converter entrypoint failure state differs")
    if predecessors.get("failed_approval_sha256") != evidence_document.get(
        "approval_sha256"
    ):
        raise ProtocolError("production-converter failed approval identity differs")

    release = document.get("release_and_approval", {})
    expected_release = {
        "release_scope_kind": (
            "PRODUCTION_HEAD30_G0_ENTRYPOINT_RECOVERY_READY_NOT_EXECUTION_APPROVAL"
        ),
        "approval_action": (
            "M6_PRODUCTION_HEAD30_G0_EFFECT_ENTRYPOINT_RECOVERY_ONCE_WITH_REPLAY_"
            "AND_INDEPENDENT_AUDIT"
        ),
        "approval_must_bind_exact_release_scope_sha256": True,
        "scope_drift_invalidates_approval": True,
        "tracked_release_scope": (
            "config/m6_csi800_production_head30_entrypoint_recovery_scope_v1.json"
        ),
        "approval_record_path": (
            "data/control/m6_csi800_production_head30_v1/approval-r1.json"
        ),
        "approval_record_git_ignored": True,
    }
    if release != expected_release:
        raise ProtocolError("production-converter recovery approval contract differs")

    recovery = document.get("recovery_change", {})
    fixed = {
        "only_changed_variable": "docker_tmpfs_yaml_serialization",
        "strategy_formula_changed": False,
        "model_or_prediction_changed": False,
        "input_identity_changed": False,
        "decision_contract_changed": False,
        "result_semantic_read_before_new_approval": False,
    }
    if any(recovery.get(key) != value for key, value in fixed.items()):
        raise ProtocolError("production-converter recovery change boundary differs")

    if document.get("execution_counting", {}) != {
        "runner_invocation_count": 1,
        "complete_internal_passes": ["first_pass", "replay"],
        "independent_auditor_invocation_count": 1,
        "new_portfolio_attempts_consumed_at_first_treatment_effect_read": 1,
        "original_failed_scope_attempts_consumed": 0,
        "model_attempt_increment": 0,
        "same_recovery_scope_retry_authorized": False,
    }:
        raise ProtocolError("production-converter recovery execution count differs")


__all__ = ["validate_entrypoint_recovery_protocol"]

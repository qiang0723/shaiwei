"""Frozen R1/R2 release-recovery lineage for the M6-5C component."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.model_attribution.contract import sha256_file
from shaiwei.research.production_conversion.contract import ProtocolError


R1_PATH = (
    PROJECT_ROOT
    / "config/m6_csi800_production_head30_delisting_risk_release_context_recovery_v1.yaml"
)
R2_PATH = (
    PROJECT_ROOT
    / "config/m6_csi800_production_head30_delisting_risk_scope_runtime_recovery_v2.yaml"
)
R1_IMAGE = "shaiwei:m6-head30-delisting-risk-release-r1-v1"
R2_IMAGE = "shaiwei:m6-head30-delisting-risk-release-r2-v1"


def _mapping(path: Path, *, yaml_document: bool = False) -> dict[str, Any]:
    try:
        value = (
            yaml.safe_load(path.read_text(encoding="utf-8"))
            if yaml_document
            else json.loads(path.read_text(encoding="utf-8"))
        )
    except (OSError, ValueError, yaml.YAMLError) as error:
        raise ProtocolError(f"M6-5C recovery document is invalid: {path.name}") from error
    if not isinstance(value, dict):
        raise ProtocolError(f"M6-5C recovery document is not a mapping: {path.name}")
    return value


def _authority(document: dict[str, Any], where: str) -> None:
    authority = document.get("authority", {})
    allowed = {
        "recovery_engineering_authorized",
        "one_successor_offline_build_authorized",
        "one_successor_synthetic_fixture_authorized",
        "metadata_only_scope_authorized",
    }
    if any(authority.get(key) is not True for key in allowed) or any(
        value not in (False, "none")
        for key, value in authority.items()
        if key not in allowed
    ):
        raise ProtocolError(f"M6-5C {where} authority differs")


def _validate_r1(document: dict[str, Any], protocol_sha256: str) -> None:
    predecessor = document.get("predecessor", {})
    failure_path = PROJECT_ROOT / str(predecessor.get("failure_evidence", ""))
    failure = _mapping(failure_path)
    if (
        document.get("schema_version")
        != "m6-csi800-production-head30-delisting-risk-release-context-recovery-v1"
        or document.get("stage") != "RESULT_BLIND_DOCKER_CONTEXT_RECOVERY_ONLY"
        or predecessor.get("base_release_protocol_sha256") != protocol_sha256
        or sha256_file(failure_path) != predecessor.get("failure_evidence_sha256")
        or failure.get("decision") != "BLOCKED_BEFORE_SYNTHETIC_DOMAIN_ENTRY"
        or failure.get("effect_or_target_or_price_read") is not False
        or failure.get("new_attempts_consumed") != 0
    ):
        raise ProtocolError("M6-5C R1 predecessor identity differs")
    single = document.get("single_change", {})
    if (
        single.get("add_dedicated_dockerignore")
        != "Dockerfile.m6-head30-delisting-risk-release.dockerignore"
        or single.get("successor_image_reference") != R1_IMAGE
        or single.get("domain_code_change_authorized") is not False
        or single.get("claim_or_gate_change_authorized") is not False
        or single.get("compose_mount_change_authorized") is not False
        or len(single.get("copy_required_predecessor_documents", [])) != 3
    ):
        raise ProtocolError("M6-5C R1 single change differs")
    _authority(document, "R1")


def _validate_r2(document: dict[str, Any]) -> None:
    predecessor = document.get("predecessor", {})
    failure_path = PROJECT_ROOT / str(predecessor.get("failure_evidence", ""))
    failure = _mapping(failure_path)
    if (
        document.get("schema_version")
        != "m6-csi800-production-head30-delisting-risk-scope-runtime-recovery-v2"
        or document.get("stage") != "RESULT_BLIND_PRECLAIM_SCOPE_RUNTIME_RECOVERY_ONLY"
        or sha256_file(failure_path) != predecessor.get("failure_evidence_sha256")
        or failure.get("decision")
        != "BLOCKED_BEFORE_CLAIM_BY_COMPONENT_RUNTIME_REGISTRY_VALIDATION"
        or failure.get("canonical_ledger_write") is not False
        or failure.get("effect_or_target_or_price_read") is not False
        or failure.get("new_attempts_consumed") != 0
        or predecessor.get("same_failed_scope_retry_authorized") is not False
    ):
        raise ProtocolError("M6-5C R2 predecessor identity differs")
    single = document.get("single_change", {})
    if (
        single.get("successor_image_reference") != R2_IMAGE
        or single.get("successor_scope_path")
        != "config/m6_csi800_production_head30_delisting_risk_release_scope_r2_v1.json"
        or single.get("domain_or_metric_change_authorized") is not False
        or single.get("claim_semantics_change_authorized") is not False
        or single.get("input_or_gate_change_authorized") is not False
        or single.get("daemon_fixture", {}).get(
            "must_cross_real_release_scope_loader_in_successor_image"
        )
        is not True
    ):
        raise ProtocolError("M6-5C R2 single change differs")
    attempt = document.get("attempt", {})
    if (
        attempt.get("family") != "m6_head30_500k_delisting_risk_overlay_v1"
        or attempt.get("family_attempts_before_run") != 0
        or attempt.get("attempt_ordinal") != 1
    ):
        raise ProtocolError("M6-5C R2 attempt lineage differs")
    _authority(document, "R2")


def load_release_recoveries(protocol_sha256: str) -> tuple[str, str]:
    r1 = _mapping(R1_PATH, yaml_document=True)
    r2 = _mapping(R2_PATH, yaml_document=True)
    _validate_r1(r1, protocol_sha256)
    _validate_r2(r2)
    return sha256_file(R1_PATH), sha256_file(R2_PATH)

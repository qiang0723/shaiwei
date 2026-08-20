"""Versioned contract for the Head30 independent-audit identity recovery."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.model_attribution.contract import (
    canonical_json,
    canonical_sha256,
    sha256_file,
)
from shaiwei.research.production_conversion.contract import ProtocolError


PROTOCOL_PATH = PROJECT_ROOT / "config/m6_csi800_production_head30_audit_identity_recovery_v1.yaml"
SCOPE_PATH = PROJECT_ROOT / "config/m6_csi800_production_head30_audit_identity_recovery_scope_v1.json"
COMPOSE_PATH = PROJECT_ROOT / "compose.m6-production-head30-audit-recovery.yaml"
ACTION = "M6_PRODUCTION_HEAD30_AUDIT_IDENTITY_RECOVERY_ONCE"
SCOPE_KIND = "PRODUCTION_HEAD30_AUDIT_IDENTITY_RECOVERY_READY_NOT_EXECUTION_APPROVAL"
IMAGE = "shaiwei:m6-production-head30-audit-recovery-v1"

COMMAND = [
    "python", "/opt/shaiwei/m6-head30-audit-recovery/entrypoint.py",
    "--recovery-protocol", "/inputs/recovery-protocol.yaml",
    "--recovery-release", "/inputs/recovery-release.json",
    "--recovery-approval", "/inputs/recovery-approval.json",
    "--recovery-compose", "/inputs/recovery-compose.yaml",
    "--original-protocol", "/inputs/original-protocol.yaml",
    "--original-release", "/inputs/original-release.json",
    "--original-approval", "/inputs/original-approval.json",
    "--failure-evidence", "/inputs/audit-failure.json",
    "--effect-root", "/outputs", "--audit-root", "/audit",
]

MOUNTS = [
    {"source": "config/m6_csi800_production_head30_audit_identity_recovery_v1.yaml", "target": "/inputs/recovery-protocol.yaml", "mode": "ro"},
    {"source": "config/m6_csi800_production_head30_audit_identity_recovery_scope_v1.json", "target": "/inputs/recovery-release.json", "mode": "ro"},
    {"source": "data/control/m6_csi800_production_head30_v1/audit-identity-recovery-approval.json", "target": "/inputs/recovery-approval.json", "mode": "ro"},
    {"source": "compose.m6-production-head30-audit-recovery.yaml", "target": "/inputs/recovery-compose.yaml", "mode": "ro"},
    {"source": "config/m6_csi800_production_head30_price_recovery_v1.yaml", "target": "/inputs/original-protocol.yaml", "mode": "ro"},
    {"source": "config/m6_csi800_production_head30_price_recovery_scope_v1.json", "target": "/inputs/original-release.json", "mode": "ro"},
    {"source": "data/control/m6_csi800_production_head30_v1/approval-r2.json", "target": "/inputs/original-approval.json", "mode": "ro"},
    {"source": "config/m6_csi800_production_head30_price_recovery_audit_failure_v1.json", "target": "/inputs/audit-failure.json", "mode": "ro"},
    {"source": "data/research/m6_csi800_production_head30_v1/effect-r2", "target": "/outputs", "mode": "ro"},
    {"source": "data/research/m6_csi800_production_head30_v1/effect-r2-audit-recovery", "target": "/audit", "mode": "rw"},
]


def mapping(path: Path, *, yaml_document: bool = False) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text()) if yaml_document else json.loads(path.read_text())
    except (OSError, ValueError, yaml.YAMLError) as error:
        raise ProtocolError(f"Head30 audit-recovery document is invalid: {path.name}") from error
    if not isinstance(value, dict):
        raise ProtocolError(f"Head30 audit-recovery document is not a mapping: {path.name}")
    return value


def _sha(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _validate_protocol(document: dict[str, Any]) -> None:
    if document.get("schema_version") != "m6-production-head30-audit-identity-recovery-protocol-v1":
        raise ProtocolError("Head30 audit-recovery protocol schema differs")
    if document.get("recovery_id") != "m6-csi800-production-head30-audit-identity-recovery-v1":
        raise ProtocolError("Head30 audit-recovery protocol identity differs")
    if document.get("status") != "FROZEN_AFTER_R2_AUDIT_FAILURE_BEFORE_RECOVERY_IMPLEMENTATION":
        raise ProtocolError("Head30 audit-recovery protocol stage differs")
    if document.get("objective") != {
        "recover_exactly_one_independent_audit_of_the_existing_r2_effect_tree": True,
        "research_question_or_result_change": False,
        "runner_or_effect_recomputation": False,
        "additional_portfolio_attempt_count": 0,
    }:
        raise ProtocolError("Head30 audit-recovery objective differs")
    original = document.get("original_authority", {})
    for key in ("release_scope_sha256", "release_document_sha256", "approval_sha256", "base_runtime_code_snapshot_sha256"):
        if not _sha(original.get(key)):
            raise ProtocolError("Head30 audit-recovery original identity is invalid")
    if not str(original.get("base_image_id", "")).startswith("sha256:"):
        raise ProtocolError("Head30 audit-recovery base image identity is invalid")
    sealed = document.get("sealed_r2_effect", {})
    for key in ("tree_sha256", "authorization_sha256", "treatment_effect_started_sha256", "first_pass_bundle_sha256", "replay_bundle_sha256", "report_sha256", "primary_result_sha256"):
        if not _sha(sealed.get(key)):
            raise ProtocolError("Head30 audit-recovery sealed identity is invalid")
    if (
        sealed.get("first_pass_bundle_sha256") != sealed.get("replay_bundle_sha256")
        or sealed.get("runner_invocation_count") != 1
        or sealed.get("portfolio_attempts_consumed_in_r2") != 1
        or sealed.get("family_portfolio_attempts_consumed") != 2
        or sealed.get("model_attempt_increment") != 0
        or sealed.get("same_r2_runner_retry_authorized") is not False
        or sealed.get("file_count") != 5
        or int(sealed.get("total_bytes", 0)) <= 0
        or sealed.get("failure_document_exists") is not False
    ):
        raise ProtocolError("Head30 audit-recovery sealed state differs")
    failed = document.get("failed_r2_auditor", {})
    if (
        failed.get("invocation_count") != 1
        or failed.get("audit_function_entered") is not True
        or failed.get("effect_semantics_read") is not True
        or failed.get("audit_output_file_count") != 0
        or failed.get("failed_check") != "reported_result_identity"
        or failed.get("same_r2_auditor_retry_authorized") is not False
        or not _sha(failed.get("tracked_failure_evidence_sha256"))
    ):
        raise ProtocolError("Head30 audit-recovery failed-auditor state differs")
    cause = document.get("root_cause", {})
    if (
        cause.get("primary_result_identity_correct") is not True
        or cause.get("independent_reconstruction_equivalent_under_frozen_tolerance") is not True
        or cause.get("decision_agreement") is not True
        or cause.get("research_or_statistical_defect") is not False
    ):
        raise ProtocolError("Head30 audit-recovery cause differs")
    recovered = document.get("recovered_audit_contract", {})
    independent = recovered.get("independent_reconstruction", {})
    if (
        independent.get("implementation") != "existing_audit_statistics_independently_evaluate"
        or independent.get("imports_primary_calculation_code") is not False
        or independent.get("relative_tolerance") != 1e-12
        or independent.get("absolute_tolerance") != 1e-12
        or independent.get("exact_canonical_sha_equality_with_primary_required") is not False
        or recovered.get("decision_identity", {}).get("report_primary_and_independent_decisions_must_match_exactly") is not True
    ):
        raise ProtocolError("Head30 recovered audit semantics differ")
    requirements = document.get("recovery_release_requirements", {})
    exact = {
        "scope_kind": SCOPE_KIND, "approval_action": ACTION, "network_mode": "none",
        "qlib_mount": False, "effect_mount": "ro", "recovery_audit_mount": "rw",
        "full_project_root_mount": False, "env_or_secret_mount": False,
        "docker_socket_mount": False, "production_ledger_mount": False,
        "run_as_non_root": True, "read_only_root": True, "cap_drop_all": True,
        "no_new_privileges": True, "cpus": 2, "memory": "4g", "pids_limit": 128,
    }
    if any(requirements.get(key) != value for key, value in exact.items()):
        raise ProtocolError("Head30 audit-recovery runtime boundary differs")
    if document.get("production_authorization") != "none":
        raise ProtocolError("Head30 audit recovery cannot authorize production")


@dataclass(frozen=True)
class RecoveryProtocol:
    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path = PROTOCOL_PATH) -> "RecoveryProtocol":
        resolved = path.resolve()
        document = mapping(resolved, yaml_document=True)
        _validate_protocol(document)
        return cls(resolved, document, sha256_file(resolved))


def effect_tree_identity(root: Path) -> dict[str, Any]:
    if not root.is_dir():
        raise ProtocolError("Head30 sealed effect root is absent")
    rows: list[dict[str, Any]] = []
    total = 0
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if path.is_symlink():
            raise ProtocolError("Head30 sealed effect contains a symlink")
        size = path.stat().st_size
        rows.append({"path": path.relative_to(root).as_posix(), "sha256": sha256_file(path), "size": size})
        total += size
    if not rows:
        raise ProtocolError("Head30 sealed effect root is empty")
    return {"file_count": len(rows), "total_bytes": total, "tree_sha256": hashlib.sha256(canonical_json(rows)).hexdigest()}


def expected_authority() -> dict[str, Any]:
    return {
        "release_ready": True, "execution_authorized": False,
        "sealed_effect_read_authorized": False, "independent_audit_write_authorized": False,
        "qlib_mount_authorized": False, "runner_invocation_authorized": False,
        "model_fit_prediction_backtest_authorized": False,
        "experiment_ledger_write_authorized": False, "external_network_authorized": False,
        "env_or_secret_read_authorized": False, "forward_signal_authorized": False,
        "paper_portfolio_authorized": False, "web_authorized": False,
        "production_authorization": "none",
    }


def expected_sealed(protocol: RecoveryProtocol) -> dict[str, Any]:
    sealed = protocol.document["sealed_r2_effect"]
    return {key: sealed[key] for key in (
        "effect_root", "recovery_audit_root", "file_count", "total_bytes", "tree_sha256",
        "authorization_sha256", "treatment_effect_started_sha256", "first_pass_bundle_sha256",
        "replay_bundle_sha256", "report_sha256", "primary_result_sha256", "primary_decision",
    )}


def validate_scope(scope: dict[str, Any], protocol: RecoveryProtocol, compose_path: Path) -> None:
    if scope.get("scope_kind") != SCOPE_KIND or scope.get("recovery_id") != protocol.document["recovery_id"]:
        raise ProtocolError("Head30 audit-recovery scope identity differs")
    if scope.get("protocol_sha256") != protocol.sha256:
        raise ProtocolError("Head30 audit-recovery protocol hash differs")
    if scope.get("original_authority") != protocol.document["original_authority"]:
        raise ProtocolError("Head30 audit-recovery original authority differs")
    if scope.get("sealed_effect") != expected_sealed(protocol):
        raise ProtocolError("Head30 audit-recovery sealed effect differs")
    failed = protocol.document["failed_r2_auditor"]
    if scope.get("failure_evidence") != {"path": failed["tracked_failure_evidence_path"], "sha256": failed["tracked_failure_evidence_sha256"]}:
        raise ProtocolError("Head30 audit-recovery failure evidence differs")
    implementation = scope.get("implementation", {})
    commit = implementation.get("git_commit")
    if not isinstance(commit, str) or len(commit) != 40 or implementation.get("origin_main_commit") != commit:
        raise ProtocolError("Head30 audit-recovery implementation commit differs")
    for key in ("contract_sha256", "entrypoint_sha256", "dockerfile_sha256"):
        if not _sha(implementation.get(key)):
            raise ProtocolError("Head30 audit-recovery implementation identity is invalid")
    image = scope.get("image", {})
    original = protocol.document["original_authority"]
    if (
        image.get("reference") != IMAGE or image.get("base_reference") != original["base_image_reference"]
        or image.get("base_image_id") != original["base_image_id"] or image.get("git_commit") != commit
        or image.get("contract_sha256") != implementation["contract_sha256"]
        or image.get("entrypoint_sha256") != implementation["entrypoint_sha256"]
        or not str(image.get("image_id", "")).startswith("sha256:")
        or image.get("platform") not in {"linux/arm64", "linux/amd64"}
    ):
        raise ProtocolError("Head30 audit-recovery image identity differs")
    if scope.get("authority") != expected_authority():
        raise ProtocolError("Head30 audit-recovery authority differs")
    if scope.get("execution") != {
        "approval_action": ACTION, "runner_invocation_count": 0,
        "recovery_auditor_invocation_count": 1, "additional_portfolio_attempt_count": 0,
        "same_recovery_retry_authorized": False,
    }:
        raise ProtocolError("Head30 audit-recovery execution count differs")
    container = scope.get("container", {})
    expected_container = {
        "compose_path": "compose.m6-production-head30-audit-recovery.yaml",
        "compose_sha256": sha256_file(compose_path), "network_mode": "none",
        "read_only_root": True, "run_as_non_root": True, "cap_drop_all": True,
        "no_new_privileges": True, "env_file_mounted": False, "docker_socket_mounted": False,
        "full_project_root_mounted": False, "qlib_mounted": False,
        "production_ledger_mounted": False, "service": "m6-production-head30-audit-recovery",
        "command": COMMAND, "mounts": MOUNTS, "cpus": 2, "memory": "4g", "pids_limit": 128,
    }
    if container != expected_container:
        raise ProtocolError("Head30 audit-recovery container boundary differs")


@dataclass(frozen=True)
class RecoveryReleaseScope:
    path: Path
    scope: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path, protocol: RecoveryProtocol, *, compose_path: Path = COMPOSE_PATH) -> "RecoveryReleaseScope":
        document = mapping(path.resolve())
        if set(document) != {"schema_version", "recovery_scope_sha256", "scope"}:
            raise ProtocolError("Head30 audit-recovery scope fields differ")
        if document.get("schema_version") != "m6-production-head30-audit-identity-recovery-scope-v1":
            raise ProtocolError("Head30 audit-recovery scope schema differs")
        scope = document.get("scope")
        if not isinstance(scope, dict) or document.get("recovery_scope_sha256") != canonical_sha256(scope):
            raise ProtocolError("Head30 audit-recovery scope self hash differs")
        validate_scope(scope, protocol, compose_path.resolve())
        return cls(path.resolve(), scope, document["recovery_scope_sha256"])


@dataclass(frozen=True)
class RecoveryApproval:
    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path, release: RecoveryReleaseScope) -> "RecoveryApproval":
        document = mapping(path.resolve())
        expected = {
            "schema_version": "m6-production-head30-audit-identity-recovery-approval-v1",
            "recovery_scope_sha256": release.sha256, "action": ACTION,
            "sealed_effect_read_authorized": True, "independent_audit_write_authorized": True,
            "qlib_mount_authorized": False, "runner_invocation_authorized": False,
            "model_fit_prediction_backtest_authorized": False,
            "experiment_ledger_write_authorized": False, "external_network_authorized": False,
            "env_or_secret_read_authorized": False, "production_authorization": "none",
        }
        if set(document) != set(expected) | {"approved_at", "consumed"}:
            raise ProtocolError("Head30 audit-recovery approval fields differ")
        if any(document.get(key) != value for key, value in expected.items()):
            raise ProtocolError("Head30 audit-recovery approval authority differs")
        if not document.get("approved_at") or document.get("consumed") is not False:
            raise ProtocolError("Head30 audit-recovery approval state differs")
        return cls(path.resolve(), document, sha256_file(path.resolve()))


__all__ = [
    "ACTION", "COMMAND", "COMPOSE_PATH", "IMAGE", "MOUNTS", "PROTOCOL_PATH", "SCOPE_KIND",
    "SCOPE_PATH", "RecoveryApproval", "RecoveryProtocol", "RecoveryReleaseScope",
    "effect_tree_identity", "expected_authority", "expected_sealed", "mapping", "validate_scope",
]

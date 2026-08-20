"""Frozen contract for the Head30 audit-entrypoint recovery."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.model_attribution.contract import canonical_sha256, sha256_file
from shaiwei.research.production_conversion.contract import ProtocolError


PROTOCOL_PATH = PROJECT_ROOT / "config/m6_csi800_production_head30_audit_entrypoint_recovery_v1.yaml"
SCOPE_PATH = PROJECT_ROOT / "config/m6_csi800_production_head30_audit_entrypoint_recovery_scope_v1.json"
COMPOSE_PATH = PROJECT_ROOT / "compose.m6-production-head30-audit-entrypoint-recovery.yaml"
ACTION = "M6_PRODUCTION_HEAD30_AUDIT_ENTRYPOINT_RECOVERY_ONCE"
SCOPE_KIND = "PRODUCTION_HEAD30_AUDIT_ENTRYPOINT_RECOVERY_READY_NOT_EXECUTION_APPROVAL"
IMAGE = "shaiwei:m6-production-head30-audit-entrypoint-recovery-v1"
EMBEDDED_ORIGINAL_PROTOCOL = Path(
    "/workspace/config/m6_csi800_production_head30_price_recovery_v1.yaml"
)

COMMAND = [
    "python", "/opt/shaiwei/m6-head30-audit-entry-recovery/entrypoint.py",
    "--recovery-protocol", "/inputs/recovery-protocol.yaml",
    "--recovery-release", "/inputs/recovery-release.json",
    "--recovery-approval", "/inputs/recovery-approval.json",
    "--recovery-compose", "/inputs/recovery-compose.yaml",
    "--r3-release", "/inputs/r3-release.json",
    "--r3-failure-evidence", "/inputs/r3-execution-failure.json",
    "--original-release", "/inputs/original-release.json",
    "--original-approval", "/inputs/original-approval.json",
    "--effect-root", "/outputs", "--audit-root", "/audit",
]

MOUNTS = [
    {"source": "config/m6_csi800_production_head30_audit_entrypoint_recovery_v1.yaml", "target": "/inputs/recovery-protocol.yaml", "mode": "ro"},
    {"source": "config/m6_csi800_production_head30_audit_entrypoint_recovery_scope_v1.json", "target": "/inputs/recovery-release.json", "mode": "ro"},
    {"source": "data/control/m6_csi800_production_head30_v1/audit-entrypoint-recovery-approval.json", "target": "/inputs/recovery-approval.json", "mode": "ro"},
    {"source": "compose.m6-production-head30-audit-entrypoint-recovery.yaml", "target": "/inputs/recovery-compose.yaml", "mode": "ro"},
    {"source": "config/m6_csi800_production_head30_audit_identity_recovery_scope_v1.json", "target": "/inputs/r3-release.json", "mode": "ro"},
    {"source": "config/m6_csi800_production_head30_audit_identity_recovery_execution_failure_v1.json", "target": "/inputs/r3-execution-failure.json", "mode": "ro"},
    {"source": "config/m6_csi800_production_head30_price_recovery_scope_v1.json", "target": "/inputs/original-release.json", "mode": "ro"},
    {"source": "data/control/m6_csi800_production_head30_v1/approval-r2.json", "target": "/inputs/original-approval.json", "mode": "ro"},
    {"source": "data/research/m6_csi800_production_head30_v1/effect-r2", "target": "/outputs", "mode": "ro"},
    {"source": "data/research/m6_csi800_production_head30_v1/effect-r2-audit-entrypoint-recovery", "target": "/audit", "mode": "rw"},
]


def mapping(path: Path, *, yaml_document: bool = False) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text()) if yaml_document else json.loads(path.read_text())
    except (OSError, ValueError, yaml.YAMLError) as error:
        raise ProtocolError(f"Head30 audit-entry recovery document is invalid: {path.name}") from error
    if not isinstance(value, dict):
        raise ProtocolError(f"Head30 audit-entry recovery document is not a mapping: {path.name}")
    return value


def _sha(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _validate_protocol(document: dict[str, Any]) -> None:
    if document.get("schema_version") != "m6-production-head30-audit-entrypoint-recovery-protocol-v1":
        raise ProtocolError("Head30 audit-entry recovery protocol schema differs")
    if document.get("recovery_id") != "m6-csi800-production-head30-audit-entrypoint-recovery-v1":
        raise ProtocolError("Head30 audit-entry recovery identity differs")
    if document.get("status") != "FROZEN_AFTER_R3_ENTRYPOINT_FAILURE_BEFORE_R4_IMPLEMENTATION":
        raise ProtocolError("Head30 audit-entry recovery stage differs")
    objective = document.get("objective", {})
    if objective != {
        "recover_exactly_one_independent_audit_of_the_existing_r2_effect_tree": True,
        "change_only_the_original_protocol_container_path": True,
        "research_question_or_result_change": False,
        "audit_semantics_change": False,
        "runner_or_effect_recomputation": False,
        "additional_portfolio_attempt_count": 0,
    }:
        raise ProtocolError("Head30 audit-entry recovery objective differs")
    r3 = document.get("r3_authority", {})
    failure = document.get("r3_execution_failure", {})
    for value in (
        r3.get("protocol_sha256"), r3.get("release_scope_sha256"),
        r3.get("release_document_sha256"), r3.get("approval_sha256"),
        r3.get("contract_sha256"), r3.get("entrypoint_sha256"),
        failure.get("evidence_sha256"),
    ):
        if not _sha(value):
            raise ProtocolError("Head30 audit-entry recovery R3 identity is invalid")
    if (
        failure.get("auditor_invocation_count") != 1
        or failure.get("effect_semantics_read") is not False
        or failure.get("audit_output_file_count") != 0
        or failure.get("runner_invocation_count") != 0
        or failure.get("additional_portfolio_attempt_count") != 0
        or failure.get("same_r3_scope_retry_authorized") is not False
    ):
        raise ProtocolError("Head30 audit-entry recovery R3 failure state differs")
    change = document.get("root_cause_and_only_change", {})
    if (
        change.get("rejected_path") != "/inputs/original-protocol.yaml"
        or change.get("rejected_path_must_not_be_mounted_or_used") is not True
        or change.get("frozen_loader_allowlist_is_unchanged") is not True
        or change.get("embedded_allowed_path") != str(EMBEDDED_ORIGINAL_PROTOCOL)
        or change.get("embedded_allowed_path_is_the_only_runtime_path_change") is not True
        or not _sha(change.get("embedded_protocol_sha256"))
        or change.get("original_protocol_copy_or_rewrite_forbidden") is not True
    ):
        raise ProtocolError("Head30 audit-entry recovery path change differs")
    sealed = document.get("sealed_r2_effect", {})
    for key in (
        "tree_sha256", "authorization_sha256", "treatment_effect_started_sha256",
        "first_pass_bundle_sha256", "replay_bundle_sha256", "report_sha256",
        "primary_result_sha256",
    ):
        if not _sha(sealed.get(key)):
            raise ProtocolError("Head30 audit-entry recovery sealed identity is invalid")
    if (
        sealed.get("file_count") != 5
        or int(sealed.get("total_bytes", 0)) <= 0
        or sealed.get("first_pass_bundle_sha256") != sealed.get("replay_bundle_sha256")
        or sealed.get("family_portfolio_attempts_consumed") != 2
    ):
        raise ProtocolError("Head30 audit-entry recovery sealed state differs")
    semantics = document.get("inherited_audit_semantics", {})
    if (
        semantics.get("source_protocol_sha256") != r3.get("protocol_sha256")
        or semantics.get("main_artifact_identity_requires_exact_physical_and_canonical_hashes") is not True
        or semantics.get("independent_reconstruction_implementation") != "existing_audit_statistics_independently_evaluate"
        or semantics.get("independent_reconstruction_imports_primary_calculation_code") is not False
        or semantics.get("independent_relative_tolerance") != 1e-12
        or semantics.get("independent_absolute_tolerance") != 1e-12
        or semantics.get("independent_exact_canonical_sha_equality_with_primary_required") is not False
        or semantics.get("report_primary_and_independent_decisions_must_match_exactly") is not True
    ):
        raise ProtocolError("Head30 audit-entry recovery inherited semantics differ")
    requirements = document.get("release_requirements", {})
    exact = {
        "scope_kind": SCOPE_KIND, "approval_action": ACTION,
        "daemon_fixture_must_load_exact_embedded_allowed_path": True,
        "daemon_fixture_must_use_final_image_and_compose_service": True,
        "network_mode": "none", "qlib_mount": False, "effect_mount": "ro",
        "recovery_audit_mount": "rw", "full_project_root_mount": False,
        "env_or_secret_mount": False, "docker_socket_mount": False,
        "production_ledger_mount": False, "run_as_non_root": True,
        "read_only_root": True, "cap_drop_all": True, "no_new_privileges": True,
        "cpus": 2, "memory": "4g", "pids_limit": 128,
    }
    if any(requirements.get(key) != value for key, value in exact.items()):
        raise ProtocolError("Head30 audit-entry recovery runtime boundary differs")
    if document.get("production_authorization") != "none":
        raise ProtocolError("Head30 audit-entry recovery cannot authorize production")


@dataclass(frozen=True)
class EntryRecoveryProtocol:
    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path = PROTOCOL_PATH) -> "EntryRecoveryProtocol":
        resolved = path.resolve()
        document = mapping(resolved, yaml_document=True)
        _validate_protocol(document)
        return cls(resolved, document, sha256_file(resolved))


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


def expected_sealed(protocol: EntryRecoveryProtocol) -> dict[str, Any]:
    return dict(protocol.document["sealed_r2_effect"])


def validate_scope(scope: dict[str, Any], protocol: EntryRecoveryProtocol, compose_path: Path) -> None:
    if scope.get("scope_kind") != SCOPE_KIND or scope.get("recovery_id") != protocol.document["recovery_id"]:
        raise ProtocolError("Head30 audit-entry recovery scope identity differs")
    if scope.get("protocol_sha256") != protocol.sha256:
        raise ProtocolError("Head30 audit-entry recovery protocol hash differs")
    if scope.get("r3_authority") != protocol.document["r3_authority"]:
        raise ProtocolError("Head30 audit-entry recovery R3 authority differs")
    if scope.get("r3_execution_failure") != protocol.document["r3_execution_failure"]:
        raise ProtocolError("Head30 audit-entry recovery failure evidence differs")
    if scope.get("sealed_effect") != expected_sealed(protocol):
        raise ProtocolError("Head30 audit-entry recovery sealed effect differs")
    implementation = scope.get("implementation", {})
    commit = implementation.get("git_commit")
    if not isinstance(commit, str) or len(commit) != 40 or implementation.get("origin_main_commit") != commit:
        raise ProtocolError("Head30 audit-entry recovery implementation commit differs")
    for key in ("contract_sha256", "entrypoint_sha256", "release_builder_sha256", "dockerfile_sha256", "r3_contract_sha256", "r3_entrypoint_sha256"):
        if not _sha(implementation.get(key)):
            raise ProtocolError("Head30 audit-entry recovery implementation identity is invalid")
    image = scope.get("image", {})
    if (
        image.get("reference") != IMAGE
        or image.get("base_reference") != protocol.document["r3_authority"]["image_reference"]
        or image.get("base_image_id") != protocol.document["r3_authority"]["image_id"]
        or image.get("git_commit") != commit
        or not str(image.get("image_id", "")).startswith("sha256:")
        or image.get("platform") not in {"linux/arm64", "linux/amd64"}
    ):
        raise ProtocolError("Head30 audit-entry recovery image identity differs")
    if scope.get("authority") != expected_authority():
        raise ProtocolError("Head30 audit-entry recovery authority differs")
    if scope.get("execution") != {
        "approval_action": ACTION, "runner_invocation_count": 0,
        "recovery_auditor_invocation_count": 1, "additional_portfolio_attempt_count": 0,
        "family_portfolio_attempts_consumed": 2, "same_recovery_retry_authorized": False,
    }:
        raise ProtocolError("Head30 audit-entry recovery execution count differs")
    expected_container = {
        "compose_path": COMPOSE_PATH.relative_to(PROJECT_ROOT).as_posix(),
        "compose_sha256": sha256_file(compose_path), "network_mode": "none",
        "read_only_root": True, "run_as_non_root": True, "cap_drop_all": True,
        "no_new_privileges": True, "env_file_mounted": False,
        "docker_socket_mounted": False, "full_project_root_mounted": False,
        "qlib_mounted": False, "production_ledger_mounted": False,
        "service": "m6-production-head30-audit-entrypoint-recovery",
        "command": COMMAND, "mounts": MOUNTS, "cpus": 2, "memory": "4g", "pids_limit": 128,
        "embedded_original_protocol_path": str(EMBEDDED_ORIGINAL_PROTOCOL),
    }
    if scope.get("container") != expected_container:
        raise ProtocolError("Head30 audit-entry recovery container boundary differs")
    fixture = scope.get("daemon_fixture", {})
    if fixture.get("status") != "PASS" or fixture.get("loaded_path") != str(EMBEDDED_ORIGINAL_PROTOCOL):
        raise ProtocolError("Head30 audit-entry recovery daemon fixture differs")
    if fixture.get("protocol_sha256") != protocol.document["root_cause_and_only_change"]["embedded_protocol_sha256"]:
        raise ProtocolError("Head30 audit-entry recovery daemon path identity differs")


@dataclass(frozen=True)
class EntryRecoveryScope:
    path: Path
    scope: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path, protocol: EntryRecoveryProtocol, *, compose_path: Path = COMPOSE_PATH) -> "EntryRecoveryScope":
        document = mapping(path.resolve())
        if set(document) != {"schema_version", "recovery_scope_sha256", "scope"}:
            raise ProtocolError("Head30 audit-entry recovery scope fields differ")
        if document.get("schema_version") != "m6-production-head30-audit-entrypoint-recovery-scope-v1":
            raise ProtocolError("Head30 audit-entry recovery scope schema differs")
        scope = document.get("scope")
        if not isinstance(scope, dict) or document.get("recovery_scope_sha256") != canonical_sha256(scope):
            raise ProtocolError("Head30 audit-entry recovery scope self hash differs")
        validate_scope(scope, protocol, compose_path.resolve())
        return cls(path.resolve(), scope, document["recovery_scope_sha256"])


@dataclass(frozen=True)
class EntryRecoveryApproval:
    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path, release: EntryRecoveryScope) -> "EntryRecoveryApproval":
        document = mapping(path.resolve())
        expected = {
            "schema_version": "m6-production-head30-audit-entrypoint-recovery-approval-v1",
            "recovery_scope_sha256": release.sha256, "action": ACTION,
            "sealed_effect_read_authorized": True, "independent_audit_write_authorized": True,
            "qlib_mount_authorized": False, "runner_invocation_authorized": False,
            "model_fit_prediction_backtest_authorized": False,
            "experiment_ledger_write_authorized": False, "external_network_authorized": False,
            "env_or_secret_read_authorized": False, "production_authorization": "none",
        }
        if set(document) != set(expected) | {"approved_at", "consumed"}:
            raise ProtocolError("Head30 audit-entry recovery approval fields differ")
        if any(document.get(key) != value for key, value in expected.items()):
            raise ProtocolError("Head30 audit-entry recovery approval authority differs")
        if not document.get("approved_at") or document.get("consumed") is not False:
            raise ProtocolError("Head30 audit-entry recovery approval state differs")
        return cls(path.resolve(), document, sha256_file(path.resolve()))


__all__ = [
    "ACTION", "COMMAND", "COMPOSE_PATH", "EMBEDDED_ORIGINAL_PROTOCOL", "IMAGE", "MOUNTS",
    "PROTOCOL_PATH", "SCOPE_KIND", "SCOPE_PATH", "EntryRecoveryApproval",
    "EntryRecoveryProtocol", "EntryRecoveryScope", "expected_authority", "expected_sealed",
    "mapping", "validate_scope",
]

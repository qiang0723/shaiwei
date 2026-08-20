"""Frozen contract for the Head30 audit-lineage entry recovery."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.model_attribution.contract import canonical_sha256, sha256_file
from shaiwei.research.production_conversion.audit_entrypoint_recovery_contract import (
    expected_authority,
    mapping,
)
from shaiwei.research.production_conversion.contract import ProtocolError


PROTOCOL_PATH = PROJECT_ROOT / "config/m6_csi800_production_head30_audit_lineage_entry_recovery_v1.yaml"
SCOPE_PATH = PROJECT_ROOT / "config/m6_csi800_production_head30_audit_lineage_entry_recovery_scope_v1.json"
COMPOSE_PATH = PROJECT_ROOT / "compose.m6-production-head30-audit-lineage-recovery.yaml"
PREFLIGHT_EVIDENCE_PATH = (
    PROJECT_ROOT
    / "data/research/m6_csi800_production_head30_v1/r5-daemon-preflight/preflight.json"
)
ACTION = "M6_PRODUCTION_HEAD30_AUDIT_LINEAGE_ENTRY_RECOVERY_ONCE"
SCOPE_KIND = "PRODUCTION_HEAD30_AUDIT_LINEAGE_ENTRY_RECOVERY_READY_NOT_EXECUTION_APPROVAL"
IMAGE = "shaiwei:m6-production-head30-audit-lineage-recovery-v1"
R3_PROTOCOL_TARGET = "/inputs/r3-protocol.yaml"
ORIGINAL_PROTOCOL_TARGET = "/workspace/config/m6_csi800_production_head30_price_recovery_v1.yaml"

PREFLIGHT_COMMAND = [
    "python", "/opt/shaiwei/m6-head30-audit-lineage-recovery/entrypoint.py",
    "--preflight", "--recovery-protocol", "/inputs/recovery-protocol.yaml",
    "--r4-release", "/inputs/r4-release.json",
    "--r3-protocol", R3_PROTOCOL_TARGET,
    "--r3-release", "/inputs/r3-release.json",
    "--r4-failure-evidence", "/inputs/r4-execution-failure.json",
    "--original-release", "/inputs/original-release.json",
    "--original-approval", "/inputs/original-approval.json",
    "--preflight-output", "/fixture/preflight.json",
]

COMMAND = [
    "python", "/opt/shaiwei/m6-head30-audit-lineage-recovery/entrypoint.py",
    "--recovery-protocol", "/inputs/recovery-protocol.yaml",
    "--recovery-release", "/inputs/recovery-release.json",
    "--recovery-approval", "/inputs/recovery-approval.json",
    "--recovery-compose", "/inputs/recovery-compose.yaml",
    "--r4-release", "/inputs/r4-release.json",
    "--r3-protocol", R3_PROTOCOL_TARGET,
    "--r3-release", "/inputs/r3-release.json",
    "--r4-failure-evidence", "/inputs/r4-execution-failure.json",
    "--original-release", "/inputs/original-release.json",
    "--original-approval", "/inputs/original-approval.json",
    "--effect-root", "/outputs", "--audit-root", "/audit",
]

LINEAGE_MOUNTS = [
    {"source": "config/m6_csi800_production_head30_audit_lineage_entry_recovery_v1.yaml", "target": "/inputs/recovery-protocol.yaml", "mode": "ro"},
    {"source": "config/m6_csi800_production_head30_audit_entrypoint_recovery_scope_v1.json", "target": "/inputs/r4-release.json", "mode": "ro"},
    {"source": "config/m6_csi800_production_head30_audit_identity_recovery_v1.yaml", "target": R3_PROTOCOL_TARGET, "mode": "ro"},
    {"source": "config/m6_csi800_production_head30_audit_identity_recovery_scope_v1.json", "target": "/inputs/r3-release.json", "mode": "ro"},
    {"source": "config/m6_csi800_production_head30_audit_entrypoint_recovery_execution_failure_v1.json", "target": "/inputs/r4-execution-failure.json", "mode": "ro"},
    {"source": "config/m6_csi800_production_head30_price_recovery_scope_v1.json", "target": "/inputs/original-release.json", "mode": "ro"},
    {"source": "data/control/m6_csi800_production_head30_v1/approval-r2.json", "target": "/inputs/original-approval.json", "mode": "ro"},
]

MOUNTS = [
    LINEAGE_MOUNTS[0],
    {"source": "config/m6_csi800_production_head30_audit_lineage_entry_recovery_scope_v1.json", "target": "/inputs/recovery-release.json", "mode": "ro"},
    {"source": "data/control/m6_csi800_production_head30_v1/audit-lineage-entry-recovery-approval.json", "target": "/inputs/recovery-approval.json", "mode": "ro"},
    {"source": "compose.m6-production-head30-audit-lineage-recovery.yaml", "target": "/inputs/recovery-compose.yaml", "mode": "ro"},
    *LINEAGE_MOUNTS[1:],
    {"source": "data/research/m6_csi800_production_head30_v1/effect-r2", "target": "/outputs", "mode": "ro"},
    {"source": "data/research/m6_csi800_production_head30_v1/effect-r2-audit-lineage-entry-recovery", "target": "/audit", "mode": "rw"},
]


def _sha(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _validate_protocol(document: dict[str, Any]) -> None:
    if document.get("schema_version") != "m6-production-head30-audit-lineage-entry-recovery-protocol-v1":
        raise ProtocolError("Head30 audit-lineage protocol schema differs")
    if document.get("recovery_id") != "m6-csi800-production-head30-audit-lineage-entry-recovery-v1":
        raise ProtocolError("Head30 audit-lineage protocol identity differs")
    if document.get("status") != "FROZEN_AFTER_R4_LINEAGE_FILE_FAILURE_BEFORE_R5_IMPLEMENTATION":
        raise ProtocolError("Head30 audit-lineage protocol stage differs")
    objective = document.get("objective", {})
    if objective != {
        "recover_exactly_one_independent_audit_of_the_existing_r2_effect_tree": True,
        "change_only_r3_protocol_delivery_into_the_container": True,
        "research_question_or_result_change": False, "audit_semantics_change": False,
        "runner_or_effect_recomputation": False, "additional_portfolio_attempt_count": 0,
    }:
        raise ProtocolError("Head30 audit-lineage objective differs")
    r4 = document.get("r4_authority", {})
    failure = document.get("r4_execution_failure", {})
    for value in (
        r4.get("protocol_sha256"), r4.get("release_scope_sha256"),
        r4.get("release_document_sha256"), r4.get("approval_sha256"),
        r4.get("contract_sha256"), r4.get("entrypoint_sha256"),
        failure.get("evidence_sha256"),
    ):
        if not _sha(value):
            raise ProtocolError("Head30 audit-lineage predecessor identity is invalid")
    if (
        failure.get("auditor_invocation_count") != 1
        or failure.get("effect_semantics_read") is not False
        or failure.get("audit_output_file_count") != 0
        or failure.get("runner_invocation_count") != 0
        or failure.get("additional_portfolio_attempt_count") != 0
        or failure.get("same_r4_scope_retry_authorized") is not False
    ):
        raise ProtocolError("Head30 audit-lineage predecessor failure differs")
    change = document.get("root_cause_and_only_change", {})
    if (
        change.get("r3_protocol_container_path") != R3_PROTOCOL_TARGET
        or change.get("r3_protocol_read_only_mount_is_the_only_runtime_input_change") is not True
        or change.get("r3_protocol_loader_accepts_explicit_path_without_allowlist_change") is not True
        or change.get("original_r2_protocol_path_remains") != ORIGINAL_PROTOCOL_TARGET
        or not _sha(change.get("r3_protocol_sha256"))
        or not _sha(change.get("original_r2_protocol_sha256"))
    ):
        raise ProtocolError("Head30 audit-lineage path change differs")
    sealed = document.get("sealed_r2_effect", {})
    for key in (
        "tree_sha256", "authorization_sha256", "treatment_effect_started_sha256",
        "first_pass_bundle_sha256", "replay_bundle_sha256", "report_sha256",
        "primary_result_sha256",
    ):
        if not _sha(sealed.get(key)):
            raise ProtocolError("Head30 audit-lineage sealed identity is invalid")
    if (
        sealed.get("file_count") != 5 or int(sealed.get("total_bytes", 0)) <= 0
        or sealed.get("first_pass_bundle_sha256") != sealed.get("replay_bundle_sha256")
        or sealed.get("family_portfolio_attempts_consumed") != 2
    ):
        raise ProtocolError("Head30 audit-lineage sealed state differs")
    preflight = document.get("daemon_preflight_requirements", {})
    if (
        preflight.get("final_image_and_compose_service_required") is not True
        or preflight.get("same_preflight_function_as_real_entrypoint_required") is not True
        or preflight.get("effect_mount_forbidden") is not True
        or preflight.get("effect_semantics_read") is not False
        or preflight.get("audit_invoked") is not False
        or preflight.get("network_mode") != "none"
    ):
        raise ProtocolError("Head30 audit-lineage preflight boundary differs")
    requirements = document.get("release_requirements", {})
    exact = {
        "scope_kind": SCOPE_KIND, "approval_action": ACTION, "network_mode": "none",
        "qlib_mount": False, "effect_mount": "ro", "recovery_audit_mount": "rw",
        "full_project_root_mount": False, "env_or_secret_mount": False,
        "docker_socket_mount": False, "production_ledger_mount": False,
        "run_as_non_root": True, "read_only_root": True, "cap_drop_all": True,
        "no_new_privileges": True, "cpus": 2, "memory": "4g", "pids_limit": 128,
    }
    if any(requirements.get(key) != value for key, value in exact.items()):
        raise ProtocolError("Head30 audit-lineage runtime boundary differs")
    if document.get("production_authorization") != "none":
        raise ProtocolError("Head30 audit-lineage cannot authorize production")


@dataclass(frozen=True)
class LineageProtocol:
    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path = PROTOCOL_PATH) -> "LineageProtocol":
        resolved = path.resolve()
        document = mapping(resolved, yaml_document=True)
        _validate_protocol(document)
        return cls(resolved, document, sha256_file(resolved))


def expected_sealed(protocol: LineageProtocol) -> dict[str, Any]:
    return dict(protocol.document["sealed_r2_effect"])


def validate_scope(scope: dict[str, Any], protocol: LineageProtocol, compose_path: Path) -> None:
    if scope.get("scope_kind") != SCOPE_KIND or scope.get("recovery_id") != protocol.document["recovery_id"]:
        raise ProtocolError("Head30 audit-lineage scope identity differs")
    if scope.get("protocol_sha256") != protocol.sha256:
        raise ProtocolError("Head30 audit-lineage protocol hash differs")
    if scope.get("r4_authority") != protocol.document["r4_authority"]:
        raise ProtocolError("Head30 audit-lineage R4 authority differs")
    if scope.get("r4_execution_failure") != protocol.document["r4_execution_failure"]:
        raise ProtocolError("Head30 audit-lineage failure evidence differs")
    if scope.get("sealed_effect") != expected_sealed(protocol):
        raise ProtocolError("Head30 audit-lineage sealed effect differs")
    implementation = scope.get("implementation", {})
    commit = implementation.get("git_commit")
    if not isinstance(commit, str) or len(commit) != 40 or implementation.get("origin_main_commit") != commit:
        raise ProtocolError("Head30 audit-lineage implementation commit differs")
    for key in (
        "contract_sha256", "entrypoint_sha256", "release_builder_sha256",
        "r4_contract_sha256", "r4_entrypoint_sha256", "r3_contract_sha256",
        "r3_entrypoint_sha256", "dockerfile_sha256",
    ):
        if not _sha(implementation.get(key)):
            raise ProtocolError("Head30 audit-lineage implementation identity is invalid")
    image = scope.get("image", {})
    if (
        image.get("reference") != IMAGE
        or image.get("base_reference") != protocol.document["r4_authority"]["image_reference"]
        or image.get("base_image_id") != protocol.document["r4_authority"]["image_id"]
        or image.get("git_commit") != commit
        or not str(image.get("image_id", "")).startswith("sha256:")
        or image.get("platform") not in {"linux/arm64", "linux/amd64"}
    ):
        raise ProtocolError("Head30 audit-lineage image identity differs")
    if scope.get("authority") != expected_authority():
        raise ProtocolError("Head30 audit-lineage authority differs")
    if scope.get("execution") != {
        "approval_action": ACTION, "runner_invocation_count": 0,
        "recovery_auditor_invocation_count": 1, "additional_portfolio_attempt_count": 0,
        "family_portfolio_attempts_consumed": 2, "same_recovery_retry_authorized": False,
    }:
        raise ProtocolError("Head30 audit-lineage execution count differs")
    expected_container = {
        "compose_path": COMPOSE_PATH.relative_to(PROJECT_ROOT).as_posix(),
        "compose_sha256": sha256_file(compose_path), "network_mode": "none",
        "read_only_root": True, "run_as_non_root": True, "cap_drop_all": True,
        "no_new_privileges": True, "env_file_mounted": False,
        "docker_socket_mounted": False, "full_project_root_mounted": False,
        "qlib_mounted": False, "production_ledger_mounted": False,
        "service": "m6-production-head30-audit-lineage-recovery",
        "command": COMMAND, "mounts": MOUNTS, "cpus": 2, "memory": "4g", "pids_limit": 128,
    }
    if scope.get("container") != expected_container:
        raise ProtocolError("Head30 audit-lineage container boundary differs")
    fixture = scope.get("daemon_preflight", {})
    if (
        fixture.get("status") != "PASS"
        or fixture.get("r3_protocol_path") != R3_PROTOCOL_TARGET
        or fixture.get("effect_semantics_read") is not False
        or fixture.get("audit_invoked") is not False
        or fixture.get("final_image_id") != image.get("image_id")
        or fixture.get("image_git_commit") != commit
        or not _sha(fixture.get("evidence_sha256"))
    ):
        raise ProtocolError("Head30 audit-lineage daemon preflight differs")


@dataclass(frozen=True)
class LineageScope:
    path: Path
    scope: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path, protocol: LineageProtocol, *, compose_path: Path = COMPOSE_PATH) -> "LineageScope":
        document = mapping(path.resolve())
        if set(document) != {"schema_version", "recovery_scope_sha256", "scope"}:
            raise ProtocolError("Head30 audit-lineage scope fields differ")
        if document.get("schema_version") != "m6-production-head30-audit-lineage-entry-recovery-scope-v1":
            raise ProtocolError("Head30 audit-lineage scope schema differs")
        scope = document.get("scope")
        if not isinstance(scope, dict) or document.get("recovery_scope_sha256") != canonical_sha256(scope):
            raise ProtocolError("Head30 audit-lineage scope self hash differs")
        validate_scope(scope, protocol, compose_path.resolve())
        return cls(path.resolve(), scope, document["recovery_scope_sha256"])


@dataclass(frozen=True)
class LineageApproval:
    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path, release: LineageScope) -> "LineageApproval":
        document = mapping(path.resolve())
        expected = {
            "schema_version": "m6-production-head30-audit-lineage-entry-recovery-approval-v1",
            "recovery_scope_sha256": release.sha256, "action": ACTION,
            "sealed_effect_read_authorized": True, "independent_audit_write_authorized": True,
            "qlib_mount_authorized": False, "runner_invocation_authorized": False,
            "model_fit_prediction_backtest_authorized": False,
            "experiment_ledger_write_authorized": False, "external_network_authorized": False,
            "env_or_secret_read_authorized": False, "production_authorization": "none",
        }
        if set(document) != set(expected) | {"approved_at", "consumed"}:
            raise ProtocolError("Head30 audit-lineage approval fields differ")
        if any(document.get(key) != value for key, value in expected.items()):
            raise ProtocolError("Head30 audit-lineage approval authority differs")
        if not document.get("approved_at") or document.get("consumed") is not False:
            raise ProtocolError("Head30 audit-lineage approval state differs")
        return cls(path.resolve(), document, sha256_file(path.resolve()))


__all__ = [
    "ACTION", "COMMAND", "COMPOSE_PATH", "IMAGE", "LINEAGE_MOUNTS", "MOUNTS",
    "ORIGINAL_PROTOCOL_TARGET", "PREFLIGHT_COMMAND", "PREFLIGHT_EVIDENCE_PATH",
    "PROTOCOL_PATH", "R3_PROTOCOL_TARGET", "SCOPE_KIND", "SCOPE_PATH",
    "LineageApproval", "LineageProtocol", "LineageScope", "expected_authority",
    "expected_sealed", "mapping", "validate_scope",
]

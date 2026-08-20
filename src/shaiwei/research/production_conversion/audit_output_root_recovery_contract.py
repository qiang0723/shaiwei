"""Frozen contract for the Head30 audit output-root recovery."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.model_attribution.contract import canonical_sha256, sha256_file
from shaiwei.research.production_conversion.contract import ProtocolError

if __package__:
    from .audit_hash_authority_contract import expected_authority, mapping
else:
    from audit_hash_authority_contract import (  # type: ignore[no-redef]
        expected_authority,
        mapping,
    )


PROTOCOL_PATH = PROJECT_ROOT / "config/m6_csi800_production_head30_audit_output_root_recovery_v1.yaml"
SCOPE_PATH = PROJECT_ROOT / "config/m6_csi800_production_head30_audit_output_root_recovery_scope_v1.json"
COMPOSE_PATH = PROJECT_ROOT / "compose.m6-production-head30-audit-output-root-recovery.yaml"
PREFLIGHT_EVIDENCE_PATH = (
    PROJECT_ROOT / "data/research/m6_csi800_production_head30_v1/r7-daemon-preflight/preflight.json"
)
AUDIT_HOST_ROOT = (
    PROJECT_ROOT
    / "data/research/m6_csi800_production_head30_v1/effect-r2-audit-output-root-recovery"
)
ACTION = "M6_PRODUCTION_HEAD30_AUDIT_OUTPUT_ROOT_RECOVERY_ONCE"
SCOPE_KIND = "PRODUCTION_HEAD30_AUDIT_OUTPUT_ROOT_RECOVERY_READY_NOT_EXECUTION_APPROVAL"
IMAGE = "shaiwei:m6-production-head30-audit-output-root-recovery-v1"
SENTINEL_PAYLOAD = b"shaiwei-m6-r7-output-root-fixture-v1\n"
SENTINEL_SHA256 = "8577c02d1043a054e368d46b937541be12ba69bba43e0678e9854d7c0f2f15e8"

LINEAGE_ARGS = [
    "--r6-protocol", "/inputs/r6-protocol.yaml",
    "--r6-release", "/inputs/r6-release.json",
    "--r6-approval", "/inputs/r6-approval.json",
    "--r6-compose", "/inputs/r6-compose.yaml",
    "--r6-failure-evidence", "/inputs/r6-execution-failure.json",
    "--r5-protocol", "/inputs/r5-protocol.yaml",
    "--r5-release", "/inputs/r5-release.json",
    "--r5-approval", "/inputs/r5-approval.json",
    "--r5-failure-evidence", "/inputs/r5-execution-failure.json",
    "--r4-release", "/inputs/r4-release.json",
    "--r3-protocol", "/inputs/r3-protocol.yaml",
    "--r3-release", "/inputs/r3-release.json",
    "--r4-failure-evidence", "/inputs/r4-execution-failure.json",
    "--original-release", "/inputs/original-release.json",
    "--original-approval", "/inputs/original-approval.json",
]
PREFLIGHT_COMMAND = [
    "python", "/opt/shaiwei/m6-head30-audit-output-root-recovery/entrypoint.py",
    "--preflight", "--recovery-protocol", "/inputs/recovery-protocol.yaml",
    *LINEAGE_ARGS, "--preflight-output", "/fixture/preflight.json",
    "--fixture-output-root", "/fixture-output",
]
COMMAND = [
    "python", "/opt/shaiwei/m6-head30-audit-output-root-recovery/entrypoint.py",
    "--recovery-protocol", "/inputs/recovery-protocol.yaml",
    "--recovery-release", "/inputs/recovery-release.json",
    "--recovery-approval", "/inputs/recovery-approval.json",
    "--recovery-compose", "/inputs/recovery-compose.yaml",
    *LINEAGE_ARGS, "--effect-root", "/outputs", "--audit-root", "/audit",
]

LINEAGE_MOUNTS = [
    {"source": "config/m6_csi800_production_head30_audit_output_root_recovery_v1.yaml", "target": "/inputs/recovery-protocol.yaml", "mode": "ro"},
    {"source": "config/m6_csi800_production_head30_audit_hash_authority_recovery_v1.yaml", "target": "/inputs/r6-protocol.yaml", "mode": "ro"},
    {"source": "config/m6_csi800_production_head30_audit_hash_authority_recovery_scope_v1.json", "target": "/inputs/r6-release.json", "mode": "ro"},
    {"source": "data/control/m6_csi800_production_head30_v1/audit-hash-authority-recovery-approval.json", "target": "/inputs/r6-approval.json", "mode": "ro"},
    {"source": "compose.m6-production-head30-audit-hash-authority-recovery.yaml", "target": "/inputs/r6-compose.yaml", "mode": "ro"},
    {"source": "config/m6_csi800_production_head30_audit_hash_authority_recovery_execution_failure_v1.json", "target": "/inputs/r6-execution-failure.json", "mode": "ro"},
    {"source": "config/m6_csi800_production_head30_audit_lineage_entry_recovery_v1.yaml", "target": "/inputs/r5-protocol.yaml", "mode": "ro"},
    {"source": "config/m6_csi800_production_head30_audit_lineage_entry_recovery_scope_v1.json", "target": "/inputs/r5-release.json", "mode": "ro"},
    {"source": "data/control/m6_csi800_production_head30_v1/audit-lineage-entry-recovery-approval.json", "target": "/inputs/r5-approval.json", "mode": "ro"},
    {"source": "config/m6_csi800_production_head30_audit_lineage_entry_recovery_execution_failure_v1.json", "target": "/inputs/r5-execution-failure.json", "mode": "ro"},
    {"source": "config/m6_csi800_production_head30_audit_entrypoint_recovery_scope_v1.json", "target": "/inputs/r4-release.json", "mode": "ro"},
    {"source": "config/m6_csi800_production_head30_audit_identity_recovery_v1.yaml", "target": "/inputs/r3-protocol.yaml", "mode": "ro"},
    {"source": "config/m6_csi800_production_head30_audit_identity_recovery_scope_v1.json", "target": "/inputs/r3-release.json", "mode": "ro"},
    {"source": "config/m6_csi800_production_head30_audit_entrypoint_recovery_execution_failure_v1.json", "target": "/inputs/r4-execution-failure.json", "mode": "ro"},
    {"source": "config/m6_csi800_production_head30_price_recovery_scope_v1.json", "target": "/inputs/original-release.json", "mode": "ro"},
    {"source": "data/control/m6_csi800_production_head30_v1/approval-r2.json", "target": "/inputs/original-approval.json", "mode": "ro"},
]
MOUNTS = [
    LINEAGE_MOUNTS[0],
    {"source": "config/m6_csi800_production_head30_audit_output_root_recovery_scope_v1.json", "target": "/inputs/recovery-release.json", "mode": "ro"},
    {"source": "data/control/m6_csi800_production_head30_v1/audit-output-root-recovery-approval.json", "target": "/inputs/recovery-approval.json", "mode": "ro"},
    {"source": "compose.m6-production-head30-audit-output-root-recovery.yaml", "target": "/inputs/recovery-compose.yaml", "mode": "ro"},
    *LINEAGE_MOUNTS[1:],
    {"source": "data/research/m6_csi800_production_head30_v1/effect-r2", "target": "/outputs", "mode": "ro"},
    {"source": "data/research/m6_csi800_production_head30_v1/effect-r2-audit-output-root-recovery", "target": "/audit", "mode": "rw"},
]


def _sha(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _validate_protocol(document: dict[str, Any]) -> None:
    if document.get("schema_version") != "m6-production-head30-audit-output-root-recovery-protocol-v1":
        raise ProtocolError("Head30 output-root protocol schema differs")
    if document.get("recovery_id") != "m6-csi800-production-head30-audit-output-root-recovery-v1":
        raise ProtocolError("Head30 output-root protocol identity differs")
    if document.get("status") != "FROZEN_AFTER_R6_OUTPUT_ROOT_MOUNT_FAILURE_BEFORE_R7_IMPLEMENTATION":
        raise ProtocolError("Head30 output-root protocol stage differs")
    objective = document.get("objective", {})
    if objective != {
        "recover_exactly_one_independent_audit_of_the_existing_r2_effect_tree": True,
        "prepare_and_verify_the_new_writable_audit_root_before_scope_release": True,
        "audit_semantics_change": False, "research_question_or_result_change": False,
        "primary_identity_or_numeric_tolerance_change": False,
        "runner_or_effect_recomputation": False, "additional_portfolio_attempt_count": 0,
    }:
        raise ProtocolError("Head30 output-root objective differs")
    r6, failure = document.get("r6_authority", {}), document.get("r6_execution_failure", {})
    for value in (
        r6.get("protocol_sha256"), r6.get("release_scope_sha256"),
        r6.get("release_document_sha256"), r6.get("approval_sha256"),
        r6.get("contract_sha256"), r6.get("entrypoint_sha256"), failure.get("evidence_sha256"),
    ):
        if not _sha(value):
            raise ProtocolError("Head30 output-root predecessor identity is invalid")
    expected_failure = {
        "container_created": False, "r6_auditor_invocation_count": 0,
        "audit_function_entered": False, "effect_semantics_read": False,
        "independent_reconstruction_completed": False, "audit_output_file_count": 0,
        "audit_root_exists_after_failure": False, "runner_invocation_count": 0,
        "additional_portfolio_attempt_count": 0, "same_r6_scope_retry_authorized": False,
        "failure_cause": "absent_host_audit_root_with_create_host_path_false",
    }
    if any(failure.get(key) != value for key, value in expected_failure.items()):
        raise ProtocolError("Head30 output-root predecessor failure differs")
    correction = document.get("only_output_root_correction", {})
    if correction != {
        "host_audit_root": "data/research/m6_csi800_production_head30_v1/effect-r2-audit-output-root-recovery",
        "container_audit_root": "/audit", "explicitly_create_host_root_before_daemon_fixture": True,
        "create_host_path_must_remain_false": True,
        "fixture_and_real_service_must_bind_the_exact_same_host_root": True,
        "fixture_write_read_hash_delete_roundtrip_required": True,
        "fixture_root_empty_before_and_after_required": True, "fixture_effect_mount_forbidden": True,
        "real_effect_mount_read_only": True, "real_audit_mount_read_write": True,
    }:
        raise ProtocolError("Head30 output-root correction differs")
    inherited = document.get("inherited_hash_authority", {})
    if (
        inherited.get("historical_independent_sha_equality_required") is not False
        or inherited.get("current_independent_sha_must_be_recorded") is not True
        or inherited.get("primary_result_sha_must_match_sealed_identity") is not True
        or inherited.get("first_pass_and_replay_physical_identity_required") is not True
        or inherited.get("independent_reconstruction_relative_tolerance") != 1e-12
        or inherited.get("independent_reconstruction_absolute_tolerance") != 1e-12
        or inherited.get("primary_and_independent_decisions_must_match_exactly") is not True
    ):
        raise ProtocolError("Head30 output-root inherited authority differs")
    sealed = document.get("sealed_r2_effect", {})
    for key in (
        "tree_sha256", "authorization_sha256", "treatment_effect_started_sha256",
        "first_pass_bundle_sha256", "replay_bundle_sha256", "report_sha256",
        "primary_result_sha256",
    ):
        if not _sha(sealed.get(key)):
            raise ProtocolError("Head30 output-root sealed identity is invalid")
    if sealed.get("file_count") != 5 or sealed.get("first_pass_bundle_sha256") != sealed.get("replay_bundle_sha256"):
        raise ProtocolError("Head30 output-root sealed state differs")
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
        raise ProtocolError("Head30 output-root runtime boundary differs")
    if document.get("production_authorization") != "none":
        raise ProtocolError("Head30 output-root cannot authorize production")


@dataclass(frozen=True)
class OutputRootProtocol:
    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path = PROTOCOL_PATH) -> "OutputRootProtocol":
        resolved = path.resolve()
        document = mapping(resolved, yaml_document=True)
        _validate_protocol(document)
        return cls(resolved, document, sha256_file(resolved))


def expected_sealed(protocol: OutputRootProtocol) -> dict[str, Any]:
    return dict(protocol.document["sealed_r2_effect"])


def validate_scope(scope: dict[str, Any], protocol: OutputRootProtocol, compose_path: Path) -> None:
    if scope.get("scope_kind") != SCOPE_KIND or scope.get("recovery_id") != protocol.document["recovery_id"]:
        raise ProtocolError("Head30 output-root scope identity differs")
    if scope.get("protocol_sha256") != protocol.sha256:
        raise ProtocolError("Head30 output-root protocol hash differs")
    if scope.get("r6_authority") != protocol.document["r6_authority"]:
        raise ProtocolError("Head30 output-root R6 authority differs")
    if scope.get("r6_execution_failure") != protocol.document["r6_execution_failure"]:
        raise ProtocolError("Head30 output-root failure evidence differs")
    if scope.get("sealed_effect") != expected_sealed(protocol):
        raise ProtocolError("Head30 output-root sealed effect differs")
    implementation = scope.get("implementation", {})
    commit = implementation.get("git_commit")
    if not isinstance(commit, str) or len(commit) != 40 or implementation.get("origin_main_commit") != commit:
        raise ProtocolError("Head30 output-root implementation commit differs")
    for key in ("contract_sha256", "entrypoint_sha256", "release_builder_sha256", "r6_contract_sha256", "r6_entrypoint_sha256", "dockerfile_sha256"):
        if not _sha(implementation.get(key)):
            raise ProtocolError("Head30 output-root implementation identity is invalid")
    image = scope.get("image", {})
    if (
        image.get("reference") != IMAGE
        or image.get("base_reference") != protocol.document["r6_authority"]["image_reference"]
        or image.get("base_image_id") != protocol.document["r6_authority"]["image_id"]
        or image.get("git_commit") != commit or not str(image.get("image_id", "")).startswith("sha256:")
        or image.get("platform") not in {"linux/arm64", "linux/amd64"}
    ):
        raise ProtocolError("Head30 output-root image identity differs")
    if scope.get("authority") != expected_authority():
        raise ProtocolError("Head30 output-root authority differs")
    if scope.get("execution") != {
        "approval_action": ACTION, "runner_invocation_count": 0,
        "recovery_auditor_invocation_count": 1, "additional_portfolio_attempt_count": 0,
        "family_portfolio_attempts_consumed": 2, "same_recovery_retry_authorized": False,
    }:
        raise ProtocolError("Head30 output-root execution count differs")
    expected_container = {
        "compose_path": COMPOSE_PATH.relative_to(PROJECT_ROOT).as_posix(),
        "compose_sha256": sha256_file(compose_path), "network_mode": "none",
        "read_only_root": True, "run_as_non_root": True, "cap_drop_all": True,
        "no_new_privileges": True, "env_file_mounted": False, "docker_socket_mounted": False,
        "full_project_root_mounted": False, "qlib_mounted": False,
        "production_ledger_mounted": False,
        "service": "m6-production-head30-audit-output-root-recovery",
        "command": COMMAND, "mounts": MOUNTS, "cpus": 2, "memory": "4g", "pids_limit": 128,
    }
    if scope.get("container") != expected_container:
        raise ProtocolError("Head30 output-root container boundary differs")
    fixture = scope.get("daemon_fixture", {})
    if (
        fixture.get("status") != "PASS" or fixture.get("output_root_roundtrip") != "PASS"
        or fixture.get("output_root_empty_before") is not True
        or fixture.get("output_root_empty_after") is not True
        or fixture.get("sentinel_payload_sha256") != SENTINEL_SHA256
        or fixture.get("host_audit_root") != AUDIT_HOST_ROOT.relative_to(PROJECT_ROOT).as_posix()
        or fixture.get("same_host_root_as_real_mount") is not True
        or fixture.get("effect_semantics_read") is not False or fixture.get("audit_invoked") is not False
        or fixture.get("final_image_id") != image.get("image_id")
        or fixture.get("image_git_commit") != commit or not _sha(fixture.get("evidence_sha256"))
    ):
        raise ProtocolError("Head30 output-root daemon fixture differs")


@dataclass(frozen=True)
class OutputRootScope:
    path: Path
    scope: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path, protocol: OutputRootProtocol, *, compose_path: Path = COMPOSE_PATH) -> "OutputRootScope":
        document = mapping(path.resolve())
        if set(document) != {"schema_version", "recovery_scope_sha256", "scope"}:
            raise ProtocolError("Head30 output-root scope fields differ")
        if document.get("schema_version") != "m6-production-head30-audit-output-root-recovery-scope-v1":
            raise ProtocolError("Head30 output-root scope schema differs")
        scope = document.get("scope")
        if not isinstance(scope, dict) or document.get("recovery_scope_sha256") != canonical_sha256(scope):
            raise ProtocolError("Head30 output-root scope self hash differs")
        validate_scope(scope, protocol, compose_path.resolve())
        return cls(path.resolve(), scope, document["recovery_scope_sha256"])


@dataclass(frozen=True)
class OutputRootApproval:
    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path, release: OutputRootScope) -> "OutputRootApproval":
        document = mapping(path.resolve())
        expected = {
            "schema_version": "m6-production-head30-audit-output-root-recovery-approval-v1",
            "recovery_scope_sha256": release.sha256, "action": ACTION,
            "sealed_effect_read_authorized": True, "independent_audit_write_authorized": True,
            "qlib_mount_authorized": False, "runner_invocation_authorized": False,
            "model_fit_prediction_backtest_authorized": False,
            "experiment_ledger_write_authorized": False, "external_network_authorized": False,
            "env_or_secret_read_authorized": False, "production_authorization": "none",
        }
        if set(document) != set(expected) | {"approved_at", "consumed"}:
            raise ProtocolError("Head30 output-root approval fields differ")
        if any(document.get(key) != value for key, value in expected.items()):
            raise ProtocolError("Head30 output-root approval authority differs")
        if not document.get("approved_at") or document.get("consumed") is not False:
            raise ProtocolError("Head30 output-root approval state differs")
        return cls(path.resolve(), document, sha256_file(path.resolve()))


__all__ = [
    "ACTION", "AUDIT_HOST_ROOT", "COMMAND", "COMPOSE_PATH", "IMAGE", "LINEAGE_MOUNTS",
    "MOUNTS", "OutputRootApproval", "OutputRootProtocol", "OutputRootScope",
    "PREFLIGHT_COMMAND", "PREFLIGHT_EVIDENCE_PATH", "PROTOCOL_PATH", "SCOPE_KIND",
    "SCOPE_PATH", "SENTINEL_PAYLOAD", "SENTINEL_SHA256", "expected_authority",
    "expected_sealed", "mapping", "validate_scope",
]

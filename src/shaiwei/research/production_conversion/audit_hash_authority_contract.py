"""Frozen contract for the Head30 independent-hash authority recovery."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.model_attribution.contract import canonical_sha256, sha256_file
if __package__:
    from .audit_entrypoint_recovery_contract import expected_authority, mapping
else:
    from audit_entrypoint_recovery_contract import (  # type: ignore[no-redef]
        expected_authority,
        mapping,
    )
from shaiwei.research.production_conversion.contract import ProtocolError


PROTOCOL_PATH = PROJECT_ROOT / "config/m6_csi800_production_head30_audit_hash_authority_recovery_v1.yaml"
SCOPE_PATH = PROJECT_ROOT / "config/m6_csi800_production_head30_audit_hash_authority_recovery_scope_v1.json"
COMPOSE_PATH = PROJECT_ROOT / "compose.m6-production-head30-audit-hash-authority-recovery.yaml"
PREFLIGHT_EVIDENCE_PATH = (
    PROJECT_ROOT
    / "data/research/m6_csi800_production_head30_v1/r6-daemon-preflight/preflight.json"
)
ACTION = "M6_PRODUCTION_HEAD30_AUDIT_HASH_AUTHORITY_RECOVERY_ONCE"
SCOPE_KIND = "PRODUCTION_HEAD30_AUDIT_HASH_AUTHORITY_RECOVERY_READY_NOT_EXECUTION_APPROVAL"
IMAGE = "shaiwei:m6-production-head30-audit-hash-authority-recovery-v1"

LINEAGE_ARGS = [
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
    "python", "/opt/shaiwei/m6-head30-audit-hash-authority-recovery/entrypoint.py",
    "--preflight", "--recovery-protocol", "/inputs/recovery-protocol.yaml",
    *LINEAGE_ARGS,
    "--preflight-output", "/fixture/preflight.json",
]

COMMAND = [
    "python", "/opt/shaiwei/m6-head30-audit-hash-authority-recovery/entrypoint.py",
    "--recovery-protocol", "/inputs/recovery-protocol.yaml",
    "--recovery-release", "/inputs/recovery-release.json",
    "--recovery-approval", "/inputs/recovery-approval.json",
    "--recovery-compose", "/inputs/recovery-compose.yaml",
    *LINEAGE_ARGS,
    "--effect-root", "/outputs", "--audit-root", "/audit",
]

LINEAGE_MOUNTS = [
    {"source": "config/m6_csi800_production_head30_audit_hash_authority_recovery_v1.yaml", "target": "/inputs/recovery-protocol.yaml", "mode": "ro"},
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
    {"source": "config/m6_csi800_production_head30_audit_hash_authority_recovery_scope_v1.json", "target": "/inputs/recovery-release.json", "mode": "ro"},
    {"source": "data/control/m6_csi800_production_head30_v1/audit-hash-authority-recovery-approval.json", "target": "/inputs/recovery-approval.json", "mode": "ro"},
    {"source": "compose.m6-production-head30-audit-hash-authority-recovery.yaml", "target": "/inputs/recovery-compose.yaml", "mode": "ro"},
    *LINEAGE_MOUNTS[1:],
    {"source": "data/research/m6_csi800_production_head30_v1/effect-r2", "target": "/outputs", "mode": "ro"},
    {"source": "data/research/m6_csi800_production_head30_v1/effect-r2-audit-hash-authority-recovery", "target": "/audit", "mode": "rw"},
]


def _sha(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _validate_protocol(document: dict[str, Any]) -> None:
    if document.get("schema_version") != "m6-production-head30-audit-hash-authority-recovery-protocol-v1":
        raise ProtocolError("Head30 hash-authority protocol schema differs")
    if document.get("recovery_id") != "m6-csi800-production-head30-audit-hash-authority-recovery-v1":
        raise ProtocolError("Head30 hash-authority protocol identity differs")
    if document.get("status") != "FROZEN_AFTER_R5_HISTORICAL_INDEPENDENT_HASH_FAILURE_BEFORE_R6_IMPLEMENTATION":
        raise ProtocolError("Head30 hash-authority protocol stage differs")
    objective = document.get("objective", {})
    if objective != {
        "recover_exactly_one_independent_audit_of_the_existing_r2_effect_tree": True,
        "remove_only_historical_independent_sha_equality_as_an_authority_gate": True,
        "record_current_independent_sha": True,
        "research_question_or_result_change": False,
        "primary_identity_or_numeric_tolerance_change": False,
        "runner_or_effect_recomputation": False,
        "additional_portfolio_attempt_count": 0,
    }:
        raise ProtocolError("Head30 hash-authority objective differs")
    r5 = document.get("r5_authority", {})
    failure = document.get("r5_execution_failure", {})
    for value in (
        r5.get("protocol_sha256"), r5.get("release_scope_sha256"),
        r5.get("release_document_sha256"), r5.get("approval_sha256"),
        r5.get("contract_sha256"), r5.get("entrypoint_sha256"),
        failure.get("evidence_sha256"),
    ):
        if not _sha(value):
            raise ProtocolError("Head30 hash-authority predecessor identity is invalid")
    if (
        failure.get("auditor_invocation_count") != 1
        or failure.get("effect_semantics_read") is not True
        or failure.get("independent_reconstruction_completed") is not True
        or failure.get("independent_tolerance_equivalence_passed") is not True
        or failure.get("decision_identity_passed") is not True
        or failure.get("all_other_audit_checks_passed") is not True
        or failure.get("audit_output_file_count") != 0
        or failure.get("same_r5_scope_retry_authorized") is not False
        or failure.get("failed_check") != "independent_result_lineage"
    ):
        raise ProtocolError("Head30 hash-authority predecessor failure differs")
    correction = document.get("only_authority_correction", {})
    if (
        not _sha(correction.get("historical_independent_result_sha256"))
        or correction.get("historical_independent_sha_equality_required") is not False
        or correction.get("current_independent_sha_must_be_recorded") is not True
        or correction.get("primary_result_sha_must_match_sealed_identity") is not True
        or correction.get("first_pass_and_replay_physical_identity_required") is not True
        or correction.get("independent_reconstruction_relative_tolerance") != 1e-12
        or correction.get("independent_reconstruction_absolute_tolerance") != 1e-12
        or correction.get("primary_and_independent_decisions_must_match_exactly") is not True
    ):
        raise ProtocolError("Head30 hash-authority correction differs")
    sealed = document.get("sealed_r2_effect", {})
    for key in (
        "tree_sha256", "authorization_sha256", "treatment_effect_started_sha256",
        "first_pass_bundle_sha256", "replay_bundle_sha256", "report_sha256",
        "primary_result_sha256",
    ):
        if not _sha(sealed.get(key)):
            raise ProtocolError("Head30 hash-authority sealed identity is invalid")
    if (
        sealed.get("file_count") != 5 or int(sealed.get("total_bytes", 0)) <= 0
        or sealed.get("first_pass_bundle_sha256") != sealed.get("replay_bundle_sha256")
        or sealed.get("family_portfolio_attempts_consumed") != 2
    ):
        raise ProtocolError("Head30 hash-authority sealed state differs")
    fixture = document.get("daemon_fixture_requirements", {})
    if (
        fixture.get("historical_independent_sha_mismatch_within_tolerance_must_pass") is not True
        or fixture.get("numeric_difference_above_tolerance_must_fail") is not True
        or fixture.get("decision_difference_must_fail") is not True
        or fixture.get("effect_mount_forbidden") is not True
        or fixture.get("effect_semantics_read") is not False
        or fixture.get("audit_invoked") is not False
        or fixture.get("network_mode") != "none"
    ):
        raise ProtocolError("Head30 hash-authority fixture boundary differs")
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
        raise ProtocolError("Head30 hash-authority runtime boundary differs")
    if document.get("production_authorization") != "none":
        raise ProtocolError("Head30 hash-authority cannot authorize production")


@dataclass(frozen=True)
class HashAuthorityProtocol:
    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path = PROTOCOL_PATH) -> "HashAuthorityProtocol":
        resolved = path.resolve()
        document = mapping(resolved, yaml_document=True)
        _validate_protocol(document)
        return cls(resolved, document, sha256_file(resolved))


def expected_sealed(protocol: HashAuthorityProtocol) -> dict[str, Any]:
    return dict(protocol.document["sealed_r2_effect"])


def validate_scope(scope: dict[str, Any], protocol: HashAuthorityProtocol, compose_path: Path) -> None:
    if scope.get("scope_kind") != SCOPE_KIND or scope.get("recovery_id") != protocol.document["recovery_id"]:
        raise ProtocolError("Head30 hash-authority scope identity differs")
    if scope.get("protocol_sha256") != protocol.sha256:
        raise ProtocolError("Head30 hash-authority protocol hash differs")
    if scope.get("r5_authority") != protocol.document["r5_authority"]:
        raise ProtocolError("Head30 hash-authority R5 authority differs")
    if scope.get("r5_execution_failure") != protocol.document["r5_execution_failure"]:
        raise ProtocolError("Head30 hash-authority failure evidence differs")
    if scope.get("sealed_effect") != expected_sealed(protocol):
        raise ProtocolError("Head30 hash-authority sealed effect differs")
    implementation = scope.get("implementation", {})
    commit = implementation.get("git_commit")
    if not isinstance(commit, str) or len(commit) != 40 or implementation.get("origin_main_commit") != commit:
        raise ProtocolError("Head30 hash-authority implementation commit differs")
    for key in (
        "contract_sha256", "entrypoint_sha256", "release_builder_sha256",
        "r5_contract_sha256", "r5_entrypoint_sha256", "r4_contract_sha256",
        "r4_entrypoint_sha256", "r3_contract_sha256", "r3_entrypoint_sha256",
        "dockerfile_sha256",
    ):
        if not _sha(implementation.get(key)):
            raise ProtocolError("Head30 hash-authority implementation identity is invalid")
    image = scope.get("image", {})
    if (
        image.get("reference") != IMAGE
        or image.get("base_reference") != protocol.document["r5_authority"]["image_reference"]
        or image.get("base_image_id") != protocol.document["r5_authority"]["image_id"]
        or image.get("git_commit") != commit
        or not str(image.get("image_id", "")).startswith("sha256:")
        or image.get("platform") not in {"linux/arm64", "linux/amd64"}
    ):
        raise ProtocolError("Head30 hash-authority image identity differs")
    if scope.get("authority") != expected_authority():
        raise ProtocolError("Head30 hash-authority authority differs")
    if scope.get("execution") != {
        "approval_action": ACTION, "runner_invocation_count": 0,
        "recovery_auditor_invocation_count": 1, "additional_portfolio_attempt_count": 0,
        "family_portfolio_attempts_consumed": 2, "same_recovery_retry_authorized": False,
    }:
        raise ProtocolError("Head30 hash-authority execution count differs")
    expected_container = {
        "compose_path": COMPOSE_PATH.relative_to(PROJECT_ROOT).as_posix(),
        "compose_sha256": sha256_file(compose_path), "network_mode": "none",
        "read_only_root": True, "run_as_non_root": True, "cap_drop_all": True,
        "no_new_privileges": True, "env_file_mounted": False,
        "docker_socket_mounted": False, "full_project_root_mounted": False,
        "qlib_mounted": False, "production_ledger_mounted": False,
        "service": "m6-production-head30-audit-hash-authority-recovery",
        "command": COMMAND, "mounts": MOUNTS, "cpus": 2, "memory": "4g", "pids_limit": 128,
    }
    if scope.get("container") != expected_container:
        raise ProtocolError("Head30 hash-authority container boundary differs")
    fixture = scope.get("daemon_fixture", {})
    if (
        fixture.get("status") != "PASS"
        or fixture.get("hash_mismatch_within_tolerance") != "PASS"
        or fixture.get("above_tolerance_fail_closed") != "PASS"
        or fixture.get("decision_drift_fail_closed") != "PASS"
        or fixture.get("effect_semantics_read") is not False
        or fixture.get("audit_invoked") is not False
        or fixture.get("final_image_id") != image.get("image_id")
        or fixture.get("image_git_commit") != commit
        or not _sha(fixture.get("evidence_sha256"))
    ):
        raise ProtocolError("Head30 hash-authority daemon fixture differs")


@dataclass(frozen=True)
class HashAuthorityScope:
    path: Path
    scope: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path, protocol: HashAuthorityProtocol, *, compose_path: Path = COMPOSE_PATH) -> "HashAuthorityScope":
        document = mapping(path.resolve())
        if set(document) != {"schema_version", "recovery_scope_sha256", "scope"}:
            raise ProtocolError("Head30 hash-authority scope fields differ")
        if document.get("schema_version") != "m6-production-head30-audit-hash-authority-recovery-scope-v1":
            raise ProtocolError("Head30 hash-authority scope schema differs")
        scope = document.get("scope")
        if not isinstance(scope, dict) or document.get("recovery_scope_sha256") != canonical_sha256(scope):
            raise ProtocolError("Head30 hash-authority scope self hash differs")
        validate_scope(scope, protocol, compose_path.resolve())
        return cls(path.resolve(), scope, document["recovery_scope_sha256"])


@dataclass(frozen=True)
class HashAuthorityApproval:
    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path, release: HashAuthorityScope) -> "HashAuthorityApproval":
        document = mapping(path.resolve())
        expected = {
            "schema_version": "m6-production-head30-audit-hash-authority-recovery-approval-v1",
            "recovery_scope_sha256": release.sha256, "action": ACTION,
            "sealed_effect_read_authorized": True, "independent_audit_write_authorized": True,
            "qlib_mount_authorized": False, "runner_invocation_authorized": False,
            "model_fit_prediction_backtest_authorized": False,
            "experiment_ledger_write_authorized": False, "external_network_authorized": False,
            "env_or_secret_read_authorized": False, "production_authorization": "none",
        }
        if set(document) != set(expected) | {"approved_at", "consumed"}:
            raise ProtocolError("Head30 hash-authority approval fields differ")
        if any(document.get(key) != value for key, value in expected.items()):
            raise ProtocolError("Head30 hash-authority approval authority differs")
        if not document.get("approved_at") or document.get("consumed") is not False:
            raise ProtocolError("Head30 hash-authority approval state differs")
        return cls(path.resolve(), document, sha256_file(path.resolve()))


__all__ = [
    "ACTION", "COMMAND", "COMPOSE_PATH", "HashAuthorityApproval",
    "HashAuthorityProtocol", "HashAuthorityScope", "IMAGE", "LINEAGE_MOUNTS", "MOUNTS",
    "PREFLIGHT_COMMAND", "PREFLIGHT_EVIDENCE_PATH", "PROTOCOL_PATH", "SCOPE_KIND",
    "SCOPE_PATH", "expected_authority", "expected_sealed", "mapping", "validate_scope",
]

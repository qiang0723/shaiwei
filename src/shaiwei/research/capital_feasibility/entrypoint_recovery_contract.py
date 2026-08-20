"""Versioned authority contract for the M6-5B-R1 CLI recovery."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

from shaiwei.config import PROJECT_ROOT
from shaiwei.provenance import code_snapshot_sha256, git_head
from shaiwei.research.model_attribution.contract import canonical_sha256, sha256_file
from shaiwei.research.production_conversion.contract import ProtocolError

from .release_contract import ReleaseProtocol, expected_authority, mapping


PROTOCOL_PATH = PROJECT_ROOT / "config/m6_csi800_production_head30_500k_entrypoint_recovery_v1.yaml"
SCOPE_PATH = PROJECT_ROOT / "config/m6_csi800_production_head30_500k_entrypoint_recovery_scope_v1.json"
IMAGE = "shaiwei:m6-head30-500k-entrypoint-recovery-v1"
ACTION = "M6_HEAD30_500K_FEASIBILITY_ENTRYPOINT_RECOVERY_ONCE_WITH_REPLAY_AND_INDEPENDENT_AUDIT"
SCOPE_SCHEMA = "m6-head30-500k-entrypoint-recovery-scope-v1"
SCOPE_KIND = "HEAD30_500K_ENTRYPOINT_RECOVERY_RELEASE_READY_NOT_EXECUTION_APPROVAL"
COMPOSE_PATH = PROJECT_ROOT / "compose.m6-head30-500k-entrypoint-recovery.yaml"


def _validate_recovery(document: dict[str, Any], base: ReleaseProtocol) -> None:
    if (
        document.get("schema_version") != "m6-head30-500k-entrypoint-recovery-protocol-v1"
        or document.get("protocol_id") != "m6-csi800-production-head30-500k-entrypoint-recovery-v1"
        or document.get("stage") != "RESULT_BLIND_ENTRYPOINT_RECOVERY_ONLY"
    ):
        raise ProtocolError("M6-5B-R1 recovery protocol identity differs")
    predecessors = document.get("predecessors", {})
    expected = {
        "base_release_protocol": base.sha256,
        "target_read_recovery_protocol": base.recovery_sha256,
    }
    for key, digest in expected.items():
        item = predecessors.get(key, {})
        if sha256_file(PROJECT_ROOT / item.get("path", "")) != digest or item.get("sha256") != digest:
            raise ProtocolError(f"M6-5B-R1 predecessor differs: {key}")
    failed_scope = predecessors.get("failed_release_scope", {})
    failed_scope_path = PROJECT_ROOT / failed_scope.get("path", "")
    if sha256_file(failed_scope_path) != failed_scope.get("file_sha256"):
        raise ProtocolError("M6-5B-R1 failed scope file differs")
    failed_scope_document = mapping(failed_scope_path)
    if failed_scope_document.get("release_scope_sha256") != failed_scope.get("release_scope_sha256"):
        raise ProtocolError("M6-5B-R1 failed scope identity differs")
    failure = predecessors.get("entrypoint_failure_evidence", {})
    failure_path = PROJECT_ROOT / failure.get("path", "")
    if sha256_file(failure_path) != failure.get("sha256"):
        raise ProtocolError("M6-5B-R1 failure evidence identity differs")
    failure_document = mapping(failure_path)
    if (
        failure_document.get("failed_release_scope_sha256")
        != predecessors.get("failed_release_scope", {}).get("release_scope_sha256")
        or failure_document.get("run_function_entered") is not False
        or failure_document.get("new_semantic_attempts_consumed") != 0
        or failure_document.get("same_scope_retry_authorized") is not False
    ):
        raise ProtocolError("M6-5B-R1 failure ruling differs")
    ruling = document.get("failure_ruling", {})
    if (
        ruling.get("failed_scope_permanently_closed") is not True
        or ruling.get("family_attempts_before_future_authorized_run") != 1
        or ruling.get("total_family_attempts_after_future_authorized_run") != 2
        or ruling.get("real_price_or_effect_read") is not False
    ):
        raise ProtocolError("M6-5B-R1 attempt ruling differs")
    change = document.get("recovery_change", {})
    if (
        change.get("only_changed_variable") != "runner_and_auditor_cli_argument_mapping"
        or change.get("direct_domain_functions_changed") is not False
        or change.get("strategy_formula_changed") is not False
        or change.get("decision_contract_changed") is not False
        or change.get("result_semantic_read_before_new_approval") is not False
    ):
        raise ProtocolError("M6-5B-R1 change boundary differs")
    release = document.get("release_and_approval", {})
    if (
        release.get("release_scope_kind") != SCOPE_KIND
        or release.get("approval_action") != ACTION
        or release.get("image") != IMAGE
    ):
        raise ProtocolError("M6-5B-R1 release boundary differs")


@dataclass(frozen=True)
class EntrypointRecoveryProtocol:
    path: Path
    document: dict[str, Any]
    sha256: str
    base: ReleaseProtocol

    @classmethod
    def load(cls, path: Path = PROTOCOL_PATH) -> "EntrypointRecoveryProtocol":
        base = ReleaseProtocol.load()
        document = mapping(path, yaml_document=True)
        _validate_recovery(document, base)
        return cls(path.resolve(), document, sha256_file(path), base)


def validate_scope(scope: dict[str, Any], protocol: EntrypointRecoveryProtocol) -> None:
    if (
        scope.get("scope_kind") != SCOPE_KIND
        or scope.get("entrypoint_recovery_protocol_sha256") != protocol.sha256
        or scope.get("base_protocol_sha256") != protocol.base.sha256
        or scope.get("target_read_recovery_sha256") != protocol.base.recovery_sha256
    ):
        raise ProtocolError("M6-5B-R1 scope identity differs")
    implementation, image = scope.get("implementation", {}), scope.get("image", {})
    commit, snapshot = implementation.get("git_commit"), implementation.get("code_snapshot_sha256")
    if not isinstance(commit, str) or len(commit) != 40 or implementation.get("origin_main_commit") != commit:
        raise ProtocolError("M6-5B-R1 implementation is not pushed")
    if (
        image.get("reference") != IMAGE
        or image.get("git_commit") != commit
        or image.get("code_snapshot_sha256") != snapshot
        or not str(image.get("image_id", "")).startswith("sha256:")
    ):
        raise ProtocolError("M6-5B-R1 image identity differs")
    inputs = scope.get("inputs", {})
    if set(inputs) != {"sealed_r2", "r7_audit", "raw_batch_manifest"}:
        raise ProtocolError("M6-5B-R1 input identity set differs")
    expected_r2 = protocol.base.document["predecessors"]["sealed_r2_effect"]["tree_sha256"]
    if inputs["sealed_r2"].get("tree_sha256") != expected_r2:
        raise ProtocolError("M6-5B-R1 sealed R2 identity differs")
    execution = scope.get("execution", {})
    if execution != {
        "approval_action": ACTION,
        "runner_invocation_count": 1,
        "complete_internal_passes": ["first_pass", "replay"],
        "independent_auditor_invocation_count": 1,
        "family_attempts_before_run": 1,
        "new_attempts_consumed_at_first_real_read": 1,
        "total_family_attempts_after_run": 2,
        "same_scope_retry_authorized": False,
    }:
        raise ProtocolError("M6-5B-R1 execution boundary differs")
    if scope.get("authority") != expected_authority():
        raise ProtocolError("M6-5B-R1 authority differs")
    required_container = {
        "network_mode": "none", "read_only_root": True, "run_as_non_root": True,
        "cap_drop_all": True, "no_new_privileges": True, "env_file_mounted": False,
        "docker_socket_mounted": False, "full_project_root_mounted": False,
        "production_write_mount_present": False,
    }
    if any(scope.get("container", {}).get(key) != value for key, value in required_container.items()):
        raise ProtocolError("M6-5B-R1 container boundary differs")
    outputs = scope.get("outputs", {})
    expected_outputs = protocol.document["release_and_approval"]
    if (
        outputs.get("effect_root") != expected_outputs["effect_root"]
        or outputs.get("audit_root") != expected_outputs["audit_root"]
        or outputs.get("approval_path") != expected_outputs["approval_record_path"]
        or outputs.get("write_once") is not True
    ):
        raise ProtocolError("M6-5B-R1 output boundary differs")


@dataclass(frozen=True)
class EntrypointRecoveryScope:
    path: Path
    document: dict[str, Any]
    scope: dict[str, Any]
    sha256: str

    @classmethod
    def load(
        cls, path: Path, protocol: EntrypointRecoveryProtocol,
    ) -> "EntrypointRecoveryScope":
        document = mapping(path)
        if set(document) != {"schema_version", "release_scope_sha256", "scope"}:
            raise ProtocolError("M6-5B-R1 scope fields differ")
        if document.get("schema_version") != SCOPE_SCHEMA or not isinstance(document.get("scope"), dict):
            raise ProtocolError("M6-5B-R1 scope schema differs")
        digest = canonical_sha256(document["scope"])
        if document.get("release_scope_sha256") != digest:
            raise ProtocolError("M6-5B-R1 scope self hash differs")
        validate_scope(document["scope"], protocol)
        return cls(path.resolve(), document, document["scope"], digest)

    def verify_runtime_identity(self) -> dict[str, str]:
        expected = self.scope["implementation"]
        actual = {"git_commit": git_head(), "code_snapshot_sha256": code_snapshot_sha256()}
        if actual != {
            "git_commit": expected["git_commit"],
            "code_snapshot_sha256": expected["code_snapshot_sha256"],
        }:
            raise ProtocolError("M6-5B-R1 runtime identity differs")
        manifest = os.getenv("SHAIWEI_RELEASE_MANIFEST", "").strip()
        if not manifest or sha256_file(Path(manifest)) != self.scope["image"]["release_manifest_sha256"]:
            raise ProtocolError("M6-5B-R1 embedded release manifest differs")
        return actual


@dataclass(frozen=True)
class EntrypointRecoveryApproval:
    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path, release: EntrypointRecoveryScope) -> "EntrypointRecoveryApproval":
        document = mapping(path)
        expected = {
            "schema_version": "m6-head30-500k-entrypoint-recovery-approval-v1",
            "release_scope_sha256": release.sha256, "action": ACTION,
            "family_attempts_before_run": 1, "new_attempts_authorized": 1,
            "total_family_attempts_after_run": 2,
            "sealed_r2_semantic_read_authorized": True,
            "raw_market_value_read_authorized": True,
            "formal_effect_output_write_authorized": True,
            "independent_audit_authorized": True, "model_fit_authorized": False,
            "prediction_generation_authorized": False,
            "experiment_ledger_write_authorized": False, "external_network_authorized": False,
            "env_or_secret_read_authorized": False, "paper_portfolio_write_authorized": False,
            "production_authorization": "none",
        }
        if set(document) != set(expected) | {"approved_at", "consumed"}:
            raise ProtocolError("M6-5B-R1 approval fields differ")
        if any(document.get(key) != value for key, value in expected.items()):
            raise ProtocolError("M6-5B-R1 approval authority differs")
        if not document.get("approved_at") or document.get("consumed") is not False:
            raise ProtocolError("M6-5B-R1 approval state differs")
        return cls(path.resolve(), document, sha256_file(path))

"""Versioned release, scope, approval, and runtime contracts for M6-5B."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.provenance import code_snapshot_sha256, git_head
from shaiwei.research.model_attribution.contract import canonical_sha256, sha256_file
from shaiwei.research.production_conversion.contract import ProtocolError


PROTOCOL_PATH = PROJECT_ROOT / "config/m6_csi800_production_head30_500k_release_v1.yaml"
RECOVERY_PATH = PROJECT_ROOT / "config/m6_csi800_production_head30_500k_target_read_recovery_v1.yaml"
SCOPE_PATH = PROJECT_ROOT / "config/m6_csi800_production_head30_500k_release_scope_v1.json"
IMAGE = "shaiwei:m6-head30-500k-release-v1"
BASE_ACTION = "M6_HEAD30_500K_FEASIBILITY_ONCE_WITH_REPLAY_AND_INDEPENDENT_AUDIT"
ACTION = "M6_HEAD30_500K_FEASIBILITY_TARGET_READ_RECOVERY_ONCE_WITH_REPLAY_AND_INDEPENDENT_AUDIT"
SCOPE_SCHEMA = "m6-head30-500k-release-scope-v1"
SCOPE_KIND = "HEAD30_500K_TARGET_READ_RECOVERY_RELEASE_READY_NOT_EXECUTION_APPROVAL"


def mapping(path: Path, *, yaml_document: bool = False) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
        value = yaml.safe_load(raw) if yaml_document else json.loads(raw)
    except (OSError, ValueError, yaml.YAMLError) as error:
        raise ProtocolError(f"M6-5B document is invalid: {path.name}") from error
    if not isinstance(value, dict):
        raise ProtocolError(f"M6-5B document is not a mapping: {path.name}")
    return value


def expected_authority() -> dict[str, Any]:
    return {
        "release_ready": True,
        "execution_authorized": False,
        "sealed_r2_semantic_read_authorized": False,
        "raw_market_value_read_authorized": False,
        "formal_effect_output_write_authorized": False,
        "independent_audit_authorized": False,
        "model_fit_authorized": False,
        "prediction_generation_authorized": False,
        "experiment_ledger_write_authorized": False,
        "external_network_authorized": False,
        "env_or_secret_read_authorized": False,
        "forward_signal_authorized": False,
        "paper_portfolio_write_authorized": False,
        "web_change_authorized": False,
        "scheduler_change_or_restart_authorized": False,
        "production_authorization": "none",
    }


def validate_protocol(document: dict[str, Any]) -> None:
    if document.get("schema_version") != (
        "m6-csi800-production-head30-500k-release-protocol-v1"
    ):
        raise ProtocolError("M6-5B protocol schema differs")
    if document.get("stage") != "RESULT_BLIND_RELEASE_ENGINEERING_ONLY":
        raise ProtocolError("M6-5B protocol stage differs")
    if document.get("production_authorization") != "none":
        raise ProtocolError("M6-5B cannot authorize production")
    reuse = document.get("authoritative_reuse", {})
    if (
        reuse.get("target_source")
        != "sealed_r2_first_pass_and_replay_rebalance_targets"
        or reuse.get("windows") != ["W1", "W2", "W3", "W4", "W5", "W6"]
        or reuse.get("target_count_each_rebalance") != 30
        or reuse.get("paper_policy", {}).get("required_entrypoint")
        != "shaiwei.paper.engine.execute_day"
        or reuse.get("paper_policy", {}).get("duplicate_accounting_implementation_forbidden")
        is not True
    ):
        raise ProtocolError("M6-5B authoritative reuse differs")
    counting = document.get("execution_counting", {})
    if counting != {
        "runner_invocation_count": 1,
        "complete_internal_passes": ["first_pass", "replay"],
        "independent_auditor_invocation_count": 1,
        "family_attempts_before_run": 0,
        "new_attempts_consumed_at_first_real_target_price_or_effect_read": 1,
        "total_family_attempts_after_read": 1,
        "same_scope_retry_authorized": False,
    }:
        raise ProtocolError("M6-5B execution count differs")
    release = document.get("release_and_approval", {})
    if release.get("image") != IMAGE or release.get("approval_action") != BASE_ACTION:
        raise ProtocolError("M6-5B release identity differs")
    authority = document.get("authority_before_exact_user_approval", {})
    allowed_true = {"release_engineering_authorized", "metadata_only_raw_manifest_authorized", "synthetic_fixture_authorized"}
    if any(authority.get(key) is not True for key in allowed_true):
        raise ProtocolError("M6-5B engineering authority is absent")
    forbidden = set(authority) - allowed_true - {"production_authorization"}
    if any(authority.get(key) is not False for key in forbidden):
        raise ProtocolError("M6-5B preapproval authority was broadened")
    if authority.get("production_authorization") != "none":
        raise ProtocolError("M6-5B preapproval production authority differs")


@dataclass(frozen=True)
class ReleaseProtocol:
    path: Path
    document: dict[str, Any]
    sha256: str
    recovery_path: Path
    recovery: dict[str, Any]
    recovery_sha256: str

    @classmethod
    def load(
        cls, path: Path = PROTOCOL_PATH, recovery_path: Path = RECOVERY_PATH,
    ) -> "ReleaseProtocol":
        document = mapping(path, yaml_document=True)
        validate_protocol(document)
        recovery = mapping(recovery_path, yaml_document=True)
        digest = sha256_file(path)
        ruling = recovery.get("recovery_ruling", {})
        replacement = recovery.get("replacement_release", {})
        if (
            recovery.get("schema_version")
            != "m6-head30-500k-target-read-recovery-protocol-v1"
            or recovery.get("base_protocol", {}).get("sha256") != digest
            or ruling.get("family_attempts_before_future_authorized_real_run") != 1
            or ruling.get("total_family_attempts_after_future_authorized_real_run") != 2
            or ruling.get("further_real_target_price_or_effect_read_before_approval") is not False
            or replacement.get("scope_kind") != SCOPE_KIND
            or replacement.get("approval_action") != ACTION
        ):
            raise ProtocolError("M6-5B recovery protocol differs")
        for predecessor in document.get("predecessors", {}).values():
            if "path" in predecessor:
                target = PROJECT_ROOT / predecessor["path"]
                if sha256_file(target) != predecessor.get("sha256"):
                    raise ProtocolError(f"M6-5B predecessor differs: {target.name}")
        policy = document["authoritative_reuse"]["paper_policy"]
        if sha256_file(PROJECT_ROOT / policy["document_path"]) != policy["document_sha256"]:
            raise ProtocolError("M6-5B paper policy document differs")
        if sha256_file(PROJECT_ROOT / policy["engine_path"]) != policy["engine_sha256_at_freeze"]:
            raise ProtocolError("M6-5B paper engine differs")
        return cls(
            path.resolve(), document, digest, recovery_path.resolve(), recovery,
            sha256_file(recovery_path),
        )


def validate_scope(scope: dict[str, Any], protocol: ReleaseProtocol) -> None:
    if scope.get("scope_kind") != SCOPE_KIND or scope.get("protocol_sha256") != protocol.sha256:
        raise ProtocolError("M6-5B scope identity differs")
    implementation, image = scope.get("implementation", {}), scope.get("image", {})
    commit = implementation.get("git_commit")
    snapshot = implementation.get("code_snapshot_sha256")
    if not isinstance(commit, str) or len(commit) != 40:
        raise ProtocolError("M6-5B implementation commit is invalid")
    if implementation.get("origin_main_commit") != commit:
        raise ProtocolError("M6-5B implementation is not pushed")
    if (
        image.get("reference") != IMAGE
        or image.get("git_commit") != commit
        or image.get("code_snapshot_sha256") != snapshot
        or not str(image.get("image_id", "")).startswith("sha256:")
    ):
        raise ProtocolError("M6-5B image identity differs")
    inputs = scope.get("inputs", {})
    if set(inputs) != {"sealed_r2", "r7_audit", "raw_batch_manifest"}:
        raise ProtocolError("M6-5B input identity set differs")
    if inputs["sealed_r2"].get("tree_sha256") != protocol.document["predecessors"]["sealed_r2_effect"]["tree_sha256"]:
        raise ProtocolError("M6-5B sealed R2 identity differs")
    raw = inputs["raw_batch_manifest"]
    if raw.get("required_source_apis") != protocol.document["raw_evidence_contract"]["required_source_apis"]:
        raise ProtocolError("M6-5B raw source set differs")
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
        raise ProtocolError("M6-5B scoped execution differs")
    if scope.get("authority") != expected_authority():
        raise ProtocolError("M6-5B scoped authority differs")
    container = scope.get("container", {})
    required = {
        "network_mode": "none", "read_only_root": True, "run_as_non_root": True,
        "cap_drop_all": True, "no_new_privileges": True, "env_file_mounted": False,
        "docker_socket_mounted": False, "full_project_root_mounted": False,
        "production_write_mount_present": False,
    }
    if any(container.get(key) != value for key, value in required.items()):
        raise ProtocolError("M6-5B container boundary differs")


@dataclass(frozen=True)
class ReleaseScope:
    path: Path
    document: dict[str, Any]
    scope: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path, protocol: ReleaseProtocol) -> "ReleaseScope":
        document = mapping(path)
        if set(document) != {"schema_version", "release_scope_sha256", "scope"}:
            raise ProtocolError("M6-5B scope fields differ")
        if document.get("schema_version") != SCOPE_SCHEMA or not isinstance(document.get("scope"), dict):
            raise ProtocolError("M6-5B scope schema differs")
        digest = canonical_sha256(document["scope"])
        if document.get("release_scope_sha256") != digest:
            raise ProtocolError("M6-5B scope self hash differs")
        validate_scope(document["scope"], protocol)
        return cls(path.resolve(), document, document["scope"], digest)

    def verify_runtime_identity(self) -> dict[str, str]:
        expected = self.scope["implementation"]
        actual = {"git_commit": git_head(), "code_snapshot_sha256": code_snapshot_sha256()}
        if actual != {
            "git_commit": expected["git_commit"],
            "code_snapshot_sha256": expected["code_snapshot_sha256"],
        }:
            raise ProtocolError("M6-5B runtime identity differs")
        manifest = os.getenv("SHAIWEI_RELEASE_MANIFEST", "").strip()
        if not manifest or sha256_file(Path(manifest)) != self.scope["image"]["release_manifest_sha256"]:
            raise ProtocolError("M6-5B embedded release manifest differs")
        return actual


@dataclass(frozen=True)
class Approval:
    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path, release: ReleaseScope) -> "Approval":
        document = mapping(path)
        expected = {
            "schema_version": "m6-head30-500k-approval-v1",
            "release_scope_sha256": release.sha256,
            "action": ACTION,
            "family_attempts_before_run": 1,
            "new_attempts_authorized": 1,
            "total_family_attempts_after_run": 2,
            "sealed_r2_semantic_read_authorized": True,
            "raw_market_value_read_authorized": True,
            "formal_effect_output_write_authorized": True,
            "independent_audit_authorized": True,
            "model_fit_authorized": False,
            "prediction_generation_authorized": False,
            "experiment_ledger_write_authorized": False,
            "external_network_authorized": False,
            "env_or_secret_read_authorized": False,
            "paper_portfolio_write_authorized": False,
            "production_authorization": "none",
        }
        if set(document) != set(expected) | {"approved_at", "consumed"}:
            raise ProtocolError("M6-5B approval fields differ")
        if any(document.get(key) != value for key, value in expected.items()):
            raise ProtocolError("M6-5B approval authority differs")
        if not document.get("approved_at") or document.get("consumed") is not False:
            raise ProtocolError("M6-5B approval state differs")
        return cls(path.resolve(), document, sha256_file(path))

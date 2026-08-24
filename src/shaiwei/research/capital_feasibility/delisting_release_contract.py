"""Strict protocol, release scope, approval, and runtime identity for M6-5C-C."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any

import yaml

from shaiwei.build_identity.registry import BuildIdentityError
from shaiwei.build_identity.release import verify_sealed_component_identity
from shaiwei.build_identity.source_bundle import verify_source_manifest
from shaiwei.config import PROJECT_ROOT
from shaiwei.research.model_attribution.contract import canonical_sha256, sha256_file
from shaiwei.research.production_conversion.contract import ProtocolError

from .delisting_release_recovery_contract import R2_IMAGE, load_release_recoveries


PROTOCOL_PATH = (
    PROJECT_ROOT
    / "config/m6_csi800_production_head30_delisting_risk_release_v1.yaml"
)
SCOPE_PATH = (
    PROJECT_ROOT
    / "config/m6_csi800_production_head30_delisting_risk_release_scope_r2_v1.json"
)
COMPOSE_PATH = PROJECT_ROOT / "compose.m6-head30-delisting-risk-release.yaml"
DOCKERFILE_PATH = PROJECT_ROOT / "Dockerfile.m6-head30-delisting-risk-release"
IMAGE = R2_IMAGE
ACTION = (
    "M6_HEAD30_500K_DELISTING_RISK_RECOVERY_ONCE_WITH_CLAIM_REPLAY_"
    "AND_INDEPENDENT_AUDIT"
)
SCOPE_SCHEMA = "m6-head30-500k-delisting-risk-release-scope-v1"
SCOPE_KIND = "HEAD30_500K_DELISTING_RISK_RELEASE_READY_NOT_EXECUTION_APPROVAL"
FROZEN_REGISTRY_SHA256 = "e0251d3cd9f38da055d533f8fb2f059ef5213f7ed13ef9caab7a653e64155035"
FROZEN_COMPONENT_ASSET_IDENTITIES = (
    (
        "Dockerfile.m6-head30-delisting-risk-release",
        "cd8cd0d2b0936000469d64b045c3d4be62272b57c933d3f22c9a7a8ebbca6cf1",
    ),
    (
        "Dockerfile.m6-head30-delisting-risk-release.dockerignore",
        "7f07b42ba260027a96709488be80f9d81ee392bf29c26e113c09fee1148661c4",
    ),
    (
        "compose.m6-head30-delisting-risk-release.yaml",
        "e0be8c53994a15f99710ae62e9f8e7c0a1c316ee71da609b58ad454f61cddd3e",
    ),
)
FROZEN_COMPONENT_BUILD_SNAPSHOT_SHA256 = (
    "0bb3e0bb58cdd5fb5c514cbdf224100201b29bda499d640e4f9d69480cbf5a34"
)


def mapping(path: Path, *, yaml_document: bool = False) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
        value = yaml.safe_load(raw) if yaml_document else json.loads(raw)
    except (OSError, ValueError, yaml.YAMLError) as error:
        raise ProtocolError(f"M6-5C-C document is invalid: {path.name}") from error
    if not isinstance(value, dict):
        raise ProtocolError(f"M6-5C-C document is not a mapping: {path.name}")
    return value


def expected_authority() -> dict[str, Any]:
    return {
        "release_ready": True,
        "execution_authorized": False,
        "real_target_read_authorized": False,
        "real_price_read_authorized": False,
        "real_effect_read_authorized": False,
        "canonical_ledger_write_authorized": False,
        "claim_receipt_write_authorized": False,
        "formal_effect_output_write_authorized": False,
        "independent_audit_authorized": False,
        "model_fit_authorized": False,
        "prediction_generation_authorized": False,
        "external_network_authorized": False,
        "env_or_secret_read_authorized": False,
        "paper_portfolio_write_authorized": False,
        "web_change_authorized": False,
        "scheduler_change_or_restart_authorized": False,
        "production_authorization": "none",
    }


def _validate_protocol(document: dict[str, Any]) -> None:
    if (
        document.get("schema_version")
        != "m6-csi800-production-head30-delisting-risk-release-v1"
        or document.get("stage")
        != "RESULT_BLIND_CLAIM_FIRST_RELEASE_ENGINEERING_ONLY"
        or document.get("production_authorization") != "none"
    ):
        raise ProtocolError("M6-5C-C protocol identity differs")
    for name, item in document.get("predecessors", {}).items():
        path = PROJECT_ROOT / str(item.get("path", ""))
        expected = item.get("sha256", item.get("file_sha256"))
        if not path.is_file() or sha256_file(path) != expected:
            raise ProtocolError(f"M6-5C-C predecessor differs: {name}")
    blocked_scope = document["predecessors"]["blocked_scope"]
    if (
        mapping(PROJECT_ROOT / blocked_scope["path"]).get("release_scope_sha256")
        != blocked_scope["release_scope_sha256"]
        or blocked_scope.get("permanently_closed") is not True
    ):
        raise ProtocolError("M6-5C-C blocked scope ruling differs")
    failure = document["predecessors"]["blocked_failure"]
    if mapping(PROJECT_ROOT / failure["path"]).get("decision") != failure["decision"]:
        raise ProtocolError("M6-5C-C blocked failure ruling differs")
    claim = document.get("attempt_claim", {})
    if claim != {
        "attempt_family": "m6_head30_500k_delisting_risk_overlay_v1",
        "attempt_ordinal": 1,
        "family_attempts_before_run": 0,
        "family_attempts_after_claim": 1,
        "candidate_source": "sealed-m6-r2-production-head30",
        "model_or_engine": "paper-v2-delisting-risk-exit",
        "engine_version": "m6-5c-risk-overlay-v1",
        "feature_or_formula": "10 valid closes < 1 CNY; latch exit; no replacement",
        "train_period": "none; fixed post-hoc method recovery",
        "valid_period": "sealed W1-W6 historical diagnostic",
        "canonical_ledger": "ledger/experiments.csv",
        "receipt_before_effect_read": True,
        "same_scope_retry_authorized": False,
    }:
        raise ProtocolError("M6-5C-C attempt claim differs")
    execution = document.get("execution", {})
    if execution != {
        "runner_invocation_count": 1,
        "complete_internal_passes": ["first_pass", "replay"],
        "independent_auditor_invocation_count": 1,
        "action": ACTION,
        "no_raw_or_r2_mount_for_auditor": True,
        "numeric_tolerance": 1e-12,
    }:
        raise ProtocolError("M6-5C-C execution boundary differs")
    authority = document.get("authority_before_exact_user_approval", {})
    allowed = {
        "release_engineering_authorized",
        "synthetic_fixture_authorized",
        "metadata_identity_read_authorized",
        "build_image_authorized",
        "build_release_scope_authorized",
    }
    if any(authority.get(key) is not True for key in allowed):
        raise ProtocolError("M6-5C-C engineering authority is absent")
    if any(
        value not in (False, "none")
        for key, value in authority.items()
        if key not in allowed
    ):
        raise ProtocolError("M6-5C-C preapproval authority was broadened")


@dataclass(frozen=True)
class ReleaseProtocol:
    path: Path
    document: dict[str, Any]
    sha256: str
    recovery_sha256: str
    scope_runtime_recovery_sha256: str
    blocked_scope: dict[str, Any]

    @classmethod
    def load(cls, path: Path = PROTOCOL_PATH) -> "ReleaseProtocol":
        document = mapping(path, yaml_document=True)
        _validate_protocol(document)
        recovery_sha256, runtime_recovery_sha256 = load_release_recoveries(
            sha256_file(path)
        )
        blocked = mapping(
            PROJECT_ROOT / document["predecessors"]["blocked_scope"]["path"]
        )["scope"]
        return cls(
            path.resolve(),
            document,
            sha256_file(path),
            recovery_sha256,
            runtime_recovery_sha256,
            blocked,
        )


def _expected_execution() -> dict[str, Any]:
    return {
        "approval_action": ACTION,
        "runner_invocation_count": 1,
        "complete_internal_passes": ["first_pass", "replay"],
        "independent_auditor_invocation_count": 1,
        "attempt_family": "m6_head30_500k_delisting_risk_overlay_v1",
        "family_attempts_before_run": 0,
        "new_attempts_consumed_at_claim": 1,
        "total_family_attempts_after_claim": 1,
        "same_scope_retry_authorized": False,
    }


def validate_scope(scope: dict[str, Any], protocol: ReleaseProtocol) -> None:
    if (
        scope.get("scope_kind") != SCOPE_KIND
        or scope.get("protocol_sha256") != protocol.sha256
        or scope.get("recovery_protocol_sha256") != protocol.recovery_sha256
        or scope.get("scope_runtime_recovery_sha256")
        != protocol.scope_runtime_recovery_sha256
    ):
        raise ProtocolError("M6-5C-C scope identity differs")
    implementation = scope.get("implementation", {})
    commit = implementation.get("git_commit")
    if (
        not isinstance(commit, str)
        or len(commit) != 40
        or implementation.get("origin_main_commit") != commit
        or len(str(implementation.get("source_bundle_sha256", ""))) != 64
    ):
        raise ProtocolError("M6-5C-C implementation identity differs")
    try:
        records = verify_sealed_component_identity(
            implementation,
            registry_sha256=FROZEN_REGISTRY_SHA256,
            build_assets=FROZEN_COMPONENT_ASSET_IDENTITIES,
            component_build_snapshot_sha256_value=(
                FROZEN_COMPONENT_BUILD_SNAPSHOT_SHA256
            ),
        )
    except BuildIdentityError as error:
        raise ProtocolError("M6-5C-C component build identity differs") from error
    asset_hashes = {record["path"]: record["sha256"] for record in records}
    if len(str(implementation.get("source_manifest_sha256", ""))) != 64:
        raise ProtocolError("M6-5C-C component build identity differs")
    image = scope.get("image", {})
    if (
        image.get("reference") != IMAGE
        or image.get("git_commit") != commit
        or image.get("source_bundle_sha256")
        != implementation.get("source_bundle_sha256")
        or not str(image.get("image_id", "")).startswith("sha256:")
        or image.get("component_build_snapshot_sha256")
        != implementation.get("component_build_snapshot_sha256")
    ):
        raise ProtocolError("M6-5C-C image identity differs")
    inputs = scope.get("inputs", {})
    if set(inputs) != {"sealed_r2", "r7_audit", "raw_batch_manifest"}:
        raise ProtocolError("M6-5C-C input identity set differs")
    blocked_inputs = protocol.blocked_scope["inputs"]
    if (
        inputs["sealed_r2"] != blocked_inputs["sealed_r2"]
        or inputs["r7_audit"] != blocked_inputs["r7_audit"]
        or inputs["raw_batch_manifest"] != blocked_inputs["raw_batch_manifest"]
    ):
        raise ProtocolError("M6-5C-C frozen input identity differs")
    if scope.get("execution") != _expected_execution():
        raise ProtocolError("M6-5C-C execution scope differs")
    attempt = scope.get("attempt_claim", {})
    if (
        attempt.get("spec") != protocol.document["attempt_claim"]
        or attempt.get("input_identity_sha256") != canonical_sha256(inputs)
        or attempt.get("claim_before_effect_reader") is not True
    ):
        raise ProtocolError("M6-5C-C scoped claim differs")
    if scope.get("authority") != expected_authority():
        raise ProtocolError("M6-5C-C authority differs")
    container = scope.get("container", {})
    required = {
        "network_mode": "none",
        "read_only_root": True,
        "run_as_non_root": True,
        "cap_drop_all": True,
        "no_new_privileges": True,
        "env_file_mounted": False,
        "docker_socket_mounted": False,
        "full_project_root_mounted": False,
        "production_write_mount_present": False,
        "canonical_ledger_mount": "runner-rw-auditor-ro",
        "claim_receipt_mount": "runner-rw-auditor-ro",
        "auditor_raw_or_r2_mount": False,
    }
    if any(container.get(key) != value for key, value in required.items()):
        raise ProtocolError("M6-5C-C container boundary differs")
    if (
        container.get("compose_path") != COMPOSE_PATH.name
        or container.get("compose_sha256") != asset_hashes.get(COMPOSE_PATH.name)
        or container.get("dockerfile_path") != DOCKERFILE_PATH.name
        or container.get("dockerfile_sha256") != asset_hashes.get(DOCKERFILE_PATH.name)
    ):
        raise ProtocolError("M6-5C-C container build asset differs")


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
            raise ProtocolError("M6-5C-C scope fields differ")
        if document.get("schema_version") != SCOPE_SCHEMA:
            raise ProtocolError("M6-5C-C scope schema differs")
        digest = canonical_sha256(document.get("scope"))
        if document.get("release_scope_sha256") != digest:
            raise ProtocolError("M6-5C-C scope self hash differs")
        validate_scope(document["scope"], protocol)
        return cls(path.resolve(), document, document["scope"], digest)

    def verify_runtime_identity(self) -> dict[str, str]:
        manifest_path = os.getenv("SHAIWEI_COMPONENT_SOURCE_MANIFEST", "").strip()
        revision = os.getenv("SHAIWEI_COMPONENT_GIT_COMMIT", "").strip()
        if not manifest_path or not revision:
            raise ProtocolError("M6-5C-C runtime identity environment is absent")
        manifest = mapping(Path(manifest_path))
        verified = verify_source_manifest(manifest, root=PROJECT_ROOT)
        expected = self.scope["implementation"]
        if (
            revision != expected["git_commit"]
            or verified["git_commit"] != revision
            or verified["source_bundle_sha256"] != expected["source_bundle_sha256"]
        ):
            raise ProtocolError("M6-5C-C runtime identity differs")
        return {
            "git_commit": revision,
            "source_bundle_sha256": str(verified["source_bundle_sha256"]),
        }


@dataclass(frozen=True)
class Approval:
    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path, release: ReleaseScope) -> "Approval":
        document = mapping(path)
        expected = {
            "schema_version": "m6-head30-500k-delisting-risk-approval-v1",
            "release_scope_sha256": release.sha256,
            "action": ACTION,
            "attempt_family": "m6_head30_500k_delisting_risk_overlay_v1",
            "family_attempts_before_run": 0,
            "new_attempts_authorized": 1,
            "total_family_attempts_after_claim": 1,
            "real_target_read_authorized": True,
            "real_price_read_authorized": True,
            "real_effect_read_authorized": True,
            "canonical_ledger_write_authorized": True,
            "claim_receipt_write_authorized": True,
            "formal_effect_output_write_authorized": True,
            "independent_audit_authorized": True,
            "model_fit_authorized": False,
            "prediction_generation_authorized": False,
            "external_network_authorized": False,
            "env_or_secret_read_authorized": False,
            "paper_portfolio_write_authorized": False,
            "production_authorization": "none",
        }
        if set(document) != set(expected) | {"approved_at", "consumed"}:
            raise ProtocolError("M6-5C-C approval fields differ")
        if any(document.get(key) != value for key, value in expected.items()):
            raise ProtocolError("M6-5C-C approval authority differs")
        if not document.get("approved_at") or document.get("consumed") is not False:
            raise ProtocolError("M6-5C-C approval state differs")
        return cls(path.resolve(), document, sha256_file(path))

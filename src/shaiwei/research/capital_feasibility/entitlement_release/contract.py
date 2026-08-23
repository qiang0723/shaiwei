"""Strict result-blind contract for the M6-5C-C-R4 successor release."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any

import yaml

from shaiwei.build_identity.registry import load_build_registry
from shaiwei.build_identity.release import component_build_snapshot_sha256
from shaiwei.build_identity.source_bundle import verify_source_manifest
from shaiwei.config import PROJECT_ROOT
from shaiwei.research.model_attribution.contract import canonical_sha256, sha256_file
from shaiwei.research.production_conversion.contract import ProtocolError


PROTOCOL_PATH = (
    PROJECT_ROOT
    / "config/m6_csi800_production_head30_delisting_entitlement_release_v1.yaml"
)
SCOPE_PATH = (
    PROJECT_ROOT
    / "config/m6_csi800_production_head30_delisting_entitlement_release_scope_v1.json"
)
COMPONENT_ID = "m6-head30-delisting-entitlement-release"
IMAGE = "shaiwei:m6-head30-delisting-entitlement-release-v1"
ACTION = (
    "M6_HEAD30_500K_DELISTING_ENTITLEMENT_RECOVERY_ONCE_WITH_CLAIM_REPLAY_"
    "AND_INDEPENDENT_AUDIT"
)
SCOPE_SCHEMA = "m6-head30-500k-delisting-entitlement-release-scope-v1"
SCOPE_KIND = "HEAD30_500K_DELISTING_ENTITLEMENT_RELEASE_READY_NOT_EXECUTION_APPROVAL"


def mapping(path: Path, *, yaml_document: bool = False) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
        value = yaml.safe_load(raw) if yaml_document else json.loads(raw)
    except (OSError, ValueError, yaml.YAMLError) as error:
        raise ProtocolError(f"M6-5C-C-R4 document is invalid: {path.name}") from error
    if not isinstance(value, dict):
        raise ProtocolError(f"M6-5C-C-R4 document is not a mapping: {path.name}")
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
        != "m6-csi800-production-head30-delisting-entitlement-release-v1"
        or document.get("stage") != "RESULT_BLIND_ORDINAL_TWO_RELEASE_ENGINEERING_ONLY"
        or document.get("production_authorization") != "none"
    ):
        raise ProtocolError("M6-5C-C-R4 protocol identity differs")
    for name, item in document.get("predecessors", {}).items():
        path = PROJECT_ROOT / str(item.get("path", ""))
        expected = item.get("sha256", item.get("file_sha256"))
        if not path.is_file() or sha256_file(path) != expected:
            raise ProtocolError(f"M6-5C-C-R4 predecessor differs: {name}")
    single = document.get("single_variable", {})
    if (
        single.get("execution_entrypoint")
        != "shaiwei.paper.stock_dividend_entitlement.execute_entitlement_recovery_day"
        or sha256_file(PROJECT_ROOT / str(single.get("adapter_path", "")))
        != single.get("adapter_sha256")
        or any(
            single.get(key) is not False
            for key in (
                "risk_parameter_change_authorized",
                "target_or_rebalance_change_authorized",
                "capital_gate_change_authorized",
                "model_fit_or_prediction_authorized",
            )
        )
    ):
        raise ProtocolError("M6-5C-C-R4 single variable differs")
    claim = document.get("attempt_claim", {})
    if (
        claim.get("attempt_family") != "m6_head30_500k_delisting_risk_overlay_v1"
        or claim.get("attempt_ordinal") != 2
        or claim.get("parent_experiment_id") != "6797875cf3c0"
        or claim.get("family_attempts_before_run") != 1
        or claim.get("family_attempts_after_claim") != 2
        or claim.get("receipt_before_effect_read") is not True
        or claim.get("same_scope_retry_authorized") is not False
    ):
        raise ProtocolError("M6-5C-C-R4 attempt lineage differs")
    release = document.get("release", {})
    if (
        release.get("component_id") != COMPONENT_ID
        or release.get("image_reference") != IMAGE
        or release.get("approval_action") != ACTION
        or release.get("runner_invocation_count") != 1
        or release.get("independent_auditor_invocation_count") != 1
        or release.get("network_mode") != "none"
        or release.get("auditor_raw_or_r2_mount") is not False
    ):
        raise ProtocolError("M6-5C-C-R4 release boundary differs")
    authority = document.get("authority_before_exact_user_approval", {})
    allowed = {
        "release_engineering_authorized",
        "synthetic_fixture_authorized",
        "metadata_identity_read_authorized",
        "build_image_authorized",
        "build_release_scope_authorized",
    }
    if any(authority.get(key) is not True for key in allowed) or any(
        value not in (False, "none")
        for key, value in authority.items()
        if key not in allowed
    ):
        raise ProtocolError("M6-5C-C-R4 preapproval authority was broadened")


@dataclass(frozen=True)
class ReleaseProtocol:
    path: Path
    document: dict[str, Any]
    sha256: str
    failed_scope: dict[str, Any]

    @classmethod
    def load(cls, path: Path = PROTOCOL_PATH) -> "ReleaseProtocol":
        document = mapping(path, yaml_document=True)
        _validate_protocol(document)
        failed_path = PROJECT_ROOT / document["predecessors"]["failed_scope"]["path"]
        failed_document = mapping(failed_path)
        if (
            failed_document.get("release_scope_sha256")
            != document["predecessors"]["failed_scope"]["release_scope_sha256"]
        ):
            raise ProtocolError("M6-5C-C-R4 failed scope ruling differs")
        return cls(path.resolve(), document, sha256_file(path), failed_document["scope"])


def _build_records(raw: object, assets: tuple[str, ...]) -> list[dict[str, str]]:
    if not isinstance(raw, list) or [row.get("path") for row in raw] != list(assets):
        raise ProtocolError("M6-5C-C-R4 build asset paths differ")
    records: list[dict[str, str]] = []
    for row in raw:
        if not isinstance(row, dict) or set(row) != {"path", "sha256"}:
            raise ProtocolError("M6-5C-C-R4 build asset record differs")
        digest = row.get("sha256")
        if not isinstance(digest, str) or len(digest) != 64:
            raise ProtocolError("M6-5C-C-R4 build asset digest differs")
        records.append({"path": str(row["path"]), "sha256": digest})
    return records


def validate_scope(scope: dict[str, Any], protocol: ReleaseProtocol) -> None:
    if scope.get("scope_kind") != SCOPE_KIND or scope.get("protocol_sha256") != protocol.sha256:
        raise ProtocolError("M6-5C-C-R4 scope identity differs")
    implementation = scope.get("implementation", {})
    commit = implementation.get("git_commit")
    if (
        not isinstance(commit, str)
        or len(commit) != 40
        or implementation.get("origin_main_commit") != commit
    ):
        raise ProtocolError("M6-5C-C-R4 implementation identity differs")
    registry = load_build_registry(validate_filesystem=False)
    component = registry.component(COMPONENT_ID)
    records = _build_records(implementation.get("build_assets"), component.assets)
    if (
        implementation.get("registry_sha256") != registry.registry_sha256
        or implementation.get("component_build_snapshot_sha256")
        != component_build_snapshot_sha256(records)
        or len(str(implementation.get("source_bundle_sha256", ""))) != 64
    ):
        raise ProtocolError("M6-5C-C-R4 component identity differs")
    image = scope.get("image", {})
    if (
        image.get("reference") != IMAGE
        or image.get("git_commit") != commit
        or image.get("source_bundle_sha256") != implementation.get("source_bundle_sha256")
        or image.get("component_build_snapshot_sha256")
        != implementation.get("component_build_snapshot_sha256")
        or not str(image.get("image_id", "")).startswith("sha256:")
    ):
        raise ProtocolError("M6-5C-C-R4 image identity differs")
    inputs = scope.get("inputs", {})
    if inputs != protocol.failed_scope.get("inputs"):
        raise ProtocolError("M6-5C-C-R4 frozen inputs differ")
    claim = scope.get("attempt_claim", {})
    if (
        claim.get("spec") != protocol.document["attempt_claim"]
        or claim.get("input_identity_sha256") != canonical_sha256(inputs)
        or claim.get("claim_before_effect_reader") is not True
    ):
        raise ProtocolError("M6-5C-C-R4 scoped claim differs")
    execution = scope.get("execution", {})
    if execution != {
        "approval_action": ACTION,
        "runner_invocation_count": 1,
        "complete_internal_passes": ["first_pass", "replay"],
        "independent_auditor_invocation_count": 1,
        "attempt_family": "m6_head30_500k_delisting_risk_overlay_v1",
        "family_attempts_before_run": 1,
        "new_attempts_consumed_at_claim": 1,
        "total_family_attempts_after_claim": 2,
        "same_scope_retry_authorized": False,
    }:
        raise ProtocolError("M6-5C-C-R4 execution scope differs")
    if scope.get("authority") != expected_authority():
        raise ProtocolError("M6-5C-C-R4 authority differs")
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
        raise ProtocolError("M6-5C-C-R4 container boundary differs")


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
            raise ProtocolError("M6-5C-C-R4 scope fields differ")
        if document.get("schema_version") != SCOPE_SCHEMA:
            raise ProtocolError("M6-5C-C-R4 scope schema differs")
        digest = canonical_sha256(document.get("scope"))
        if document.get("release_scope_sha256") != digest:
            raise ProtocolError("M6-5C-C-R4 scope self hash differs")
        validate_scope(document["scope"], protocol)
        return cls(path.resolve(), document, document["scope"], digest)

    def verify_runtime_identity(self) -> dict[str, str]:
        manifest_path = os.getenv("SHAIWEI_COMPONENT_SOURCE_MANIFEST", "").strip()
        revision = os.getenv("SHAIWEI_COMPONENT_GIT_COMMIT", "").strip()
        if not manifest_path or not revision:
            raise ProtocolError("M6-5C-C-R4 runtime identity environment is absent")
        verified = verify_source_manifest(mapping(Path(manifest_path)), root=PROJECT_ROOT)
        expected = self.scope["implementation"]
        if (
            revision != expected["git_commit"]
            or verified["git_commit"] != revision
            or verified["source_bundle_sha256"] != expected["source_bundle_sha256"]
        ):
            raise ProtocolError("M6-5C-C-R4 runtime identity differs")
        return {"git_commit": revision, "source_bundle_sha256": verified["source_bundle_sha256"]}


@dataclass(frozen=True)
class Approval:
    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path, release: ReleaseScope) -> "Approval":
        document = mapping(path)
        expected = {
            "schema_version": "m6-head30-500k-delisting-entitlement-approval-v1",
            "release_scope_sha256": release.sha256,
            "action": ACTION,
            "attempt_family": "m6_head30_500k_delisting_risk_overlay_v1",
            "family_attempts_before_run": 1,
            "new_attempts_authorized": 1,
            "total_family_attempts_after_claim": 2,
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
            raise ProtocolError("M6-5C-C-R4 approval fields differ")
        if any(document.get(key) != value for key, value in expected.items()):
            raise ProtocolError("M6-5C-C-R4 approval authority differs")
        if not document.get("approved_at") or document.get("consumed") is not False:
            raise ProtocolError("M6-5C-C-R4 approval state differs")
        return cls(path.resolve(), document, sha256_file(path))

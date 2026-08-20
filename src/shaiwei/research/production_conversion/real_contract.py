"""Exact release, approval, and runtime contracts for M6 production Head30."""

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
from shaiwei.research.model_attribution.effect_contract import write_once_document
from shaiwei.research.production_conversion.contract import (
    APPROVAL_ACTION,
    Protocol,
    ProtocolError,
)
from shaiwei.research.production_conversion.recovery_validation import (
    validate_entrypoint_recovery_protocol,
)
from shaiwei.research.production_conversion.price_recovery_validation import (
    validate_price_recovery_protocol,
)
from shaiwei.research.production_conversion.runtime_profiles import (
    BASE_PROFILE,
    RuntimeProfile,
    runtime_profile,
)


RELEASE_PROTOCOL = PROJECT_ROOT / "config/m6_csi800_production_head30_release_v1.yaml"
ENTRYPOINT_RECOVERY_PROTOCOL = (
    PROJECT_ROOT / "config/m6_csi800_production_head30_entrypoint_recovery_v1.yaml"
)
PRICE_RECOVERY_PROTOCOL = (
    PROJECT_ROOT / "config/m6_csi800_production_head30_price_recovery_v1.yaml"
)
ORIGINAL_M6_SCOPE = PROJECT_ROOT / "config/m6_csi800_model_attribution_release_scope_v1.json"
SCOPE_SCHEMA = "m6-production-head30-release-scope-v1"
SCOPE_KIND = "PRODUCTION_HEAD30_G0_RELEASE_READY_NOT_EXECUTION_APPROVAL"
IMAGE = "shaiwei:m6-production-head30-release-v1"
RUNNER_COMMAND = list(BASE_PROFILE.runner_command)
AUDITOR_COMMAND = list(BASE_PROFILE.auditor_command)


def mapping(path: Path, *, yaml_document: bool = False) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
        value = yaml.safe_load(raw) if yaml_document else json.loads(raw)
    except (OSError, ValueError, yaml.YAMLError) as error:
        raise ProtocolError(f"production-converter document is invalid: {path.name}") from error
    if not isinstance(value, dict):
        raise ProtocolError(f"production-converter document is not a mapping: {path.name}")
    return value


def expected_authority() -> dict[str, Any]:
    return {
        "release_ready": True,
        "execution_authorized": False,
        "qlib_read_authorized": False,
        "sealed_m6_effect_read_authorized": False,
        "real_treatment_backtest_authorized": False,
        "sealed_control_report_read_authorized": False,
        "formal_effect_output_write_authorized": False,
        "independent_audit_authorized": False,
        "model_fit_authorized": False,
        "prediction_generation_authorized": False,
        "experiment_ledger_write_authorized": False,
        "external_network_authorized": False,
        "env_or_secret_read_authorized": False,
        "forward_signal_authorized": False,
        "paper_portfolio_authorized": False,
        "production_authorization": "none",
    }


@dataclass(frozen=True)
class ReleaseProtocol:
    path: Path
    document: dict[str, Any]
    sha256: str
    base: Protocol

    @classmethod
    def load(cls, path: Path | None = None) -> "ReleaseProtocol":
        path = (path or RELEASE_PROTOCOL).resolve()
        if path not in {
            RELEASE_PROTOCOL.resolve(),
            ENTRYPOINT_RECOVERY_PROTOCOL.resolve(),
            PRICE_RECOVERY_PROTOCOL.resolve(),
        }:
            raise ProtocolError("production-converter release protocol path is not allowed")
        base = Protocol.load()
        document = mapping(path, yaml_document=True)
        protocol_id = document.get("protocol_id")
        allowed = {
            "m6-csi800-production-head30-release-v1": "RESULT_BLIND_RELEASE_ENGINEERING_ONLY",
            "m6-csi800-production-head30-entrypoint-recovery-v1": (
                "RESULT_BLIND_ENTRYPOINT_RECOVERY_ONLY"
            ),
            "m6-csi800-production-head30-price-recovery-v1": (
                "RESULT_BLIND_PRICE_RECOVERY_ONLY"
            ),
        }
        if protocol_id not in allowed:
            raise ProtocolError("production-converter release identity differs")
        if document.get("stage") != allowed[protocol_id]:
            raise ProtocolError("production-converter release stage differs")
        if protocol_id.endswith("entrypoint-recovery-v1"):
            validate_entrypoint_recovery_protocol(document, PROJECT_ROOT)
            cls._validate_preapproval_authority(document)
            return cls(path, document, sha256_file(path), base)
        if protocol_id.endswith("price-recovery-v1"):
            validate_price_recovery_protocol(document, PROJECT_ROOT)
            cls._validate_preapproval_authority(document)
            return cls(path, document, sha256_file(path), base)
        predecessors = document.get("predecessors", {})
        expected = {
            "production_converter_protocol": base.sha256,
            "production_converter_hash_addendum": base.addendum_sha256,
        }
        for name, digest in expected.items():
            row = predecessors.get(name, {})
            if row.get("sha256") != digest or sha256_file(PROJECT_ROOT / row.get("path", "")) != digest:
                raise ProtocolError(f"production-converter release predecessor differs: {name}")
        m6_scope = predecessors.get("m6_real_release_scope", {})
        m6_path = PROJECT_ROOT / m6_scope.get("path", "")
        m6_document = mapping(m6_path)
        if (
            m6_scope.get("file_sha256") != sha256_file(m6_path)
            or m6_scope.get("release_scope_sha256") != m6_document.get("release_scope_sha256")
        ):
            raise ProtocolError("production-converter M6 release predecessor differs")
        release = document.get("release_and_approval", {})
        if release.get("release_scope_kind") != SCOPE_KIND or release.get("approval_action") != APPROVAL_ACTION:
            raise ProtocolError("production-converter release approval contract differs")
        cls._validate_preapproval_authority(document)
        return cls(path, document, sha256_file(path), base)

    @staticmethod
    def _validate_preapproval_authority(document: dict[str, Any]) -> None:
        authority = document.get("authority_before_exact_user_approval", {})
        forbidden = (
            "sealed_effect_semantic_read_authorized", "qlib_provider_mount_or_read_authorized",
            "real_treatment_backtest_authorized", "sealed_control_report_semantic_read_authorized",
            "real_model_fit_authorized", "real_prediction_generation_authorized",
            "formal_effect_output_write_authorized", "experiment_ledger_write_authorized",
            "external_runtime_network_authorized", "env_or_secret_read_authorized",
        )
        if any(authority.get(key) is not False for key in forbidden):
            raise ProtocolError("production-converter preapproval authority is broadened")

    @property
    def is_recovery(self) -> bool:
        return self.document["protocol_id"].endswith(
            ("entrypoint-recovery-v1", "price-recovery-v1")
        )

    @property
    def is_price_recovery(self) -> bool:
        return self.document["protocol_id"].endswith("price-recovery-v1")

    @property
    def scope_kind(self) -> str:
        return str(self.document["release_and_approval"]["release_scope_kind"])

    @property
    def approval_action(self) -> str:
        return str(self.document["release_and_approval"]["approval_action"])

    @property
    def image(self) -> str:
        return str(self.document["docker"]["image"])

    @property
    def runtime_profile(self) -> RuntimeProfile:
        return runtime_profile(str(self.document["protocol_id"]))

    @property
    def runner_command(self) -> list[str]:
        return list(self.runtime_profile.runner_command)

    @property
    def auditor_command(self) -> list[str]:
        return list(self.runtime_profile.auditor_command)

    @property
    def runner_service(self) -> str:
        return self.runtime_profile.runner_service

    @property
    def auditor_service(self) -> str:
        return self.runtime_profile.auditor_service

    @property
    def tracked_release_scope(self) -> str:
        release = self.document["release_and_approval"]
        if "tracked_release_scope" in release:
            return str(release["tracked_release_scope"])
        return str(self.document["artifact_contract"]["tracked_release_scope"])

    @property
    def output_roots(self) -> dict[str, str | bool]:
        artifact = self.document.get("artifact_contract", {})
        return {
            "effect_root": artifact.get(
                "ignored_effect_root",
                "data/research/m6_csi800_production_head30_v1/effect",
            ),
            "audit_root": artifact.get(
                "ignored_audit_root",
                "data/research/m6_csi800_production_head30_v1/effect-audit",
            ),
            "experiment_ledger_write_authorized": False,
        }


def validate_scope(scope: dict[str, Any], protocol: ReleaseProtocol) -> None:
    if (
        scope.get("scope_kind") != protocol.scope_kind
        or scope.get("protocol_id") != protocol.document["protocol_id"]
    ):
        raise ProtocolError("production-converter release scope identity differs")
    if scope.get("protocols") != {
        "converter_sha256": protocol.base.sha256,
        "hash_addendum_sha256": protocol.base.addendum_sha256,
        "release_engineering_sha256": protocol.sha256,
    }:
        raise ProtocolError("production-converter release protocol hashes differ")
    implementation, image = scope.get("implementation", {}), scope.get("image", {})
    commit = implementation.get("git_commit")
    snapshot = implementation.get("code_snapshot_sha256")
    if not isinstance(commit, str) or len(commit) != 40 or implementation.get("origin_main_commit") != commit:
        raise ProtocolError("production-converter implementation is not pushed")
    if image.get("reference") != protocol.image or image.get("git_commit") != commit:
        raise ProtocolError("production-converter image Git identity differs")
    if image.get("code_snapshot_sha256") != snapshot or not str(image.get("image_id", "")).startswith("sha256:"):
        raise ProtocolError("production-converter image content identity differs")
    if image.get("platform") not in {"linux/arm64", "linux/amd64"}:
        raise ProtocolError("production-converter image platform differs")
    if scope.get("authority") != expected_authority():
        raise ProtocolError("production-converter release authority differs")
    inputs = scope.get("inputs", {})
    original = mapping(ORIGINAL_M6_SCOPE)["scope"]["inputs"]
    if inputs.get("qlib") != original:
        raise ProtocolError("production-converter Qlib identity differs")
    for name in ("sealed_m6_effect", "sealed_m6_audit"):
        if not isinstance(inputs.get(name), dict):
            raise ProtocolError(f"production-converter {name} identity is absent")
    if scope.get("execution") != {
        "approval_action": protocol.approval_action,
        "runner_invocation_count": 1,
        "complete_internal_passes": ["first_pass", "replay"],
        "independent_auditor_invocation_count": 1,
        "new_portfolio_attempts_consumed_at_first_treatment_effect_read": 1,
        "model_attempt_increment": 0,
        "same_release_retry_authorized": False,
    }:
        raise ProtocolError("production-converter execution count differs")
    docker = protocol.document["docker"]
    container = scope.get("container", {})
    common = {
        "compose_path": docker["compose_file"], "network_mode": "none",
        "read_only_root": True, "run_as_non_root": True, "cap_drop_all": True,
        "no_new_privileges": True, "env_file_mounted": False,
        "docker_socket_mounted": False, "full_project_root_mounted": False,
        "production_ledger_mounted": False,
    }
    if any(container.get(key) != value for key, value in common.items()):
        raise ProtocolError("production-converter container boundary differs")
    if container.get("compose_sha256") != sha256_file(PROJECT_ROOT / docker["compose_file"]):
        raise ProtocolError("production-converter compose identity differs")
    expected_services = {
        "runner": (
            protocol.runner_service, protocol.runner_command, 4, "8g", 192,
            docker["runner_mounts"],
        ),
        "auditor": (
            protocol.auditor_service, protocol.auditor_command, 2, "4g", 128,
            docker["auditor_mounts"],
        ),
    }
    for role, expected in expected_services.items():
        row = container.get(role, {})
        actual = tuple(row.get(key) for key in ("service", "command", "cpus", "memory", "pids_limit", "mounts"))
        if actual != expected:
            raise ProtocolError(f"production-converter {role} boundary differs")
    if scope.get("outputs") != protocol.output_roots:
        raise ProtocolError("production-converter output boundary differs")


@dataclass(frozen=True)
class ReleaseScope:
    path: Path
    document: dict[str, Any]
    scope: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path, protocol: ReleaseProtocol) -> "ReleaseScope":
        document = mapping(path.resolve())
        if set(document) != {"schema_version", "release_scope_sha256", "scope"}:
            raise ProtocolError("production-converter release document fields differ")
        if document.get("schema_version") != SCOPE_SCHEMA or not isinstance(document.get("scope"), dict):
            raise ProtocolError("production-converter release document schema differs")
        digest = canonical_sha256(document["scope"])
        if document.get("release_scope_sha256") != digest:
            raise ProtocolError("production-converter release self hash differs")
        validate_scope(document["scope"], protocol)
        return cls(path.resolve(), document, document["scope"], digest)

    def verify_runtime_identity(self) -> dict[str, str]:
        expected = self.scope["implementation"]
        actual = {"git_commit": git_head(), "code_snapshot_sha256": code_snapshot_sha256()}
        if actual != {"git_commit": expected["git_commit"], "code_snapshot_sha256": expected["code_snapshot_sha256"]}:
            raise ProtocolError("production-converter runtime identity differs")
        manifest = os.getenv("SHAIWEI_RELEASE_MANIFEST", "").strip()
        if not manifest or sha256_file(Path(manifest)) != self.scope["image"]["release_manifest_sha256"]:
            raise ProtocolError("production-converter embedded manifest differs")
        return actual


@dataclass(frozen=True)
class Approval:
    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path, release: ReleaseScope) -> "Approval":
        document = mapping(path.resolve())
        expected = {
            "schema_version": "m6-production-head30-approval-v1",
            "release_scope_sha256": release.sha256,
            "action": release.scope["execution"]["approval_action"],
            "qlib_read_authorized": True,
            "sealed_m6_effect_read_authorized": True,
            "real_treatment_backtest_authorized": True,
            "sealed_control_report_read_authorized": True,
            "formal_effect_output_write_authorized": True,
            "independent_audit_authorized": True,
            "model_fit_authorized": False,
            "prediction_generation_authorized": False,
            "experiment_ledger_write_authorized": False,
            "external_network_authorized": False,
            "env_or_secret_read_authorized": False,
            "production_authorization": "none",
        }
        if set(document) != set(expected) | {"approved_at", "consumed"}:
            raise ProtocolError("production-converter approval fields differ")
        if any(document.get(key) != value for key, value in expected.items()):
            raise ProtocolError("production-converter approval authority differs")
        if not document.get("approved_at") or document.get("consumed") is not False:
            raise ProtocolError("production-converter approval state differs")
        return cls(path.resolve(), document, sha256_file(path.resolve()))


__all__ = [
    "APPROVAL_ACTION", "AUDITOR_COMMAND", "Approval", "IMAGE", "PRICE_RECOVERY_PROTOCOL",
    "RUNNER_COMMAND",
    "ReleaseProtocol", "ReleaseScope", "SCOPE_KIND", "SCOPE_SCHEMA", "expected_authority",
    "mapping", "validate_scope", "write_once_document",
]

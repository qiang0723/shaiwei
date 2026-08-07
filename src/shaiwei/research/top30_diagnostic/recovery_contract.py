"""Versioned release contracts for the M6 Top30 orchestration recovery."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.model_attribution.contract import sha256_file
from shaiwei.research.top30_diagnostic.contract import (
    PROTOCOL_PATH as BASE_PROTOCOL_PATH,
    Protocol,
    code_bundle_identity,
    mapping,
)
from shaiwei.research.top30_diagnostic.exact import DiagnosticError, canonical_sha256


PROTOCOL_PATH = PROJECT_ROOT / "config/m6_csi800_top30_compatibility_diagnostic_recovery_v2.yaml"
SCOPE_PATH = PROJECT_ROOT / "config/m6_csi800_top30_compatibility_diagnostic_recovery_scope_v2.json"
COMPOSE_PATH = PROJECT_ROOT / "compose.m6-top30-diagnostic-recovery.yaml"
DOCKERFILE_PATH = PROJECT_ROOT / "Dockerfile.m6-top30-diagnostic-recovery"
ACTION = "M6_TOP30_COMPATIBILITY_DIAGNOSTIC_MATRIX_RECOVERY_ONCE"
SCOPE_KIND = "TOP30_COMPATIBILITY_DIAGNOSTIC_RECOVERY_RELEASE_READY_NOT_EXECUTION_APPROVAL"
SCOPE_SCHEMA = "m6-top30-compatibility-diagnostic-recovery-release-scope-v2"
APPROVAL_SCHEMA = "m6-top30-compatibility-diagnostic-recovery-approval-v2"
ORIGINAL_IMAGE = "shaiwei:m6-top30-diagnostic-recovery-original-v2"
CURRENT_IMAGE = "shaiwei:m6-top30-diagnostic-recovery-current-v2"
MANIFEST_PATH = Path("/opt/shaiwei/m6-top30-diagnostic-recovery/release-manifest.json")
OUTPUT_ROOT = "data/research/m6_csi800_top30_compatibility_diagnostic_recovery_v2"
APPROVAL_PATH = "data/control/m6_csi800_top30_compatibility_diagnostic_recovery_v2/approval.json"

ORIGINAL_COMMAND = [
    "python", "-m", "shaiwei.research.top30_diagnostic.recovery_runner",
    "--lane", "original", "--protocol", "/inputs/protocol.yaml",
    "--release", "/inputs/release.json", "--approval", "/inputs/approval.json",
    "--provider-root", "/qlib", "--m6-effect-root", "/m6-effect",
    "--failed-effect-root", "/failed-effect", "--output-root", "/diagnostic/original",
]
CURRENT_COMMAND = [
    "python", "-m", "shaiwei.research.top30_diagnostic.recovery_runner",
    "--lane", "current", "--protocol", "/inputs/protocol.yaml",
    "--release", "/inputs/release.json", "--approval", "/inputs/approval.json",
    "--provider-root", "/qlib", "--m6-effect-root", "/m6-effect",
    "--failed-effect-root", "/failed-effect", "--output-root", "/diagnostic/current",
]
AUDITOR_COMMAND = [
    "python", "-m", "shaiwei.research.top30_diagnostic.recovery_audit",
    "--protocol", "/inputs/protocol.yaml", "--release", "/inputs/release.json",
    "--approval", "/inputs/approval.json", "--canonical-report", "/inputs/canonical.parquet",
    "--original-root", "/diagnostic/original", "--current-root", "/diagnostic/current",
    "--audit-root", "/audit",
]
RUNNER_COMMON_MOUNTS = [
    {"source": "config/m6_csi800_top30_compatibility_diagnostic_recovery_v2.yaml", "target": "/inputs/protocol.yaml", "mode": "ro"},
    {"source": "config/m6_csi800_top30_compatibility_diagnostic_v1.yaml", "target": "/inputs/base-protocol.yaml", "mode": "ro"},
    {"source": "config/m6_csi800_top30_compatibility_diagnostic_recovery_scope_v2.json", "target": "/inputs/release.json", "mode": "ro"},
    {"source": APPROVAL_PATH, "target": "/inputs/approval.json", "mode": "ro"},
    {"source": "data/qlib_bin", "target": "/qlib", "mode": "ro"},
    {"source": "data/research/m6_csi800_model_attribution_v1/effect", "target": "/m6-effect", "mode": "ro"},
    {"source": "data/research/m6_csi800_topk20_conversion_v1/effect", "target": "/failed-effect", "mode": "ro"},
]
ORIGINAL_MOUNTS = [
    *RUNNER_COMMON_MOUNTS,
    {"source": f"{OUTPUT_ROOT}/original", "target": "/diagnostic/original", "mode": "rw"},
]
CURRENT_MOUNTS = [
    *RUNNER_COMMON_MOUNTS,
    {"source": f"{OUTPUT_ROOT}/current", "target": "/diagnostic/current", "mode": "rw"},
]
AUDITOR_MOUNTS = [
    {"source": "config/m6_csi800_top30_compatibility_diagnostic_recovery_v2.yaml", "target": "/inputs/protocol.yaml", "mode": "ro"},
    {"source": "config/m6_csi800_top30_compatibility_diagnostic_v1.yaml", "target": "/inputs/base-protocol.yaml", "mode": "ro"},
    {"source": "config/m6_csi800_top30_compatibility_diagnostic_recovery_scope_v2.json", "target": "/inputs/release.json", "mode": "ro"},
    {"source": APPROVAL_PATH, "target": "/inputs/approval.json", "mode": "ro"},
    {"source": "data/research/m6_csi800_model_attribution_v1/effect/first_pass/W1/backtest/clean_lgbm_control_v1.parquet", "target": "/inputs/canonical.parquet", "mode": "ro"},
    {"source": f"{OUTPUT_ROOT}/original", "target": "/diagnostic/original", "mode": "ro"},
    {"source": f"{OUTPUT_ROOT}/current", "target": "/diagnostic/current", "mode": "ro"},
    {"source": f"{OUTPUT_ROOT}/audit", "target": "/audit", "mode": "rw"},
]
TMPFS = {
    "original": "/tmp:rw,noexec,nosuid,size=1g,mode=1777",
    "current": "/tmp:rw,noexec,nosuid,size=1g,mode=1777",
    "auditor": "/tmp:rw,noexec,nosuid,size=512m,mode=1777",
}


@dataclass(frozen=True)
class RecoveryProtocol:
    path: Path
    recovery_document: dict[str, Any]
    document: dict[str, Any]
    sha256: str
    base: Protocol

    @classmethod
    def load(cls, path: Path = PROTOCOL_PATH) -> "RecoveryProtocol":
        resolved = path.resolve()
        recovery = mapping(resolved, yaml_document=True)
        base_path = (
            BASE_PROTOCOL_PATH
            if resolved == PROTOCOL_PATH.resolve()
            else resolved.parent / "base-protocol.yaml"
        )
        base = Protocol.load(base_path)
        future = recovery.get("future_release_contract", {})
        predecessor = recovery.get("predecessor_failure", {})
        single = recovery.get("single_change_contract", {})
        if recovery.get("protocol_id") != "m6-csi800-top30-compatibility-diagnostic-recovery-v2":
            raise DiagnosticError("Top30 recovery protocol identity differs")
        if recovery.get("stage") != "RESULT_BLIND_ORCHESTRATION_RECOVERY_PROTOCOL_FREEZE_ONLY":
            raise DiagnosticError("Top30 recovery protocol stage differs")
        if predecessor.get("protocol_sha256") != base.sha256 or predecessor.get("top30_backtest_count") != 0:
            raise DiagnosticError("Top30 recovery predecessor identity differs")
        if predecessor.get("same_scope_retry_authorized") is not False:
            raise DiagnosticError("Top30 recovery predecessor retry boundary differs")
        if single.get("tmpfs") != {**TMPFS, "yaml_list_cardinality_each_service": 1,
                                    "docker_compose_expansion_cardinality_each_service": 1}:
            raise DiagnosticError("Top30 recovery single-change tmpfs contract differs")
        if future.get("scope_kind") != SCOPE_KIND or future.get("approval_action") != ACTION:
            raise DiagnosticError("Top30 recovery future release contract differs")
        if future.get("total_top30_backtest_count") != 6 or future.get("top20_backtest_count") != 0:
            raise DiagnosticError("Top30 recovery execution matrix differs")
        authority = recovery.get("authority", {})
        prohibited = (
            "real_qlib_read_authorized", "sealed_prediction_or_report_read_authorized",
            "failed_release_evidence_semantic_read_authorized", "real_top30_diagnostic_backtest_authorized",
            "real_top20_read_or_backtest_authorized", "model_fit_authorized",
            "prediction_generation_authorized", "experiment_ledger_write_authorized",
            "external_network_authorized", "env_or_secret_read_authorized",
        )
        if any(authority.get(key) is not False for key in prohibited):
            raise DiagnosticError("Top30 recovery preapproval authority differs")
        return cls(resolved, recovery, base.document, sha256_file(resolved), base)


def expected_preapproval_authority() -> dict[str, Any]:
    return {
        "release_ready": True,
        "execution_authorized": False,
        "real_qlib_read_authorized": False,
        "sealed_prediction_or_report_read_authorized": False,
        "real_top30_diagnostic_backtest_authorized": False,
        "real_top20_read_or_backtest_authorized": False,
        "model_fit_authorized": False,
        "prediction_generation_authorized": False,
        "experiment_ledger_write_authorized": False,
        "external_network_authorized": False,
        "env_or_secret_read_authorized": False,
        "production_authorization": "none",
    }


def expected_inputs(protocol: RecoveryProtocol) -> dict[str, Any]:
    frozen = protocol.document["frozen_runtime_inputs"]
    case = protocol.document["frozen_diagnostic_case"]
    failed = protocol.document["failed_release"]
    return {
        "qlib": {key: frozen[key] for key in (
            "qlib_manifest_sha256", "qlib_tree_sha256", "qlib_file_count",
            "calendar_sha256", "calendar_row_count",
        )},
        "sealed_m6_effect": {
            "file_count": 199, "total_bytes": 84957571,
            "tree_sha256": "dfbc0b52f40250b7151d74d9a45f3fdc17a69ca1f7b9c853267c1071b4b0d5cb",
        },
        "failed_m6_3c_effect": {
            "file_count": failed["effect_file_count"], "total_bytes": failed["effect_total_bytes"],
            "tree_sha256": failed["effect_tree_sha256"],
        },
        "case_files": {key: dict(case[key]) for key in (
            "prediction", "canonical_report", "canonical_schedule",
        )},
    }


def expected_container() -> dict[str, Any]:
    return {
        "compose_path": COMPOSE_PATH.name,
        "compose_sha256": sha256_file(COMPOSE_PATH),
        "network_mode": "none", "read_only_root": True, "run_as_non_root": True,
        "cap_drop_all": True, "no_new_privileges": True, "env_file_mounted": False,
        "docker_socket_mounted": False, "full_project_root_mounted": False,
        "production_ledger_mounted": False,
        "tmpfs": TMPFS,
        "fixture_real_input_mount_count": 0,
        "services": {
            "original": {"service": "m6-top30-diagnostic-recovery-original", "image": ORIGINAL_IMAGE,
                         "command": ORIGINAL_COMMAND, "mounts": ORIGINAL_MOUNTS,
                         "cpus": 2, "memory": "4g", "pids_limit": 128},
            "current": {"service": "m6-top30-diagnostic-recovery-current", "image": CURRENT_IMAGE,
                        "command": CURRENT_COMMAND, "mounts": CURRENT_MOUNTS,
                        "cpus": 2, "memory": "4g", "pids_limit": 128},
            "auditor": {"service": "m6-top30-diagnostic-recovery-auditor", "image": CURRENT_IMAGE,
                        "command": AUDITOR_COMMAND, "mounts": AUDITOR_MOUNTS,
                        "cpus": 1, "memory": "2g", "pids_limit": 64, "qlib_mounted": False},
        },
    }


def _validate_scope(scope: dict[str, Any], protocol: RecoveryProtocol) -> None:
    if scope.get("scope_kind") != SCOPE_KIND or scope.get("protocol_id") != protocol.recovery_document["protocol_id"]:
        raise DiagnosticError("Top30 recovery release identity differs")
    if scope.get("protocol_sha256") != protocol.sha256 or scope.get("base_protocol_sha256") != protocol.base.sha256:
        raise DiagnosticError("Top30 recovery protocol hash differs")
    if scope.get("predecessor_failure") != protocol.recovery_document["predecessor_failure"]:
        raise DiagnosticError("Top30 recovery predecessor evidence differs")
    if scope.get("authority") != expected_preapproval_authority():
        raise DiagnosticError("Top30 recovery preapproval authority differs")
    implementation = scope.get("implementation", {})
    bundle = code_bundle_identity()
    commit = implementation.get("git_commit")
    if (
        not isinstance(commit, str) or len(commit) != 40
        or implementation.get("origin_main_commit") != commit
        or implementation.get("code_bundle_sha256") != bundle["sha256"]
        or implementation.get("code_bundle_file_count") != bundle["file_count"]
        or implementation.get("dockerfile_sha256") != sha256_file(DOCKERFILE_PATH)
        or implementation.get("compose_sha256") != sha256_file(COMPOSE_PATH)
    ):
        raise DiagnosticError("Top30 recovery implementation identity differs")
    expected_execution = {
        "approval_action": ACTION, "original_runner_invocation_count": 1,
        "current_runner_invocation_count": 1, "independent_auditor_invocation_count": 1,
        "total_top30_backtest_count": 6, "top20_backtest_count": 0,
        "research_attempt_increment": 0, "same_release_retry_authorized": False,
    }
    if scope.get("execution") != expected_execution or scope.get("inputs") != expected_inputs(protocol):
        raise DiagnosticError("Top30 recovery execution or input contract differs")
    if scope.get("container") != expected_container():
        raise DiagnosticError("Top30 recovery container boundary differs")
    outputs = {"root": OUTPUT_ROOT, "original": f"{OUTPUT_ROOT}/original",
               "current": f"{OUTPUT_ROOT}/current", "audit": f"{OUTPUT_ROOT}/audit",
               "experiment_ledger_write_authorized": False}
    if scope.get("outputs") != outputs:
        raise DiagnosticError("Top30 recovery output boundary differs")
    for role, reference in (("original", ORIGINAL_IMAGE), ("current", CURRENT_IMAGE)):
        image = scope.get("images", {}).get(role, {})
        if image.get("reference") != reference or not str(image.get("image_id", "")).startswith("sha256:"):
            raise DiagnosticError("Top30 recovery wrapper image identity differs")
        if image.get("git_commit") != commit or image.get("code_bundle_sha256") != bundle["sha256"]:
            raise DiagnosticError("Top30 recovery wrapper implementation differs")


@dataclass(frozen=True)
class RecoveryReleaseScope:
    path: Path
    document: dict[str, Any]
    scope: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path, protocol: RecoveryProtocol) -> "RecoveryReleaseScope":
        document = mapping(path.resolve())
        if set(document) != {"schema_version", "diagnostic_scope_sha256", "scope"}:
            raise DiagnosticError("Top30 recovery release document fields differ")
        if document.get("schema_version") != SCOPE_SCHEMA or not isinstance(document.get("scope"), dict):
            raise DiagnosticError("Top30 recovery release schema differs")
        digest = canonical_sha256(document["scope"])
        if document.get("diagnostic_scope_sha256") != digest:
            raise DiagnosticError("Top30 recovery release self hash differs")
        _validate_scope(document["scope"], protocol)
        return cls(path.resolve(), document, document["scope"], digest)


@dataclass(frozen=True)
class RecoveryApproval:
    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path, release: RecoveryReleaseScope) -> "RecoveryApproval":
        document = mapping(path.resolve())
        expected = {
            "schema_version": APPROVAL_SCHEMA, "diagnostic_scope_sha256": release.sha256,
            "action": ACTION, "real_qlib_read_authorized": True,
            "sealed_prediction_or_report_read_authorized": True,
            "failed_release_evidence_read_authorized": True,
            "real_top30_diagnostic_backtest_authorized": True,
            "real_top20_read_or_backtest_authorized": False, "model_fit_authorized": False,
            "prediction_generation_authorized": False, "experiment_ledger_write_authorized": False,
            "external_network_authorized": False, "env_or_secret_read_authorized": False,
            "production_authorization": "none",
        }
        if set(document) != set(expected) | {"approved_at", "consumed"}:
            raise DiagnosticError("Top30 recovery approval fields differ")
        if any(document.get(key) != value for key, value in expected.items()):
            raise DiagnosticError("Top30 recovery approval authority differs")
        if not document.get("approved_at") or document.get("consumed") is not False:
            raise DiagnosticError("Top30 recovery approval state differs")
        return cls(path.resolve(), document, sha256_file(path.resolve()))


def runtime_identity(release: RecoveryReleaseScope, role: str) -> dict[str, str]:
    if role not in {"original", "current"}:
        raise DiagnosticError("Top30 recovery runtime role differs")
    image = release.scope["images"][role]
    actual = {
        "git_commit": os.getenv("SHAIWEI_M6_TOP30_RECOVERY_GIT_HEAD", ""),
        "role": os.getenv("SHAIWEI_M6_TOP30_RECOVERY_ROLE", ""),
        "base_image_id": os.getenv("SHAIWEI_M6_TOP30_RECOVERY_BASE_IMAGE_ID", ""),
        "code_bundle_sha256": code_bundle_identity()["sha256"],
        "release_manifest_sha256": sha256_file(MANIFEST_PATH),
    }
    expected = {key: image[key] for key in (
        "git_commit", "role", "base_image_id", "code_bundle_sha256", "release_manifest_sha256",
    )}
    if actual != expected:
        raise DiagnosticError("Top30 recovery runtime identity differs")
    manifest = mapping(MANIFEST_PATH)
    if manifest != {"schema_version": "m6-top30-diagnostic-recovery-image-manifest-v2",
                    **{key: actual[key] for key in (
                        "git_commit", "role", "base_image_id", "code_bundle_sha256",
                    )}}:
        raise DiagnosticError("Top30 recovery image manifest differs")
    return actual

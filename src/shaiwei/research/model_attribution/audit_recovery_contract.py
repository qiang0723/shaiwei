"""M6 auditor-entrypoint recovery protocol, scope, approval, and tree identity."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.model_attribution.contract import (
    AttributionError,
    canonical_json,
    canonical_sha256,
    sha256_file,
)


RECOVERY_PROTOCOL_PATH = (
    PROJECT_ROOT / "config/m6_csi800_model_attribution_audit_entrypoint_recovery_v1.yaml"
)
RECOVERY_SCOPE_PATH = (
    PROJECT_ROOT / "config/m6_csi800_model_attribution_audit_recovery_scope_v1.json"
)
RECOVERY_COMPOSE_PATH = PROJECT_ROOT / "compose.m6-audit-recovery.yaml"
RECOVERY_ACTION = "M6_INDEPENDENT_AUDIT_ENTRYPOINT_RECOVERY_ONCE"
RECOVERY_SCOPE_KIND = "AUDITOR_ENTRYPOINT_RECOVERY_READY_NOT_EXECUTION_APPROVAL"
RECOVERY_IMAGE = "shaiwei:m6-audit-entrypoint-recovery-v1"


RECOVERY_COMMAND = [
    "python", "/opt/shaiwei/m6-audit-recovery/entrypoint.py",
    "--recovery-protocol", "/inputs/recovery-protocol.yaml",
    "--recovery-release", "/inputs/recovery-release.json",
    "--recovery-approval", "/inputs/recovery-approval.json",
    "--recovery-compose", "/inputs/recovery-compose.yaml",
    "--original-release", "/inputs/original-release.json",
    "--original-approval", "/inputs/original-approval.json",
    "--effect-root", "/outputs", "--audit-root", "/audit",
]

RECOVERY_MOUNTS = [
    {"source": "config/m6_csi800_model_attribution_audit_entrypoint_recovery_v1.yaml", "target": "/inputs/recovery-protocol.yaml", "mode": "ro"},
    {"source": "config/m6_csi800_model_attribution_audit_recovery_scope_v1.json", "target": "/inputs/recovery-release.json", "mode": "ro"},
    {"source": "data/control/m6_csi800_model_attribution_v1/audit-recovery-approval.json", "target": "/inputs/recovery-approval.json", "mode": "ro"},
    {"source": "compose.m6-audit-recovery.yaml", "target": "/inputs/recovery-compose.yaml", "mode": "ro"},
    {"source": "config/m6_csi800_model_attribution_release_scope_v1.json", "target": "/inputs/original-release.json", "mode": "ro"},
    {"source": "data/control/m6_csi800_model_attribution_v1/approval.json", "target": "/inputs/original-approval.json", "mode": "ro"},
    {"source": "data/research/m6_csi800_model_attribution_v1/effect", "target": "/outputs", "mode": "ro"},
    {"source": "data/research/m6_csi800_model_attribution_v1/effect-audit", "target": "/audit", "mode": "rw"},
]


def _mapping(path: Path, *, yaml_document: bool = False) -> dict[str, Any]:
    try:
        value = (
            yaml.safe_load(path.read_text(encoding="utf-8"))
            if yaml_document
            else json.loads(path.read_text(encoding="utf-8"))
        )
    except (OSError, ValueError, yaml.YAMLError) as error:
        raise AttributionError(f"M6 audit recovery document is invalid: {path.name}") from error
    if not isinstance(value, dict):
        raise AttributionError(f"M6 audit recovery document is not a mapping: {path.name}")
    return value


def _sha(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _validate_protocol(document: dict[str, Any]) -> None:
    if document.get("schema_version") != "m6-model-attribution-audit-entrypoint-recovery-v1":
        raise AttributionError("M6 audit recovery protocol schema differs")
    if document.get("recovery_id") != "m6-csi800-model-attribution-audit-entrypoint-recovery-v1":
        raise AttributionError("M6 audit recovery protocol identity differs")
    if document.get("status") != "FROZEN_AFTER_RUNNER_BEFORE_AUDIT_RECOVERY_IMPLEMENTATION":
        raise AttributionError("M6 audit recovery protocol stage differs")
    objective = document.get("objective", {})
    if objective != {
        "recover_exactly_one_independent_audit_of_the_existing_sealed_effect_tree": True,
        "research_question_or_result_change": False,
        "runner_or_effect_recomputation": False,
    }:
        raise AttributionError("M6 audit recovery objective differs")
    original = document.get("original_authority", {})
    required_original_hashes = (
        "release_scope_sha256",
        "release_document_sha256",
        "approval_sha256",
        "base_runtime_code_snapshot_sha256",
    )
    if any(not _sha(original.get(key)) for key in required_original_hashes):
        raise AttributionError("M6 audit recovery original identity is invalid")
    if not str(original.get("base_image_id", "")).startswith("sha256:"):
        raise AttributionError("M6 audit recovery base image identity is invalid")
    sealed = document.get("sealed_runner_state", {})
    required_sealed_hashes = (
        "effect_tree_sha256",
        "report_sha256",
        "authorization_sha256",
        "effect_read_marker_sha256",
        "first_pass_manifest_sha256",
        "replay_manifest_sha256",
    )
    if any(not _sha(sealed.get(key)) for key in required_sealed_hashes):
        raise AttributionError("M6 audit recovery sealed identity is invalid")
    if sealed.get("first_pass_manifest_sha256") != sealed.get("replay_manifest_sha256"):
        raise AttributionError("M6 audit recovery pass manifests differ")
    if (
        sealed.get("runner_invocation_count") != 1
        or sealed.get("alternative_attempts_consumed") != 2
        or sealed.get("same_release_runner_retry_authorized") is not False
        or sealed.get("failure_document_exists") is not False
        or int(sealed.get("effect_file_count", 0)) <= 0
        or int(sealed.get("effect_total_bytes", 0)) <= 0
    ):
        raise AttributionError("M6 audit recovery sealed runner state differs")
    failed = document.get("failed_auditor_state", {})
    if (
        failed.get("process_invocation_count") != 1
        or failed.get("audit_function_entered") is not False
        or failed.get("sealed_effect_semantics_read_by_auditor") is not False
        or failed.get("audit_output_file_count") != 0
        or failed.get("same_release_auditor_retry_authorized") is not False
    ):
        raise AttributionError("M6 failed auditor state differs")
    change = document.get("authorized_change", {})
    if (
        change.get("effect_metric_statistic_threshold_or_decision_change") is not False
        or change.get("original_report_or_artifact_rewrite") is not False
    ):
        raise AttributionError("M6 audit recovery research semantics were broadened")
    requirements = document.get("recovery_release_requirements", {})
    exact = {
        "scope_kind": RECOVERY_SCOPE_KIND,
        "approval_action": RECOVERY_ACTION,
        "network_mode": "none",
        "qlib_mount": False,
        "effect_mount": "ro",
        "audit_mount": "rw",
        "full_project_root_mount": False,
        "env_or_secret_mount": False,
        "docker_socket_mount": False,
        "production_ledger_mount": False,
        "run_as_non_root": True,
        "read_only_root": True,
        "cap_drop_all": True,
        "no_new_privileges": True,
        "cpus": 2,
        "memory": "4g",
        "pids_limit": 256,
    }
    if any(requirements.get(key) != value for key, value in exact.items()):
        raise AttributionError("M6 audit recovery runtime boundary differs")
    if document.get("production_authorization") != "none":
        raise AttributionError("M6 audit recovery cannot authorize production")


@dataclass(frozen=True)
class RecoveryProtocol:
    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path = RECOVERY_PROTOCOL_PATH) -> "RecoveryProtocol":
        resolved = path.resolve()
        document = _mapping(resolved, yaml_document=True)
        _validate_protocol(document)
        return cls(path=resolved, document=document, sha256=sha256_file(resolved))


def effect_tree_identity(root: Path) -> dict[str, Any]:
    if not root.is_dir():
        raise AttributionError("M6 sealed effect root is absent")
    rows: list[dict[str, Any]] = []
    total_bytes = 0
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if path.is_symlink():
            raise AttributionError("M6 sealed effect tree contains a symlink")
        size = path.stat().st_size
        rows.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": sha256_file(path),
                "size": size,
            }
        )
        total_bytes += size
    if not rows:
        raise AttributionError("M6 sealed effect tree is empty")
    return {
        "file_count": len(rows),
        "total_bytes": total_bytes,
        "tree_sha256": hashlib.sha256(canonical_json(rows)).hexdigest(),
    }


def _expected_authority() -> dict[str, Any]:
    return {
        "release_ready": True,
        "execution_authorized": False,
        "sealed_effect_read_authorized": False,
        "independent_audit_write_authorized": False,
        "qlib_mount_authorized": False,
        "real_model_fit_authorized": False,
        "real_prediction_authorized": False,
        "real_backtest_authorized": False,
        "experiment_ledger_write_authorized": False,
        "external_network_authorized": False,
        "env_or_secret_read_authorized": False,
        "forward_signal_authorized": False,
        "paper_portfolio_authorized": False,
        "production_authorization": "none",
    }


def _validate_scope(scope: dict[str, Any], protocol: RecoveryProtocol, compose_path: Path) -> None:
    if scope.get("scope_kind") != RECOVERY_SCOPE_KIND:
        raise AttributionError("M6 audit recovery scope kind differs")
    if scope.get("recovery_id") != protocol.document["recovery_id"]:
        raise AttributionError("M6 audit recovery scope identity differs")
    if scope.get("protocol_sha256") != protocol.sha256:
        raise AttributionError("M6 audit recovery protocol hash differs")
    original = protocol.document["original_authority"]
    if scope.get("original_authority") != original:
        raise AttributionError("M6 audit recovery original authority differs")
    sealed_protocol = protocol.document["sealed_runner_state"]
    expected_sealed = {
        "effect_root": "data/research/m6_csi800_model_attribution_v1/effect",
        "audit_root": "data/research/m6_csi800_model_attribution_v1/effect-audit",
        "file_count": sealed_protocol["effect_file_count"],
        "total_bytes": sealed_protocol["effect_total_bytes"],
        "tree_sha256": sealed_protocol["effect_tree_sha256"],
        "report_sha256": sealed_protocol["report_sha256"],
        "authorization_sha256": sealed_protocol["authorization_sha256"],
        "effect_read_marker_sha256": sealed_protocol["effect_read_marker_sha256"],
        "first_pass_manifest_sha256": sealed_protocol["first_pass_manifest_sha256"],
        "replay_manifest_sha256": sealed_protocol["replay_manifest_sha256"],
    }
    if scope.get("sealed_effect") != expected_sealed:
        raise AttributionError("M6 audit recovery sealed effect identity differs")
    implementation = scope.get("implementation", {})
    commit = implementation.get("git_commit")
    if not isinstance(commit, str) or len(commit) != 40:
        raise AttributionError("M6 audit recovery implementation commit is invalid")
    if implementation.get("origin_main_commit") != commit:
        raise AttributionError("M6 audit recovery implementation is not on origin/main")
    for key in ("contract_sha256", "entrypoint_sha256", "dockerfile_sha256"):
        if not _sha(implementation.get(key)):
            raise AttributionError("M6 audit recovery implementation file identity is invalid")
    image = scope.get("image", {})
    if (
        image.get("reference") != RECOVERY_IMAGE
        or image.get("base_reference") != original["base_image_reference"]
        or image.get("base_image_id") != original["base_image_id"]
        or image.get("git_commit") != commit
        or image.get("contract_sha256") != implementation["contract_sha256"]
        or image.get("entrypoint_sha256") != implementation["entrypoint_sha256"]
        or not str(image.get("image_id", "")).startswith("sha256:")
        or image.get("platform") not in {"linux/arm64", "linux/amd64"}
    ):
        raise AttributionError("M6 audit recovery image identity differs")
    if scope.get("authority") != _expected_authority():
        raise AttributionError("M6 audit recovery preapproval authority differs")
    if scope.get("execution") != {
        "approval_action": RECOVERY_ACTION,
        "runner_invocation_count": 0,
        "recovery_auditor_invocation_count": 1,
        "additional_alternative_attempt_count": 0,
        "same_recovery_retry_authorized": False,
    }:
        raise AttributionError("M6 audit recovery execution count differs")
    container = scope.get("container", {})
    expected_container = {
        "compose_path": "compose.m6-audit-recovery.yaml",
        "compose_sha256": sha256_file(compose_path),
        "network_mode": "none",
        "read_only_root": True,
        "run_as_non_root": True,
        "cap_drop_all": True,
        "no_new_privileges": True,
        "env_file_mounted": False,
        "docker_socket_mounted": False,
        "full_project_root_mounted": False,
        "qlib_mounted": False,
        "production_ledger_mounted": False,
        "service": "m6-audit-recovery",
        "command": RECOVERY_COMMAND,
        "mounts": RECOVERY_MOUNTS,
        "cpus": 2,
        "memory": "4g",
        "pids_limit": 256,
    }
    if container != expected_container:
        raise AttributionError("M6 audit recovery container boundary differs")


@dataclass(frozen=True)
class RecoveryReleaseScope:
    path: Path
    scope: dict[str, Any]
    sha256: str

    @classmethod
    def load(
        cls,
        path: Path,
        protocol: RecoveryProtocol,
        *,
        compose_path: Path = RECOVERY_COMPOSE_PATH,
    ) -> "RecoveryReleaseScope":
        document = _mapping(path.resolve())
        if set(document) != {"schema_version", "recovery_scope_sha256", "scope"}:
            raise AttributionError("M6 audit recovery scope document fields differ")
        if document.get("schema_version") != "m6-model-attribution-audit-recovery-scope-v1":
            raise AttributionError("M6 audit recovery scope schema differs")
        scope = document.get("scope")
        if not isinstance(scope, dict) or document.get("recovery_scope_sha256") != canonical_sha256(scope):
            raise AttributionError("M6 audit recovery scope self hash differs")
        _validate_scope(scope, protocol, compose_path.resolve())
        return cls(path=path.resolve(), scope=scope, sha256=document["recovery_scope_sha256"])


@dataclass(frozen=True)
class RecoveryApproval:
    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path, release: RecoveryReleaseScope) -> "RecoveryApproval":
        document = _mapping(path.resolve())
        expected = {
            "schema_version": "m6-model-attribution-audit-recovery-approval-v1",
            "recovery_scope_sha256": release.sha256,
            "action": RECOVERY_ACTION,
            "sealed_effect_read_authorized": True,
            "independent_audit_write_authorized": True,
            "qlib_mount_authorized": False,
            "runner_invocation_authorized": False,
            "model_fit_prediction_backtest_authorized": False,
            "experiment_ledger_write_authorized": False,
            "external_network_authorized": False,
            "env_or_secret_read_authorized": False,
            "production_authorization": "none",
        }
        if set(document) != set(expected) | {"approved_at", "consumed"}:
            raise AttributionError("M6 audit recovery approval fields differ")
        if any(document.get(key) != value for key, value in expected.items()):
            raise AttributionError("M6 audit recovery approval authority differs")
        if not isinstance(document.get("approved_at"), str) or not document["approved_at"]:
            raise AttributionError("M6 audit recovery approval time is absent")
        if document.get("consumed") is not False:
            raise AttributionError("M6 audit recovery approval is consumed or malformed")
        return cls(path=path.resolve(), document=document, sha256=sha256_file(path.resolve()))

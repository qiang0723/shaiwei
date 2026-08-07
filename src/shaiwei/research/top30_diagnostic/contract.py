"""Protocol, release, approval, and runtime contracts for M6-3C-R1."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.model_attribution.contract import sha256_file
from shaiwei.research.model_attribution.effect_contract import write_once_document
from shaiwei.research.top30_diagnostic.exact import DiagnosticError, canonical_json, canonical_sha256


PROTOCOL_PATH = PROJECT_ROOT / "config/m6_csi800_top30_compatibility_diagnostic_v1.yaml"
SCOPE_PATH = PROJECT_ROOT / "config/m6_csi800_top30_compatibility_diagnostic_scope_v1.json"
COMPOSE_PATH = PROJECT_ROOT / "compose.m6-top30-diagnostic.yaml"
ACTION = "M6_TOP30_COMPATIBILITY_DIAGNOSTIC_MATRIX_ONCE"
SCOPE_KIND = "TOP30_COMPATIBILITY_DIAGNOSTIC_RELEASE_READY_NOT_EXECUTION_APPROVAL"
SCOPE_SCHEMA = "m6-top30-compatibility-diagnostic-release-scope-v1"
APPROVAL_SCHEMA = "m6-top30-compatibility-diagnostic-approval-v1"
ORIGINAL_IMAGE = "shaiwei:m6-top30-diagnostic-original-v1"
CURRENT_IMAGE = "shaiwei:m6-top30-diagnostic-current-v1"
MANIFEST_PATH = Path("/opt/shaiwei/m6-top30-diagnostic/release-manifest.json")

ORIGINAL_COMMAND = [
    "python", "-m", "shaiwei.research.top30_diagnostic.runner",
    "--lane", "original", "--protocol", "/inputs/protocol.yaml",
    "--release", "/inputs/release.json", "--approval", "/inputs/approval.json",
    "--provider-root", "/qlib", "--m6-effect-root", "/m6-effect",
    "--failed-effect-root", "/failed-effect", "--output-root", "/diagnostic/original",
]
CURRENT_COMMAND = [
    "python", "-m", "shaiwei.research.top30_diagnostic.runner",
    "--lane", "current", "--protocol", "/inputs/protocol.yaml",
    "--release", "/inputs/release.json", "--approval", "/inputs/approval.json",
    "--provider-root", "/qlib", "--m6-effect-root", "/m6-effect",
    "--failed-effect-root", "/failed-effect", "--output-root", "/diagnostic/current",
]
AUDITOR_COMMAND = [
    "python", "-m", "shaiwei.research.top30_diagnostic.audit",
    "--protocol", "/inputs/protocol.yaml", "--release", "/inputs/release.json",
    "--approval", "/inputs/approval.json", "--canonical-report", "/inputs/canonical.parquet",
    "--original-root", "/diagnostic/original", "--current-root", "/diagnostic/current",
    "--audit-root", "/audit",
]
RUNNER_COMMON_MOUNTS = [
    {"source": "config/m6_csi800_top30_compatibility_diagnostic_v1.yaml", "target": "/inputs/protocol.yaml", "mode": "ro"},
    {"source": "config/m6_csi800_top30_compatibility_diagnostic_scope_v1.json", "target": "/inputs/release.json", "mode": "ro"},
    {"source": "data/control/m6_csi800_top30_compatibility_diagnostic_v1/approval.json", "target": "/inputs/approval.json", "mode": "ro"},
    {"source": "data/qlib_bin", "target": "/qlib", "mode": "ro"},
    {"source": "data/research/m6_csi800_model_attribution_v1/effect", "target": "/m6-effect", "mode": "ro"},
    {"source": "data/research/m6_csi800_topk20_conversion_v1/effect", "target": "/failed-effect", "mode": "ro"},
]
ORIGINAL_MOUNTS = [
    *RUNNER_COMMON_MOUNTS,
    {"source": "data/research/m6_csi800_top30_compatibility_diagnostic_v1/original", "target": "/diagnostic/original", "mode": "rw"},
]
CURRENT_MOUNTS = [
    *RUNNER_COMMON_MOUNTS,
    {"source": "data/research/m6_csi800_top30_compatibility_diagnostic_v1/current", "target": "/diagnostic/current", "mode": "rw"},
]
AUDITOR_MOUNTS = [
    {"source": "config/m6_csi800_top30_compatibility_diagnostic_v1.yaml", "target": "/inputs/protocol.yaml", "mode": "ro"},
    {"source": "config/m6_csi800_top30_compatibility_diagnostic_scope_v1.json", "target": "/inputs/release.json", "mode": "ro"},
    {"source": "data/control/m6_csi800_top30_compatibility_diagnostic_v1/approval.json", "target": "/inputs/approval.json", "mode": "ro"},
    {"source": "data/research/m6_csi800_model_attribution_v1/effect/first_pass/W1/backtest/clean_lgbm_control_v1.parquet", "target": "/inputs/canonical.parquet", "mode": "ro"},
    {"source": "data/research/m6_csi800_top30_compatibility_diagnostic_v1/original", "target": "/diagnostic/original", "mode": "ro"},
    {"source": "data/research/m6_csi800_top30_compatibility_diagnostic_v1/current", "target": "/diagnostic/current", "mode": "ro"},
    {"source": "data/research/m6_csi800_top30_compatibility_diagnostic_v1/audit", "target": "/audit", "mode": "rw"},
]


def mapping(path: Path, *, yaml_document: bool = False) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
        value = yaml.safe_load(raw) if yaml_document else json.loads(raw)
    except (OSError, ValueError, yaml.YAMLError) as error:
        raise DiagnosticError(f"Top30 diagnostic document is invalid: {path.name}") from error
    if not isinstance(value, dict):
        raise DiagnosticError(f"Top30 diagnostic document is not a mapping: {path.name}")
    return value


def tree_identity(root: Path) -> dict[str, Any]:
    if not root.is_dir():
        raise DiagnosticError("Top30 diagnostic input tree is absent")
    rows: list[dict[str, Any]] = []
    total = 0
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if path.is_symlink():
            raise DiagnosticError("Top30 diagnostic input tree contains a symlink")
        size = path.stat().st_size
        rows.append({"path": path.relative_to(root).as_posix(), "sha256": sha256_file(path), "size": size})
        total += size
    if not rows:
        raise DiagnosticError("Top30 diagnostic input tree is empty")
    return {
        "file_count": len(rows),
        "total_bytes": total,
        "tree_sha256": hashlib.sha256(canonical_json(rows)).hexdigest(),
    }


def code_bundle_identity(root: Path | None = None) -> dict[str, Any]:
    base = root or Path(__file__).resolve().parent
    rows = [
        {"path": path.name, "sha256": sha256_file(path), "size": path.stat().st_size}
        for path in sorted(base.glob("*.py"))
        if path.is_file()
    ]
    if not rows:
        raise DiagnosticError("Top30 diagnostic code bundle is empty")
    return {"file_count": len(rows), "sha256": canonical_sha256(rows), "files": rows}


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


@dataclass(frozen=True)
class Protocol:
    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path = PROTOCOL_PATH) -> "Protocol":
        resolved = path.resolve()
        document = mapping(resolved, yaml_document=True)
        if document.get("protocol_id") != "m6-csi800-top30-compatibility-diagnostic-v1":
            raise DiagnosticError("Top30 diagnostic protocol identity differs")
        if document.get("stage") != "RESULT_BLIND_DIAGNOSTIC_PROTOCOL_FREEZE_ONLY":
            raise DiagnosticError("Top30 diagnostic protocol stage differs")
        matrix = document.get("diagnostic_matrix", {})
        if matrix.get("total_top30_backtest_count") != 6 or matrix.get("top20_backtest_count") != 0:
            raise DiagnosticError("Top30 diagnostic execution matrix differs")
        requirements = document.get("future_release_requirements", {})
        if requirements.get("scope_kind") != SCOPE_KIND or requirements.get("approval_action") != ACTION:
            raise DiagnosticError("Top30 diagnostic approval contract differs")
        if document.get("stop_condition", {}).get("top20_remains_prohibited_after_diagnostic") is not True:
            raise DiagnosticError("Top30 diagnostic Top20 stop is absent")
        return cls(resolved, document, sha256_file(resolved))


def _validate_scope(scope: dict[str, Any], protocol: Protocol) -> None:
    if scope.get("scope_kind") != SCOPE_KIND or scope.get("protocol_id") != protocol.document["protocol_id"]:
        raise DiagnosticError("Top30 diagnostic release identity differs")
    if scope.get("protocol_sha256") != protocol.sha256:
        raise DiagnosticError("Top30 diagnostic protocol hash differs")
    if scope.get("authority") != expected_preapproval_authority():
        raise DiagnosticError("Top30 diagnostic preapproval authority differs")
    implementation = scope.get("implementation", {})
    commit = implementation.get("git_commit")
    bundle = code_bundle_identity()
    if (
        not isinstance(commit, str)
        or len(commit) != 40
        or implementation.get("origin_main_commit") != commit
        or implementation.get("code_bundle_sha256") != bundle["sha256"]
        or implementation.get("code_bundle_file_count") != bundle["file_count"]
        or implementation.get("dockerfile_sha256") != sha256_file(PROJECT_ROOT / "Dockerfile.m6-top30-diagnostic")
        or implementation.get("compose_sha256") != sha256_file(COMPOSE_PATH)
    ):
        raise DiagnosticError("Top30 diagnostic implementation identity differs")
    execution = scope.get("execution", {})
    if execution != {
        "approval_action": ACTION,
        "original_runner_invocation_count": 1,
        "current_runner_invocation_count": 1,
        "independent_auditor_invocation_count": 1,
        "total_top30_backtest_count": 6,
        "top20_backtest_count": 0,
        "research_attempt_increment": 0,
        "same_release_retry_authorized": False,
    }:
        raise DiagnosticError("Top30 diagnostic execution count differs")
    images = scope.get("images", {})
    for role, reference in (("original", ORIGINAL_IMAGE), ("current", CURRENT_IMAGE)):
        image = images.get(role, {})
        if image.get("reference") != reference or not str(image.get("image_id", "")).startswith("sha256:"):
            raise DiagnosticError("Top30 diagnostic wrapper image identity differs")
        if image.get("git_commit") != scope.get("implementation", {}).get("git_commit"):
            raise DiagnosticError("Top30 diagnostic wrapper Git identity differs")
        if image.get("code_bundle_sha256") != scope.get("implementation", {}).get("code_bundle_sha256"):
            raise DiagnosticError("Top30 diagnostic wrapper code identity differs")
        if not str(image.get("base_image_id", "")).startswith("sha256:"):
            raise DiagnosticError("Top30 diagnostic base image identity differs")
        if not isinstance(image.get("release_manifest_sha256"), str):
            raise DiagnosticError("Top30 diagnostic image manifest identity differs")
    frozen = protocol.document["frozen_runtime_inputs"]
    case = protocol.document["frozen_diagnostic_case"]
    failed = protocol.document["failed_release"]
    expected_inputs = {
        "qlib": {
            key: frozen[key]
            for key in (
                "qlib_manifest_sha256", "qlib_tree_sha256", "qlib_file_count",
                "calendar_sha256", "calendar_row_count",
            )
        },
        "sealed_m6_effect": {
            "file_count": 199,
            "total_bytes": 84957571,
            "tree_sha256": "dfbc0b52f40250b7151d74d9a45f3fdc17a69ca1f7b9c853267c1071b4b0d5cb",
        },
        "failed_m6_3c_effect": {
            "file_count": failed["effect_file_count"],
            "total_bytes": failed["effect_total_bytes"],
            "tree_sha256": failed["effect_tree_sha256"],
        },
        "case_files": {
            key: dict(case[key]) for key in ("prediction", "canonical_report", "canonical_schedule")
        },
    }
    if scope.get("inputs") != expected_inputs:
        raise DiagnosticError("Top30 diagnostic frozen inputs differ")
    if scope.get("outputs") != {
        "root": "data/research/m6_csi800_top30_compatibility_diagnostic_v1",
        "original": "data/research/m6_csi800_top30_compatibility_diagnostic_v1/original",
        "current": "data/research/m6_csi800_top30_compatibility_diagnostic_v1/current",
        "audit": "data/research/m6_csi800_top30_compatibility_diagnostic_v1/audit",
        "experiment_ledger_write_authorized": False,
    }:
        raise DiagnosticError("Top30 diagnostic output boundary differs")
    expected_container = {
        "compose_path": "compose.m6-top30-diagnostic.yaml",
        "compose_sha256": sha256_file(COMPOSE_PATH),
        "network_mode": "none",
        "read_only_root": True,
        "run_as_non_root": True,
        "cap_drop_all": True,
        "no_new_privileges": True,
        "env_file_mounted": False,
        "docker_socket_mounted": False,
        "full_project_root_mounted": False,
        "production_ledger_mounted": False,
        "services": {
            "original": {
                "service": "m6-top30-diagnostic-original", "image": ORIGINAL_IMAGE,
                "command": ORIGINAL_COMMAND, "mounts": ORIGINAL_MOUNTS,
                "cpus": 2, "memory": "4g", "pids_limit": 128,
            },
            "current": {
                "service": "m6-top30-diagnostic-current", "image": CURRENT_IMAGE,
                "command": CURRENT_COMMAND, "mounts": CURRENT_MOUNTS,
                "cpus": 2, "memory": "4g", "pids_limit": 128,
            },
            "auditor": {
                "service": "m6-top30-diagnostic-auditor", "image": CURRENT_IMAGE,
                "command": AUDITOR_COMMAND, "mounts": AUDITOR_MOUNTS,
                "cpus": 1, "memory": "2g", "pids_limit": 64,
                "qlib_mounted": False,
            },
        },
    }
    if scope.get("container") != expected_container:
        raise DiagnosticError("Top30 diagnostic container boundary differs")


@dataclass(frozen=True)
class ReleaseScope:
    path: Path
    document: dict[str, Any]
    scope: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path, protocol: Protocol) -> "ReleaseScope":
        document = mapping(path.resolve())
        if set(document) != {"schema_version", "diagnostic_scope_sha256", "scope"}:
            raise DiagnosticError("Top30 diagnostic release document fields differ")
        if document.get("schema_version") != SCOPE_SCHEMA or not isinstance(document.get("scope"), dict):
            raise DiagnosticError("Top30 diagnostic release schema differs")
        digest = canonical_sha256(document["scope"])
        if document.get("diagnostic_scope_sha256") != digest:
            raise DiagnosticError("Top30 diagnostic release self hash differs")
        _validate_scope(document["scope"], protocol)
        return cls(path.resolve(), document, document["scope"], digest)


@dataclass(frozen=True)
class Approval:
    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path, release: ReleaseScope) -> "Approval":
        document = mapping(path.resolve())
        expected = {
            "schema_version": APPROVAL_SCHEMA,
            "diagnostic_scope_sha256": release.sha256,
            "action": ACTION,
            "real_qlib_read_authorized": True,
            "sealed_prediction_or_report_read_authorized": True,
            "failed_release_evidence_read_authorized": True,
            "real_top30_diagnostic_backtest_authorized": True,
            "real_top20_read_or_backtest_authorized": False,
            "model_fit_authorized": False,
            "prediction_generation_authorized": False,
            "experiment_ledger_write_authorized": False,
            "external_network_authorized": False,
            "env_or_secret_read_authorized": False,
            "production_authorization": "none",
        }
        if set(document) != set(expected) | {"approved_at", "consumed"}:
            raise DiagnosticError("Top30 diagnostic approval fields differ")
        if any(document.get(key) != value for key, value in expected.items()):
            raise DiagnosticError("Top30 diagnostic approval authority differs")
        if not document.get("approved_at") or document.get("consumed") is not False:
            raise DiagnosticError("Top30 diagnostic approval state differs")
        return cls(path.resolve(), document, sha256_file(path.resolve()))


def runtime_identity(release: ReleaseScope, role: str) -> dict[str, str]:
    if role not in {"original", "current"}:
        raise DiagnosticError("Top30 diagnostic runtime role differs")
    image = release.scope["images"][role]
    actual = {
        "git_commit": os.getenv("SHAIWEI_M6_TOP30_DIAGNOSTIC_GIT_HEAD", ""),
        "role": os.getenv("SHAIWEI_M6_TOP30_DIAGNOSTIC_ROLE", ""),
        "base_image_id": os.getenv("SHAIWEI_M6_TOP30_DIAGNOSTIC_BASE_IMAGE_ID", ""),
        "code_bundle_sha256": code_bundle_identity()["sha256"],
        "release_manifest_sha256": sha256_file(MANIFEST_PATH),
    }
    expected = {
        "git_commit": image["git_commit"],
        "role": role,
        "base_image_id": image["base_image_id"],
        "code_bundle_sha256": image["code_bundle_sha256"],
        "release_manifest_sha256": image["release_manifest_sha256"],
    }
    if actual != expected:
        raise DiagnosticError("Top30 diagnostic runtime identity differs")
    manifest = mapping(MANIFEST_PATH)
    if manifest != {
        "schema_version": "m6-top30-diagnostic-image-manifest-v1",
        "git_commit": actual["git_commit"],
        "role": actual["role"],
        "base_image_id": actual["base_image_id"],
        "code_bundle_sha256": actual["code_bundle_sha256"],
    }:
        raise DiagnosticError("Top30 diagnostic embedded image manifest differs")
    return actual


__all__ = [
    "ACTION", "APPROVAL_SCHEMA", "AUDITOR_COMMAND", "AUDITOR_MOUNTS", "Approval",
    "COMPOSE_PATH", "CURRENT_COMMAND", "CURRENT_IMAGE", "CURRENT_MOUNTS",
    "DiagnosticError", "ORIGINAL_COMMAND", "ORIGINAL_IMAGE", "ORIGINAL_MOUNTS",
    "PROTOCOL_PATH", "Protocol", "ReleaseScope", "SCOPE_KIND", "SCOPE_PATH",
    "code_bundle_identity", "expected_preapproval_authority", "mapping", "runtime_identity",
    "tree_identity", "write_once_document",
]

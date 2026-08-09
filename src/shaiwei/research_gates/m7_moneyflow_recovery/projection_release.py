"""Content-addressed release and approval for one offline target projection."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from shaiwei.research_gates.m7_moneyflow.contract import canonical_json, sha256_file, sha256_json

from .contract import RecoveryError
from .projection_contract import ACTION, TargetProjectionProtocol


APPROVER_SHA256 = "7df97c84a6ddbde116d9b2ec059200349035842d6c88bf55e90880002315b48d"
COMMANDS = {
    "projector": [
        "python",
        "-m",
        "shaiwei.research_gates.m7_moneyflow_recovery.projection_runner",
        "--project-root",
        "/opt/shaiwei",
        "--input-root",
        "/inputs",
        "--release-scope",
        "/authorization/release.json",
        "--approval-envelope",
        "/authorization/approval.json",
        "--output-root",
        "/outputs",
        "--claim-root",
        "/claims",
    ],
    "auditor": [
        "python",
        "-m",
        "shaiwei.research_gates.m7_moneyflow_recovery.projection_auditor",
        "--project-root",
        "/opt/shaiwei",
        "--input-root",
        "/inputs",
        "--release-scope",
        "/authorization/release.json",
        "--approval-envelope",
        "/authorization/approval.json",
        "--output-root",
        "/outputs",
        "--audit-root",
        "/audit",
        "--claim-root",
        "/claims",
    ],
}
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
CODE_BUNDLE_ROOTS = (
    ".dockerignore",
    "Dockerfile.m7-moneyflow-target-projection",
    "compose.m7-moneyflow-target-projection.yaml",
    "requirements.m5-data-gate.lock",
    "config/m7_star_custom_pool_moneyflow_data_v1.yaml",
    "config/m7_star_custom_pool_moneyflow_proposal_export_v1.json",
    "config/m7_moneyflow_gap_lineage_v1.yaml",
    "config/m7_moneyflow_gap_lineage_input_manifest_v1.json",
    "config/m7_moneyflow_gap_lineage_execution_manifest_v1.json",
    "config/m7_moneyflow_recovery_engineering_v1.yaml",
    "config/m7_moneyflow_evidence_recovery_v1.yaml",
    "config/m7_moneyflow_evidence_recovery_engineering_v1.yaml",
    "config/m7_moneyflow_recovery_release_build_v1.yaml",
    "config/m7_moneyflow_recovery_target_projection_v2.yaml",
    "src/shaiwei/research_gates/m7_moneyflow",
    "src/shaiwei/research_gates/m7_moneyflow_lineage",
    "src/shaiwei/research_gates/m7_moneyflow_recovery",
)


def code_bundle_sha256(project_root: Path) -> str:
    root = project_root.resolve(strict=True)
    files: set[Path] = set()
    for relative in CODE_BUNDLE_ROOTS:
        unresolved = root / relative
        if unresolved.is_symlink():
            raise RecoveryError("recovery target code root cannot be a symlink")
        candidate = unresolved.resolve(strict=True)
        try:
            candidate.relative_to(root)
        except ValueError as error:
            raise RecoveryError("recovery target code root is outside project") from error
        members = tuple(candidate.rglob("*")) if candidate.is_dir() else (candidate,)
        if any(member.is_symlink() for member in members):
            raise RecoveryError("recovery target code bundle cannot contain symlinks")
        files.update(members)
    inventory = [
        {
            "path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(files)
        if path.is_file() and not path.is_symlink()
    ]
    if not inventory:
        raise RecoveryError("recovery target code bundle is empty")
    return sha256_json(inventory)


def _mounts(protocol: TargetProjectionProtocol, git_commit: str) -> list[dict[str, str]]:
    suffix = f"{protocol.sha256[:12]}-{git_commit[:7]}"
    authorization = f"data/control/m7-recovery/target-authorizations/{suffix}"
    outputs = f"data/control/m7-recovery/target-projections/{suffix}"
    claims = f"data/control/m7-recovery/target-projection-claims/{suffix}"
    audits = f"data/control/m7-recovery/target-projection-audits/{suffix}"
    inputs = protocol.input_bundle_relative_path
    return [
        {"role": "projector", "source": authorization, "target": "/authorization", "mode": "ro"},
        {"role": "projector", "source": inputs, "target": "/inputs", "mode": "ro"},
        {"role": "projector", "source": outputs, "target": "/outputs", "mode": "rw"},
        {"role": "projector", "source": claims, "target": "/claims", "mode": "rw"},
        {"role": "auditor", "source": authorization, "target": "/authorization", "mode": "ro"},
        {"role": "auditor", "source": inputs, "target": "/inputs", "mode": "ro"},
        {"role": "auditor", "source": outputs, "target": "/outputs", "mode": "ro"},
        {"role": "auditor", "source": audits, "target": "/audit", "mode": "rw"},
        {"role": "auditor", "source": claims, "target": "/claims", "mode": "rw"},
    ]


def _authority() -> dict[str, Any]:
    return {
        "release_ready": True,
        "approval_recorded": False,
        "execution_authorized": False,
        "real_security_key_read_authorized": False,
        "numeric_moneyflow_value_read_authorized": False,
        "provider_call_authorized": False,
        "network_authorized": False,
        "candidate_effect_model_backtest_authorized": False,
        "scheduler_or_web_change_authorized": False,
        "production_authorization": "none",
    }


@dataclass(frozen=True)
class TargetProjectionRelease:
    document: dict[str, Any]
    scope: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path, protocol: TargetProjectionProtocol) -> TargetProjectionRelease:
        serialized = path.read_text(encoding="utf-8")
        document = json.loads(serialized)
        scope = document.get("scope") if isinstance(document, dict) else None
        if (
            not isinstance(scope, dict)
            or serialized != canonical_json(document) + "\n"
            or document.get("schema_version") != "m7-moneyflow-recovery-target-release-v1"
            or document.get("release_scope_sha256") != sha256_json(scope)
            or scope.get("scope_kind") != "TARGET_PROJECTION_RELEASE_NOT_EXECUTION_APPROVAL"
            or scope.get("action") != ACTION
            or scope.get("protocol_sha256") != protocol.sha256
            or scope.get("commands") != COMMANDS
        ):
            raise RecoveryError("recovery target projection release identity differs")
        implementation = scope.get("implementation", {})
        if (
            re.fullmatch(r"[0-9a-f]{40}", str(implementation.get("git_commit", ""))) is None
            or implementation.get("origin_main_commit") != implementation.get("git_commit")
            or implementation.get("commit_pushed_before_scope") is not True
            or SHA_RE.fullmatch(str(implementation.get("code_bundle_sha256", ""))) is None
            or implementation.get("code_bundle_roots") != list(CODE_BUNDLE_ROOTS)
            or re.fullmatch(r"sha256:[0-9a-f]{64}", str(scope.get("image", {}).get("image_id", "")))
            is None
        ):
            raise RecoveryError("recovery target projection implementation identity differs")
        container = scope.get("container", {})
        expected_container = {
            "network_mode": "none",
            "user": "65532:65532",
            "read_only_root": True,
            "cap_drop_all": True,
            "no_new_privileges": True,
            "pids_limit": 128,
            "mounts": _mounts(protocol, str(implementation["git_commit"])),
            "resources": {
                "projector": {"cpus": "2.0", "memory": "4g"},
                "auditor": {"cpus": "1.0", "memory": "2g"},
            },
        }
        if container != expected_container:
            raise RecoveryError("recovery target projection container boundary differs")
        if (
            scope.get("lineage_core_sha256") != protocol.expected_lineage_core_sha256
            or scope.get("lineage_input_bundle")
            != protocol.document["frozen_predecessors"]["lineage_input_bundle"]
            or scope.get("authority") != _authority()
        ):
            raise RecoveryError("recovery target projection release expands authority")
        return cls(document, scope, str(document["release_scope_sha256"]))


@dataclass(frozen=True)
class TargetProjectionApproval:
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path, release: TargetProjectionRelease) -> TargetProjectionApproval:
        serialized = path.read_text(encoding="utf-8")
        document = json.loads(serialized)
        if (
            not isinstance(document, dict)
            or serialized != canonical_json(document) + "\n"
            or set(document)
            != {
                "schema_version",
                "action",
                "release_scope_sha256",
                "approved_at",
                "approval_actor_sha256",
                "execution_authorized",
            }
            or document.get("schema_version") != "m7-moneyflow-recovery-target-approval-v1"
            or document.get("action") != ACTION
            or document.get("release_scope_sha256") != release.sha256
            or document.get("approval_actor_sha256") != APPROVER_SHA256
            or document.get("execution_authorized") is not True
        ):
            raise RecoveryError("recovery target projection approval differs")
        if datetime.fromisoformat(str(document["approved_at"])).tzinfo is None:
            raise RecoveryError("recovery target projection approval lacks timezone")
        return cls(document, sha256_json(document))


def build_release_document(
    protocol: TargetProjectionProtocol,
    *,
    created_at: str,
    git_commit: str,
    code_bundle_sha256: str,
    image_id: str,
    platform: str,
) -> dict[str, Any]:
    scope = {
        "scope_kind": "TARGET_PROJECTION_RELEASE_NOT_EXECUTION_APPROVAL",
        "scope_created_at": created_at,
        "action": ACTION,
        "protocol_sha256": protocol.sha256,
        "lineage_core_sha256": protocol.expected_lineage_core_sha256,
        "lineage_input_bundle": protocol.document["frozen_predecessors"]["lineage_input_bundle"],
        "implementation": {
            "git_commit": git_commit,
            "origin_main_commit": git_commit,
            "commit_pushed_before_scope": True,
            "code_bundle_sha256": code_bundle_sha256,
            "code_bundle_roots": list(CODE_BUNDLE_ROOTS),
        },
        "image": {"image_id": image_id, "platform": platform},
        "commands": COMMANDS,
        "container": {
            "network_mode": "none",
            "user": "65532:65532",
            "read_only_root": True,
            "cap_drop_all": True,
            "no_new_privileges": True,
            "pids_limit": 128,
            "mounts": _mounts(protocol, git_commit),
            "resources": {
                "projector": {"cpus": "2.0", "memory": "4g"},
                "auditor": {"cpus": "1.0", "memory": "2g"},
            },
        },
        "authority": _authority(),
    }
    return {
        "schema_version": "m7-moneyflow-recovery-target-release-v1",
        "release_scope_sha256": sha256_json(scope),
        "scope": scope,
    }

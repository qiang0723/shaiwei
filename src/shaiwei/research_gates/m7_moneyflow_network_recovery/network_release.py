"""Exact content-addressed release and approval for M7 provider recovery."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from shaiwei.research_gates.m7_moneyflow.contract import canonical_json, sha256_file, sha256_json

from shaiwei.research_gates.m7_moneyflow_recovery.contract import RecoveryError

from .network_contract import NetworkReleaseProtocol


ACTION = "M7_MONEYFLOW_EVIDENCE_RECOVERY_ONCE"
APPROVER_SHA256 = "7df97c84a6ddbde116d9b2ec059200349035842d6c88bf55e90880002315b48d"
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
CODE_RE = re.compile(r"[0-9]{6}\.(?:SH|SZ|BJ)")
ROLES = ("status_collector", "moneyflow_collector", "evaluator", "auditor")
CODE_BUNDLE_ROOTS = (
    ".dockerignore",
    "Dockerfile.m7-moneyflow-recovery-network",
    "Dockerfile.m7-moneyflow-recovery-network.dockerignore",
    "compose.m7-moneyflow-recovery-network.yaml",
    "requirements.m7-moneyflow-recovery-network.lock",
    "config/m7_moneyflow_evidence_recovery_v1.yaml",
    "config/m7_moneyflow_evidence_recovery_engineering_v1.yaml",
    "config/m7_moneyflow_recovery_release_build_v1.yaml",
    "config/m7_moneyflow_recovery_target_projection_v2.yaml",
    "config/m7_moneyflow_recovery_target_projection_execution_manifest_v1.json",
    "config/m7_moneyflow_evidence_recovery_network_release_v1.yaml",
    "config/m7_moneyflow_evidence_recovery_request_plan_manifest_v1.json",
    "src/shaiwei/research_gates/m7_moneyflow",
    "src/shaiwei/research_gates/m7_moneyflow_lineage",
    "src/shaiwei/research_gates/m7_moneyflow_recovery",
    "src/shaiwei/research_gates/m7_moneyflow_network_recovery",
)


def code_bundle_sha256(project_root: Path) -> str:
    root = project_root.resolve(strict=True)
    files: set[Path] = set()
    for relative in CODE_BUNDLE_ROOTS:
        unresolved = root / relative
        if unresolved.is_symlink():
            raise RecoveryError("recovery network code root cannot be a symlink")
        candidate = unresolved.resolve(strict=True)
        try:
            candidate.relative_to(root)
        except ValueError as error:
            raise RecoveryError("recovery network code root is outside project") from error
        members = tuple(candidate.rglob("*")) if candidate.is_dir() else (candidate,)
        if any(member.is_symlink() for member in members):
            raise RecoveryError("recovery network code bundle cannot contain symlinks")
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
        raise RecoveryError("recovery network code bundle is empty")
    return sha256_json(inventory)


def _command(module: str, role_paths: list[tuple[str, str]]) -> list[str]:
    command = [
        "python",
        "-m",
        f"shaiwei.research_gates.m7_moneyflow_network_recovery.{module}",
        "--project-root",
        "/opt/shaiwei",
        "--plan-root",
        "/plans",
        "--release-scope",
        "/authorization/release.json",
        "--approval-envelope",
        "/authorization/approval.json",
    ]
    for name, value in role_paths:
        command.extend((name, value))
    return command


def _mounts(
    protocol: NetworkReleaseProtocol,
    plan_manifest: dict[str, Any],
    git_commit: str,
) -> dict[str, list[dict[str, str]]]:
    suffix = f"{str(plan_manifest['plan_id'])[:12]}-{git_commit[:7]}"
    base = f"data/control/m7-recovery/network-runs/{suffix}"
    authorization = f"data/control/m7-recovery/network-authorizations/{suffix}"
    plans = str(plan_manifest["plan_root_relative_path"])
    targets = protocol.target_projection_root
    secret = "data/control/m7-recovery/secrets/tushare_token"
    return {
        "status_collector": [
            {"source": authorization, "target": "/authorization", "mode": "ro"},
            {"source": plans, "target": "/plans", "mode": "ro"},
            {"source": f"{base}/status-batches", "target": "/batches", "mode": "rw"},
            {"source": f"{base}/status-claims", "target": "/claims", "mode": "rw"},
        ],
        "moneyflow_collector": [
            {"source": authorization, "target": "/authorization", "mode": "ro"},
            {"source": plans, "target": "/plans", "mode": "ro"},
            {"source": secret, "target": "/run/secrets/tushare_token", "mode": "ro"},
            {"source": f"{base}/moneyflow-batches", "target": "/batches", "mode": "rw"},
            {"source": f"{base}/moneyflow-claims", "target": "/claims", "mode": "rw"},
        ],
        "evaluator": [
            {"source": authorization, "target": "/authorization", "mode": "ro"},
            {"source": plans, "target": "/plans", "mode": "ro"},
            {"source": targets, "target": "/targets", "mode": "ro"},
            {"source": f"{base}/status-batches", "target": "/status", "mode": "ro"},
            {"source": f"{base}/moneyflow-batches", "target": "/moneyflow", "mode": "ro"},
            {"source": f"{base}/evaluation", "target": "/run", "mode": "rw"},
            {"source": f"{base}/evaluator-claims", "target": "/claims", "mode": "rw"},
        ],
        "auditor": [
            {"source": authorization, "target": "/authorization", "mode": "ro"},
            {"source": plans, "target": "/plans", "mode": "ro"},
            {"source": targets, "target": "/targets", "mode": "ro"},
            {"source": f"{base}/status-batches", "target": "/status", "mode": "ro"},
            {"source": f"{base}/moneyflow-batches", "target": "/moneyflow", "mode": "ro"},
            {"source": f"{base}/evaluation", "target": "/run", "mode": "ro"},
            {"source": f"{base}/audit", "target": "/audit", "mode": "rw"},
            {"source": f"{base}/auditor-claims", "target": "/claims", "mode": "rw"},
        ],
    }


def _roles(
    protocol: NetworkReleaseProtocol,
    plan_manifest: dict[str, Any],
    git_commit: str,
) -> dict[str, Any]:
    mounts = _mounts(protocol, plan_manifest, git_commit)
    return {
        "status_collector": {
            "command": _command(
                "network_status_collector",
                [("--batch-root", "/batches"), ("--claim-root", "/claims")],
            ),
            "network_mode": "bridge",
            "mounts": mounts["status_collector"],
            "resources": {"cpus": "1.0", "memory": "1g"},
        },
        "moneyflow_collector": {
            "command": _command(
                "network_moneyflow_collector",
                [
                    ("--batch-root", "/batches"),
                    ("--claim-root", "/claims"),
                    ("--secret-file", "/run/secrets/tushare_token"),
                ],
            ),
            "network_mode": "bridge",
            "mounts": mounts["moneyflow_collector"],
            "resources": {"cpus": "1.0", "memory": "2g"},
        },
        "evaluator": {
            "command": _command(
                "network_evaluator",
                [
                    ("--target-root", "/targets"),
                    ("--status-root", "/status"),
                    ("--moneyflow-root", "/moneyflow"),
                    ("--output-root", "/run"),
                    ("--claim-root", "/claims"),
                ],
            ),
            "network_mode": "none",
            "mounts": mounts["evaluator"],
            "resources": {"cpus": "2.0", "memory": "4g"},
        },
        "auditor": {
            "command": _command(
                "network_auditor",
                [
                    ("--target-root", "/targets"),
                    ("--status-root", "/status"),
                    ("--moneyflow-root", "/moneyflow"),
                    ("--evaluation-root", "/run"),
                    ("--audit-root", "/audit"),
                    ("--claim-root", "/claims"),
                ],
            ),
            "network_mode": "none",
            "mounts": mounts["auditor"],
            "resources": {"cpus": "1.0", "memory": "2g"},
        },
    }


def build_release_document(
    protocol: NetworkReleaseProtocol,
    plan_manifest: dict[str, Any],
    *,
    plan_manifest_sha256: str,
    created_at: str,
    git_commit: str,
    code_bundle_sha256: str,
    image_id: str,
    platform: str,
) -> dict[str, Any]:
    if (
        re.fullmatch(r"[0-9a-f]{40}", git_commit) is None
        or SHA_RE.fullmatch(code_bundle_sha256) is None
        or re.fullmatch(r"sha256:[0-9a-f]{64}", image_id) is None
        or platform != "linux/arm64"
        or datetime.fromisoformat(created_at).tzinfo is None
    ):
        raise RecoveryError("recovery network implementation identity differs")
    counts = plan_manifest["request_summary"]
    if (
        int(counts["status"]["required_key_count"]) != 527
        or int(counts["status"]["request_count"]) > 527
        or int(counts["full_market"]["request_count"]) > 541
        or int(counts["targeted"]["request_count"]) != 541
    ):
        raise RecoveryError("recovery network exact request counts differ")
    total = sum(int(counts[name]["request_count"]) for name in ("status", "full_market", "targeted"))
    scope = {
        "scope_kind": "RECOVERY_NETWORK_RELEASE_NOT_EXECUTION_APPROVAL",
        "scope_created_at": created_at,
        "action": ACTION,
        "protocol_sha256": protocol.sha256,
        "authoritative_lineage_core_sha256": protocol.document["supersession"][
            "authoritative_core_sha256"
        ],
        "implementation": {
            "git_commit": git_commit,
            "origin_main_commit": git_commit,
            "commit_pushed_before_scope": True,
            "code_bundle_sha256": code_bundle_sha256,
            "code_bundle_roots": list(CODE_BUNDLE_ROOTS),
        },
        "image": {"image_id": image_id, "platform": platform},
        "request_plan": {
            "plan_id": plan_manifest["plan_id"],
            "manifest_sha256": plan_manifest_sha256,
            "plan_root_relative_path": plan_manifest["plan_root_relative_path"],
            "target_identity": plan_manifest["target_identity"],
            "request_summary": counts,
        },
        "provider_limits": {
            "exact_provider_request_count": total,
            "maximum_transport_attempts_per_claim": 3,
            "maximum_transport_attempt_count": total * 3,
            "sequential_only": True,
            "semantic_empty_retry_authorized": False,
            "same_scope_rerun_authorized": False,
            "provider_cost_usd_cap": 0,
        },
        "roles": _roles(protocol, plan_manifest, git_commit),
        "security": {
            "user": "65532:65532",
            "read_only_root": True,
            "cap_drop_all": True,
            "no_new_privileges": True,
            "pids_limit": 128,
            "docker_socket_mount": False,
            "project_worktree_mount": False,
            "production_mounts_present": False,
            "dotenv_mount": False,
            "collectors_share_writable_mount": False,
        },
        "authority": {
            "release_ready": True,
            "approval_recorded": False,
            "execution_authorized": False,
            "network_authorized": False,
            "provider_call_authorized": False,
            "secret_read_authorized": False,
            "adjusted_coverage_authorized": False,
            "candidate_effect_model_backtest_authorized": False,
            "production_authorization": "none",
        },
    }
    if CODE_RE.search(canonical_json(scope)):
        raise RecoveryError("recovery network release leaks a security code")
    return {
        "schema_version": "m7-moneyflow-evidence-recovery-network-release-v1",
        "release_scope_sha256": sha256_json(scope),
        "scope": scope,
    }


@dataclass(frozen=True)
class NetworkRecoveryRelease:
    document: dict[str, Any]
    scope: dict[str, Any]
    sha256: str

    @classmethod
    def load(
        cls,
        path: Path,
        protocol: NetworkReleaseProtocol,
        *,
        plan_manifest: dict[str, Any],
        plan_manifest_sha256: str,
    ) -> NetworkRecoveryRelease:
        serialized = path.read_text(encoding="utf-8")
        document = json.loads(serialized)
        scope = document.get("scope") if isinstance(document, dict) else None
        if not isinstance(scope, dict):
            raise RecoveryError("recovery network release is not an object")
        expected = build_release_document(
            protocol,
            plan_manifest,
            plan_manifest_sha256=plan_manifest_sha256,
            created_at=str(scope.get("scope_created_at", "")),
            git_commit=str(scope.get("implementation", {}).get("git_commit", "")),
            code_bundle_sha256=str(scope.get("implementation", {}).get("code_bundle_sha256", "")),
            image_id=str(scope.get("image", {}).get("image_id", "")),
            platform=str(scope.get("image", {}).get("platform", "")),
        )
        if (
            serialized != canonical_json(document) + "\n"
            or document != expected
            or scope.get("implementation", {}).get("origin_main_commit")
            != scope.get("implementation", {}).get("git_commit")
            or re.fullmatch(r"[0-9a-f]{40}", str(scope["implementation"]["git_commit"])) is None
            or SHA_RE.fullmatch(str(scope["implementation"]["code_bundle_sha256"])) is None
            or re.fullmatch(r"sha256:[0-9a-f]{64}", str(scope["image"]["image_id"])) is None
        ):
            raise RecoveryError("recovery network release identity differs")
        return cls(document, scope, str(document["release_scope_sha256"]))


@dataclass(frozen=True)
class NetworkRecoveryApproval:
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path, release: NetworkRecoveryRelease) -> NetworkRecoveryApproval:
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
                "network_authorized",
                "provider_call_authorized",
                "secret_read_authorized",
                "same_scope_rerun_authorized",
            }
            or document.get("schema_version") != "m7-moneyflow-recovery-network-approval-v1"
            or document.get("action") != ACTION
            or document.get("release_scope_sha256") != release.sha256
            or document.get("approval_actor_sha256") != APPROVER_SHA256
            or document.get("execution_authorized") is not True
            or document.get("network_authorized") is not True
            or document.get("provider_call_authorized") is not True
            or document.get("secret_read_authorized") is not True
            or document.get("same_scope_rerun_authorized") is not False
        ):
            raise RecoveryError("recovery network approval differs")
        if datetime.fromisoformat(str(document["approved_at"])).tzinfo is None:
            raise RecoveryError("recovery network approval lacks timezone")
        return cls(document, sha256_json(document))

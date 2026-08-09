"""Validate build authority and create a synthetic, non-executable four-role release."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from shaiwei.research_gates.m7_moneyflow.contract import canonical_json, sha256_file, sha256_json

from .contract import RecoveryError


BUILD_SHA256 = "af04ba7353e4d3f6249ad603657d722643b83ef675e30aaf062afc6db15fdc28"
ACTION = "M7_MONEYFLOW_EVIDENCE_RECOVERY_ONCE"
CODE_RE = re.compile(r"[0-9]{6}\.(?:SH|SZ|BJ)")
ROLES = ("status_collector", "moneyflow_collector", "evaluator", "auditor")


@dataclass(frozen=True)
class RecoveryReleaseBuild:
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path, *, project_root: Path) -> RecoveryReleaseBuild:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        if (
            not isinstance(document, dict)
            or sha256_file(path) != BUILD_SHA256
            or document.get("build_protocol_id") != "m7-moneyflow-recovery-release-build-v1"
            or document.get("stage") != "REAL_RELEASE_IMPLEMENTATION_SYNTHETIC_ONLY"
        ):
            raise RecoveryError("recovery release build identity differs")
        for item in document["frozen_predecessors"].values():
            if not isinstance(item, dict) or "path" not in item:
                continue
            frozen = project_root / str(item["path"])
            if frozen.is_symlink() or sha256_file(frozen) != item["sha256"]:
                raise RecoveryError("recovery release predecessor differs")
        authority = document["authority"]
        if (
            authority["release_engineering_authorized"] is not True
            or authority["synthetic_fixture_authorized"] is not True
            or authority["real_target_projection_authorized"] is not False
            or authority["live_provider_call_authorized"] is not False
            or authority["external_network_authorized"] is not False
            or authority["recovery_execution_authorized"] is not False
            or authority["production_authorization"] != "none"
        ):
            raise RecoveryError("recovery release build authority differs")
        return cls(document, BUILD_SHA256)


@dataclass(frozen=True)
class NonExecutableRecoveryRelease:
    document: dict[str, Any]
    sha256: str

    @classmethod
    def parse(cls, serialized: str, build: RecoveryReleaseBuild) -> NonExecutableRecoveryRelease:
        document = json.loads(serialized)
        scope = document.get("scope") if isinstance(document, dict) else None
        if (
            not isinstance(scope, dict)
            or serialized != canonical_json(document) + "\n"
            or document.get("schema_version") != "m7-moneyflow-recovery-synthetic-release-v1"
            or document.get("release_scope_sha256") != sha256_json(scope)
            or scope.get("action") != ACTION
            or scope.get("build_contract_sha256") != build.sha256
            or set(scope.get("roles", {})) != set(ROLES)
            or scope.get("authority", {}).get("execution_authorized") is not False
            or scope.get("authority", {}).get("real_scope") is not False
        ):
            raise RecoveryError("recovery synthetic release shape or authority differs")
        implementation = scope.get("implementation", {})
        if (
            re.fullmatch(r"[0-9a-f]{40}", str(implementation.get("git_commit", ""))) is None
            or re.fullmatch(r"[0-9a-f]{64}", str(implementation.get("code_bundle_sha256", ""))) is None
            or re.fullmatch(r"sha256:[0-9a-f]{64}", str(implementation.get("image_id", ""))) is None
            or re.fullmatch(r"[0-9a-f]{64}", str(scope.get("target_plan_manifest_sha256", ""))) is None
        ):
            raise RecoveryError("recovery synthetic release implementation identity differs")
        roles = scope["roles"]
        writable = [
            mount["source"]
            for role in roles.values()
            for mount in role["mounts"]
            if mount["mode"] == "rw"
        ]
        if (
            len(writable) != len(set(writable))
            or any(role["network_mode"] != "none" for role in roles.values())
            or any(role["read_only_root"] is not True for role in roles.values())
        ):
            raise RecoveryError("recovery synthetic release role isolation differs")
        if CODE_RE.search(serialized):
            raise RecoveryError("recovery synthetic release leaks a security code")
        return cls(document, str(document["release_scope_sha256"]))


def build_synthetic_release(
    build: RecoveryReleaseBuild,
    *,
    implementation_commit: str,
    code_bundle_sha256: str,
    image_id: str,
    target_plan_manifest_sha256: str,
    request_bundles: dict[str, dict[str, object]],
) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{40}", implementation_commit):
        raise RecoveryError("recovery synthetic release commit differs")
    roles = {
        "status_collector": {
            "command": ["NON_EXECUTABLE_SYNTHETIC_STATUS_COLLECTOR"],
            "network_mode": "none",
            "future_network_requirement": "baostock_after_exact_approval",
            "read_only_root": True,
            "mounts": [
                {"source": "synthetic/targets", "target": "/targets", "mode": "ro"},
                {"source": "synthetic/status", "target": "/status", "mode": "rw"},
            ],
            "resources": {"cpus": "1.0", "memory": "1g"},
        },
        "moneyflow_collector": {
            "command": ["NON_EXECUTABLE_SYNTHETIC_MONEYFLOW_COLLECTOR"],
            "network_mode": "none",
            "future_network_requirement": "tushare_after_exact_approval",
            "read_only_root": True,
            "mounts": [
                {"source": "synthetic/targets", "target": "/targets", "mode": "ro"},
                {"source": "synthetic/moneyflow", "target": "/moneyflow", "mode": "rw"},
            ],
            "resources": {"cpus": "1.0", "memory": "1g"},
        },
        "evaluator": {
            "command": ["python", "-m", "shaiwei.research_gates.m7_moneyflow_recovery.evaluator"],
            "network_mode": "none",
            "future_network_requirement": "none",
            "read_only_root": True,
            "mounts": [
                {"source": "synthetic/targets", "target": "/targets", "mode": "ro"},
                {"source": "synthetic/status", "target": "/status", "mode": "ro"},
                {"source": "synthetic/moneyflow", "target": "/moneyflow", "mode": "ro"},
                {"source": "synthetic/run", "target": "/run", "mode": "rw"},
            ],
            "resources": {"cpus": "2.0", "memory": "4g"},
        },
        "auditor": {
            "command": ["python", "-m", "shaiwei.research_gates.m7_moneyflow_recovery.auditor"],
            "network_mode": "none",
            "future_network_requirement": "none",
            "read_only_root": True,
            "mounts": [
                {"source": "synthetic/targets", "target": "/targets", "mode": "ro"},
                {"source": "synthetic/status", "target": "/status", "mode": "ro"},
                {"source": "synthetic/moneyflow", "target": "/moneyflow", "mode": "ro"},
                {"source": "synthetic/run", "target": "/run", "mode": "ro"},
                {"source": "synthetic/audit", "target": "/audit", "mode": "rw"},
            ],
            "resources": {"cpus": "1.0", "memory": "2g"},
        },
    }
    scope = {
        "scope_kind": "RECOVERY_RELEASE_NOT_EXECUTION_APPROVAL",
        "action": ACTION,
        "build_contract_sha256": build.sha256,
        "implementation": {
            "git_commit": implementation_commit,
            "code_bundle_sha256": code_bundle_sha256,
            "image_id": image_id,
        },
        "target_plan_manifest_sha256": target_plan_manifest_sha256,
        "request_identity_bundles": request_bundles,
        "roles": roles,
        "security": {
            "read_only_root": True,
            "run_as_non_root": True,
            "cap_drop_all": True,
            "no_new_privileges": True,
            "collectors_share_writable_mount": False,
            "production_mounts_present": False,
        },
        "authority": {
            "synthetic_only": True,
            "real_scope": False,
            "approval_present": False,
            "execution_authorized": False,
            "provider_call_authorized": False,
            "production_authorization": "none",
        },
    }
    return {
        "schema_version": "m7-moneyflow-recovery-synthetic-release-v1",
        "release_scope_sha256": sha256_json(scope),
        "scope": scope,
    }

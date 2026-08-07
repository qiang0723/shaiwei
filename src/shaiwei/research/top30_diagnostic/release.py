"""Build the content-addressed preapproval scope for M6 Top30 diagnostics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from typing import Any

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.model_attribution.contract import sha256_file
from shaiwei.research.top30_diagnostic.contract import (
    ACTION,
    AUDITOR_COMMAND,
    AUDITOR_MOUNTS,
    COMPOSE_PATH,
    CURRENT_COMMAND,
    CURRENT_IMAGE,
    CURRENT_MOUNTS,
    ORIGINAL_COMMAND,
    ORIGINAL_IMAGE,
    ORIGINAL_MOUNTS,
    Protocol,
    SCOPE_KIND,
    code_bundle_identity,
    expected_preapproval_authority,
)
from shaiwei.research.top30_diagnostic.exact import DiagnosticError, canonical_sha256


def _git(name: str) -> str:
    result = subprocess.run(
        ["git", "rev-parse", name], cwd=PROJECT_ROOT, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _image(
    *,
    reference: str,
    image_id: str,
    base_reference: str,
    base_image_id: str,
    platform: str,
    manifest_sha256: str,
    commit: str,
    bundle_sha256: str,
) -> dict[str, Any]:
    if not image_id.startswith("sha256:") or not base_image_id.startswith("sha256:"):
        raise DiagnosticError("Top30 diagnostic image ID is invalid")
    if platform not in {"linux/arm64", "linux/amd64"} or len(manifest_sha256) != 64:
        raise DiagnosticError("Top30 diagnostic image metadata is invalid")
    return {
        "reference": reference,
        "image_id": image_id,
        "base_reference": base_reference,
        "base_image_id": base_image_id,
        "platform": platform,
        "git_commit": commit,
        "code_bundle_sha256": bundle_sha256,
        "release_manifest_sha256": manifest_sha256,
    }


def build_scope(
    *,
    original_image_id: str,
    current_image_id: str,
    original_manifest_sha256: str,
    current_manifest_sha256: str,
    platform: str,
) -> dict[str, Any]:
    protocol = Protocol.load()
    commit, origin = _git("HEAD"), _git("origin/main")
    if commit != origin:
        raise DiagnosticError("Top30 diagnostic implementation is not pushed to origin/main")
    bundle = code_bundle_identity()
    frozen = protocol.document["frozen_runtime_inputs"]
    case = protocol.document["frozen_diagnostic_case"]
    failed = protocol.document["failed_release"]
    images = {
        "original": _image(
            reference=ORIGINAL_IMAGE,
            image_id=original_image_id,
            base_reference=frozen["original_m6_image"]["reference"],
            base_image_id=frozen["original_m6_image"]["image_id"],
            platform=platform,
            manifest_sha256=original_manifest_sha256,
            commit=commit,
            bundle_sha256=bundle["sha256"],
        ),
        "current": _image(
            reference=CURRENT_IMAGE,
            image_id=current_image_id,
            base_reference=frozen["failed_m6_3c_image"]["reference"],
            base_image_id=frozen["failed_m6_3c_image"]["image_id"],
            platform=platform,
            manifest_sha256=current_manifest_sha256,
            commit=commit,
            bundle_sha256=bundle["sha256"],
        ),
    }
    scope = {
        "scope_kind": SCOPE_KIND,
        "protocol_id": protocol.document["protocol_id"],
        "protocol_sha256": protocol.sha256,
        "implementation": {
            "git_commit": commit,
            "origin_main_commit": origin,
            "code_bundle_sha256": bundle["sha256"],
            "code_bundle_file_count": bundle["file_count"],
            "dockerfile_sha256": sha256_file(PROJECT_ROOT / "Dockerfile.m6-top30-diagnostic"),
            "compose_sha256": sha256_file(COMPOSE_PATH),
        },
        "images": images,
        "inputs": {
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
        },
        "authority": expected_preapproval_authority(),
        "execution": {
            "approval_action": ACTION,
            "original_runner_invocation_count": 1,
            "current_runner_invocation_count": 1,
            "independent_auditor_invocation_count": 1,
            "total_top30_backtest_count": 6,
            "top20_backtest_count": 0,
            "research_attempt_increment": 0,
            "same_release_retry_authorized": False,
        },
        "container": {
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
                    "cpus": 1, "memory": "2g", "pids_limit": 64, "qlib_mounted": False,
                },
            },
        },
        "outputs": {
            "root": "data/research/m6_csi800_top30_compatibility_diagnostic_v1",
            "original": "data/research/m6_csi800_top30_compatibility_diagnostic_v1/original",
            "current": "data/research/m6_csi800_top30_compatibility_diagnostic_v1/current",
            "audit": "data/research/m6_csi800_top30_compatibility_diagnostic_v1/audit",
            "experiment_ledger_write_authorized": False,
        },
    }
    return {
        "schema_version": "m6-top30-compatibility-diagnostic-release-scope-v1",
        "diagnostic_scope_sha256": canonical_sha256(scope),
        "scope": scope,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original-image-id", required=True)
    parser.add_argument("--current-image-id", required=True)
    parser.add_argument("--original-manifest-sha256", required=True)
    parser.add_argument("--current-manifest-sha256", required=True)
    parser.add_argument("--platform", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    document = build_scope(
        original_image_id=args.original_image_id,
        current_image_id=args.current_image_id,
        original_manifest_sha256=args.original_manifest_sha256,
        current_manifest_sha256=args.current_manifest_sha256,
        platform=args.platform,
    )
    args.output.write_text(
        json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    print(document["diagnostic_scope_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

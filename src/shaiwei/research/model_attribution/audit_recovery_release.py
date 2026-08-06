"""Build the metadata-only M6 auditor-entrypoint recovery scope."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Any

from shaiwei.config import PROJECT_ROOT
from shaiwei.provenance import git_head
from shaiwei.research.model_attribution.audit_recovery_contract import (
    RECOVERY_ACTION,
    RECOVERY_COMMAND,
    RECOVERY_COMPOSE_PATH,
    RECOVERY_IMAGE,
    RECOVERY_MOUNTS,
    RECOVERY_PROTOCOL_PATH,
    RECOVERY_SCOPE_KIND,
    RECOVERY_SCOPE_PATH,
    RecoveryProtocol,
    _expected_authority,
    _validate_scope,
    effect_tree_identity,
)
from shaiwei.research.model_attribution.contract import (
    AttributionError,
    canonical_sha256,
    sha256_file,
)
from shaiwei.research.model_attribution.effect_contract import write_once_document


CONTRACT_PATH = PROJECT_ROOT / "src/shaiwei/research/model_attribution/audit_recovery_contract.py"
ENTRYPOINT_PATH = PROJECT_ROOT / "src/shaiwei/research/model_attribution/audit_recovery_entrypoint.py"
DOCKERFILE_PATH = PROJECT_ROOT / "Dockerfile.m6-audit-recovery"
ORIGINAL_RELEASE_PATH = PROJECT_ROOT / "config/m6_csi800_model_attribution_release_scope_v1.json"
ORIGINAL_APPROVAL_PATH = PROJECT_ROOT / "data/control/m6_csi800_model_attribution_v1/approval.json"
EFFECT_ROOT = PROJECT_ROOT / "data/research/m6_csi800_model_attribution_v1/effect"
AUDIT_ROOT = PROJECT_ROOT / "data/research/m6_csi800_model_attribution_v1/effect-audit"


def _origin_main() -> str:
    value = subprocess.run(
        ["git", "rev-parse", "origin/main"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if len(value) != 40:
        raise AttributionError("M6 recovery origin/main identity is invalid")
    return value


def _sealed_effect(protocol: RecoveryProtocol) -> dict[str, Any]:
    expected = protocol.document["sealed_runner_state"]
    observed = effect_tree_identity(EFFECT_ROOT)
    if observed != {
        "file_count": expected["effect_file_count"],
        "total_bytes": expected["effect_total_bytes"],
        "tree_sha256": expected["effect_tree_sha256"],
    }:
        raise AttributionError("M6 sealed effect tree changed before recovery release")
    files = {
        "report_sha256": "report.json",
        "authorization_sha256": "authorization.json",
        "effect_read_marker_sha256": "effect_read_started.json",
        "first_pass_manifest_sha256": "first_pass/manifest.json",
        "replay_manifest_sha256": "replay/manifest.json",
    }
    if any(sha256_file(EFFECT_ROOT / path) != expected[key] for key, path in files.items()):
        raise AttributionError("M6 sealed effect key artifact changed before recovery release")
    if (EFFECT_ROOT / "failure.json").exists():
        raise AttributionError("M6 runner failure appeared before recovery release")
    if AUDIT_ROOT.exists() and any(AUDIT_ROOT.iterdir()):
        raise AttributionError("M6 audit output exists before recovery release")
    return {
        "effect_root": EFFECT_ROOT.relative_to(PROJECT_ROOT).as_posix(),
        "audit_root": AUDIT_ROOT.relative_to(PROJECT_ROOT).as_posix(),
        **observed,
        **{key: expected[key] for key in files},
    }


def _verify_original_inputs(protocol: RecoveryProtocol) -> None:
    original = protocol.document["original_authority"]
    if sha256_file(ORIGINAL_RELEASE_PATH) != original["release_document_sha256"]:
        raise AttributionError("M6 original release changed before recovery release")
    if sha256_file(ORIGINAL_APPROVAL_PATH) != original["approval_sha256"]:
        raise AttributionError("M6 original approval changed before recovery release")


def build_release_document(
    *,
    protocol: RecoveryProtocol,
    created_at: str,
    implementation_git_commit: str,
    origin_main_commit: str,
    image_id: str,
    image_platform: str,
    image_git_commit: str,
    base_image_id: str,
    sealed_effect: dict[str, Any],
) -> dict[str, Any]:
    if implementation_git_commit != origin_main_commit:
        raise AttributionError("M6 recovery implementation is not pushed to origin/main")
    if image_git_commit != implementation_git_commit:
        raise AttributionError("M6 recovery image Git identity differs")
    original = protocol.document["original_authority"]
    if base_image_id != original["base_image_id"]:
        raise AttributionError("M6 recovery base image identity differs")
    scope = {
        "scope_kind": RECOVERY_SCOPE_KIND,
        "created_at": created_at,
        "recovery_id": protocol.document["recovery_id"],
        "protocol_sha256": protocol.sha256,
        "original_authority": original,
        "sealed_effect": sealed_effect,
        "implementation": {
            "git_commit": implementation_git_commit,
            "origin_main_commit": origin_main_commit,
            "contract_sha256": sha256_file(CONTRACT_PATH),
            "entrypoint_sha256": sha256_file(ENTRYPOINT_PATH),
            "dockerfile_sha256": sha256_file(DOCKERFILE_PATH),
        },
        "image": {
            "reference": RECOVERY_IMAGE,
            "image_id": image_id,
            "platform": image_platform,
            "git_commit": image_git_commit,
            "base_reference": original["base_image_reference"],
            "base_image_id": original["base_image_id"],
            "contract_sha256": sha256_file(CONTRACT_PATH),
            "entrypoint_sha256": sha256_file(ENTRYPOINT_PATH),
        },
        "execution": {
            "approval_action": RECOVERY_ACTION,
            "runner_invocation_count": 0,
            "recovery_auditor_invocation_count": 1,
            "additional_alternative_attempt_count": 0,
            "same_recovery_retry_authorized": False,
        },
        "container": {
            "compose_path": RECOVERY_COMPOSE_PATH.relative_to(PROJECT_ROOT).as_posix(),
            "compose_sha256": sha256_file(RECOVERY_COMPOSE_PATH),
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
        },
        "authority": _expected_authority(),
    }
    document = {
        "schema_version": "m6-model-attribution-audit-recovery-scope-v1",
        "recovery_scope_sha256": canonical_sha256(scope),
        "scope": scope,
    }
    _validate_scope(scope, protocol, RECOVERY_COMPOSE_PATH)
    return document


def build(
    *,
    image_id: str,
    image_platform: str,
    image_git_commit: str,
    base_image_id: str,
    output: Path,
    created_at: str,
) -> dict[str, Any]:
    if output.resolve() != RECOVERY_SCOPE_PATH.resolve():
        raise AttributionError("M6 recovery scope output path differs")
    protocol = RecoveryProtocol.load(RECOVERY_PROTOCOL_PATH)
    _verify_original_inputs(protocol)
    head, origin = git_head(), _origin_main()
    document = build_release_document(
        protocol=protocol,
        created_at=created_at,
        implementation_git_commit=head,
        origin_main_commit=origin,
        image_id=image_id,
        image_platform=image_platform,
        image_git_commit=image_git_commit,
        base_image_id=base_image_id,
        sealed_effect=_sealed_effect(protocol),
    )
    digest, reused = write_once_document(output, document)
    return {
        "recovery_scope_sha256": document["recovery_scope_sha256"],
        "document_sha256": digest,
        "reused": reused,
        "release_ready": True,
        "execution_authorized": False,
        "sealed_effect_read_authorized": False,
        "production_authorization": "none",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--image-platform", required=True)
    parser.add_argument("--image-git-commit", required=True)
    parser.add_argument("--base-image-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--created-at", default=datetime.now(timezone.utc).isoformat())
    print(json.dumps(build(**vars(parser.parse_args())), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

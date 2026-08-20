"""Build the metadata-only Head30 audit identity recovery scope."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Any

from shaiwei.config import PROJECT_ROOT
from shaiwei.provenance import git_head
from shaiwei.research.model_attribution.contract import canonical_sha256, sha256_file
from shaiwei.research.production_conversion.audit_identity_recovery_contract import (
    ACTION,
    COMMAND,
    COMPOSE_PATH,
    IMAGE,
    MOUNTS,
    PROTOCOL_PATH,
    SCOPE_KIND,
    SCOPE_PATH,
    RecoveryProtocol,
    effect_tree_identity,
    expected_authority,
    expected_sealed,
    validate_scope,
)
from shaiwei.research.production_conversion.contract import ProtocolError
from shaiwei.research.production_conversion.real_contract import write_once_document


CONTRACT_PATH = PROJECT_ROOT / "src/shaiwei/research/production_conversion/audit_identity_recovery_contract.py"
ENTRYPOINT_PATH = PROJECT_ROOT / "src/shaiwei/research/production_conversion/audit_identity_recovery_entrypoint.py"
DOCKERFILE_PATH = PROJECT_ROOT / "Dockerfile.m6-production-head30-audit-recovery"
ORIGINAL_RELEASE_PATH = PROJECT_ROOT / "config/m6_csi800_production_head30_price_recovery_scope_v1.json"
ORIGINAL_APPROVAL_PATH = PROJECT_ROOT / "data/control/m6_csi800_production_head30_v1/approval-r2.json"
FAILURE_EVIDENCE_PATH = PROJECT_ROOT / "config/m6_csi800_production_head30_price_recovery_audit_failure_v1.json"
EFFECT_ROOT = PROJECT_ROOT / "data/research/m6_csi800_production_head30_v1/effect-r2"
OLD_AUDIT_ROOT = PROJECT_ROOT / "data/research/m6_csi800_production_head30_v1/effect-r2-audit"
RECOVERY_AUDIT_ROOT = PROJECT_ROOT / "data/research/m6_csi800_production_head30_v1/effect-r2-audit-recovery"


def _origin_main() -> str:
    value = subprocess.run(
        ["git", "rev-parse", "origin/main"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if len(value) != 40:
        raise ProtocolError("Head30 audit-recovery origin/main identity is invalid")
    return value


def verify_sealed_inputs(protocol: RecoveryProtocol) -> dict[str, Any]:
    original = protocol.document["original_authority"]
    if sha256_file(ORIGINAL_RELEASE_PATH) != original["release_document_sha256"]:
        raise ProtocolError("Head30 original release changed before recovery release")
    if sha256_file(ORIGINAL_APPROVAL_PATH) != original["approval_sha256"]:
        raise ProtocolError("Head30 original approval changed before recovery release")
    failed = protocol.document["failed_r2_auditor"]
    if sha256_file(FAILURE_EVIDENCE_PATH) != failed["tracked_failure_evidence_sha256"]:
        raise ProtocolError("Head30 audit failure evidence changed before recovery release")
    observed = effect_tree_identity(EFFECT_ROOT)
    sealed = protocol.document["sealed_r2_effect"]
    if observed != {key: sealed[key] for key in ("file_count", "total_bytes", "tree_sha256")}:
        raise ProtocolError("Head30 sealed R2 effect changed before recovery release")
    artifact_paths = {
        "authorization_sha256": "authorization.json",
        "treatment_effect_started_sha256": "treatment_effect_started.json",
        "first_pass_bundle_sha256": "first_pass/bundle.json",
        "replay_bundle_sha256": "replay/bundle.json",
        "report_sha256": "report.json",
    }
    if any(sha256_file(EFFECT_ROOT / path) != sealed[key] for key, path in artifact_paths.items()):
        raise ProtocolError("Head30 sealed R2 key artifact changed before recovery release")
    if OLD_AUDIT_ROOT.exists() and any(OLD_AUDIT_ROOT.iterdir()):
        raise ProtocolError("Head30 failed R2 audit root no longer empty")
    if RECOVERY_AUDIT_ROOT.exists() and any(RECOVERY_AUDIT_ROOT.iterdir()):
        raise ProtocolError("Head30 recovery audit output already exists")
    return expected_sealed(protocol)


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
    if implementation_git_commit != origin_main_commit or image_git_commit != implementation_git_commit:
        raise ProtocolError("Head30 audit-recovery implementation is not the pushed image commit")
    original = protocol.document["original_authority"]
    if base_image_id != original["base_image_id"]:
        raise ProtocolError("Head30 audit-recovery base image identity differs")
    implementation = {
        "git_commit": implementation_git_commit,
        "origin_main_commit": origin_main_commit,
        "contract_sha256": sha256_file(CONTRACT_PATH),
        "entrypoint_sha256": sha256_file(ENTRYPOINT_PATH),
        "dockerfile_sha256": sha256_file(DOCKERFILE_PATH),
    }
    scope = {
        "scope_kind": SCOPE_KIND,
        "created_at": created_at,
        "recovery_id": protocol.document["recovery_id"],
        "protocol_sha256": protocol.sha256,
        "original_authority": original,
        "sealed_effect": sealed_effect,
        "failure_evidence": {
            "path": protocol.document["failed_r2_auditor"]["tracked_failure_evidence_path"],
            "sha256": protocol.document["failed_r2_auditor"]["tracked_failure_evidence_sha256"],
        },
        "implementation": implementation,
        "image": {
            "reference": IMAGE,
            "image_id": image_id,
            "platform": image_platform,
            "git_commit": image_git_commit,
            "base_reference": original["base_image_reference"],
            "base_image_id": original["base_image_id"],
            "contract_sha256": implementation["contract_sha256"],
            "entrypoint_sha256": implementation["entrypoint_sha256"],
        },
        "execution": {
            "approval_action": ACTION,
            "runner_invocation_count": 0,
            "recovery_auditor_invocation_count": 1,
            "additional_portfolio_attempt_count": 0,
            "same_recovery_retry_authorized": False,
        },
        "container": {
            "compose_path": COMPOSE_PATH.relative_to(PROJECT_ROOT).as_posix(),
            "compose_sha256": sha256_file(COMPOSE_PATH),
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
            "service": "m6-production-head30-audit-recovery",
            "command": COMMAND,
            "mounts": MOUNTS,
            "cpus": 2,
            "memory": "4g",
            "pids_limit": 128,
        },
        "authority": expected_authority(),
    }
    document = {
        "schema_version": "m6-production-head30-audit-identity-recovery-scope-v1",
        "recovery_scope_sha256": canonical_sha256(scope),
        "scope": scope,
    }
    validate_scope(scope, protocol, COMPOSE_PATH)
    return document


def build(
    *, image_id: str, image_platform: str, image_git_commit: str,
    base_image_id: str, output: Path, created_at: str,
) -> dict[str, Any]:
    if output.resolve() != SCOPE_PATH.resolve():
        raise ProtocolError("Head30 audit-recovery scope output path differs")
    protocol = RecoveryProtocol.load(PROTOCOL_PATH)
    document = build_release_document(
        protocol=protocol,
        created_at=created_at,
        implementation_git_commit=git_head(),
        origin_main_commit=_origin_main(),
        image_id=image_id,
        image_platform=image_platform,
        image_git_commit=image_git_commit,
        base_image_id=base_image_id,
        sealed_effect=verify_sealed_inputs(protocol),
    )
    digest, reused = write_once_document(output, document)
    return {
        "recovery_scope_sha256": document["recovery_scope_sha256"],
        "document_sha256": digest,
        "reused": reused,
        "release_ready": True,
        "execution_authorized": False,
        "additional_portfolio_attempt_count": 0,
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

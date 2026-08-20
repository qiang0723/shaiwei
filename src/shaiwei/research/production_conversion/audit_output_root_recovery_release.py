"""Build the metadata-only Head30 audit output-root recovery scope."""

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
from shaiwei.research.production_conversion.audit_identity_recovery_contract import effect_tree_identity
from shaiwei.research.production_conversion.audit_output_root_recovery_contract import (
    ACTION,
    AUDIT_HOST_ROOT,
    COMMAND,
    COMPOSE_PATH,
    IMAGE,
    MOUNTS,
    PREFLIGHT_EVIDENCE_PATH,
    PROTOCOL_PATH,
    SCOPE_KIND,
    SCOPE_PATH,
    SENTINEL_SHA256,
    OutputRootProtocol,
    expected_authority,
    expected_sealed,
    mapping,
    validate_scope,
)
from shaiwei.research.production_conversion.contract import ProtocolError
from shaiwei.research.production_conversion.real_contract import write_once_document


MODULE_ROOT = PROJECT_ROOT / "src/shaiwei/research/production_conversion"
CONTRACT_PATH = MODULE_ROOT / "audit_output_root_recovery_contract.py"
ENTRYPOINT_PATH = MODULE_ROOT / "audit_output_root_recovery_entrypoint.py"
RELEASE_BUILDER_PATH = MODULE_ROOT / "audit_output_root_recovery_release.py"
R6_CONTRACT_PATH = MODULE_ROOT / "audit_hash_authority_contract.py"
R6_ENTRYPOINT_PATH = MODULE_ROOT / "audit_hash_authority_entrypoint.py"
DOCKERFILE_PATH = PROJECT_ROOT / "Dockerfile.m6-production-head30-audit-output-root-recovery"
R6_PROTOCOL_PATH = PROJECT_ROOT / "config/m6_csi800_production_head30_audit_hash_authority_recovery_v1.yaml"
R6_RELEASE_PATH = PROJECT_ROOT / "config/m6_csi800_production_head30_audit_hash_authority_recovery_scope_v1.json"
R6_APPROVAL_PATH = PROJECT_ROOT / "data/control/m6_csi800_production_head30_v1/audit-hash-authority-recovery-approval.json"
R6_FAILURE_PATH = PROJECT_ROOT / "config/m6_csi800_production_head30_audit_hash_authority_recovery_execution_failure_v1.json"
EFFECT_ROOT = PROJECT_ROOT / "data/research/m6_csi800_production_head30_v1/effect-r2"


def _origin_main() -> str:
    value = subprocess.run(
        ["git", "rev-parse", "origin/main"], cwd=PROJECT_ROOT,
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    if len(value) != 40:
        raise ProtocolError("Head30 output-root origin/main identity is invalid")
    return value


def verify_inputs(protocol: OutputRootProtocol) -> dict[str, Any]:
    r6, failure = protocol.document["r6_authority"], protocol.document["r6_execution_failure"]
    exact = {
        R6_PROTOCOL_PATH: r6["protocol_sha256"], R6_RELEASE_PATH: r6["release_document_sha256"],
        R6_APPROVAL_PATH: r6["approval_sha256"], R6_FAILURE_PATH: failure["evidence_sha256"],
    }
    if any(sha256_file(path) != digest for path, digest in exact.items()):
        raise ProtocolError("Head30 output-root predecessor file changed")
    observed = effect_tree_identity(EFFECT_ROOT)
    sealed = protocol.document["sealed_r2_effect"]
    if observed != {key: sealed[key] for key in ("file_count", "total_bytes", "tree_sha256")}:
        raise ProtocolError("Head30 sealed R2 effect changed before R7 release")
    artifacts = {
        "authorization_sha256": "authorization.json",
        "treatment_effect_started_sha256": "treatment_effect_started.json",
        "first_pass_bundle_sha256": "first_pass/bundle.json",
        "replay_bundle_sha256": "replay/bundle.json", "report_sha256": "report.json",
    }
    if any(sha256_file(EFFECT_ROOT / path) != sealed[key] for key, path in artifacts.items()):
        raise ProtocolError("Head30 sealed R2 key artifact changed before R7 release")
    if not AUDIT_HOST_ROOT.is_dir() or any(AUDIT_HOST_ROOT.iterdir()):
        raise ProtocolError("Head30 R7 audit host root is absent or not empty")
    return expected_sealed(protocol)


def verify_daemon_fixture(
    protocol: OutputRootProtocol, *, image_id: str, image_git_commit: str
) -> dict[str, Any]:
    evidence = mapping(PREFLIGHT_EVIDENCE_PATH)
    r6, failure = protocol.document["r6_authority"], protocol.document["r6_execution_failure"]
    expected = {
        "schema_version": "m6-production-head30-audit-output-root-daemon-fixture-v1",
        "status": "PASS", "r7_protocol_sha256": protocol.sha256,
        "r6_protocol_sha256": r6["protocol_sha256"],
        "r6_release_document_sha256": r6["release_document_sha256"],
        "r6_release_scope_sha256": r6["release_scope_sha256"],
        "r6_approval_sha256": r6["approval_sha256"],
        "r6_failure_evidence_sha256": failure["evidence_sha256"],
        "r6_r5_r4_r3_r2_lineage_preflight_status": "PASS",
        "hash_mismatch_within_tolerance": "PASS", "above_tolerance_fail_closed": "PASS",
        "decision_drift_fail_closed": "PASS", "output_root_roundtrip": "PASS",
        "output_root_empty_before": True, "output_root_empty_after": True,
        "sentinel_payload_sha256": SENTINEL_SHA256, "image_git_commit": image_git_commit,
        "effect_mounted": False, "effect_semantics_read": False,
        "audit_invoked": False, "production_authorization": "none",
    }
    if evidence != expected or any(AUDIT_HOST_ROOT.iterdir()):
        raise ProtocolError("Head30 output-root daemon fixture evidence differs")
    return {
        "status": "PASS", "evidence_sha256": sha256_file(PREFLIGHT_EVIDENCE_PATH),
        "output_root_roundtrip": "PASS", "output_root_empty_before": True,
        "output_root_empty_after": True, "sentinel_payload_sha256": SENTINEL_SHA256,
        "host_audit_root": AUDIT_HOST_ROOT.relative_to(PROJECT_ROOT).as_posix(),
        "same_host_root_as_real_mount": True, "effect_semantics_read": False,
        "audit_invoked": False, "final_image_id": image_id, "image_git_commit": image_git_commit,
    }


def build_release_document(
    *, protocol: OutputRootProtocol, created_at: str,
    implementation_git_commit: str, origin_main_commit: str,
    image_id: str, image_platform: str, image_git_commit: str,
    base_image_id: str, sealed_effect: dict[str, Any], daemon_fixture: dict[str, Any],
) -> dict[str, Any]:
    if implementation_git_commit != origin_main_commit or image_git_commit != implementation_git_commit:
        raise ProtocolError("Head30 output-root implementation is not the pushed image commit")
    if base_image_id != protocol.document["r6_authority"]["image_id"]:
        raise ProtocolError("Head30 output-root base image identity differs")
    implementation = {
        "git_commit": implementation_git_commit, "origin_main_commit": origin_main_commit,
        "contract_sha256": sha256_file(CONTRACT_PATH), "entrypoint_sha256": sha256_file(ENTRYPOINT_PATH),
        "release_builder_sha256": sha256_file(RELEASE_BUILDER_PATH),
        "r6_contract_sha256": sha256_file(R6_CONTRACT_PATH),
        "r6_entrypoint_sha256": sha256_file(R6_ENTRYPOINT_PATH),
        "dockerfile_sha256": sha256_file(DOCKERFILE_PATH),
    }
    scope = {
        "scope_kind": SCOPE_KIND, "created_at": created_at,
        "recovery_id": protocol.document["recovery_id"], "protocol_sha256": protocol.sha256,
        "r6_authority": protocol.document["r6_authority"],
        "r6_execution_failure": protocol.document["r6_execution_failure"],
        "sealed_effect": sealed_effect, "implementation": implementation,
        "image": {
            "reference": IMAGE, "image_id": image_id, "platform": image_platform,
            "git_commit": image_git_commit,
            "base_reference": protocol.document["r6_authority"]["image_reference"],
            "base_image_id": protocol.document["r6_authority"]["image_id"],
        },
        "execution": {
            "approval_action": ACTION, "runner_invocation_count": 0,
            "recovery_auditor_invocation_count": 1, "additional_portfolio_attempt_count": 0,
            "family_portfolio_attempts_consumed": 2, "same_recovery_retry_authorized": False,
        },
        "container": {
            "compose_path": COMPOSE_PATH.relative_to(PROJECT_ROOT).as_posix(),
            "compose_sha256": sha256_file(COMPOSE_PATH), "network_mode": "none",
            "read_only_root": True, "run_as_non_root": True, "cap_drop_all": True,
            "no_new_privileges": True, "env_file_mounted": False,
            "docker_socket_mounted": False, "full_project_root_mounted": False,
            "qlib_mounted": False, "production_ledger_mounted": False,
            "service": "m6-production-head30-audit-output-root-recovery",
            "command": COMMAND, "mounts": MOUNTS, "cpus": 2, "memory": "4g", "pids_limit": 128,
        },
        "daemon_fixture": daemon_fixture, "authority": expected_authority(),
    }
    document = {
        "schema_version": "m6-production-head30-audit-output-root-recovery-scope-v1",
        "recovery_scope_sha256": canonical_sha256(scope), "scope": scope,
    }
    validate_scope(scope, protocol, COMPOSE_PATH)
    return document


def build(
    *, image_id: str, image_platform: str, image_git_commit: str,
    base_image_id: str, output: Path, created_at: str,
) -> dict[str, Any]:
    if output.resolve() != SCOPE_PATH.resolve():
        raise ProtocolError("Head30 output-root scope output path differs")
    protocol = OutputRootProtocol.load(PROTOCOL_PATH)
    document = build_release_document(
        protocol=protocol, created_at=created_at, implementation_git_commit=git_head(),
        origin_main_commit=_origin_main(), image_id=image_id, image_platform=image_platform,
        image_git_commit=image_git_commit, base_image_id=base_image_id,
        sealed_effect=verify_inputs(protocol),
        daemon_fixture=verify_daemon_fixture(
            protocol, image_id=image_id, image_git_commit=image_git_commit
        ),
    )
    digest, reused = write_once_document(output, document)
    return {
        "recovery_scope_sha256": document["recovery_scope_sha256"],
        "document_sha256": digest, "reused": reused, "release_ready": True,
        "execution_authorized": False, "effect_semantics_read": False,
        "additional_portfolio_attempt_count": 0, "production_authorization": "none",
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

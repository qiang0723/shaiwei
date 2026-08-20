"""Build the metadata-only Head30 independent-hash authority recovery scope."""

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
from shaiwei.research.production_conversion.audit_hash_authority_contract import (
    ACTION,
    COMMAND,
    COMPOSE_PATH,
    IMAGE,
    MOUNTS,
    PREFLIGHT_EVIDENCE_PATH,
    PROTOCOL_PATH,
    SCOPE_KIND,
    SCOPE_PATH,
    HashAuthorityProtocol,
    expected_authority,
    expected_sealed,
    mapping,
    validate_scope,
)
from shaiwei.research.production_conversion.audit_identity_recovery_contract import effect_tree_identity
from shaiwei.research.production_conversion.contract import ProtocolError
from shaiwei.research.production_conversion.real_contract import write_once_document


MODULE_ROOT = PROJECT_ROOT / "src/shaiwei/research/production_conversion"
CONTRACT_PATH = MODULE_ROOT / "audit_hash_authority_contract.py"
ENTRYPOINT_PATH = MODULE_ROOT / "audit_hash_authority_entrypoint.py"
RELEASE_BUILDER_PATH = MODULE_ROOT / "audit_hash_authority_release.py"
R5_CONTRACT_PATH = MODULE_ROOT / "audit_lineage_recovery_contract.py"
R5_ENTRYPOINT_PATH = MODULE_ROOT / "audit_lineage_recovery_entrypoint.py"
R4_CONTRACT_PATH = MODULE_ROOT / "audit_entrypoint_recovery_contract.py"
R4_ENTRYPOINT_PATH = MODULE_ROOT / "audit_entrypoint_recovery_entrypoint.py"
R3_CONTRACT_PATH = MODULE_ROOT / "audit_identity_recovery_contract.py"
R3_ENTRYPOINT_PATH = MODULE_ROOT / "audit_identity_recovery_entrypoint.py"
DOCKERFILE_PATH = PROJECT_ROOT / "Dockerfile.m6-production-head30-audit-hash-authority-recovery"
R5_PROTOCOL_PATH = PROJECT_ROOT / "config/m6_csi800_production_head30_audit_lineage_entry_recovery_v1.yaml"
R5_RELEASE_PATH = PROJECT_ROOT / "config/m6_csi800_production_head30_audit_lineage_entry_recovery_scope_v1.json"
R5_APPROVAL_PATH = PROJECT_ROOT / "data/control/m6_csi800_production_head30_v1/audit-lineage-entry-recovery-approval.json"
R5_FAILURE_PATH = PROJECT_ROOT / "config/m6_csi800_production_head30_audit_lineage_entry_recovery_execution_failure_v1.json"
R4_RELEASE_PATH = PROJECT_ROOT / "config/m6_csi800_production_head30_audit_entrypoint_recovery_scope_v1.json"
R3_PROTOCOL_PATH = PROJECT_ROOT / "config/m6_csi800_production_head30_audit_identity_recovery_v1.yaml"
R3_RELEASE_PATH = PROJECT_ROOT / "config/m6_csi800_production_head30_audit_identity_recovery_scope_v1.json"
R4_FAILURE_PATH = PROJECT_ROOT / "config/m6_csi800_production_head30_audit_entrypoint_recovery_execution_failure_v1.json"
ORIGINAL_RELEASE_PATH = PROJECT_ROOT / "config/m6_csi800_production_head30_price_recovery_scope_v1.json"
ORIGINAL_APPROVAL_PATH = PROJECT_ROOT / "data/control/m6_csi800_production_head30_v1/approval-r2.json"
EFFECT_ROOT = PROJECT_ROOT / "data/research/m6_csi800_production_head30_v1/effect-r2"
AUDIT_ROOT = PROJECT_ROOT / "data/research/m6_csi800_production_head30_v1/effect-r2-audit-hash-authority-recovery"


def _origin_main() -> str:
    value = subprocess.run(
        ["git", "rev-parse", "origin/main"], cwd=PROJECT_ROOT,
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    if len(value) != 40:
        raise ProtocolError("Head30 hash-authority origin/main identity is invalid")
    return value


def verify_inputs(protocol: HashAuthorityProtocol) -> dict[str, Any]:
    r5 = protocol.document["r5_authority"]
    failure = protocol.document["r5_execution_failure"]
    exact = {
        R5_PROTOCOL_PATH: r5["protocol_sha256"],
        R5_RELEASE_PATH: r5["release_document_sha256"],
        R5_APPROVAL_PATH: r5["approval_sha256"],
        R5_FAILURE_PATH: failure["evidence_sha256"],
        R4_RELEASE_PATH: "b51abde30b00222600c621e5b4a83dd77695e53008be29de3748083fe739bef1",
        R3_PROTOCOL_PATH: "60e36c6ebedcf9051561f6fc823866787a982dac79651e24c40bfb39c2f8d2e2",
        R3_RELEASE_PATH: "b6f385911832e104b04ca3354e3ec385af92645f24a2fc81a0c5f7fb6d9a40bd",
        R4_FAILURE_PATH: "923738bed05629af82aeb82fbd73bc47bcd65390a5050eb44dff2dee5f1e57de",
        ORIGINAL_RELEASE_PATH: "166bd54bfc768929905795a86429ad4233c4bf96c7ceef0dcc232e542d08a663",
        ORIGINAL_APPROVAL_PATH: "0fe053c832897632d8cd8fbbb165252580b4134a44b62e27e9f416ebe4f47336",
    }
    if any(sha256_file(path) != digest for path, digest in exact.items()):
        raise ProtocolError("Head30 hash-authority predecessor file changed")
    observed = effect_tree_identity(EFFECT_ROOT)
    sealed = protocol.document["sealed_r2_effect"]
    if observed != {key: sealed[key] for key in ("file_count", "total_bytes", "tree_sha256")}:
        raise ProtocolError("Head30 sealed R2 effect changed before R6 release")
    artifacts = {
        "authorization_sha256": "authorization.json",
        "treatment_effect_started_sha256": "treatment_effect_started.json",
        "first_pass_bundle_sha256": "first_pass/bundle.json",
        "replay_bundle_sha256": "replay/bundle.json", "report_sha256": "report.json",
    }
    if any(sha256_file(EFFECT_ROOT / path) != sealed[key] for key, path in artifacts.items()):
        raise ProtocolError("Head30 sealed R2 key artifact changed before R6 release")
    if AUDIT_ROOT.exists() and any(AUDIT_ROOT.iterdir()):
        raise ProtocolError("Head30 R6 audit output already exists")
    return expected_sealed(protocol)


def verify_daemon_fixture(
    protocol: HashAuthorityProtocol, *, image_id: str, image_git_commit: str
) -> dict[str, Any]:
    evidence = mapping(PREFLIGHT_EVIDENCE_PATH)
    expected = {
        "schema_version": "m6-production-head30-audit-hash-authority-daemon-fixture-v1",
        "status": "PASS", "r6_protocol_sha256": protocol.sha256,
        "r5_protocol_sha256": protocol.document["r5_authority"]["protocol_sha256"],
        "r5_release_document_sha256": protocol.document["r5_authority"]["release_document_sha256"],
        "r5_release_scope_sha256": protocol.document["r5_authority"]["release_scope_sha256"],
        "r5_approval_sha256": protocol.document["r5_authority"]["approval_sha256"],
        "r5_failure_evidence_sha256": protocol.document["r5_execution_failure"]["evidence_sha256"],
        "r5_r4_r3_r2_lineage_preflight_status": "PASS",
        "hash_mismatch_within_tolerance": "PASS",
        "above_tolerance_fail_closed": "PASS", "decision_drift_fail_closed": "PASS",
        "image_git_commit": image_git_commit,
        "effect_mounted": False, "effect_semantics_read": False,
        "audit_invoked": False, "production_authorization": "none",
    }
    if evidence != expected:
        raise ProtocolError("Head30 hash-authority daemon fixture evidence differs")
    return {
        "status": "PASS", "evidence_sha256": sha256_file(PREFLIGHT_EVIDENCE_PATH),
        "hash_mismatch_within_tolerance": "PASS",
        "above_tolerance_fail_closed": "PASS", "decision_drift_fail_closed": "PASS",
        "effect_semantics_read": False, "audit_invoked": False,
        "final_image_id": image_id, "image_git_commit": image_git_commit,
    }


def build_release_document(
    *, protocol: HashAuthorityProtocol, created_at: str,
    implementation_git_commit: str, origin_main_commit: str,
    image_id: str, image_platform: str, image_git_commit: str,
    base_image_id: str, sealed_effect: dict[str, Any], daemon_fixture: dict[str, Any],
) -> dict[str, Any]:
    if implementation_git_commit != origin_main_commit or image_git_commit != implementation_git_commit:
        raise ProtocolError("Head30 hash-authority implementation is not the pushed image commit")
    if base_image_id != protocol.document["r5_authority"]["image_id"]:
        raise ProtocolError("Head30 hash-authority base image identity differs")
    implementation = {
        "git_commit": implementation_git_commit, "origin_main_commit": origin_main_commit,
        "contract_sha256": sha256_file(CONTRACT_PATH), "entrypoint_sha256": sha256_file(ENTRYPOINT_PATH),
        "release_builder_sha256": sha256_file(RELEASE_BUILDER_PATH),
        "r5_contract_sha256": sha256_file(R5_CONTRACT_PATH),
        "r5_entrypoint_sha256": sha256_file(R5_ENTRYPOINT_PATH),
        "r4_contract_sha256": sha256_file(R4_CONTRACT_PATH),
        "r4_entrypoint_sha256": sha256_file(R4_ENTRYPOINT_PATH),
        "r3_contract_sha256": sha256_file(R3_CONTRACT_PATH),
        "r3_entrypoint_sha256": sha256_file(R3_ENTRYPOINT_PATH),
        "dockerfile_sha256": sha256_file(DOCKERFILE_PATH),
    }
    scope = {
        "scope_kind": SCOPE_KIND, "created_at": created_at,
        "recovery_id": protocol.document["recovery_id"], "protocol_sha256": protocol.sha256,
        "r5_authority": protocol.document["r5_authority"],
        "r5_execution_failure": protocol.document["r5_execution_failure"],
        "sealed_effect": sealed_effect, "implementation": implementation,
        "image": {
            "reference": IMAGE, "image_id": image_id, "platform": image_platform,
            "git_commit": image_git_commit,
            "base_reference": protocol.document["r5_authority"]["image_reference"],
            "base_image_id": protocol.document["r5_authority"]["image_id"],
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
            "service": "m6-production-head30-audit-hash-authority-recovery",
            "command": COMMAND, "mounts": MOUNTS, "cpus": 2, "memory": "4g", "pids_limit": 128,
        },
        "daemon_fixture": daemon_fixture, "authority": expected_authority(),
    }
    document = {
        "schema_version": "m6-production-head30-audit-hash-authority-recovery-scope-v1",
        "recovery_scope_sha256": canonical_sha256(scope), "scope": scope,
    }
    validate_scope(scope, protocol, COMPOSE_PATH)
    return document


def build(
    *, image_id: str, image_platform: str, image_git_commit: str,
    base_image_id: str, output: Path, created_at: str,
) -> dict[str, Any]:
    if output.resolve() != SCOPE_PATH.resolve():
        raise ProtocolError("Head30 hash-authority scope output path differs")
    protocol = HashAuthorityProtocol.load(PROTOCOL_PATH)
    document = build_release_document(
        protocol=protocol, created_at=created_at, implementation_git_commit=git_head(),
        origin_main_commit=_origin_main(), image_id=image_id, image_platform=image_platform,
        image_git_commit=image_git_commit, base_image_id=base_image_id,
        sealed_effect=verify_inputs(protocol),
        daemon_fixture=verify_daemon_fixture(protocol, image_id=image_id, image_git_commit=image_git_commit),
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

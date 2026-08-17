"""Build the result-blind R3G-2 effect entrypoint-recovery scope."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from shaiwei.config import PROJECT_ROOT
from shaiwei.provenance import code_snapshot_sha256, git_head, verify_release_manifest
from shaiwei.research.trend_swing.r3g2.contract import EffectProtocol, R3G2Error, sha256_file
from shaiwei.research.trend_swing.r3g2.effect_control import (
    AUDITOR_COMMAND,
    RUNNER_COMMAND,
    EffectApproval,
    EffectReleaseScope,
    canonical_sha256,
    expected_scope_authority,
)
from shaiwei.research.trend_swing.r3g2.effect_recovery_control import (
    RECOVERY_ACTION,
    RECOVERY_APPROVAL_PATH,
    RECOVERY_AUDIT_ROOT,
    RECOVERY_COMPOSE,
    RECOVERY_EFFECT_ROOT,
    RECOVERY_IMAGE,
    RECOVERY_SCOPE_KIND,
    RECOVERY_SCOPE_PATH,
    RECOVERY_SCOPE_SCHEMA,
    RecoveryProtocol,
    predecessor_record,
    recovery_mounts,
    validate_recovery_scope,
)
from shaiwei.research.trend_swing.r3g2.effect_release import _manifest, _origin_main
from shaiwei.research.trend_swing.r3g2.evidence import write_once_json


OUTPUT_PATH = PROJECT_ROOT / RECOVERY_SCOPE_PATH
APPROVAL_PATH = PROJECT_ROOT / RECOVERY_APPROVAL_PATH
EFFECT_ROOT = PROJECT_ROOT / RECOVERY_EFFECT_ROOT
AUDIT_ROOT = PROJECT_ROOT / RECOVERY_AUDIT_ROOT
PREFLIGHT_PATH = PROJECT_ROOT / (
    "data/research/trend_swing/ts-v5-r3g2-effect-entrypoint-recovery-preflight-v1/"
    "report.json"
)


def _json(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise R3G2Error(f"R3G-2 recovery evidence is invalid: {path.name}") from error
    if not isinstance(document, dict):
        raise R3G2Error(f"R3G-2 recovery evidence is not a mapping: {path.name}")
    return document


def _files(root: Path) -> list[str]:
    if not root.is_dir():
        raise R3G2Error(f"R3G-2 recovery evidence root is absent: {root.name}")
    return sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file())


def verify_predecessor_evidence(
    protocol: EffectProtocol, recovery: RecoveryProtocol
) -> dict[str, Any]:
    predecessor = recovery.document["predecessor"]
    original_spec = predecessor["original_release"]
    original_path = PROJECT_ROOT / original_spec["path"]
    if sha256_file(original_path) != original_spec["document_sha256"]:
        raise R3G2Error("R3G-2 original release document differs")
    original = EffectReleaseScope.load(original_path, protocol)
    if original.sha256 != original_spec["scope_sha256"]:
        raise R3G2Error("R3G-2 original release scope differs")

    approval_spec = predecessor["original_approval"]
    approval_path = PROJECT_ROOT / approval_spec["path"]
    approval = EffectApproval.load(approval_path, original)
    if approval.sha256 != approval_spec["sha256"]:
        raise R3G2Error("R3G-2 original approval differs")

    failure_spec = predecessor["failure_receipt"]
    failure_path = PROJECT_ROOT / failure_spec["path"]
    failure = _json(failure_path)
    observed = {
        key: failure.get(key) for key in failure_spec["frozen_facts"]
    }
    if (
        sha256_file(failure_path) != failure_spec["sha256"]
        or failure.get("release_scope_sha256") != original.sha256
        or failure.get("approval_sha256") != approval.sha256
        or failure.get("error_type") != failure_spec["error_type"]
        or failure.get("error_message") != failure_spec["error_message"]
        or observed != failure_spec["frozen_facts"]
        or failure.get("strategy_effective") != "NOT_EVALUATED"
        or failure.get("production_authorization") != "none"
    ):
        raise R3G2Error("R3G-2 original entrypoint failure evidence differs")

    preserved = predecessor["preserved_original_outputs"]
    if _files(PROJECT_ROOT / preserved["effect_root"]) != preserved["expected_files"]:
        raise R3G2Error("R3G-2 original effect root was not preserved")
    if len(_files(PROJECT_ROOT / preserved["audit_root"])) != preserved[
        "expected_audit_file_count"
    ]:
        raise R3G2Error("R3G-2 original audit root was not preserved")
    return predecessor_record(recovery)


def build_release_document(
    *,
    protocol: EffectProtocol,
    recovery: RecoveryProtocol,
    predecessor: dict[str, Any],
    inputs: dict[str, Any],
    created_at: str,
    implementation_git_commit: str,
    origin_main_commit: str,
    code_snapshot: str,
    image_id: str,
    image_platform: str,
    image_git_commit: str,
    image_release_manifest_path: Path,
) -> dict[str, Any]:
    if implementation_git_commit != origin_main_commit or image_git_commit != implementation_git_commit:
        raise R3G2Error("R3G-2 recovery implementation is not the pushed image identity")
    manifest = _manifest(image_release_manifest_path)
    if manifest.get("code_snapshot_sha256") != code_snapshot:
        raise R3G2Error("R3G-2 recovery image and host snapshots differ")
    runner_mounts, auditor_mounts = recovery_mounts()
    scope = {
        "scope_kind": RECOVERY_SCOPE_KIND,
        "created_at": created_at,
        "effect_protocol_sha256": protocol.sha256,
        "release_protocol_sha256": recovery.sha256,
        "predecessor_failure": predecessor,
        "implementation": {
            "git_commit": implementation_git_commit,
            "origin_main_commit": origin_main_commit,
            "code_snapshot_sha256": code_snapshot,
        },
        "image": {
            "reference": RECOVERY_IMAGE,
            "image_id": image_id,
            "platform": image_platform,
            "git_commit": image_git_commit,
            "release_manifest_sha256": sha256_file(image_release_manifest_path),
            "release_manifest_file_count": int(manifest["file_count"]),
        },
        "inputs": inputs,
        "execution": {
            "approval_action": RECOVERY_ACTION,
            "runner_invocation_count": 1,
            "complete_internal_passes": ["first_pass", "replay"],
            "independent_auditor_invocation_count": 1,
            "strategy_effect_attempt_count": 3,
            "same_release_retry_authorized": False,
            "original_release_retry_authorized": False,
            "discovery_first_holdout_firewall": True,
        },
        "container": {
            "compose_path": RECOVERY_COMPOSE,
            "compose_sha256": sha256_file(PROJECT_ROOT / RECOVERY_COMPOSE),
            "network_mode": "none",
            "read_only_root": True,
            "run_as_non_root": True,
            "cap_drop_all": True,
            "no_new_privileges": True,
            "env_file_mounted": False,
            "docker_socket_mounted": False,
            "full_project_root_mounted": False,
            "production_ledger_mounted": False,
            "frozen_research_lineage_ledgers_mounted": True,
            "runner": {
                "service": "ts-v5-r3g2-effect-recovery-runner",
                "command": RUNNER_COMMAND,
                "mounts": runner_mounts,
                "cpus": 6,
                "memory": "14g",
                "pids_limit": 256,
            },
            "auditor": {
                "service": "ts-v5-r3g2-effect-recovery-auditor",
                "command": AUDITOR_COMMAND,
                "mounts": auditor_mounts,
                "cpus": 2,
                "memory": "4g",
                "pids_limit": 256,
            },
        },
        "outputs": {
            "effect_root": RECOVERY_EFFECT_ROOT,
            "audit_root": RECOVERY_AUDIT_ROOT,
            "empty_at_scope_freeze": True,
            "approval_file_exists_at_scope_freeze": False,
            "experiment_ledger_write_authorized": False,
        },
        "authority": expected_scope_authority(),
    }
    validate_recovery_scope(scope, protocol, recovery)
    return {
        "schema_version": RECOVERY_SCOPE_SCHEMA,
        "release_scope_sha256": canonical_sha256(scope),
        "scope": scope,
    }


def build(
    *, image_id: str, image_platform: str, image_git_commit: str,
    image_release_manifest: Path, output: Path, created_at: str,
) -> dict[str, Any]:
    if output.resolve() != OUTPUT_PATH.resolve():
        raise R3G2Error("R3G-2 recovery release output path differs")
    if any(not path.is_dir() or any(path.iterdir()) for path in (EFFECT_ROOT, AUDIT_ROOT)):
        raise R3G2Error("R3G-2 recovery output roots are absent or non-empty")
    if APPROVAL_PATH.exists():
        raise R3G2Error("R3G-2 recovery approval exists before exact user instruction")
    head, origin = git_head(), _origin_main()
    if head != origin:
        raise R3G2Error("R3G-2 recovery HEAD is not synchronized with origin/main")
    snapshot = code_snapshot_sha256()
    if verify_release_manifest(image_release_manifest, root=PROJECT_ROOT) != snapshot:
        raise R3G2Error("R3G-2 recovery host tree differs from the built image")
    protocol = EffectProtocol.load()
    bound = protocol.validate_bound_inputs()
    recovery = RecoveryProtocol.load(protocol)
    predecessor = verify_predecessor_evidence(protocol, recovery)
    preflight = _json(PREFLIGHT_PATH)
    inputs = {
        "pre_effect_preflight_sha256": canonical_sha256(preflight),
        "bound_input_hashes": bound,
        "w7_recovery_manifest_sha256": (
            "fe7b7aeedc9d0d63d44ff56ad17046ff61290f81ca7f99e93888994bddf1579f"
        ),
    }
    document = build_release_document(
        protocol=protocol, recovery=recovery, predecessor=predecessor, inputs=inputs,
        created_at=created_at, implementation_git_commit=head, origin_main_commit=origin,
        code_snapshot=snapshot, image_id=image_id, image_platform=image_platform,
        image_git_commit=image_git_commit,
        image_release_manifest_path=image_release_manifest,
    )
    digest, reused = write_once_json(output, document)
    return {
        "release_scope_sha256": document["release_scope_sha256"],
        "document_sha256": digest,
        "reused": reused,
        "release_ready": True,
        "execution_authorized": False,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--image-platform", required=True)
    parser.add_argument("--image-git-commit", required=True)
    parser.add_argument("--image-release-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--created-at", default=datetime.now(timezone.utc).isoformat())
    print(json.dumps(build(**vars(parser.parse_args())), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

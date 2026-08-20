"""Build the exact metadata-only M6 production Head30 release scope."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Any

from shaiwei.config import PROJECT_ROOT
from shaiwei.provenance import RELEASE_MANIFEST_SCHEMA, code_snapshot_sha256, git_head, verify_release_manifest
from shaiwei.research.model_attribution.audit_recovery_contract import effect_tree_identity
from shaiwei.research.model_attribution.contract import canonical_sha256, sha256_file
from shaiwei.research.production_conversion.contract import ProtocolError
from shaiwei.research.production_conversion.real_contract import (
    SCOPE_SCHEMA, ReleaseProtocol, expected_authority, mapping, validate_scope,
    write_once_document,
)


def _origin_main() -> str:
    value = subprocess.run(["git", "rev-parse", "origin/main"], cwd=PROJECT_ROOT, check=True, capture_output=True, text=True).stdout.strip()
    if len(value) != 40:
        raise ProtocolError("production-converter origin/main identity is invalid")
    return value


def _sealed_inputs(effect_root: Path, audit_path: Path) -> dict[str, Any]:
    effect_root = effect_root.resolve()
    audit_path = audit_path.resolve()
    project_root = PROJECT_ROOT.resolve()
    if project_root not in effect_root.parents or project_root not in audit_path.parents:
        raise ProtocolError("production-converter sealed inputs must remain inside the project")
    identity = effect_tree_identity(effect_root)
    first = mapping(effect_root / "first_pass/manifest.json")
    replay = mapping(effect_root / "replay/manifest.json")
    return {
        "sealed_m6_effect": {
            **identity,
            "report_sha256": sha256_file(effect_root / "report.json"),
            "first_pass_bundle_sha256": first["bundle_sha256"],
            "replay_bundle_sha256": replay["bundle_sha256"],
        },
        "sealed_m6_audit": {"path": str(audit_path.relative_to(project_root)), "sha256": sha256_file(audit_path), "independent_audit": "PASS"},
    }


def build_release_document(
    *, protocol: ReleaseProtocol, created_at: str, implementation_git_commit: str,
    origin_main_commit: str, code_snapshot: str, image_id: str, image_platform: str,
    image_git_commit: str, image_release_manifest_path: Path, inputs: dict[str, Any],
) -> dict[str, Any]:
    if implementation_git_commit != origin_main_commit or image_git_commit != implementation_git_commit:
        raise ProtocolError("production-converter implementation/image is not pushed")
    image_manifest = mapping(image_release_manifest_path)
    if image_manifest.get("schema_version") != RELEASE_MANIFEST_SCHEMA or image_manifest.get("code_snapshot_sha256") != code_snapshot:
        raise ProtocolError("production-converter image manifest differs")
    docker = protocol.document["docker"]
    scope = {
        "scope_kind": protocol.scope_kind, "created_at": created_at,
        "protocol_id": protocol.document["protocol_id"],
        "protocols": {"converter_sha256": protocol.base.sha256, "hash_addendum_sha256": protocol.base.addendum_sha256, "release_engineering_sha256": protocol.sha256},
        "implementation": {"git_commit": implementation_git_commit, "origin_main_commit": origin_main_commit, "code_snapshot_sha256": code_snapshot},
        "image": {"reference": protocol.image, "image_id": image_id, "platform": image_platform, "git_commit": image_git_commit, "code_snapshot_sha256": code_snapshot, "release_manifest_sha256": sha256_file(image_release_manifest_path), "release_manifest_file_count": image_manifest["file_count"]},
        "inputs": inputs,
        "execution": {"approval_action": protocol.approval_action, "runner_invocation_count": 1, "complete_internal_passes": ["first_pass", "replay"], "independent_auditor_invocation_count": 1, "new_portfolio_attempts_consumed_at_first_treatment_effect_read": 1, "model_attempt_increment": 0, "same_release_retry_authorized": False},
        "container": {
            "compose_path": docker["compose_file"], "compose_sha256": sha256_file(PROJECT_ROOT / docker["compose_file"]),
            "network_mode": "none", "read_only_root": True, "run_as_non_root": True, "cap_drop_all": True,
            "no_new_privileges": True, "env_file_mounted": False, "docker_socket_mounted": False,
            "full_project_root_mounted": False, "production_ledger_mounted": False,
            "runner": {"service": protocol.runner_service, "command": protocol.runner_command, "cpus": 4, "memory": "8g", "pids_limit": 192, "mounts": [dict(row) for row in docker["runner_mounts"]]},
            "auditor": {"service": protocol.auditor_service, "command": protocol.auditor_command, "cpus": 2, "memory": "4g", "pids_limit": 128, "mounts": [dict(row) for row in docker["auditor_mounts"]]},
        },
        "outputs": {"effect_root": "data/research/m6_csi800_production_head30_v1/effect", "audit_root": "data/research/m6_csi800_production_head30_v1/effect-audit", "experiment_ledger_write_authorized": False},
        "authority": expected_authority(),
    }
    validate_scope(scope, protocol)
    return {"schema_version": SCOPE_SCHEMA, "release_scope_sha256": canonical_sha256(scope), "scope": scope}


def build(*, image_id: str, image_platform: str, image_git_commit: str, image_release_manifest: Path, effect_root: Path, audit_path: Path, output: Path, created_at: str, protocol_path: Path | None = None) -> dict[str, Any]:
    protocol = ReleaseProtocol.load(protocol_path)
    expected = PROJECT_ROOT / protocol.tracked_release_scope
    if output.resolve() != expected.resolve():
        raise ProtocolError("production-converter release output path differs")
    head, origin = git_head(), _origin_main()
    if head != origin:
        raise ProtocolError("production-converter implementation is not synchronized")
    snapshot = code_snapshot_sha256()
    if verify_release_manifest(image_release_manifest, root=PROJECT_ROOT) != snapshot:
        raise ProtocolError("production-converter host and image controlled trees differ")
    inputs = {"qlib": mapping(PROJECT_ROOT / "config/m6_csi800_model_attribution_release_scope_v1.json")["scope"]["inputs"], **_sealed_inputs(effect_root, audit_path)}
    document = build_release_document(protocol=protocol, created_at=created_at, implementation_git_commit=head, origin_main_commit=origin, code_snapshot=snapshot, image_id=image_id, image_platform=image_platform, image_git_commit=image_git_commit, image_release_manifest_path=image_release_manifest, inputs=inputs)
    digest, reused = write_once_document(output, document)
    return {"release_scope_sha256": document["release_scope_sha256"], "document_sha256": digest, "reused": reused, "release_ready": True, "execution_authorized": False, "production_authorization": "none"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--image-platform", required=True)
    parser.add_argument("--image-git-commit", required=True)
    parser.add_argument("--image-release-manifest", type=Path, required=True)
    parser.add_argument("--effect-root", type=Path, required=True)
    parser.add_argument("--audit-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--protocol-path", type=Path)
    parser.add_argument("--created-at", default=datetime.now(timezone.utc).isoformat())
    args = parser.parse_args()
    print(json.dumps(build(**vars(args)), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

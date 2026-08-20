"""Build the exact metadata-only M6-5B target-read recovery release scope."""

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
from shaiwei.research.production_conversion.real_contract import mapping, write_once_document

from .raw_manifest import write_manifest
from .release_contract import (
    ACTION, IMAGE, SCOPE_KIND, SCOPE_SCHEMA, ReleaseProtocol, expected_authority,
    validate_scope,
)


def _origin_main() -> str:
    value = subprocess.run(
        ["git", "rev-parse", "origin/main"], cwd=PROJECT_ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    if len(value) != 40:
        raise ProtocolError("M6-5B origin/main identity is invalid")
    return value


def build_document(
    *, protocol: ReleaseProtocol, created_at: str, commit: str, origin: str,
    snapshot: str, image_id: str, image_platform: str, image_manifest_path: Path,
    r2_root: Path, r7_audit: Path, raw_manifest_path: Path,
) -> dict[str, Any]:
    if commit != origin:
        raise ProtocolError("M6-5B implementation is not pushed")
    image_manifest = mapping(image_manifest_path)
    if image_manifest.get("schema_version") != RELEASE_MANIFEST_SCHEMA:
        raise ProtocolError("M6-5B image manifest schema differs")
    if image_manifest.get("code_snapshot_sha256") != snapshot:
        raise ProtocolError("M6-5B image and host snapshots differ")
    raw = mapping(raw_manifest_path)
    r2 = effect_tree_identity(r2_root)
    expected_r2 = protocol.document["predecessors"]["sealed_r2_effect"]
    if r2 != {key: expected_r2[key] for key in ("file_count", "total_bytes", "tree_sha256")}:
        raise ProtocolError("M6-5B sealed R2 identity differs")
    if sha256_file(r7_audit) != expected_r2["independent_audit_sha256"]:
        raise ProtocolError("M6-5B R7 audit identity differs")
    scope = {
        "scope_kind": SCOPE_KIND, "created_at": created_at,
        "protocol_sha256": protocol.sha256, "recovery_sha256": protocol.recovery_sha256,
        "implementation": {"git_commit": commit, "origin_main_commit": origin, "code_snapshot_sha256": snapshot},
        "image": {
            "reference": IMAGE, "image_id": image_id, "platform": image_platform,
            "git_commit": commit, "code_snapshot_sha256": snapshot,
            "release_manifest_sha256": sha256_file(image_manifest_path),
            "release_manifest_file_count": image_manifest["file_count"],
        },
        "inputs": {
            "sealed_r2": {**r2, "path": str(r2_root.relative_to(PROJECT_ROOT))},
            "r7_audit": {"path": str(r7_audit.relative_to(PROJECT_ROOT)), "sha256": sha256_file(r7_audit)},
            "raw_batch_manifest": {
                "path": str(raw_manifest_path.relative_to(PROJECT_ROOT)),
                "sha256": sha256_file(raw_manifest_path), "entry_count": raw["entry_count"],
                "api_entry_counts": raw["api_entry_counts"],
                "required_source_apis": raw["required_source_apis"],
            },
        },
        "execution": {
            "approval_action": ACTION, "runner_invocation_count": 1,
            "complete_internal_passes": ["first_pass", "replay"],
            "independent_auditor_invocation_count": 1, "family_attempts_before_run": 1,
            "new_attempts_consumed_at_first_real_read": 1,
            "total_family_attempts_after_run": 2, "same_scope_retry_authorized": False,
        },
        "container": {
            "compose_path": "compose.m6-head30-500k-release.yaml",
            "compose_sha256": sha256_file(PROJECT_ROOT / "compose.m6-head30-500k-release.yaml"),
            "network_mode": "none", "read_only_root": True, "run_as_non_root": True,
            "cap_drop_all": True, "no_new_privileges": True, "env_file_mounted": False,
            "docker_socket_mounted": False, "full_project_root_mounted": False,
            "production_write_mount_present": False,
        },
        "outputs": protocol.document["artifact_contract"], "authority": expected_authority(),
    }
    validate_scope(scope, protocol)
    return {"schema_version": SCOPE_SCHEMA, "release_scope_sha256": canonical_sha256(scope), "scope": scope}


def build(
    *, image_id: str, image_platform: str, image_manifest: Path, r2_root: Path,
    r7_audit: Path, raw_manifest: Path, output: Path, created_at: str,
) -> dict[str, Any]:
    protocol = ReleaseProtocol.load()
    head, origin = git_head(), _origin_main()
    if head != origin:
        raise ProtocolError("M6-5B implementation is not synchronized")
    snapshot = code_snapshot_sha256()
    if verify_release_manifest(image_manifest, root=PROJECT_ROOT) != snapshot:
        raise ProtocolError("M6-5B embedded manifest does not match host")
    raw_manifest.parent.mkdir(parents=True, exist_ok=True)
    _, _, reused_raw = write_manifest(PROJECT_ROOT / "ledger/ingest_batches.csv", raw_manifest)
    document = build_document(
        protocol=protocol, created_at=created_at, commit=head, origin=origin,
        snapshot=snapshot, image_id=image_id, image_platform=image_platform,
        image_manifest_path=image_manifest, r2_root=r2_root, r7_audit=r7_audit,
        raw_manifest_path=raw_manifest,
    )
    digest, reused = write_once_document(output, document)
    return {
        "release_scope_sha256": document["release_scope_sha256"],
        "document_sha256": digest, "scope_reused": reused,
        "raw_manifest_reused": reused_raw, "execution_authorized": False,
        "family_attempts_before_run": 1, "production_authorization": "none",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--image-platform", required=True)
    parser.add_argument("--image-manifest", type=Path, required=True)
    parser.add_argument("--r2-root", type=Path, required=True)
    parser.add_argument("--r7-audit", type=Path, required=True)
    parser.add_argument("--raw-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--created-at", default=datetime.now(timezone.utc).isoformat())
    print(json.dumps(build(**vars(parser.parse_args())), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

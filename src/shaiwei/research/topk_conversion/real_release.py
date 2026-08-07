"""Build the exact metadata-only M6-3C Top20 release scope."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Any

from shaiwei.config import PROJECT_ROOT
from shaiwei.provenance import (
    RELEASE_MANIFEST_SCHEMA,
    code_snapshot_sha256,
    git_head,
    verify_release_manifest,
)
from shaiwei.research.model_attribution.contract import canonical_sha256, sha256_file
from shaiwei.research.model_attribution.audit_recovery_contract import effect_tree_identity
from shaiwei.research.topk_conversion.contract import ConversionError
from shaiwei.research.topk_conversion.real_contract import (
    APPROVAL_ACTION,
    AUDITOR_COMMAND,
    IMAGE,
    RUNNER_COMMAND,
    SCOPE_KIND,
    SCOPE_SCHEMA,
    RealProtocol,
    expected_authority,
    expected_inputs,
    mapping,
    validate_scope,
    write_once_document,
)


def _origin_main() -> str:
    value = subprocess.run(
        ["git", "rev-parse", "origin/main"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if len(value) != 40:
        raise ConversionError("M6-3C origin/main identity is invalid")
    return value


def _image_manifest(path: Path) -> dict[str, Any]:
    document = mapping(path)
    if document.get("schema_version") != RELEASE_MANIFEST_SCHEMA:
        raise ConversionError("M6-3C image release manifest schema differs")
    return document


def _verify_sealed_metadata(protocol: RealProtocol) -> None:
    frozen = expected_inputs(protocol)
    effect = frozen["sealed_m6_effect"]
    root = PROJECT_ROOT / effect["root"]
    observed = effect_tree_identity(root)
    if observed != {
        "file_count": effect["file_count"],
        "total_bytes": effect["total_bytes"],
        "tree_sha256": effect["tree_sha256"],
    }:
        raise ConversionError("M6-3C sealed effect metadata drifted before release")
    if sha256_file(root / "report.json") != effect["report_sha256"]:
        raise ConversionError("M6-3C sealed effect report drifted before release")
    audit = frozen["sealed_m6_audit"]
    if sha256_file(PROJECT_ROOT / audit["path"]) != audit["sha256"]:
        raise ConversionError("M6-3C sealed audit drifted before release")


def build_release_document(
    *,
    protocol: RealProtocol,
    created_at: str,
    implementation_git_commit: str,
    origin_main_commit: str,
    code_snapshot: str,
    image_id: str,
    image_platform: str,
    image_git_commit: str,
    image_release_manifest_path: Path,
) -> dict[str, Any]:
    if implementation_git_commit != origin_main_commit:
        raise ConversionError("M6-3C implementation is not pushed to origin/main")
    image_manifest = _image_manifest(image_release_manifest_path)
    if image_manifest.get("code_snapshot_sha256") != code_snapshot:
        raise ConversionError("M6-3C image and host code snapshots differ")
    if image_git_commit != implementation_git_commit:
        raise ConversionError("M6-3C image Git identity differs")
    docker = protocol.document["docker"]
    scope = {
        "scope_kind": SCOPE_KIND,
        "created_at": created_at,
        "protocol_id": protocol.document["protocol_id"],
        "protocols": {
            "real_release_sha256": protocol.sha256,
            "result_sha256": protocol.result_sha256,
            "engineering_sha256": protocol.engineering_sha256,
            "schedule_addendum_sha256": protocol.addendum_sha256,
        },
        "implementation": {
            "git_commit": implementation_git_commit,
            "origin_main_commit": origin_main_commit,
            "code_snapshot_sha256": code_snapshot,
        },
        "image": {
            "reference": IMAGE,
            "image_id": image_id,
            "platform": image_platform,
            "git_commit": image_git_commit,
            "code_snapshot_sha256": image_manifest["code_snapshot_sha256"],
            "release_manifest_sha256": sha256_file(image_release_manifest_path),
            "release_manifest_file_count": image_manifest["file_count"],
        },
        "inputs": expected_inputs(protocol),
        "execution": {
            "approval_action": APPROVAL_ACTION,
            "runner_invocation_count": 1,
            "complete_internal_passes": ["first_pass", "replay"],
            "independent_auditor_invocation_count": 1,
            "portfolio_attempt_count_consumed_at_first_top20_effect_read": 2,
            "model_attempt_increment": 0,
            "same_release_retry_authorized": False,
        },
        "container": {
            "compose_path": docker["compose_file"],
            "compose_sha256": sha256_file(PROJECT_ROOT / docker["compose_file"]),
            "network_mode": "none",
            "read_only_root": True,
            "run_as_non_root": True,
            "cap_drop_all": True,
            "no_new_privileges": True,
            "env_file_mounted": False,
            "docker_socket_mounted": False,
            "full_project_root_mounted": False,
            "production_ledger_mounted": False,
            "runner": {
                "service": "m6-topk-effect-runner",
                "command": RUNNER_COMMAND,
                "cpus": 4,
                "memory": "8g",
                "pids_limit": 192,
                "mounts": [dict(row) for row in docker["runner_mounts"]],
            },
            "auditor": {
                "service": "m6-topk-effect-auditor",
                "command": AUDITOR_COMMAND,
                "cpus": 2,
                "memory": "4g",
                "pids_limit": 128,
                "mounts": [dict(row) for row in docker["auditor_mounts"]],
            },
        },
        "outputs": {
            "effect_root": "data/research/m6_csi800_topk20_conversion_v1/effect",
            "audit_root": "data/research/m6_csi800_topk20_conversion_v1/effect-audit",
            "experiment_ledger_write_authorized": False,
        },
        "authority": expected_authority(),
    }
    validate_scope(scope, protocol)
    return {
        "schema_version": SCOPE_SCHEMA,
        "release_scope_sha256": canonical_sha256(scope),
        "scope": scope,
    }


def build(
    *,
    image_id: str,
    image_platform: str,
    image_git_commit: str,
    image_release_manifest: Path,
    output: Path,
    created_at: str,
) -> dict[str, Any]:
    expected = PROJECT_ROOT / "config/m6_csi800_topk20_conversion_release_scope_v1.json"
    if output.resolve() != expected.resolve():
        raise ConversionError("M6-3C release output path differs")
    protocol = RealProtocol.load()
    _verify_sealed_metadata(protocol)
    head, origin = git_head(), _origin_main()
    if head != origin:
        raise ConversionError("M6-3C implementation HEAD is not synchronized with origin/main")
    snapshot = code_snapshot_sha256()
    if verify_release_manifest(image_release_manifest, root=PROJECT_ROOT) != snapshot:
        raise ConversionError("M6-3C host controlled tree differs from the built image")
    document = build_release_document(
        protocol=protocol,
        created_at=created_at,
        implementation_git_commit=head,
        origin_main_commit=origin,
        code_snapshot=snapshot,
        image_id=image_id,
        image_platform=image_platform,
        image_git_commit=image_git_commit,
        image_release_manifest_path=image_release_manifest,
    )
    digest, reused = write_once_document(output, document)
    return {
        "release_scope_sha256": document["release_scope_sha256"],
        "document_sha256": digest,
        "reused": reused,
        "release_ready": True,
        "execution_authorized": False,
        "strategy_effective": "NOT_EVALUATED_FOR_PRODUCTION",
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
    args = parser.parse_args()
    print(json.dumps(build(**vars(args)), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

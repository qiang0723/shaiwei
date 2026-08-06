"""Build the exact metadata-only M6-2 effect release scope."""

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
from shaiwei.research.model_attribution.contract import (
    AttributionError,
    canonical_sha256,
    sha256_file,
)
from shaiwei.research.model_attribution.effect_contract import (
    APPROVAL_ACTION,
    ENGINEERING_MANIFEST,
    EffectProtocol,
    SCOPE_KIND,
    _expected_authority,
    _validate_release_scope,
    write_once_document,
)


RUNNER_COMMAND = [
    "python",
    "-m",
    "shaiwei.research.model_attribution.effect_run",
    "--release",
    "/inputs/release.json",
    "--approval",
    "/inputs/approval.json",
    "--provider-root",
    "/qlib",
    "--output-root",
    "/outputs",
]
AUDITOR_COMMAND = [
    "python",
    "-m",
    "shaiwei.research.model_attribution.effect_audit",
    "--release",
    "/inputs/release.json",
    "--approval",
    "/inputs/approval.json",
    "--effect-root",
    "/outputs",
    "--audit-root",
    "/audit",
]


def _origin_main() -> str:
    value = subprocess.run(
        ["git", "rev-parse", "origin/main"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if len(value) != 40:
        raise AttributionError("M6 origin/main identity is invalid")
    return value


def _manifest(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AttributionError("M6 image release manifest is invalid") from error
    if not isinstance(document, dict) or document.get("schema_version") != RELEASE_MANIFEST_SCHEMA:
        raise AttributionError("M6 image release manifest schema differs")
    return document


def build_release_document(
    *,
    protocol: EffectProtocol,
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
        raise AttributionError("M6 implementation commit is not pushed to origin/main")
    manifest = _manifest(image_release_manifest_path)
    if manifest.get("code_snapshot_sha256") != code_snapshot:
        raise AttributionError("M6 image and implementation code snapshots differ")
    if image_git_commit != implementation_git_commit:
        raise AttributionError("M6 image Git identity differs")
    engineering = json.loads(ENGINEERING_MANIFEST.read_text(encoding="utf-8"))
    inputs = {
        key: engineering["frozen_inputs"][key]
        for key in (
            "qlib_manifest_sha256",
            "qlib_tree_sha256",
            "qlib_file_count",
            "calendar_sha256",
            "calendar_row_count",
        )
    }
    docker = protocol.document["docker"]
    scope = {
        "scope_kind": SCOPE_KIND,
        "created_at": created_at,
        "protocol_id": protocol.document["protocol_id"],
        "protocol_sha256": protocol.sha256,
        "result_protocol_sha256": protocol.result_sha256,
        "engineering_manifest_sha256": protocol.document["predecessors"]["engineering_manifest"]["sha256"],
        "implementation": {
            "git_commit": implementation_git_commit,
            "origin_main_commit": origin_main_commit,
            "code_snapshot_sha256": code_snapshot,
            "code_bundle_sha256": code_snapshot,
        },
        "image": {
            "reference": docker["image"],
            "image_id": image_id,
            "platform": image_platform,
            "git_commit": image_git_commit,
            "code_snapshot_sha256": str(manifest["code_snapshot_sha256"]),
            "release_manifest_sha256": sha256_file(image_release_manifest_path),
            "release_manifest_file_count": int(manifest["file_count"]),
        },
        "inputs": inputs,
        "execution": {
            "approval_action": APPROVAL_ACTION,
            "runner_invocation_count": 1,
            "complete_internal_passes": ["first_pass", "replay"],
            "independent_auditor_invocation_count": 1,
            "alternative_attempt_count_consumed_at_first_real_effect_read": 2,
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
                "service": "m6-effect-runner",
                "command": RUNNER_COMMAND,
                "mounts": [dict(row) for row in docker["runner_mounts"]],
                "cpus": 6,
                "memory": "12g",
                "pids_limit": 256,
            },
            "auditor": {
                "service": "m6-effect-auditor",
                "command": AUDITOR_COMMAND,
                "mounts": [dict(row) for row in docker["auditor_mounts"]],
                "cpus": 2,
                "memory": "4g",
                "pids_limit": 256,
            },
        },
        "outputs": {
            "effect_root": "data/research/m6_csi800_model_attribution_v1/effect",
            "audit_root": "data/research/m6_csi800_model_attribution_v1/effect-audit",
            "experiment_ledger_write_authorized": False,
        },
        "authority": _expected_authority(),
    }
    _validate_release_scope(scope, protocol)
    return {
        "schema_version": "m6-model-attribution-release-scope-v1",
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
    expected_output = (PROJECT_ROOT / "config/m6_csi800_model_attribution_release_scope_v1.json").resolve()
    if output.resolve() != expected_output:
        raise AttributionError("M6 release scope output path differs")
    protocol = EffectProtocol.load()
    head = git_head()
    origin = _origin_main()
    if head != origin:
        raise AttributionError("M6 implementation HEAD is not synchronized with origin/main")
    snapshot = code_snapshot_sha256()
    verified = verify_release_manifest(image_release_manifest, root=PROJECT_ROOT)
    if snapshot != verified:
        raise AttributionError("M6 host controlled tree differs from the built image")
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
    args = parser.parse_args()
    print(json.dumps(build(**vars(args)), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

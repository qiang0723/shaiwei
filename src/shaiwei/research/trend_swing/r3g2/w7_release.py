"""Build the metadata-only W7 lineage release scope after image verification."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Any

from shaiwei.config import PROJECT_ROOT
from shaiwei.provenance import code_snapshot_sha256, git_head, verify_release_manifest
from shaiwei.research.model_attribution.contract import ProtocolBundle
from shaiwei.research.trend_swing.contract import canonical_sha256
from shaiwei.research.trend_swing.r3g2.contract import EffectProtocol, R3G2Error, sha256_file
from shaiwei.research.trend_swing.r3g2.evidence import write_once_json
from shaiwei.research.trend_swing.r3g2.w7_control import (
    ACTION,
    AUDITOR_COMMAND,
    RELEASE_PROTOCOL_PATH,
    RUNNER_COMMAND,
    SCOPE_KIND,
    _expected_mounts,
    _validate_scope,
    load_release_protocol,
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
        raise R3G2Error("R3G-2 W7 origin/main identity is invalid")
    return value


def _provider_identity(root: Path) -> dict[str, Any]:
    metadata = ProtocolBundle.load().verify_metadata_inputs(
        root / "_shaiwei_manifest.json", root / "calendars/day.txt"
    )
    return {
        "qlib_manifest_sha256": metadata["qlib_manifest_sha256"],
        "qlib_tree_sha256": metadata["qlib_tree_sha256"],
        "qlib_file_count": metadata["qlib_file_count"],
        "calendar_sha256": sha256_file(root / "calendars/day.txt"),
        "calendar_row_count": metadata["calendar_row_count"],
    }


def build_release_document(
    *,
    protocol: EffectProtocol,
    release_protocol: dict[str, Any],
    release_protocol_sha256: str,
    created_at: str,
    implementation_git_commit: str,
    origin_main_commit: str,
    code_snapshot: str,
    image_id: str,
    image_platform: str,
    image_git_commit: str,
    image_release_manifest_sha256: str,
    image_release_manifest_file_count: int,
    inputs: dict[str, Any],
    document_schema: str = "ts-v5-r3g2-w7-release-scope-v1",
    scope_kind: str = SCOPE_KIND,
    action: str = ACTION,
    release_protocol_path: Path = RELEASE_PROTOCOL_PATH,
    predecessor_failure: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if implementation_git_commit != origin_main_commit:
        raise R3G2Error("R3G-2 W7 implementation is not pushed to origin/main")
    if image_git_commit != implementation_git_commit:
        raise R3G2Error("R3G-2 W7 image Git identity differs")
    if image_platform not in {"linux/arm64", "linux/amd64"}:
        raise R3G2Error("R3G-2 W7 image platform differs")
    docker = release_protocol["docker"]
    scope = {
        "scope_kind": scope_kind,
        "created_at": created_at,
        "protocol_sha256": protocol.sha256,
        "release_protocol_sha256": release_protocol_sha256,
        "implementation": {
            "git_commit": implementation_git_commit,
            "origin_main_commit": origin_main_commit,
            "code_snapshot_sha256": code_snapshot,
        },
        "image": {
            "reference": docker["image"],
            "image_id": image_id,
            "platform": image_platform,
            "git_commit": image_git_commit,
            "code_snapshot_sha256": code_snapshot,
            "release_manifest_sha256": image_release_manifest_sha256,
            "release_manifest_file_count": image_release_manifest_file_count,
        },
        "inputs": inputs,
        "execution": {
            "approval_action": action,
            "runner_invocation_count": 1,
            "complete_internal_passes": ["first_pass", "replay"],
            "independent_auditor_invocation_count": 1,
            "strategy_effect_attempt_count": 0,
            "same_release_retry_authorized": False,
        },
        "container": {
            "compose_path": docker["compose_file"],
            "compose_sha256": sha256_file(PROJECT_ROOT / docker["compose_file"]),
            "network_mode": "none",
            "read_only_root": True,
            "run_as_non_root": True,
            "env_file_mounted": False,
            "docker_socket_mounted": False,
            "full_project_root_mounted": False,
            "production_ledger_mounted": False,
            "runner": {
                "service": docker["runner"]["service"],
                "command": RUNNER_COMMAND,
                "mounts": _expected_mounts(release_protocol, "runner"),
                "cpus": 6,
                "memory": "12g",
                "pids_limit": 256,
            },
            "auditor": {
                "service": docker["auditor"]["service"],
                "command": AUDITOR_COMMAND,
                "mounts": _expected_mounts(release_protocol, "auditor"),
                "cpus": 2,
                "memory": "4g",
                "pids_limit": 256,
            },
        },
        "outputs": {
            "lineage_root": release_protocol["outputs"]["lineage_root"],
            "audit_root": release_protocol["outputs"]["audit_root"],
            "experiment_ledger_write_authorized": False,
        },
        "authority": {
            "w7_training_and_prediction_after_explicit_approval": True,
            "label_rankic_return_or_effect_read": False,
            "external_network": False,
            "env_or_secret_read": False,
            "experiment_ledger_write": False,
            "paper_web_scheduler_or_production_change": False,
            "production_authorization": "none",
        },
    }
    if predecessor_failure is not None:
        scope["predecessor_failure"] = predecessor_failure
    _validate_scope(
        scope,
        protocol,
        release_protocol,
        release_protocol_path=release_protocol_path,
        scope_kind=scope_kind,
        action=action,
        predecessor_failure=predecessor_failure,
    )
    return {
        "schema_version": document_schema,
        "release_scope_sha256": canonical_sha256(scope),
        "scope": scope,
    }


def build(
    *,
    image_id: str,
    image_platform: str,
    image_git_commit: str,
    image_release_manifest: Path,
    provider_root: Path,
    output: Path,
    created_at: str,
) -> dict[str, Any]:
    expected = (PROJECT_ROOT / "config/ts_v5_r3g2_w7_release_scope_v1.json").resolve()
    if output.resolve() != expected:
        raise R3G2Error("R3G-2 W7 release output path differs")
    protocol = EffectProtocol.load()
    protocol.validate_bound_inputs()
    release_protocol, release_protocol_sha = load_release_protocol(protocol)
    head, origin = git_head(), _origin_main()
    if head != origin:
        raise R3G2Error("R3G-2 W7 HEAD is not synchronized with origin/main")
    snapshot = code_snapshot_sha256()
    if verify_release_manifest(image_release_manifest, root=PROJECT_ROOT) != snapshot:
        raise R3G2Error("R3G-2 W7 host and image controlled trees differ")
    manifest = json.loads(image_release_manifest.read_text(encoding="utf-8"))
    inputs = _provider_identity(provider_root)
    if inputs != release_protocol["frozen_provider"]:
        raise R3G2Error("R3G-2 W7 provider differs from release protocol")
    document = build_release_document(
        protocol=protocol,
        release_protocol=release_protocol,
        release_protocol_sha256=release_protocol_sha,
        created_at=created_at,
        implementation_git_commit=head,
        origin_main_commit=origin,
        code_snapshot=snapshot,
        image_id=image_id,
        image_platform=image_platform,
        image_git_commit=image_git_commit,
        image_release_manifest_sha256=sha256_file(image_release_manifest),
        image_release_manifest_file_count=int(manifest["file_count"]),
        inputs=inputs,
    )
    digest, reused = write_once_json(output, document)
    return {
        "release_scope_sha256": document["release_scope_sha256"],
        "document_sha256": digest,
        "reused": reused,
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
    parser.add_argument("--provider-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--created-at", default=datetime.now(timezone.utc).isoformat())
    args = parser.parse_args()
    print(json.dumps(build(**vars(args)), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Build the exact metadata-only R3G-2 real-effect release scope."""

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
from shaiwei.research.trend_swing.r3g2.contract import EffectProtocol, R3G2Error, sha256_file
from shaiwei.research.trend_swing.r3g2.effect_control import (
    ACTION,
    AUDITOR_COMMAND,
    RUNNER_COMMAND,
    SCOPE_KIND,
    ReleaseProtocol,
    _validate_scope,
    canonical_sha256,
    expected_scope_authority,
)
from shaiwei.research.trend_swing.r3g2.evidence import write_once_json


SCOPE_PATH = PROJECT_ROOT / "config/ts_v5_r3g2_effect_release_scope_v1.json"
PREFLIGHT_PATH = PROJECT_ROOT / (
    "data/research/trend_swing/ts-v5-r3g2-effect-preflight-v1/report.json"
)
EFFECT_ROOT = PROJECT_ROOT / "data/research/trend_swing/ts-v5-r3g2-effect-v1"
AUDIT_ROOT = PROJECT_ROOT / "data/research/trend_swing/ts-v5-r3g2-effect-v1-audit"
APPROVAL_PATH = PROJECT_ROOT / "data/control/ts-v5-r3g2-effect-v1/approval.json"


def _origin_main() -> str:
    value = subprocess.run(
        ["git", "rev-parse", "origin/main"], cwd=PROJECT_ROOT,
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    if len(value) != 40:
        raise R3G2Error("R3G-2 origin/main identity is invalid")
    return value


def _manifest(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise R3G2Error("R3G-2 image release manifest is invalid") from error
    if document.get("schema_version") != RELEASE_MANIFEST_SCHEMA:
        raise R3G2Error("R3G-2 image release manifest schema differs")
    return document


def _mounts() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    sources = [
        ("data/raw", "/workspace/data/raw"),
        ("data/research/trend_swing/ts-v3-data-gate-r3", "/workspace/data/research/trend_swing/ts-v3-data-gate-r3"),
        ("data/research/trend_swing/ts-v5-r3g-executable-semantics", "/workspace/data/research/trend_swing/ts-v5-r3g-executable-semantics"),
        ("data/research/trend_swing/ts-v5-r3g1-recent-density-r2", "/workspace/data/research/trend_swing/ts-v5-r3g1-recent-density-r2"),
        ("data/research/trend_swing/ts-v5-r3g2-benchmark-lineage-v1", "/workspace/data/research/trend_swing/ts-v5-r3g2-benchmark-lineage-v1"),
        ("data/research/m6_csi800_model_attribution_v1/effect/first_pass", "/workspace/data/research/m6_csi800_model_attribution_v1/effect/first_pass"),
        ("data/research/trend_swing/ts-v5-r3g2-w7-lineage-recovery", "/workspace/data/research/trend_swing/ts-v5-r3g2-w7-lineage-recovery"),
        ("data/research/trend_swing/ts-v5-r3g2-w7-lineage-recovery-audit", "/workspace/data/research/trend_swing/ts-v5-r3g2-w7-lineage-recovery-audit"),
    ]
    runner = [{"source": source, "target": target, "access": "read_only"} for source, target in sources]
    runner.extend(
        [
            {"source": "config/ts_v5_r3g2_effect_release_scope_v1.json", "target": "/inputs/release.json", "access": "read_only"},
            {"source": "data/control/ts-v5-r3g2-effect-v1/approval.json", "target": "/inputs/approval.json", "access": "read_only"},
            {"source": "data/research/trend_swing/ts-v5-r3g2-effect-v1", "target": "/outputs", "access": "read_write"},
        ]
    )
    auditor = [
        {"source": "config/ts_v5_r3g2_effect_release_scope_v1.json", "target": "/inputs/release.json", "access": "read_only"},
        {"source": "data/control/ts-v5-r3g2-effect-v1/approval.json", "target": "/inputs/approval.json", "access": "read_only"},
        {"source": "data/research/trend_swing/ts-v5-r3g2-effect-v1", "target": "/outputs", "access": "read_only"},
        {"source": "data/research/trend_swing/ts-v5-r3g2-effect-v1-audit", "target": "/audit", "access": "read_write"},
    ]
    return runner, auditor


def build_release_document(
    *,
    protocol: EffectProtocol,
    release_protocol: ReleaseProtocol,
    preflight: dict[str, Any],
    created_at: str,
    implementation_git_commit: str,
    origin_main_commit: str,
    code_snapshot: str,
    image_id: str,
    image_platform: str,
    image_git_commit: str,
    image_release_manifest_path: Path,
    bound_input_hashes: dict[str, str],
) -> dict[str, Any]:
    if implementation_git_commit != origin_main_commit or image_git_commit != implementation_git_commit:
        raise R3G2Error("R3G-2 implementation is not the pushed image identity")
    if bound_input_hashes != protocol.bound_input_contract():
        raise R3G2Error("R3G-2 validated bound-input claims differ from the protocol")
    manifest = _manifest(image_release_manifest_path)
    if manifest.get("code_snapshot_sha256") != code_snapshot:
        raise R3G2Error("R3G-2 image and host code snapshots differ")
    runner_mounts, auditor_mounts = _mounts()
    scope = {
        "scope_kind": SCOPE_KIND,
        "created_at": created_at,
        "effect_protocol_sha256": protocol.sha256,
        "release_protocol_sha256": release_protocol.sha256,
        "implementation": {
            "git_commit": implementation_git_commit,
            "origin_main_commit": origin_main_commit,
            "code_snapshot_sha256": code_snapshot,
        },
        "image": {
            "reference": release_protocol.document["docker"]["image"],
            "image_id": image_id,
            "platform": image_platform,
            "git_commit": image_git_commit,
            "release_manifest_sha256": sha256_file(image_release_manifest_path),
            "release_manifest_file_count": int(manifest["file_count"]),
        },
        "inputs": {
            "pre_effect_preflight_sha256": canonical_sha256(preflight),
            "bound_input_hashes": dict(bound_input_hashes),
            "w7_recovery_manifest_sha256": release_protocol.document["predecessors"]["w7_recovery_manifest"]["sha256"],
        },
        "execution": {
            "approval_action": ACTION,
            "runner_invocation_count": 1,
            "complete_internal_passes": ["first_pass", "replay"],
            "independent_auditor_invocation_count": 1,
            "strategy_effect_attempt_count": 3,
            "same_release_retry_authorized": False,
            "discovery_first_holdout_firewall": True,
        },
        "container": {
            "compose_path": release_protocol.document["docker"]["compose_file"],
            "compose_sha256": sha256_file(
                PROJECT_ROOT / release_protocol.document["docker"]["compose_file"]
            ),
            "network_mode": "none", "read_only_root": True, "run_as_non_root": True,
            "cap_drop_all": True, "no_new_privileges": True, "env_file_mounted": False,
            "docker_socket_mounted": False, "full_project_root_mounted": False,
            "production_ledger_mounted": False,
            "runner": {
                "service": "ts-v5-r3g2-effect-runner", "command": RUNNER_COMMAND,
                "mounts": runner_mounts, "cpus": 6, "memory": "12g", "pids_limit": 256,
            },
            "auditor": {
                "service": "ts-v5-r3g2-effect-auditor", "command": AUDITOR_COMMAND,
                "mounts": auditor_mounts, "cpus": 2, "memory": "4g", "pids_limit": 256,
            },
        },
        "outputs": {
            "effect_root": "data/research/trend_swing/ts-v5-r3g2-effect-v1",
            "audit_root": "data/research/trend_swing/ts-v5-r3g2-effect-v1-audit",
            "empty_at_scope_freeze": True,
            "approval_file_exists_at_scope_freeze": False,
            "experiment_ledger_write_authorized": False,
        },
        "authority": expected_scope_authority(),
    }
    _validate_scope(scope, protocol, release_protocol)
    return {
        "schema_version": "ts-v5-r3g2-effect-release-scope-v1",
        "release_scope_sha256": canonical_sha256(scope),
        "scope": scope,
    }


def build(
    *, image_id: str, image_platform: str, image_git_commit: str,
    image_release_manifest: Path, output: Path, created_at: str,
) -> dict[str, Any]:
    if output.resolve() != SCOPE_PATH.resolve():
        raise R3G2Error("R3G-2 release scope output path differs")
    if not PREFLIGHT_PATH.is_file():
        raise R3G2Error("R3G-2 key-only preflight report is absent")
    if any(not path.is_dir() or any(path.iterdir()) for path in (EFFECT_ROOT, AUDIT_ROOT)):
        raise R3G2Error("R3G-2 effect or audit output is absent or non-empty")
    if APPROVAL_PATH.exists():
        raise R3G2Error("R3G-2 approval exists before the exact user instruction")
    head, origin = git_head(), _origin_main()
    if head != origin:
        raise R3G2Error("R3G-2 implementation HEAD is not synchronized with origin/main")
    snapshot = code_snapshot_sha256()
    if verify_release_manifest(image_release_manifest, root=PROJECT_ROOT) != snapshot:
        raise R3G2Error("R3G-2 controlled host tree differs from the built image")
    release_protocol = ReleaseProtocol.load()
    release_protocol.validate_bound_predecessors()
    protocol = EffectProtocol.load()
    bound_input_hashes = protocol.validate_bound_inputs()
    document = build_release_document(
        protocol=protocol, release_protocol=release_protocol,
        preflight=json.loads(PREFLIGHT_PATH.read_text(encoding="utf-8")),
        created_at=created_at, implementation_git_commit=head, origin_main_commit=origin,
        code_snapshot=snapshot, image_id=image_id, image_platform=image_platform,
        image_git_commit=image_git_commit, image_release_manifest_path=image_release_manifest,
        bound_input_hashes=bound_input_hashes,
    )
    digest, reused = write_once_json(output, document)
    return {
        "release_scope_sha256": document["release_scope_sha256"],
        "document_sha256": digest, "reused": reused, "release_ready": True,
        "execution_authorized": False, "strategy_effective": "NOT_EVALUATED",
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

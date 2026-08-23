"""Build source identity and metadata-only M6-5C release scope."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Any

from shaiwei.build_identity.registry import load_build_registry
from shaiwei.build_identity.release import component_build_snapshot_sha256
from shaiwei.build_identity.source_bundle import build_source_manifest, verify_source_manifest
from shaiwei.config import PROJECT_ROOT
from shaiwei.research.model_attribution.contract import canonical_sha256, sha256_file
from shaiwei.research.production_conversion.contract import ProtocolError
from shaiwei.research.production_conversion.real_contract import write_once_document

from .delisting_release_contract import (
    COMPOSE_PATH,
    DOCKERFILE_PATH,
    IMAGE,
    SCOPE_KIND,
    SCOPE_SCHEMA,
    ReleaseProtocol,
    ReleaseScope,
    expected_authority,
)


MANIFEST_PATH = PROJECT_ROOT / ".web-release/m6-head30-delisting-risk-source-manifest.json"


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=PROJECT_ROOT, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _revision() -> str:
    head = _git("rev-parse", "HEAD")
    origin = _git("rev-parse", "origin/main")
    if head != origin:
        raise ProtocolError("M6-5C implementation is not pushed to origin/main")
    changed = _git("diff", "--name-only", "--", "src", "config", "pyproject.toml")
    if changed:
        raise ProtocolError("M6-5C source tree has uncommitted tracked changes")
    return head


def prepare_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    revision = _revision()
    names = sorted(
        line for line in _git("ls-files", "--", "src", "config", "pyproject.toml").splitlines()
        if line
    )
    document = build_source_manifest(PROJECT_ROOT, names, revision)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return document


def _component_identity() -> dict[str, Any]:
    registry = load_build_registry()
    component = registry.component("m6-head30-delisting-risk-release")
    records = [
        {"path": name, "sha256": sha256_file(PROJECT_ROOT / name)}
        for name in component.assets
    ]
    return {
        "registry_sha256": registry.registry_sha256,
        "build_assets": records,
        "component_build_snapshot_sha256": component_build_snapshot_sha256(records),
    }


def _image(reference: str) -> dict[str, Any]:
    raw = subprocess.run(
        ["docker", "image", "inspect", reference],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    items = json.loads(raw)
    if not isinstance(items, list) or len(items) != 1:
        raise ProtocolError("M6-5C image inspect differs")
    item = items[0]
    labels = item.get("Config", {}).get("Labels", {}) or {}
    return {"image_id": item["Id"], "labels": labels}


def build_scope(
    *, output: Path, fixture_evidence: Path, manifest_path: Path = MANIFEST_PATH,
) -> dict[str, Any]:
    protocol = ReleaseProtocol.load()
    revision = _revision()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    verified = verify_source_manifest(manifest, root=PROJECT_ROOT)
    if verified["git_commit"] != revision:
        raise ProtocolError("M6-5C source manifest revision differs")
    component = _component_identity()
    inspected = _image(IMAGE)
    labels = inspected["labels"]
    expected_labels = {
        "org.opencontainers.image.revision": revision,
        "io.shaiwei.component_build_snapshot_sha256": component[
            "component_build_snapshot_sha256"
        ],
        "io.shaiwei.source_bundle_sha256": verified["source_bundle_sha256"],
    }
    if any(labels.get(key) != value for key, value in expected_labels.items()):
        raise ProtocolError("M6-5C image labels differ")
    fixture = json.loads(fixture_evidence.read_text(encoding="utf-8"))
    if fixture.get("status") != "PASS" or fixture.get("production_authorization") != "none":
        raise ProtocolError("M6-5C daemon fixture differs")
    inputs = protocol.blocked_scope["inputs"]
    scope = {
        "scope_kind": SCOPE_KIND,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": protocol.sha256,
        "implementation": {
            "git_commit": revision,
            "origin_main_commit": revision,
            "source_bundle_sha256": verified["source_bundle_sha256"],
            "source_manifest_sha256": sha256_file(manifest_path),
            **component,
        },
        "image": {
            "reference": IMAGE,
            "image_id": inspected["image_id"],
            "git_commit": revision,
            "source_bundle_sha256": verified["source_bundle_sha256"],
            "component_build_snapshot_sha256": component[
                "component_build_snapshot_sha256"
            ],
            "labels": expected_labels,
        },
        "inputs": inputs,
        "attempt_claim": {
            "spec": protocol.document["attempt_claim"],
            "input_identity_sha256": canonical_sha256(inputs),
            "claim_before_effect_reader": True,
        },
        "execution": {
            "approval_action": protocol.document["execution"]["action"],
            "runner_invocation_count": 1,
            "complete_internal_passes": ["first_pass", "replay"],
            "independent_auditor_invocation_count": 1,
            "attempt_family": "m6_head30_500k_delisting_risk_overlay_v1",
            "family_attempts_before_run": 0,
            "new_attempts_consumed_at_claim": 1,
            "total_family_attempts_after_claim": 1,
            "same_scope_retry_authorized": False,
        },
        "container": {
            "compose_path": COMPOSE_PATH.name,
            "compose_sha256": sha256_file(COMPOSE_PATH),
            "dockerfile_path": DOCKERFILE_PATH.name,
            "dockerfile_sha256": sha256_file(DOCKERFILE_PATH),
            "network_mode": "none",
            "read_only_root": True,
            "run_as_non_root": True,
            "cap_drop_all": True,
            "no_new_privileges": True,
            "env_file_mounted": False,
            "docker_socket_mounted": False,
            "full_project_root_mounted": False,
            "production_write_mount_present": False,
            "canonical_ledger_mount": "runner-rw-auditor-ro",
            "claim_receipt_mount": "runner-rw-auditor-ro",
            "auditor_raw_or_r2_mount": False,
        },
        "daemon_fixture": {
            "evidence_sha256": sha256_file(fixture_evidence),
            "image_id": inspected["image_id"],
            "claim_before_effect_reader": fixture["claim_before_effect_reader"],
            "same_scope_retry_blocked": fixture["same_scope_retry_blocked"],
            "internal_replay_pass": fixture["internal_replay_pass"],
            "independent_reconstruction_pass": fixture["independent_reconstruction_pass"],
            "real_target_or_price_or_effect_read": False,
            "canonical_ledger_write": False,
        },
        "outputs": {
            "approval_path": "data/control/m6_csi800_production_head30_500k_feasibility_v1/delisting-risk-approval.json",
            "claim_receipt_path": "data/control/m6_csi800_production_head30_500k_feasibility_v1/delisting-risk-claim/claim.json",
            "effect_root": "data/research/m6_csi800_production_head30_500k_feasibility_v1/effect-delisting-risk",
            "audit_root": "data/research/m6_csi800_production_head30_500k_feasibility_v1/effect-delisting-risk-audit",
            "write_once": True,
        },
        "authority": expected_authority(),
    }
    document = {
        "schema_version": SCOPE_SCHEMA,
        "release_scope_sha256": canonical_sha256(scope),
        "scope": scope,
    }
    write_once_document(output, document)
    ReleaseScope.load(output, protocol)
    return document


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare-manifest")
    prepare.add_argument("--output", type=Path, default=MANIFEST_PATH)
    scope = subparsers.add_parser("build-scope")
    scope.add_argument("--output", type=Path, required=True)
    scope.add_argument("--fixture-evidence", type=Path, required=True)
    scope.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    args = parser.parse_args()
    document = (
        prepare_manifest(args.output)
        if args.command == "prepare-manifest"
        else build_scope(
            output=args.output,
            fixture_evidence=args.fixture_evidence,
            manifest_path=args.manifest,
        )
    )
    print(json.dumps(document, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

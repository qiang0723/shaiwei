"""Build source identity and metadata-only ordinal-two entitlement scope."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Any

from shaiwei.build_identity.registry import ComponentStatus, load_build_registry
from shaiwei.build_identity.release import component_build_snapshot_sha256
from shaiwei.build_identity.source_bundle import build_source_manifest, verify_source_manifest
from shaiwei.config import PROJECT_ROOT
from shaiwei.research.model_attribution.contract import canonical_sha256, sha256_file
from shaiwei.research.production_conversion.contract import ProtocolError
from shaiwei.research.production_conversion.real_contract import write_once_document

from .contract import (
    COMPONENT_ID,
    IMAGE,
    SCOPE_KIND,
    SCOPE_SCHEMA,
    ReleaseProtocol,
    ReleaseScope,
    expected_authority,
)


MANIFEST_PATH = (
    PROJECT_ROOT / ".web-release/m6-head30-delisting-entitlement-source-manifest.json"
)


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=PROJECT_ROOT, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _revision() -> str:
    head = _git("rev-parse", "HEAD")
    if head != _git("rev-parse", "origin/main"):
        raise ProtocolError("M6-5C-C-R4 implementation is not pushed to origin/main")
    changed = _git("diff", "--name-only", "--", "src", "config", "pyproject.toml")
    if changed:
        raise ProtocolError("M6-5C-C-R4 source tree has uncommitted tracked changes")
    return head


def prepare_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    revision = _revision()
    names = sorted(
        line
        for line in _git("ls-files", "--", "src", "config", "pyproject.toml").splitlines()
        if line
    )
    document = build_source_manifest(PROJECT_ROOT, names, revision)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return document


def component_identity() -> dict[str, Any]:
    registry = load_build_registry()
    component = registry.component(COMPONENT_ID)
    if component.status is not ComponentStatus.ACTIVE_LOCAL_READ_ONLY:
        raise ProtocolError("M6-5C-C-R4 component is closed and cannot form a new release")
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
        raise ProtocolError("M6-5C-C-R4 image inspect differs")
    item = items[0]
    return {"image_id": item["Id"], "labels": item.get("Config", {}).get("Labels", {}) or {}}


def build_scope(
    *, output: Path, fixture_evidence: Path, manifest_path: Path = MANIFEST_PATH
) -> dict[str, Any]:
    protocol = ReleaseProtocol.load()
    revision = _revision()
    verified = verify_source_manifest(
        json.loads(manifest_path.read_text(encoding="utf-8")), root=PROJECT_ROOT
    )
    if verified["git_commit"] != revision:
        raise ProtocolError("M6-5C-C-R4 source manifest revision differs")
    component = component_identity()
    inspected = _image(IMAGE)
    expected_labels = {
        "org.opencontainers.image.revision": revision,
        "io.shaiwei.component_build_snapshot_sha256": component[
            "component_build_snapshot_sha256"
        ],
        "io.shaiwei.source_bundle_sha256": verified["source_bundle_sha256"],
    }
    if any(inspected["labels"].get(key) != value for key, value in expected_labels.items()):
        raise ProtocolError("M6-5C-C-R4 image labels differ")
    fixture = json.loads(fixture_evidence.read_text(encoding="utf-8"))
    if (
        fixture.get("status") != "PASS"
        or fixture.get("release_scope_loader_pass") is not True
        or fixture.get("production_authorization") != "none"
    ):
        raise ProtocolError("M6-5C-C-R4 daemon fixture differs")
    inputs = protocol.failed_scope["inputs"]
    protocol_release = protocol.document["release"]
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
            "approval_action": protocol_release["approval_action"],
            "runner_invocation_count": 1,
            "complete_internal_passes": ["first_pass", "replay"],
            "independent_auditor_invocation_count": 1,
            "attempt_family": "m6_head30_500k_delisting_risk_overlay_v1",
            "family_attempts_before_run": 1,
            "new_attempts_consumed_at_claim": 1,
            "total_family_attempts_after_claim": 2,
            "same_scope_retry_authorized": False,
        },
        "container": {
            "compose_path": protocol_release["compose"],
            "compose_sha256": sha256_file(PROJECT_ROOT / protocol_release["compose"]),
            "dockerfile_path": protocol_release["dockerfile"],
            "dockerfile_sha256": sha256_file(PROJECT_ROOT / protocol_release["dockerfile"]),
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
            "claim_before_effect_reader": True,
            "same_scope_retry_blocked": True,
            "internal_replay_pass": True,
            "independent_reconstruction_pass": True,
            "detached_entitlement_round_trip_pass": True,
            "real_target_or_price_or_effect_read": False,
            "canonical_ledger_write": False,
        },
        "outputs": {
            "approval_path": "data/control/m6_csi800_production_head30_500k_feasibility_v1/delisting-entitlement-approval-r4.json",
            "claim_receipt_path": "data/control/m6_csi800_production_head30_500k_feasibility_v1/delisting-entitlement-claim-r4/claim.json",
            "effect_root": "data/research/m6_csi800_production_head30_500k_feasibility_v1/effect-delisting-entitlement-r4",
            "audit_root": "data/research/m6_csi800_production_head30_500k_feasibility_v1/effect-delisting-entitlement-r4-audit",
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
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare-manifest")
    prepare.add_argument("--output", type=Path, default=MANIFEST_PATH)
    scope = commands.add_parser("build-scope")
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

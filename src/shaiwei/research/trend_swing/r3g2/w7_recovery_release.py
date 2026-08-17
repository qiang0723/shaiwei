"""Build the result-blind W7 entrypoint-recovery release scope."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from shaiwei.config import PROJECT_ROOT
from shaiwei.provenance import code_snapshot_sha256, git_head, verify_release_manifest
from shaiwei.research.trend_swing.r3g2.contract import (
    EffectProtocol,
    R3G2Error,
    project_path,
    sha256_file,
)
from shaiwei.research.trend_swing.r3g2.evidence import write_once_json
from shaiwei.research.trend_swing.r3g2.w7_control import (
    EXPECTED_FAILURE_FACTS,
    RECOVERY_ACTION,
    RECOVERY_PROTOCOL_PATH,
    RECOVERY_SCOPE_KIND,
    load_recovery_protocol,
    recovery_predecessor_record,
)
from shaiwei.research.trend_swing.r3g2.w7_release import (
    _origin_main,
    _provider_identity,
    build_release_document,
)


OUTPUT_PATH = PROJECT_ROOT / "config/ts_v5_r3g2_w7_recovery_scope_v1.json"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise R3G2Error(f"R3G-2 W7 recovery evidence is invalid: {path.name}") from error
    if not isinstance(document, dict):
        raise R3G2Error(f"R3G-2 W7 recovery evidence is not a mapping: {path.name}")
    return document


def _verify_empty_root(spec: dict[str, Any]) -> int:
    root = project_path(str(spec["path"]))
    if not root.is_dir():
        raise R3G2Error("R3G-2 W7 original output root is absent")
    count = sum(1 for path in root.rglob("*") if path.is_file())
    if count != spec["expected_file_count"]:
        raise R3G2Error("R3G-2 W7 original output roots are not empty")
    return count


def verify_predecessor_evidence(recovery: dict[str, Any]) -> dict[str, Any]:
    predecessor = recovery["predecessor"]
    original_spec = predecessor["original_release"]
    original_path = project_path(str(original_spec["path"]))
    original = _read_json(original_path)
    if (
        sha256_file(original_path) != original_spec["document_sha256"]
        or original.get("release_scope_sha256") != original_spec["scope_sha256"]
    ):
        raise R3G2Error("R3G-2 W7 original release evidence differs")

    approval_spec = predecessor["original_approval"]
    approval_path = project_path(str(approval_spec["path"]))
    approval = _read_json(approval_path)
    if sha256_file(approval_path) != approval_spec["sha256"] or approval != {
        "schema_version": "ts-v5-r3g2-w7-explicit-approval-v1",
        "release_scope_sha256": original_spec["scope_sha256"],
        "action": "TS_R3G2_W7_SCORE_LINEAGE_ONCE_WITH_REPLAY_AND_INDEPENDENT_AUDIT",
        "approved": True,
    }:
        raise R3G2Error("R3G-2 W7 original approval evidence differs")

    receipt_spec = predecessor["failure_receipt"]
    receipt_path = project_path(str(receipt_spec["path"]))
    receipt = _read_json(receipt_path)
    observed_facts = {key: receipt.get(key) for key in EXPECTED_FAILURE_FACTS}
    if (
        sha256_file(receipt_path) != receipt_spec["sha256"]
        or receipt.get("schema_version") != "ts-v5-r3g2-w7-entrypoint-failure-v1"
        or receipt.get("release_scope_sha256") != original_spec["scope_sha256"]
        or receipt.get("approval_sha256") != approval_spec["sha256"]
        or receipt.get("error_type") != receipt_spec["error_type"]
        or receipt.get("error_message") != receipt_spec["error_message"]
        or observed_facts != receipt_spec["frozen_facts"]
        or receipt.get("label_rankic_return_or_effect_read") is not False
        or receipt.get("w7_model_or_prediction_generated") is not False
        or receipt.get("production_authorization") != "none"
    ):
        raise R3G2Error("R3G-2 W7 entrypoint failure evidence differs")

    empty = predecessor["preserved_empty_roots"]
    if _verify_empty_root(empty["lineage"]) != 0 or _verify_empty_root(empty["audit"]) != 0:
        raise R3G2Error("R3G-2 W7 original output roots differ")
    return recovery_predecessor_record(recovery)


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
    if output.resolve() != OUTPUT_PATH.resolve():
        raise R3G2Error("R3G-2 W7 recovery release output path differs")
    protocol = EffectProtocol.load()
    protocol.validate_bound_inputs()
    recovery, recovery_sha = load_recovery_protocol(protocol)
    predecessor = verify_predecessor_evidence(recovery)
    head, origin = git_head(), _origin_main()
    if head != origin:
        raise R3G2Error("R3G-2 W7 recovery HEAD is not synchronized with origin/main")
    snapshot = code_snapshot_sha256()
    if verify_release_manifest(image_release_manifest, root=PROJECT_ROOT) != snapshot:
        raise R3G2Error("R3G-2 W7 recovery host and image controlled trees differ")
    manifest = _read_json(image_release_manifest)
    inputs = _provider_identity(provider_root)
    if inputs != recovery["frozen_provider"]:
        raise R3G2Error("R3G-2 W7 recovery provider differs from release protocol")
    document = build_release_document(
        protocol=protocol,
        release_protocol=recovery,
        release_protocol_sha256=recovery_sha,
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
        document_schema="ts-v5-r3g2-w7-entrypoint-recovery-scope-v1",
        scope_kind=RECOVERY_SCOPE_KIND,
        action=RECOVERY_ACTION,
        release_protocol_path=RECOVERY_PROTOCOL_PATH,
        predecessor_failure=predecessor,
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

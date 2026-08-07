"""Build the content-addressed M6 Top30 recovery release scope."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from typing import Any

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.model_attribution.contract import sha256_file
from shaiwei.research.top30_diagnostic.contract import code_bundle_identity
from shaiwei.research.top30_diagnostic.exact import DiagnosticError, canonical_sha256
from shaiwei.research.top30_diagnostic.recovery_contract import (
    ACTION,
    COMPOSE_PATH,
    CURRENT_IMAGE,
    DOCKERFILE_PATH,
    ORIGINAL_IMAGE,
    OUTPUT_ROOT,
    RecoveryProtocol,
    SCOPE_KIND,
    SCOPE_SCHEMA,
    expected_container,
    expected_inputs,
    expected_preapproval_authority,
)


def _git(name: str) -> str:
    result = subprocess.run(
        ["git", "rev-parse", name], cwd=PROJECT_ROOT, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _image(
    *,
    role: str,
    reference: str,
    image_id: str,
    base_reference: str,
    base_image_id: str,
    platform: str,
    manifest_sha256: str,
    commit: str,
    bundle_sha256: str,
) -> dict[str, Any]:
    if role not in {"original", "current"}:
        raise DiagnosticError("Top30 recovery image role differs")
    if not image_id.startswith("sha256:") or not base_image_id.startswith("sha256:"):
        raise DiagnosticError("Top30 recovery image ID is invalid")
    if platform not in {"linux/arm64", "linux/amd64"} or len(manifest_sha256) != 64:
        raise DiagnosticError("Top30 recovery image metadata is invalid")
    return {
        "reference": reference,
        "image_id": image_id,
        "base_reference": base_reference,
        "base_image_id": base_image_id,
        "platform": platform,
        "git_commit": commit,
        "role": role,
        "code_bundle_sha256": bundle_sha256,
        "release_manifest_sha256": manifest_sha256,
    }


def build_scope(
    *,
    original_image_id: str,
    current_image_id: str,
    original_manifest_sha256: str,
    current_manifest_sha256: str,
    platform: str,
) -> dict[str, Any]:
    protocol = RecoveryProtocol.load()
    commit, origin = _git("HEAD"), _git("origin/main")
    if commit != origin:
        raise DiagnosticError("Top30 recovery implementation is not pushed to origin/main")
    bundle = code_bundle_identity()
    frozen = protocol.document["frozen_runtime_inputs"]
    images = {
        "original": _image(
            role="original", reference=ORIGINAL_IMAGE, image_id=original_image_id,
            base_reference=frozen["original_m6_image"]["reference"],
            base_image_id=frozen["original_m6_image"]["image_id"], platform=platform,
            manifest_sha256=original_manifest_sha256, commit=commit,
            bundle_sha256=bundle["sha256"],
        ),
        "current": _image(
            role="current", reference=CURRENT_IMAGE, image_id=current_image_id,
            base_reference=frozen["failed_m6_3c_image"]["reference"],
            base_image_id=frozen["failed_m6_3c_image"]["image_id"], platform=platform,
            manifest_sha256=current_manifest_sha256, commit=commit,
            bundle_sha256=bundle["sha256"],
        ),
    }
    scope = {
        "scope_kind": SCOPE_KIND,
        "protocol_id": protocol.recovery_document["protocol_id"],
        "protocol_sha256": protocol.sha256,
        "base_protocol_sha256": protocol.base.sha256,
        "predecessor_failure": protocol.recovery_document["predecessor_failure"],
        "implementation": {
            "git_commit": commit,
            "origin_main_commit": origin,
            "code_bundle_sha256": bundle["sha256"],
            "code_bundle_file_count": bundle["file_count"],
            "dockerfile_sha256": sha256_file(DOCKERFILE_PATH),
            "compose_sha256": sha256_file(COMPOSE_PATH),
        },
        "images": images,
        "inputs": expected_inputs(protocol),
        "authority": expected_preapproval_authority(),
        "execution": {
            "approval_action": ACTION,
            "original_runner_invocation_count": 1,
            "current_runner_invocation_count": 1,
            "independent_auditor_invocation_count": 1,
            "total_top30_backtest_count": 6,
            "top20_backtest_count": 0,
            "research_attempt_increment": 0,
            "same_release_retry_authorized": False,
        },
        "container": expected_container(),
        "outputs": {
            "root": OUTPUT_ROOT,
            "original": f"{OUTPUT_ROOT}/original",
            "current": f"{OUTPUT_ROOT}/current",
            "audit": f"{OUTPUT_ROOT}/audit",
            "experiment_ledger_write_authorized": False,
        },
    }
    return {
        "schema_version": SCOPE_SCHEMA,
        "diagnostic_scope_sha256": canonical_sha256(scope),
        "scope": scope,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original-image-id", required=True)
    parser.add_argument("--current-image-id", required=True)
    parser.add_argument("--original-manifest-sha256", required=True)
    parser.add_argument("--current-manifest-sha256", required=True)
    parser.add_argument("--platform", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    document = build_scope(
        original_image_id=args.original_image_id,
        current_image_id=args.current_image_id,
        original_manifest_sha256=args.original_manifest_sha256,
        current_manifest_sha256=args.current_manifest_sha256,
        platform=args.platform,
    )
    args.output.write_text(
        json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    print(document["diagnostic_scope_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

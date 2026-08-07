"""Build the content-addressed, already-authorized M6-3C-R3 read-only scope."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from typing import Any

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.top30_diagnostic.exact import DiagnosticError, canonical_sha256
from shaiwei.research.top30_provenance.contract import (
    COMPOSE_PATH,
    DOCKERFILE_PATH,
    FAILED_IMAGE,
    ORIGINAL_IMAGE,
    OUTPUT_ROOT,
    Protocol,
    SCOPE_KIND,
    SCOPE_SCHEMA,
    code_bundle_identity,
    sha256_file,
    tree_identity,
)


def _git(name: str) -> str:
    result = subprocess.run(
        ["git", "rev-parse", name], cwd=PROJECT_ROOT, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _image(
    *, role: str, reference: str, image_id: str, base: dict[str, Any],
    manifest_sha256: str, commit: str, bundle: dict[str, Any], platform: str,
) -> dict[str, Any]:
    if not image_id.startswith("sha256:") or len(manifest_sha256) != 64:
        raise DiagnosticError("Top30 provenance image identity is invalid")
    return {
        "role": role,
        "reference": reference,
        "image_id": image_id,
        "base_reference": base["reference"],
        "base_image_id": base["image_id"],
        "git_commit": commit,
        "platform": platform,
        "code_bundle_sha256": bundle["sha256"],
        "release_manifest_sha256": manifest_sha256,
    }


def build_scope(
    *, original_image_id: str, failed_image_id: str, original_manifest_sha256: str,
    failed_manifest_sha256: str, platform: str,
) -> dict[str, Any]:
    protocol = Protocol.load()
    commit, origin = _git("HEAD"), _git("origin/main")
    if commit != origin:
        raise DiagnosticError("Top30 provenance implementation is not pushed to origin/main")
    bundle = code_bundle_identity()
    frozen = protocol.document["frozen_inputs"]
    canonical = PROJECT_ROOT / frozen["canonical_report"]["path"]
    r2_root = PROJECT_ROOT / frozen["diagnostic_root"]["path"]
    inputs = {
        "canonical_report": {"sha256": sha256_file(canonical), "size": canonical.stat().st_size},
        "r2_diagnostic_tree": tree_identity(r2_root),
    }
    if (
        inputs["canonical_report"]["sha256"] != frozen["canonical_report"]["sha256"]
        or inputs["r2_diagnostic_tree"] != {
            key: frozen["diagnostic_root"][key]
            for key in ("file_count", "total_bytes", "tree_sha256")
        }
    ):
        raise DiagnosticError("Top30 provenance frozen input identity differs")
    images = {
        "original": _image(
            role="original", reference=ORIGINAL_IMAGE, image_id=original_image_id,
            base=frozen["original_m6_image"], manifest_sha256=original_manifest_sha256,
            commit=commit, bundle=bundle, platform=platform,
        ),
        "failed": _image(
            role="failed", reference=FAILED_IMAGE, image_id=failed_image_id,
            base=frozen["failed_m6_3c_image"], manifest_sha256=failed_manifest_sha256,
            commit=commit, bundle=bundle, platform=platform,
        ),
    }
    scope = {
        "scope_kind": SCOPE_KIND,
        "protocol_id": protocol.document["protocol_id"],
        "protocol_sha256": protocol.sha256,
        "predecessor": protocol.document["predecessor"],
        "implementation": {
            "git_commit": commit,
            "origin_main_commit": origin,
            "code_bundle_sha256": bundle["sha256"],
            "code_bundle_file_count": bundle["file_count"],
            "dockerfile_sha256": sha256_file(DOCKERFILE_PATH),
            "compose_sha256": sha256_file(COMPOSE_PATH),
        },
        "images": images,
        "inputs": inputs,
        "authority": {
            "execution_authorized": True,
            "authorization_basis": "user_continue_instruction_2026-08-07",
            "existing_top30_evidence_read_authorized": True,
            "top30_backtest_authorized": False,
            "top20_read_or_backtest_authorized": False,
            "qlib_read_authorized": False,
            "model_fit_authorized": False,
            "prediction_generation_authorized": False,
            "experiment_ledger_write_authorized": False,
            "external_network_authorized": False,
            "production_authorization": "none",
        },
        "execution": {
            "original_image_probe_invocation_count": 1,
            "failed_image_probe_invocation_count": 1,
            "collector_invocation_count": 1,
            "independent_auditor_invocation_count": 1,
            "total_top30_backtest_count": 0,
            "top20_backtest_count": 0,
            "research_attempt_increment": 0,
            "same_scope_retry_authorized": False,
        },
        "container": {
            "compose_path": COMPOSE_PATH.name,
            "compose_sha256": sha256_file(COMPOSE_PATH),
            "network_mode": "none",
            "read_only_root": True,
            "run_as_non_root": True,
            "cap_drop_all": True,
            "no_new_privileges": True,
            "full_project_root_mounted": False,
            "qlib_mounted": False,
            "env_file_mounted": False,
            "docker_socket_mounted": False,
            "production_ledger_mounted": False,
        },
        "outputs": {
            "root": OUTPUT_ROOT,
            "probes": f"{OUTPUT_ROOT}/probes",
            "collector": f"{OUTPUT_ROOT}/collector",
            "audit": f"{OUTPUT_ROOT}/audit",
        },
    }
    return {
        "schema_version": SCOPE_SCHEMA,
        "provenance_scope_sha256": canonical_sha256(scope),
        "scope": scope,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original-image-id", required=True)
    parser.add_argument("--failed-image-id", required=True)
    parser.add_argument("--original-manifest-sha256", required=True)
    parser.add_argument("--failed-manifest-sha256", required=True)
    parser.add_argument("--platform", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    document = build_scope(**{key: value for key, value in vars(args).items() if key != "output"})
    args.output.write_text(
        json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    print(document["provenance_scope_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

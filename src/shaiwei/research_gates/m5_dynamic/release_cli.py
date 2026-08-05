"""Create a non-executable M5 data release scope from pushed code and metadata-only inputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .contract import InputManifest, M5DataProtocol, M5GateError, canonical_json, sha256_file
from .implementation_identity import build_implementation_identity
from .release import DataReleaseScope
from .release_builder import build_release_document, write_release_once


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--build-contract", type=Path, required=True)
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--repo-digest", required=True)
    parser.add_argument("--platform", choices=("linux/arm64", "linux/amd64"), required=True)
    parser.add_argument("--input-bundle-relative-path", required=True)
    parser.add_argument("--output-relative-path", required=True)
    parser.add_argument("--audit-relative-path", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        protocol = M5DataProtocol.load(
            args.protocol,
            build_path=args.build_contract,
            project_root=args.project_root,
        )
        input_manifest = InputManifest.load(args.input_manifest, protocol)
        implementation = build_implementation_identity(args.project_root)
        document = build_release_document(
            protocol,
            input_manifest,
            created_at=args.created_at,
            git_commit=implementation["git_commit"],
            origin_main_commit=implementation["origin_main_commit"],
            code_bundle_sha256=implementation["code_bundle_sha256"],
            requirements_lock_sha256=sha256_file(
                args.project_root / "requirements.m5-data-gate.lock"
            ),
            dockerfile_sha256=sha256_file(args.project_root / "Dockerfile.m5-data-gate"),
            compose_sha256=sha256_file(args.project_root / "compose.m5-gates.yaml"),
            auditor_code_sha256=sha256_file(
                args.project_root / "src/shaiwei/research_gates/m5_dynamic/auditor.py"
            ),
            image_id=args.image_id,
            repo_digest=args.repo_digest,
            platform=args.platform,
            input_bundle_relative_path=args.input_bundle_relative_path,
            output_relative_path=args.output_relative_path,
            audit_relative_path=args.audit_relative_path,
        )
        physical_sha256 = write_release_once(args.output, document)
        loaded = DataReleaseScope.load(args.output, protocol, input_manifest)
    except (M5GateError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(canonical_json({"status": "FAIL", "error_class": type(error).__name__, "message": str(error)}))
        return 2
    print(
        canonical_json(
            {
                "status": "PASS",
                "release_scope_sha256": loaded.sha256,
                "release_physical_sha256": physical_sha256,
                "code_bundle_sha256": implementation["code_bundle_sha256"],
                "data_gate_execution_authorized": False,
                "real_data_read_authorized": False,
                "production_authorization": "none",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Create an unapproved M5 lineage release from pushed code and metadata inputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from .contract import M5GateError, canonical_json, sha256_file
from .implementation_identity import build_implementation_identity
from .lineage_contract import LineageInputManifest, LineageProtocol
from .lineage_release import LineageReleaseScope
from .lineage_release_builder import (
    build_lineage_release_document,
    write_lineage_release_once,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--build-contract", type=Path, required=True)
    parser.add_argument("--protocol-scope", type=Path, required=True)
    parser.add_argument("--research-config", type=Path, required=True)
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--repo-digest", required=True)
    parser.add_argument("--platform", choices=("linux/arm64", "linux/amd64"), required=True)
    parser.add_argument("--input-relative-path", required=True)
    parser.add_argument("--output-relative-path", required=True)
    parser.add_argument("--audit-relative-path", required=True)
    parser.add_argument("--registry-relative-path", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        protocol = LineageProtocol.load(
            protocol_path=args.protocol,
            build_path=args.build_contract,
            scope_path=args.protocol_scope,
            project_root=args.project_root,
        )
        manifest = LineageInputManifest.load(args.input_manifest)
        research = yaml.safe_load(args.research_config.read_text(encoding="utf-8"))
        implementation = build_implementation_identity(args.project_root)
        document = build_lineage_release_document(
            protocol,
            manifest,
            source_proposal=research["source_proposal"],
            created_at=args.created_at,
            git_commit=implementation["git_commit"],
            origin_main_commit=implementation["origin_main_commit"],
            code_bundle_sha256=implementation["code_bundle_sha256"],
            requirements_lock_sha256=sha256_file(args.project_root / "requirements.m5-data-gate.lock"),
            dockerfile_sha256=sha256_file(args.project_root / "Dockerfile.m5-data-gate"),
            compose_sha256=sha256_file(args.project_root / "compose.m5-lineage.yaml"),
            auditor_code_sha256=sha256_file(
                args.project_root / "src/shaiwei/research_gates/m5_dynamic/audit_lineage.py"
            ),
            image_id=args.image_id,
            repo_digest=args.repo_digest,
            platform=args.platform,
            input_relative_path=args.input_relative_path,
            output_relative_path=args.output_relative_path,
            audit_relative_path=args.audit_relative_path,
            registry_relative_path=args.registry_relative_path,
        )
        physical = write_lineage_release_once(args.output, document)
        loaded = LineageReleaseScope.load(
            args.output,
            protocol,
            manifest,
            source_proposal=research["source_proposal"],
        )
    except (M5GateError, OSError, TypeError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(canonical_json({"status": "FAIL", "error_class": type(error).__name__, "message": str(error)}))
        return 2
    print(
        canonical_json(
            {
                "status": "PASS",
                "release_scope_sha256": loaded.sha256,
                "release_physical_sha256": physical,
                "code_bundle_sha256": implementation["code_bundle_sha256"],
                "lineage_execution_authorized": False,
                "real_data_read_authorized": False,
                "production_authorization": "none",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

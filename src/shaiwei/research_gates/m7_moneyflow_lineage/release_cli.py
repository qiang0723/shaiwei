"""Create the exact non-executable M7 lineage release scope."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from shaiwei.research_gates.m7_moneyflow.contract import canonical_json

from .contract import LineageError, LineageInputManifest, LineageProtocol
from .implementation_identity import build_implementation_identity
from .release import LineageRelease
from .release_builder import build_release_document, write_once


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--repo-digest", required=True)
    parser.add_argument("--platform", choices=("linux/arm64", "linux/amd64"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        protocol = LineageProtocol.load(args.protocol, project_root=args.project_root)
        manifest = LineageInputManifest.load(args.input_manifest, protocol)
        implementation = build_implementation_identity(args.project_root)
        document = build_release_document(
            protocol,
            manifest,
            created_at=args.created_at,
            implementation=implementation,
            image_id=args.image_id,
            repo_digest=args.repo_digest,
            platform=args.platform,
        )
        physical = write_once(args.output, document)
        release = LineageRelease.load(args.output, protocol, manifest)
    except (LineageError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(canonical_json({"status": "FAIL", "error_class": type(error).__name__, "message": str(error)}))
        return 2
    print(
        canonical_json(
            {
                "status": "PASS",
                "release_scope_sha256": release.sha256,
                "release_physical_sha256": physical,
                "code_bundle_sha256": implementation["code_bundle_sha256"],
                "lineage_execution_authorized": False,
                "real_security_key_read_authorized": False,
                "production_authorization": "none",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Offline write-once runner for an exactly approved M5 lineage release."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from .contract import M5GateError, canonical_json
from .lineage import assess_lineage
from .lineage_contract import CONTROL_PATHS, LineageInputManifest, LineageProtocol
from .lineage_projection import build_lineage_reports
from .lineage_reader import load_lineage_inputs
from .lineage_release import LineageApprovalEnvelope, LineageReleaseScope
from .lineage_sealing import seal_lineage_run


def run_approved_lineage(*, input_root: Path, output_root: Path) -> dict[str, object]:
    protocol = LineageProtocol.load(
        protocol_path=input_root / CONTROL_PATHS["protocol"],
        build_path=input_root / CONTROL_PATHS["build"],
        scope_path=input_root / CONTROL_PATHS["scope"],
        project_root=input_root,
    )
    manifest = LineageInputManifest.load(input_root / CONTROL_PATHS["manifest"])
    research = yaml.safe_load((input_root / CONTROL_PATHS["research"]).read_text(encoding="utf-8"))
    release = LineageReleaseScope.load(
        input_root / CONTROL_PATHS["release"],
        protocol,
        manifest,
        source_proposal=research["source_proposal"],
    )
    approval = LineageApprovalEnvelope.load(input_root / CONTROL_PATHS["approval"], release)
    observations, evidence, source = load_lineage_inputs(manifest, input_root=input_root)
    assessment = assess_lineage(observations, evidence, as_of=manifest.document["created_at"])
    lineage, gate = build_lineage_reports(
        assessment,
        protocol_scope_sha256=protocol.scope_document["protocol_scope_sha256"],
        input_manifest_sha256=manifest.sha256,
        release_scope_sha256=release.sha256,
        code_bundle_sha256=release.scope["implementation"]["code_bundle_sha256"],
        approval_event_sha256=approval.document["approval_event_sha256"],
        semantic_rows_read=source["semantic_rows_read"],
    )
    return seal_lineage_run(output_root, lineage, gate)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=Path("/lineage-input"))
    parser.add_argument("--output-root", type=Path, default=Path("/lineage-output"))
    args = parser.parse_args(argv)
    try:
        result = run_approved_lineage(input_root=args.input_root, output_root=args.output_root)
    except (M5GateError, OSError, TypeError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(canonical_json({"status": "FAIL", "error_class": type(error).__name__, "message": str(error)}))
        return 2
    print(
        canonical_json(
            {
                "status": "SEALED_PENDING_INDEPENDENT_AUDIT",
                "run_id": result["run_id"],
                "verdict": result["verdict"],
                "strategy_effective": "NOT_EVALUATED",
                "production_authorization": "none",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

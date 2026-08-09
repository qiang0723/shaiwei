"""One-shot offline projector for the two frozen real R2 recovery categories."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Callable

from shaiwei.research_gates.m7_moneyflow.contract import canonical_json, sha256_json
from shaiwei.research_gates.m7_moneyflow_lineage.contract import (
    LineageInputManifest,
    LineageProtocol,
)
from shaiwei.research_gates.m7_moneyflow_lineage.reader import LineageInputs, load_lineage_inputs

from .contract import RecoveryError, RecoveryProtocol
from .projection_contract import TargetProjectionProtocol
from .projection_release import TargetProjectionApproval, TargetProjectionRelease
from .projection_sealing import logical_target_sha256, write_projection_run_once
from .sealing import claim_role_once
from .target_projection import project_recovery_targets


CODE_RE = re.compile(r"[0-9]{6}\.(?:SH|SZ|BJ)")


def projection_run_id(
    protocol: TargetProjectionProtocol,
    release: TargetProjectionRelease,
    approval: TargetProjectionApproval,
) -> str:
    return sha256_json(
        {
            "protocol_sha256": protocol.sha256,
            "release_scope_sha256": release.sha256,
            "approval_sha256": approval.sha256,
            "lineage_core_sha256": protocol.expected_lineage_core_sha256,
            "code_bundle_sha256": release.scope["implementation"]["code_bundle_sha256"],
        }
    )


def _segments(track: str, frame: Any) -> list[dict[str, Any]]:
    rows = []
    for (universe, segment), cell in frame.groupby(["universe_id", "segment"], sort=True):
        rows.append(
            {
                "track": track,
                "universe_id": str(universe),
                "segment": str(segment),
                "member_row_count": len(cell),
                "unique_source_key_count": len(cell.drop_duplicates(["ts_code", "source_date"])),
            }
        )
    return rows


def build_projection(
    projection_protocol: TargetProjectionProtocol,
    recovery_protocol: RecoveryProtocol,
    lineage_protocol: LineageProtocol,
    lineage_manifest: LineageInputManifest,
    release: TargetProjectionRelease,
    approval: TargetProjectionApproval,
    *,
    input_loader: Callable[[], LineageInputs],
    output_root: Path,
    claim_root: Path,
    synthetic_expected_lineage_core_sha256: str | None = None,
) -> dict[str, Any]:
    run_id = projection_run_id(projection_protocol, release, approval)
    claim_role_once(
        claim_root,
        role="target_projector",
        release_scope_sha256=release.sha256,
        run_id=run_id,
    )
    inputs = input_loader()
    expected_core = (
        synthetic_expected_lineage_core_sha256
        or projection_protocol.expected_lineage_core_sha256
    )
    first_a, first_b, summary = project_recovery_targets(
        recovery_protocol,
        lineage_protocol,
        inputs,
        expected_lineage_core_sha256=expected_core,
    )
    replay_a, replay_b, replay_summary = project_recovery_targets(
        recovery_protocol,
        lineage_protocol,
        inputs,
        expected_lineage_core_sha256=expected_core,
    )
    identities = {
        "track_a": logical_target_sha256(first_a),
        "track_b": logical_target_sha256(first_b),
    }
    replay_identities = {
        "track_a": logical_target_sha256(replay_a),
        "track_b": logical_target_sha256(replay_b),
    }
    if identities != replay_identities or summary != replay_summary:
        raise RecoveryError("recovery target projection internal replay differs")
    report = {
        "schema_version": "m7-moneyflow-recovery-target-projection-report-v1",
        "run_id": run_id,
        "protocol_sha256": projection_protocol.sha256,
        "release_scope_sha256": release.sha256,
        "approval_sha256": approval.sha256,
        "lineage_input_manifest_sha256": lineage_manifest.sha256,
        "lineage_core_sha256": expected_core,
        "summary": summary,
        "logical_content_sha256": identities,
        "segments": [*_segments("A", first_a), *_segments("B", first_b)],
        "internal_replay": {"status": "PASS", "logical_content_sha256": replay_identities},
        "semantic_rows_read": True,
        "moneyflow_numeric_value_columns_read": 0,
        "daily_numeric_value_columns_read": 0,
        "provider_call_count": 0,
        "network_used": False,
        "adjusted_coverage_computed": False,
        "research_attempt_increment": 0,
        "production_authorization": "none",
        "verdict": "GO_M7_RECOVERY_TARGET_PROJECTION_ONLY",
    }
    if CODE_RE.search(canonical_json(report)):
        raise RecoveryError("recovery target projection report leaks security codes")
    return write_projection_run_once(
        output_root,
        run_id=run_id,
        track_a=first_a,
        track_b=first_b,
        report=report,
    )


def _load_runtime(args: argparse.Namespace) -> tuple[Any, ...]:
    project_root = args.project_root.resolve(strict=True)
    input_root = args.input_root.resolve(strict=True)
    projection = TargetProjectionProtocol.load(
        project_root / "config/m7_moneyflow_recovery_target_projection_v2.yaml",
        project_root=project_root,
    )
    recovery = RecoveryProtocol.load(
        project_root / "config/m7_moneyflow_evidence_recovery_v1.yaml",
        engineering_path=project_root / "config/m7_moneyflow_evidence_recovery_engineering_v1.yaml",
        project_root=project_root,
    )
    lineage = LineageProtocol.load(
        input_root / "config/m7_moneyflow_gap_lineage_v1.yaml", project_root=input_root
    )
    manifest = LineageInputManifest.load(
        input_root / "config/m7_moneyflow_gap_lineage_input_v1.json", lineage
    )
    release = TargetProjectionRelease.load(args.release_scope, projection)
    approval = TargetProjectionApproval.load(args.approval_envelope, release)
    return projection, recovery, lineage, manifest, release, approval, input_root


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--release-scope", type=Path, required=True)
    parser.add_argument("--approval-envelope", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--claim-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        projection, recovery, lineage, manifest, release, approval, input_root = _load_runtime(args)
        result = build_projection(
            projection,
            recovery,
            lineage,
            manifest,
            release,
            approval,
            input_loader=lambda: load_lineage_inputs(
                lineage, manifest, input_root=input_root
            ),
            output_root=args.output_root,
            claim_root=args.claim_root,
        )
    except (OSError, RecoveryError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(canonical_json({"status": "FAIL", "error_class": type(error).__name__, "message": str(error)}))
        return 2
    print(canonical_json({"status": "PASS", **result}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

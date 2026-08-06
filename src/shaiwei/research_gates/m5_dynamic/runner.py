"""Thin write-once M5 data-gate runner; real mode requires an exact approval envelope."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from .contract import (
    InputManifest,
    M5DataProtocol,
    M5GateError,
    canonical_json,
)
from .features import calculate_features
from .failure_projection import build_global_failure_reports
from .matrix import build_quality_report
from .membership import build_membership_panel
from .release import ApprovalEnvelope, DataReleaseScope
from .run_sealing import seal_global_failure, seal_run
from .source_reader import load_allowed_inputs
from .source_conflicts import assess_all_statement_sources
from .statements import build_candidate_components

def build_gate_result(
    protocol: M5DataProtocol,
    frames: dict[str, pd.DataFrame],
    membership_frames: dict[str, pd.DataFrame],
    *,
    input_manifest_sha256: str,
    release_scope_sha256: str,
    code_bundle_sha256: str,
    approval_event_sha256: str,
    semantic_rows_read: bool,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    members, membership_diagnostics = build_membership_panel(
        protocol, frames["tushare.trade_cal"], membership_frames
    )
    components, statement_diagnostics = build_candidate_components(protocol, members, frames)
    panel, feature_diagnostics = calculate_features(protocol, components)
    source_conflicts = sum(
        int(item["source_identity_conflicts"])
        for item in statement_diagnostics["source"].values()
    )
    quality = build_quality_report(
        protocol,
        panel,
        source_identity_conflicts=source_conflicts,
    )
    report = {
        "schema_version": (
            "m5-data-gate-report-v2"
            if protocol.recovery_mode
            else "m5-data-gate-report-v1"
        ),
        "protocol_id": protocol.document["protocol_id"],
        "protocol_sha256": protocol.sha256,
        "input_manifest_sha256": input_manifest_sha256,
        "release_scope_sha256": release_scope_sha256,
        "code_bundle_sha256": code_bundle_sha256,
        "approval_event_sha256": approval_event_sha256,
        "execution_kind": (
            "REAL_APPROVED_DATA_GATE" if semantic_rows_read else "SYNTHETIC_FIXTURE"
        ),
        "semantic_rows_read": semantic_rows_read,
        "membership_diagnostics": membership_diagnostics,
        "statement_diagnostics": statement_diagnostics,
        "feature_diagnostics": feature_diagnostics,
        "quality": quality,
        "label_read": False,
        "effect_read": False,
        "model_training_run": False,
        "backtest_run": False,
        "provider_call_count": 0,
        "provider_cost_usd": "0.00",
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "verdict": quality["verdict"],
    }
    if protocol.recovery_mode:
        report.update(
            {
                "protocol_scope_sha256": protocol.protocol_scope_sha256,
                "outcome_kind": "NORMAL_DATA_MATRIX",
            }
        )
    return panel, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--build-contract", type=Path, required=True)
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--release-scope", type=Path, required=True)
    parser.add_argument("--approval-envelope", type=Path, required=True)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        protocol = M5DataProtocol.load(
            args.protocol,
            build_path=args.build_contract,
            project_root=Path("/inputs"),
        )
        input_manifest = InputManifest.load(args.input_manifest, protocol)
        release = DataReleaseScope.load(args.release_scope, protocol, input_manifest)
        approval = ApprovalEnvelope.load(args.approval_envelope, release)
        frames, memberships, source_evidence = load_allowed_inputs(
            protocol, input_manifest, input_root=args.input_root
        )
        assessment = assess_all_statement_sources(frames) if protocol.recovery_mode else None
        if assessment is not None and assessment.has_conflicts:
            conflict_report, report = build_global_failure_reports(
                protocol,
                assessment,
                input_manifest_sha256=input_manifest.sha256,
                release_scope_sha256=release.sha256,
                code_bundle_sha256=release.scope["implementation"]["code_bundle_sha256"],
                approval_event_sha256=approval.document["approval_event_sha256"],
                source_evidence=source_evidence,
                semantic_rows_read=True,
            )
            result = seal_global_failure(args.output_root, conflict_report, report)
        else:
            panel, report = build_gate_result(
                protocol,
                frames,
                memberships,
                input_manifest_sha256=input_manifest.sha256,
                release_scope_sha256=release.sha256,
                code_bundle_sha256=release.scope["implementation"]["code_bundle_sha256"],
                approval_event_sha256=approval.document["approval_event_sha256"],
                semantic_rows_read=True,
            )
            report["source_evidence"] = source_evidence
            result = seal_run(args.output_root, panel, report)
    except (M5GateError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(canonical_json({"status": "FAIL", "error_class": type(error).__name__, "message": str(error)}))
        return 2
    print(canonical_json(result))
    return 0 if result["verdict"].startswith("GO_") else 3


if __name__ == "__main__":
    raise SystemExit(main())

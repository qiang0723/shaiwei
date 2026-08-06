"""Aggregate-only public reports for the M5 source-lineage feasibility gate."""

from __future__ import annotations

from typing import Any

from .lineage import LineageAssessment


GO_VERDICT = "GO_M5_2_SOURCE_LINEAGE_RECOVERABLE"
NO_GO_VERDICT = "NO_GO_M5_2_SOURCE_LINEAGE_PREEXECUTION"


def build_lineage_reports(
    assessment: LineageAssessment,
    *,
    protocol_scope_sha256: str,
    input_manifest_sha256: str,
    release_scope_sha256: str,
    code_bundle_sha256: str,
    approval_event_sha256: str,
    semantic_rows_read: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    verdict = GO_VERDICT if assessment.historical_pass else NO_GO_VERDICT
    identity = {
        "protocol_scope_sha256": protocol_scope_sha256,
        "input_manifest_sha256": input_manifest_sha256,
        "release_scope_sha256": release_scope_sha256,
        "code_bundle_sha256": code_bundle_sha256,
        "approval_event_sha256": approval_event_sha256,
    }
    public_analysis = {
        key: assessment.report[key]
        for key in (
            "as_of",
            "identity_field_count",
            "identity_group_count",
            "conflicting_identity_group_count",
            "tables",
            "disposition_counts",
            "unresolved_reason_counts",
            "future_evidence_count",
            "historical_lineage_pass",
            "global_lineage_commitment_sha256",
        )
    }
    authority = {
        "row_level_export": False,
        "source_selection": False,
        "data_gate_execution": False,
        "pit_compute": False,
        "candidate_compute": False,
        "label_read": False,
        "effect_read": False,
        "model_training": False,
        "backtest": False,
        "provider_call_count": 0,
        "production_authorization": "none",
    }
    lineage_report = {
        "schema_version": "m5-source-lineage-report-v1",
        "outcome_kind": "SOURCE_LINEAGE_FEASIBILITY",
        "approved_identity": identity,
        **public_analysis,
        "semantic_rows_read": semantic_rows_read,
        "authority": authority,
    }
    gate_report = {
        "schema_version": "m5-source-lineage-gate-report-v1",
        **identity,
        "outcome_kind": "SOURCE_LINEAGE_FEASIBILITY",
        "execution_kind": (
            "REAL_APPROVED_LINEAGE_FEASIBILITY" if semantic_rows_read else "SYNTHETIC_FIXTURE"
        ),
        "semantic_rows_read": semantic_rows_read,
        "source_lineage_report": {"status": "PENDING_SEAL"},
        "feature_panel": {"status": "FORBIDDEN_LINEAGE_GATE"},
        "candidate_matrix": {"status": "FORBIDDEN_LINEAGE_GATE"},
        "lineage": public_analysis,
        "label_read": False,
        "effect_read": False,
        "model_training_run": False,
        "backtest_run": False,
        "provider_call_count": 0,
        "provider_cost_usd": "0.00",
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "verdict": verdict,
    }
    return lineage_report, gate_report

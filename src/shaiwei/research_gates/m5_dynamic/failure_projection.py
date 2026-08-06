"""Canonical M5 global-data-failure projection; contains no source rows or factor values."""

from __future__ import annotations

from typing import Any

from .contract import M5DataProtocol, M5GateError
from .source_conflicts import SourceConflictAssessment


REASON_CODE = "GLOBAL_SOURCE_IDENTITY_CONFLICT"
COMPUTATION_STATUS = "NOT_COMPUTED_GLOBAL_FAILURE"
NO_GO_VERDICT = "NO_GO_M5_2_DATA_PREEXECUTION"


def _matrix(protocol: M5DataProtocol) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    detailed = [
        {
            "candidate_id": candidate_id,
            "universe_id": universe_id,
            "status": "FAIL",
            "reason_code": REASON_CODE,
            "computation_status": COMPUTATION_STATUS,
        }
        for candidate_id in protocol.candidate_ids
        for universe_id in protocol.universe_ids
    ]
    registry = [
        {
            "candidate_id": cell["candidate_id"],
            "universe_id": cell["universe_id"],
            "status": cell["status"],
        }
        for cell in detailed
    ]
    return detailed, registry


def build_global_failure_reports(
    protocol: M5DataProtocol,
    assessment: SourceConflictAssessment,
    *,
    input_manifest_sha256: str,
    release_scope_sha256: str,
    code_bundle_sha256: str,
    approval_event_sha256: str,
    source_evidence: dict[str, Any],
    semantic_rows_read: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not protocol.recovery_mode or not assessment.has_conflicts:
        raise M5GateError("M5 global failure projection requires recovery conflicts")
    identity = {
        "protocol_sha256": protocol.sha256,
        "protocol_scope_sha256": protocol.protocol_scope_sha256,
        "input_manifest_sha256": input_manifest_sha256,
        "release_scope_sha256": release_scope_sha256,
        "code_bundle_sha256": code_bundle_sha256,
        "approval_event_sha256": approval_event_sha256,
    }
    table_reports = [
        {
            "table": item["table"],
            "category_counts": item["category_counts"],
            "conflict_identity_group_count": item[
                "conflict_identity_group_count"
            ],
            "conflict_field_counts": item["conflict_field_counts"],
            "conflict_set_sha256": item["conflict_set_sha256"],
        }
        for item in assessment.report["tables"]
    ]
    authority = {
        "row_level_export": False,
        "source_selection": False,
        "label_read": False,
        "effect_read": False,
        "model_training": False,
        "backtest": False,
        "production_authorization": "none",
    }
    conflict_report = {
        "schema_version": "m5-source-conflict-report-v2",
        "outcome_kind": "GLOBAL_DATA_FAILURE",
        "approved_identity": identity,
        "table_category_counts": table_reports,
        "total_conflict_identity_group_count": assessment.report[
            "total_conflict_identity_group_count"
        ],
        "global_conflict_set_sha256": assessment.report[
            "global_conflict_set_sha256"
        ],
        "semantic_rows_read": semantic_rows_read,
        "authority": authority,
    }
    detailed_matrix, registry_matrix = _matrix(protocol)
    quality = {
        "schema_version": "m5-data-quality-report-v2",
        "outcome_kind": "GLOBAL_DATA_FAILURE",
        "candidate_count": len(protocol.candidate_ids),
        "universe_count": len(protocol.universe_ids),
        "evaluation_unit_count": len(registry_matrix),
        "global_integrity": {
            "source_identity_conflicts": assessment.report[
                "total_conflict_identity_group_count"
            ],
            "reason_code": REASON_CODE,
        },
        "global_integrity_pass": False,
        "candidate_matrix": detailed_matrix,
        "registry_candidate_matrix": registry_matrix,
        "eligible_candidate_ids": [],
        "rejected_candidate_ids": list(protocol.candidate_ids),
        "coverage_status": COMPUTATION_STATUS,
        "correlation_diagnostics": {
            "status": COMPUTATION_STATUS,
            "used_for_verdict": False,
        },
        "effect_test_count": 0,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "verdict": NO_GO_VERDICT,
    }
    data_report = {
        "schema_version": "m5-data-gate-report-v2",
        **identity,
        "outcome_kind": "GLOBAL_DATA_FAILURE",
        "execution_kind": (
            "REAL_APPROVED_DATA_GATE" if semantic_rows_read else "SYNTHETIC_FIXTURE"
        ),
        "semantic_rows_read": semantic_rows_read,
        "source_evidence": source_evidence,
        "source_conflict_report": {"status": "PENDING_SEAL"},
        "feature_panel": {"status": "NOT_CREATED_GLOBAL_FAILURE"},
        "quality": quality,
        "label_read": False,
        "effect_read": False,
        "model_training_run": False,
        "backtest_run": False,
        "provider_call_count": 0,
        "provider_cost_usd": "0.00",
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "verdict": NO_GO_VERDICT,
    }
    return conflict_report, data_report

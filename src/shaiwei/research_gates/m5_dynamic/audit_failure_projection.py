"""Independent expected M5 global-failure evidence projection."""

from __future__ import annotations

from typing import Any

from .contract import M5DataProtocol, M5GateError


REASON_CODE = "GLOBAL_SOURCE_IDENTITY_CONFLICT"
COMPUTATION_STATUS = "NOT_COMPUTED_GLOBAL_FAILURE"
VERDICT = "NO_GO_M5_2_DATA_PREEXECUTION"


def expected_global_failure(
    protocol: M5DataProtocol,
    audited: dict[str, Any],
    *,
    approved_identity: dict[str, str],
    semantic_rows_read: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not protocol.recovery_mode or not audited["has_conflicts"]:
        raise M5GateError("M5 independent global failure requires recovery conflicts")
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
        "approved_identity": approved_identity,
        "table_category_counts": audited["table_category_counts"],
        "total_conflict_identity_group_count": audited[
            "total_conflict_identity_group_count"
        ],
        "global_conflict_set_sha256": audited["global_conflict_set_sha256"],
        "semantic_rows_read": semantic_rows_read,
        "authority": authority,
    }
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
    quality = {
        "schema_version": "m5-data-quality-report-v2",
        "outcome_kind": "GLOBAL_DATA_FAILURE",
        "candidate_count": len(protocol.candidate_ids),
        "universe_count": len(protocol.universe_ids),
        "evaluation_unit_count": len(registry),
        "global_integrity": {
            "source_identity_conflicts": audited[
                "total_conflict_identity_group_count"
            ],
            "reason_code": REASON_CODE,
        },
        "global_integrity_pass": False,
        "candidate_matrix": detailed,
        "registry_candidate_matrix": registry,
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
        "verdict": VERDICT,
    }
    return conflict_report, quality

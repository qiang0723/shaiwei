"""Fail-closed validation for the result-blind Head30 price recovery."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shaiwei.research.model_attribution.contract import sha256_file
from shaiwei.research.production_conversion.contract import ProtocolError


def _project_file(project_root: Path, relative: object) -> Path:
    if not isinstance(relative, str) or not relative:
        raise ProtocolError("production-converter price recovery path is invalid")
    root = project_root.resolve()
    path = (root / relative).resolve(strict=True)
    if root not in path.parents or path.is_symlink():
        raise ProtocolError("production-converter price recovery path is outside project")
    return path


def _json_mapping(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ProtocolError("production-converter price recovery evidence is invalid") from error
    if not isinstance(value, dict):
        raise ProtocolError("production-converter price recovery evidence is not a mapping")
    return value


def _validate_predecessor_hash(
    predecessors: dict[str, Any], name: str, project_root: Path
) -> Path:
    row = predecessors.get(name, {})
    path = _project_file(project_root, row.get("path"))
    if row.get("sha256") != sha256_file(path):
        raise ProtocolError(f"production-converter price recovery predecessor differs: {name}")
    return path


def _validate_predecessors(document: dict[str, Any], project_root: Path) -> None:
    predecessors = document.get("predecessors", {})
    for name in (
        "production_converter_protocol",
        "production_converter_hash_addendum",
        "r1_recovery_protocol",
    ):
        _validate_predecessor_hash(predecessors, name, project_root)

    scope_row = predecessors.get("r1_failed_release_scope", {})
    scope_path = _project_file(project_root, scope_row.get("path"))
    scope = _json_mapping(scope_path)
    if (
        scope_row.get("file_sha256") != sha256_file(scope_path)
        or scope_row.get("release_scope_sha256") != scope.get("release_scope_sha256")
    ):
        raise ProtocolError("production-converter R1 failed scope differs")

    evidence_row = predecessors.get("r1_failure_evidence", {})
    evidence_path = _project_file(project_root, evidence_row.get("path"))
    evidence = _json_mapping(evidence_path)
    if evidence_row.get("sha256") != sha256_file(evidence_path):
        raise ProtocolError("production-converter R1 failure evidence differs")
    required = {
        "release_scope_sha256": scope_row.get("release_scope_sha256"),
        "treatment_effect_started": True,
        "real_effect_read": True,
        "portfolio_attempts_consumed": 1,
        "same_scope_retry_authorized": False,
        "replay_completed": False,
        "formal_effect_report_written": False,
        "independent_audit_invoked": False,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
    }
    if any(evidence.get(key) != value for key, value in required.items()):
        raise ProtocolError("production-converter R1 failure state differs")
    for name in (
        "authorization_sha256",
        "treatment_effect_started_sha256",
        "failure_artifact_sha256",
    ):
        if evidence_row.get(name) != evidence.get(name):
            raise ProtocolError("production-converter R1 artifact identity differs")
    if predecessors.get("preserve_without_rewrite") is not True:
        raise ProtocolError("production-converter R1 evidence preservation is absent")


def _validate_change(document: dict[str, Any]) -> None:
    change = document.get("recovery_change", {})
    if change.get("only_changed_variable") != (
        "missing_deal_price_normalization_before_existing_position_price_fallback"
    ):
        raise ProtocolError("production-converter price recovery variable differs")
    if change.get("deal_price_normalization") != {
        "finite_positive_numeric": "use_as_execution_or_valuation_price",
        "none_non_numeric_nonfinite_or_nonpositive": "return_missing",
    }:
        raise ProtocolError("production-converter deal-price normalization differs")
    if change.get("held_position_valuation") != {
        "primary": "normalized_deal_price",
        "fallback": "existing_position_price",
        "fallback_must_be_finite_positive_numeric": True,
        "invalid_fallback_action": "fail_closed_with_full_target_strategy_error",
    }:
        raise ProtocolError("production-converter valuation fallback differs")
    if change.get("target_buy_price") != {
        "missing_behavior": "preserve_existing_nan_to_zero_target_amount_and_no_buy"
    }:
        raise ProtocolError("production-converter missing buy-price behavior differs")
    if change.get("forbidden_new_sources") != [
        "prior_close",
        "future_close",
        "adjusted_close",
        "manual_price",
    ]:
        raise ProtocolError("production-converter forbidden price sources differ")
    if change.get("forbidden_actions") != [
        "drop_instrument",
        "drop_trade_day",
        "impute_price",
        "alter_signal",
        "alter_target_rank",
    ]:
        raise ProtocolError("production-converter forbidden recovery actions differ")
    unchanged = (
        "strategy_formula_changed",
        "model_or_prediction_changed",
        "input_identity_changed",
        "g0_gate_changed",
        "cost_or_window_changed",
        "result_semantic_read_before_new_approval",
    )
    if any(change.get(name) is not False for name in unchanged):
        raise ProtocolError("production-converter price recovery broadens its boundary")


def _validate_release(document: dict[str, Any]) -> None:
    release = document.get("release_and_approval", {})
    expected = {
        "release_scope_kind": "PRODUCTION_HEAD30_G0_PRICE_RECOVERY_READY_NOT_EXECUTION_APPROVAL",
        "approval_action": (
            "M6_PRODUCTION_HEAD30_G0_EFFECT_PRICE_RECOVERY_ONCE_WITH_REPLAY_"
            "AND_INDEPENDENT_AUDIT"
        ),
        "approval_must_bind_exact_release_scope_sha256": True,
        "scope_drift_invalidates_approval": True,
        "tracked_release_scope": (
            "config/m6_csi800_production_head30_price_recovery_scope_v1.json"
        ),
        "approval_record_path": (
            "data/control/m6_csi800_production_head30_v1/approval-r2.json"
        ),
        "approval_record_git_ignored": True,
    }
    if release != expected:
        raise ProtocolError("production-converter price recovery approval differs")


def validate_price_recovery_protocol(
    document: dict[str, Any], project_root: Path
) -> None:
    _validate_predecessors(document, project_root)
    _validate_change(document)
    _validate_release(document)
    if document.get("execution_counting", {}) != {
        "runner_invocation_count": 1,
        "complete_internal_passes": ["first_pass", "replay"],
        "independent_auditor_invocation_count": 1,
        "r1_portfolio_attempts_consumed": 1,
        "new_portfolio_attempts_consumed_at_first_treatment_effect_read": 1,
        "total_family_attempts_after_new_effect_read": 2,
        "model_attempt_increment": 0,
        "same_price_recovery_scope_retry_authorized": False,
    }:
        raise ProtocolError("production-converter price recovery attempt count differs")
    artifact = document.get("artifact_contract", {})
    if artifact != {
        "ignored_effect_root": "data/research/m6_csi800_production_head30_v1/effect-r2",
        "ignored_audit_root": "data/research/m6_csi800_production_head30_v1/effect-r2-audit",
        "r1_effect_root_preserved": "data/research/m6_csi800_production_head30_v1/effect",
        "r1_audit_root_preserved": "data/research/m6_csi800_production_head30_v1/effect-audit",
        "experiment_ledger_write_authorized": False,
    }:
        raise ProtocolError("production-converter price recovery output boundary differs")


__all__ = ["validate_price_recovery_protocol"]

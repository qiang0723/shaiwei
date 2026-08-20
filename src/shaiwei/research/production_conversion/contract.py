"""Result-blind M6 production-converter protocol validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.ledger import sha256_file


PROTOCOL_PATH = PROJECT_ROOT / "config/m6_csi800_production_head30_v1.yaml"
ADDENDUM_PATH = PROJECT_ROOT / "config/m6_csi800_production_head30_hash_addendum_v1.yaml"
APPROVAL_ACTION = "M6_PRODUCTION_HEAD30_G0_EFFECT_ONCE_WITH_REPLAY_AND_INDEPENDENT_AUDIT"


class ProtocolError(RuntimeError):
    """Raised when the frozen production-converter contract drifts."""


def _mapping(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProtocolError(f"production-converter {name} must be a mapping")
    return value


def _load_addendum(protocol_path: Path) -> dict[str, Any]:
    try:
        addendum = yaml.safe_load(ADDENDUM_PATH.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ProtocolError("production-converter hash addendum is unreadable") from error
    addendum = _mapping(addendum, "hash addendum")
    if addendum.get("addendum_id") != "m6-csi800-production-head30-hash-addendum-v1":
        raise ProtocolError("production-converter hash addendum identity differs")
    base = _mapping(addendum.get("base_protocol"), "hash addendum base")
    if base.get("path") != "config/m6_csi800_production_head30_v1.yaml":
        raise ProtocolError("production-converter hash addendum base path differs")
    if base.get("sha256") != sha256_file(protocol_path):
        raise ProtocolError("production-converter hash addendum base identity differs")
    correction = _mapping(addendum.get("correction"), "hash correction")
    unchanged = {
        "predecessor_content_changed",
        "research_question_changed",
        "converter_changed",
        "g0_gate_changed",
        "authority_changed",
        "attempt_policy_changed",
    }
    if any(correction.get(name) is not False for name in unchanged):
        raise ProtocolError("production-converter hash addendum changes the protocol")
    if addendum.get("effect_values_read_before_correction") is not False:
        raise ProtocolError("production-converter hash correction is not result blind")
    return addendum


def _validate_predecessors(document: dict[str, Any], addendum: dict[str, Any]) -> None:
    predecessors = _mapping(document.get("predecessors"), "predecessors")
    correction = _mapping(addendum.get("correction"), "hash correction")
    if correction.get("field") != "predecessors.m6_result_protocol.sha256":
        raise ProtocolError("production-converter hash correction field differs")
    recorded = predecessors.get("m6_result_protocol", {}).get("sha256")
    if correction.get("recorded_value") != recorded:
        raise ProtocolError("production-converter recorded predecessor hash differs")
    for name, row_value in predecessors.items():
        if name == "preserve_without_rewrite":
            if row_value is not True:
                raise ProtocolError("production-converter predecessors are not preserved")
            continue
        row = _mapping(row_value, f"predecessor {name}")
        relative = row.get("path")
        expected = row.get("sha256", row.get("file_sha256"))
        if name == "m6_result_protocol":
            expected = correction.get("corrected_value")
        if not isinstance(relative, str) or not isinstance(expected, str):
            raise ProtocolError(f"production-converter predecessor is incomplete: {name}")
        path = (PROJECT_ROOT / relative).resolve()
        if PROJECT_ROOT.resolve() not in path.parents or not path.is_file():
            raise ProtocolError(f"production-converter predecessor path is invalid: {name}")
        if sha256_file(path) != expected:
            raise ProtocolError(f"production-converter predecessor hash differs: {name}")


def _validate_authority(document: dict[str, Any]) -> None:
    authority = _mapping(document.get("authority"), "authority")
    allowed_true = {
        "protocol_freeze_authorized_by_user_instruction",
        "result_blind_implementation_and_synthetic_tests_authorized",
    }
    if any(authority.get(name) is not True for name in allowed_true):
        raise ProtocolError("production-converter result-blind authority is absent")
    forbidden = {
        "sealed_prediction_or_report_value_read_authorized",
        "qlib_feature_price_or_calendar_read_authorized",
        "real_backtest_authorized",
        "formal_effect_output_write_authorized",
        "experiment_ledger_write_authorized",
        "external_network_authorized",
        "env_or_secret_read_authorized",
        "forward_signal_change_authorized",
        "paper_portfolio_change_authorized",
        "scheduler_change_or_restart_authorized",
    }
    if any(authority.get(name) is not False for name in forbidden):
        raise ProtocolError("production-converter pre-effect authority is broadened")
    if authority.get("production_authorization") != "none":
        raise ProtocolError("production-converter production authority differs")


def _validate_single_variable(document: dict[str, Any]) -> None:
    variable = _mapping(document.get("single_variable_contract"), "single variable")
    expected = {
        "variable_name": "portfolio_converter",
        "control": "biweekly_top30_dropout_n3",
        "treatment": "rank_head_top30_equal_weight_full_target",
        "changed_variable_count": 1,
    }
    if any(variable.get(name) != value for name, value in expected.items()):
        raise ProtocolError("production-converter single variable differs")
    components = _mapping(variable.get("treatment_components"), "treatment components")
    expected_components = {
        "target_membership": "deterministic_score_desc_instrument_asc_head_30",
        "target_weight": 1.0 / 30.0,
        "target_refresh": "replace_to_current_target_set_and_reweight_all_targets",
        "target_investment_ratio": 1.0,
    }
    if components != expected_components:
        raise ProtocolError("production-converter treatment components differ")
    constants = _mapping(document.get("constants"), "constants")
    fixed = {
        "benchmark": "SH000906",
        "topk": 30,
        "rebalance_trade_days": 10,
        "account_rmb": 100_000_000,
        "deal_price": "open",
        "cost_multipliers": [1.0, 1.5, 2.0],
    }
    if any(constants.get(name) != value for name, value in fixed.items()):
        raise ProtocolError("production-converter frozen constants differ")
    if components["target_weight"] * constants["topk"] != components["target_investment_ratio"]:
        raise ProtocolError("production-converter target weights do not match investment ratio")


def _validate_gate_and_attempt(document: dict[str, Any]) -> None:
    gate = _mapping(document.get("unchanged_g0_gate"), "G0 gate")
    if gate != {
        "source": "docs/GATES.md",
        "required_window_count": 6,
        "minimum_positive_base_cost_excess_windows": 4,
        "combined_1_5x_cost_cumulative_excess_minimum": 0.0,
        "strict_additional_gate_count": 0,
        "two_x_cost_is_diagnostic_only": True,
        "control_delta_is_diagnostic_only": True,
        "no_post_result_threshold_change": True,
    }:
        raise ProtocolError("production-converter G0 gate differs")
    attempt = _mapping(document.get("attempt_policy"), "attempt policy")
    expected_attempt = {
        "attempt_family": "m6_portfolio_converter",
        "new_portfolio_attempt_count": 1,
        "attempts_consumed_on_first_authorized_treatment_effect_read": True,
        "failed_after_effect_read_still_consumes_attempt": True,
        "canonical_ledger": "ledger/experiments.csv",
        "required_candidate_source": "M6-production-head30-converter",
        "required_model_or_engine": "portfolio_converter",
        "no_replacement_or_retry_under_same_scope": True,
    }
    if any(attempt.get(name) != value for name, value in expected_attempt.items()):
        raise ProtocolError("production-converter attempt policy differs")
    release = _mapping(document.get("future_release_not_authorized_here"), "future release")
    if release.get("approval_action") != APPROVAL_ACTION:
        raise ProtocolError("production-converter approval action differs")
    if release.get("approval_state_pending_must_fail_closed") is not True:
        raise ProtocolError("production-converter pending approval is not fail closed")


@dataclass(frozen=True)
class Protocol:
    path: Path
    document: dict[str, Any]
    sha256: str
    addendum: dict[str, Any]
    addendum_sha256: str

    @property
    def target_investment_ratio(self) -> float:
        return float(
            self.document["single_variable_contract"]["treatment_components"][
                "target_investment_ratio"
            ]
        )

    @classmethod
    def load(cls, path: Path = PROTOCOL_PATH) -> "Protocol":
        resolved = path.resolve()
        try:
            document = yaml.safe_load(resolved.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as error:
            raise ProtocolError("production-converter protocol is unreadable") from error
        document = _mapping(document, "protocol")
        if document.get("protocol_id") != "m6-csi800-production-head30-converter-v1":
            raise ProtocolError("production-converter protocol identity differs")
        if document.get("protocol_stage") != "RESULT_BLIND_PROTOCOL_FREEZE_ONLY":
            raise ProtocolError("production-converter protocol stage differs")
        addendum = _load_addendum(resolved)
        _validate_predecessors(document, addendum)
        _validate_authority(document)
        _validate_single_variable(document)
        _validate_gate_and_attempt(document)
        stop = _mapping(document.get("stop_condition"), "stop condition")
        if stop.get("user_exact_scope_approval_required_before_real_effect") is not True:
            raise ProtocolError("production-converter real-effect stop is absent")
        return cls(
            path=resolved,
            document=document,
            sha256=sha256_file(resolved),
            addendum=addendum,
            addendum_sha256=sha256_file(ADDENDUM_PATH),
        )


__all__ = [
    "ADDENDUM_PATH",
    "APPROVAL_ACTION",
    "PROTOCOL_PATH",
    "Protocol",
    "ProtocolError",
]

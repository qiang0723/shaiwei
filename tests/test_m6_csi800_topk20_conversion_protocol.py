from __future__ import annotations

import hashlib
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]
PROTOCOL = ROOT / "config/m6_csi800_topk20_conversion_v1.yaml"


def _load() -> dict:
    document = yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_m6_top20_protocol_is_result_before_and_has_no_execution_authority() -> None:
    document = _load()
    authority = document["authority"]

    assert document["protocol_stage"] == (
        "RESULT_BEFORE_TOPK20_PORTFOLIO_PROTOCOL_FREEZE_ONLY"
    )
    assert document["research_question"]["prior_m6_attribution_result"] == (
        "PORTFOLIO_CONVERSION_BOTTLENECK_INDICATED"
    )
    assert document["research_question"]["new_top20_historical_effect_inspected_before_freeze"] is False
    assert {
        key
        for key, value in authority.items()
        if isinstance(value, bool) and value
    } == {
        "protocol_freeze_authorized_by_user_instruction",
        "tracked_protocol_test_and_status_write_authorized",
    }
    assert authority["production_authorization"] == "none"
    assert authority["tushare_calls"] == authority["deepseek_calls"] == 0
    assert document["future_outputs"]["tracked_outputs_exist_at_freeze"] is False


def test_m6_top20_protocol_binds_all_predecessors_without_rewrite() -> None:
    document = _load()
    predecessors = document["predecessors"]

    for key in (
        "m6_result_protocol",
        "m6_real_release_protocol",
        "m6_release_acceptance",
        "m6_authoritative_audit_acceptance",
        "paper_top20_operational_protocol",
    ):
        item = predecessors[key]
        assert _sha256(ROOT / item["path"]) == item["sha256"]
    release = predecessors["m6_real_release_scope"]
    assert _sha256(ROOT / release["path"]) == release["file_sha256"]
    assert release["release_scope_sha256"] == (
        "9b609f0764240ff3930a4aeaaf16cef9deb82579d2a5875f1be9e8c4ffb0b139"
    )
    assert predecessors["preserve_without_rewrite"] is True
    assert predecessors["paper_top20_operational_protocol"]["historical_effect_input_authorized"] is False


def test_exactly_one_portfolio_variable_changes_from_top30_to_top20() -> None:
    document = _load()
    scope = document["scope"]
    variable = document["single_variable_contract"]
    constants = document["portfolio_constants"]

    assert scope["changed_portfolio_variable_count"] == 1
    assert scope["new_model_arm_count"] == 0
    assert scope["new_model_fit_count"] == 0
    assert scope["new_prediction_generation_count"] == 0
    assert scope["additional_topk_value_authorized"] is False
    assert variable["variable_path"] == "portfolio.topk"
    assert variable["control_value"] == 30
    assert variable["treatment_value"] == 20
    assert variable["all_other_portfolio_fields_byte_semantically_equal"] is True
    assert constants == {
        "strategy": "BiweeklyTopkDropoutStrategy",
        "account_rmb": 100000000,
        "n_drop": 3,
        "rebalance_trade_days": 10,
        "only_tradable": True,
        "forbid_all_trade_at_limit": False,
        "deal_price": "open",
        "benchmark": "SH000906",
        "open_cost": 0.0006,
        "close_cost": 0.0016,
        "minimum_cost_rmb": 5,
        "cost_multipliers": [1.0, 1.5, 2.0],
        "cost_scenario_method": "scale_recorded_base_daily_cost_without_rerunning_trades",
        "capacity_model_added": False,
        "allocation_and_cash_semantics": "inherit_unmodified_biweekly_topk_dropout_defaults",
    }


def test_score_surfaces_are_frozen_and_no_new_model_attempt_is_created() -> None:
    document = _load()
    scores = document["score_surfaces"]
    attempts = document["attempt_policy"]

    assert scores["arms"] == [
        "clean_lgbm_control_v1",
        "ridge_alpha1_v1",
        "lgbm_ridge_rank_blend_50_50_v1",
    ]
    assert scores["refit_or_rescore_authorized"] is False
    assert scores["prediction_values_must_match_predecessor"] is True
    assert attempts["prior_model_alternative_attempt_count_preserved"] == 2
    assert attempts["new_model_alternative_attempt_count"] == 0
    assert attempts["portfolio_conversion_attempt_count"] == 2
    assert attempts["no_replacement_model_or_portfolio_hypothesis"] is True
    assert attempts["factor_g1_trial_count_increment"] == 0


def test_primary_inference_is_two_hypothesis_paired_difference_in_differences() -> None:
    document = _load()
    inference = document["primary_inference"]
    gate = document["conversion_gate"]

    assert "(alternative_top20-clean_top20)-(alternative_top30-clean_top30)" in inference["outcome"]
    assert inference["cost_multiplier"] == 1.0
    assert inference["hac_lags"] == 10
    assert inference["multiplicity_method"] == "holm"
    assert inference["familywise_alpha"] == 0.05
    assert inference["hypothesis_count"] == 2
    assert inference["hypothesis_family"] == [
        "ridge_alpha1_v1",
        "lgbm_ridge_rank_blend_50_50_v1",
    ]
    assert gate["interaction"] == {
        "primary_holm_adjusted_p_must_pass": True,
        "pooled_base_difference_in_differences_strictly_positive": True,
        "minimum_positive_difference_in_differences_windows": 4,
    }
    assert gate["predecessor_score_gate"]["new_rank_ic_hypothesis_or_threshold"] is False


def test_future_execution_is_separate_fail_closed_and_non_production() -> None:
    document = _load()
    compatibility = document["future_input_compatibility_gate"]
    execution = document["future_execution_contract_not_authorized_here"]
    decisions = document["decision_contract"]

    assert compatibility["top30_portfolio_replay_must_match_predecessor_canonical_reports_before_top20_effect"] is True
    assert compatibility["top30_replay_mismatch_outcome"] == "BLOCKED_PRE_EFFECT"
    assert compatibility["paper_account_artifacts_as_historical_input"] == "prohibited"
    assert execution["implementation_requires_new_main_target"] is True
    assert execution["real_execution_requires_new_exact_release_scope_and_user_approval"] is True
    assert execution["portfolio_only_runner_may_not_import_model_training_factory"] is True
    assert execution["complete_internal_passes"] == ["first_pass", "replay"]
    assert execution["scheduler_change_or_restart"] is False
    assert decisions["strategy_effective_for_every_outcome"] == "NOT_EVALUATED_FOR_PRODUCTION"
    assert decisions["production_authorization_for_every_outcome"] == "none"
    assert document["stop_condition"]["no_implementation_or_effect_read_in_this_target"] is True

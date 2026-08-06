from __future__ import annotations

import hashlib
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]
PROTOCOL = ROOT / "config/m6_csi800_model_attribution_v1.yaml"


def _document() -> dict:
    return yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_m6_protocol_is_result_blind_and_has_no_execution_authority() -> None:
    document = _document()
    authority = document["authority"]

    assert document["protocol_stage"] == "RESULT_BLIND_PROTOCOL_FREEZE_ONLY"
    assert document["research_question"]["new_m6_results_inspected_before_freeze"] is False
    assert authority["protocol_freeze_authorized_by_user_instruction"] is True
    assert {
        key
        for key, value in authority.items()
        if isinstance(value, bool) and value
    } == {"protocol_freeze_authorized_by_user_instruction"}
    assert authority["production_authorization"] == "none"
    assert authority["tushare_calls"] == authority["deepseek_calls"] == 0
    assert document["future_outputs"]["tracked_outputs_exist_at_freeze"] is False


def test_frozen_inputs_and_legacy_boundary_are_exact() -> None:
    document = _document()
    inputs = document["frozen_inputs"]

    assert _sha256(ROOT / inputs["settings"]["path"]) == inputs["settings"]["sha256"]
    assert inputs["qlib_provider"]["manifest_sha256"] == (
        "62cae2f46b57020db202bee1748f072e7859e209663046747f76aaa008f605a9"
    )
    assert inputs["qlib_provider"]["tree_sha256"] == (
        "0532f6cd7c2c78f0936f92a986aef83a848175fe6f332274e06c7ed6e8c11778"
    )
    for name in ("baseline", "strategy", "metrics"):
        assert _sha256(ROOT / inputs["legacy_code_evidence"][f"{name}_path"]) == inputs[
            "legacy_code_evidence"
        ][f"{name}_sha256"]
    assert _sha256(ROOT / inputs["route_review"]["path"]) == inputs["route_review"][
        "sha256"
    ]

    boundary = document["legacy_control_boundary"]
    assert boundary["legacy_stage0_preserved_without_rewrite"] is True
    assert boundary["legacy_stage0_is_clean_comparator_for_m6"] is False
    assert boundary["clean_control_required"] is True
    assert boundary["production_or_forward_baseline_modified_by_this_protocol"] is False


def test_exactly_two_predeclared_alternatives_change_only_learning_structure() -> None:
    document = _document()
    scope = document["scope"]
    arms = document["arms"]

    assert len(arms) == 3
    assert [arm["role"] for arm in arms] == ["CONTROL", "ALTERNATIVE_1", "ALTERNATIVE_2"]
    assert scope["control_arm_count"] == 1
    assert scope["alternative_arm_count"] == scope["formal_hypothesis_count"] == 2
    assert scope["feature_additions"] == 0
    assert scope["grid_search_authorized"] is False
    assert scope["multiple_seed_authorized"] is False
    assert scope["hyperparameter_tuning_authorized"] is False
    assert scope["portfolio_parameter_search_authorized"] is False

    lgbm, ridge, blend = arms
    assert lgbm["arm_id"] == "clean_lgbm_control_v1"
    assert lgbm["parameters"]["seed"] == 42
    assert lgbm["parameters"]["num_threads"] == 8
    assert lgbm["parameters"]["deterministic"] is True
    assert ridge["arm_id"] == "ridge_alpha1_v1"
    assert ridge["parameters"] == {
        "estimator": "ridge",
        "alpha": 1.0,
        "fit_intercept": False,
        "include_valid": False,
    }
    assert blend["trained_models"] == [lgbm["arm_id"], ridge["arm_id"]]
    assert blend["parameters"]["lgbm_weight"] == blend["parameters"]["ridge_weight"] == 0.5
    assert blend["parameters"]["missing_member_policy"] == (
        "fail_closed_no_intersection_fallback"
    )


def test_label_maturity_and_six_windows_are_frozen() -> None:
    document = _document()
    clock = document["clock_and_label"]
    windows = document["windows"]

    assert clock["label_horizon_trade_days"] == 11
    assert clock["train_and_valid_purge_policy"] == "remove_final_11_signal_dates"
    assert clock["handler_fit_end_policy"] == "purged_train_last_signal_date"
    assert clock["early_stopping_uses_purged_valid_only"] is True
    assert clock["test_boundaries_move"] is False
    assert clock["cross_window_label_carry_authorized"] is False
    assert [window["name"] for window in windows] == ["W1", "W2", "W3", "W4", "W5", "W6"]
    assert [window["purged_train_last_signal"] for window in windows] == [
        "2018-06-13",
        "2019-06-13",
        "2020-06-11",
        "2021-06-15",
        "2022-06-15",
        "2023-06-13",
    ]
    assert [window["purged_valid_last_signal"] for window in windows] == [
        "2018-12-13",
        "2019-12-16",
        "2020-12-16",
        "2021-12-16",
        "2022-12-15",
        "2023-12-14",
    ]
    assert [window["score_last_signal"] for window in windows] == [
        "2019-12-16",
        "2020-12-16",
        "2021-12-16",
        "2022-12-15",
        "2023-12-14",
        "2024-12-16",
    ]


def test_portfolio_primary_inference_and_stop_rules_are_narrow() -> None:
    document = _document()
    portfolio = document["portfolio"]
    inference = document["primary_inference"]
    attempts = document["attempt_policy"]

    assert portfolio == {
        "strategy": "BiweeklyTopkDropoutStrategy",
        "account_rmb": 100000000,
        "topk": 30,
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
        "capacity_model_added": False,
        "portfolio_variant_count": 0,
    }
    assert inference["hac_lags"] == 10
    assert inference["cost_multiplier"] == 1.0
    assert inference["pooled_definition"] == "chronological_concatenation_W1_through_W6"
    assert inference["familywise_alpha"] == 0.05
    assert inference["multiplicity_method"] == "holm"
    assert inference["hypothesis_count"] == 2
    assert inference["hypothesis_family"] == [
        "ridge_alpha1_v1",
        "lgbm_ridge_rank_blend_50_50_v1",
    ]
    assert attempts["alternative_attempt_count"] == 2
    assert attempts["no_replacement_or_third_arm"] is True
    assert attempts["no_post_result_threshold_or_arm_change"] is True
    assert attempts["factor_g1_trial_count_increment"] == 0


def test_all_attribution_outcomes_are_non_production_and_future_run_is_not_authorized() -> None:
    document = _document()
    decisions = document["attribution_decision"]
    future = document["future_execution_contract_not_authorized_here"]

    assert set(decisions) == {
        "MODEL_STRUCTURE_SUPPORTED",
        "PORTFOLIO_CONVERSION_BOTTLENECK_INDICATED",
        "FEATURE_INFORMATION_BOTTLENECK_INDICATED",
        "MIXED_NOT_CONCLUSIVE",
        "BLOCKED",
        "decision_is_not_causal_proof",
        "production_authorization_for_every_outcome",
        "decision_precedence",
    }
    assert decisions["decision_is_not_causal_proof"] is True
    assert decisions["production_authorization_for_every_outcome"] == "none"
    assert decisions["decision_precedence"] == [
        "BLOCKED",
        "MODEL_STRUCTURE_SUPPORTED",
        "PORTFOLIO_CONVERSION_BOTTLENECK_INDICATED",
        "FEATURE_INFORMATION_BOTTLENECK_INDICATED",
        "MIXED_NOT_CONCLUSIVE",
    ]
    assert future["implementation_requires_new_main_target"] is True
    assert future["formal_run_count"] == future["deterministic_replay_count"] == 1
    assert future["high_load_runs_serial_only"] is True
    assert future["production_scheduler_change_or_restart"] is False

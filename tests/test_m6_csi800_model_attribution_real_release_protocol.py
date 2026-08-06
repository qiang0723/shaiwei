from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

from shaiwei.config import PROJECT_ROOT


PROTOCOL = PROJECT_ROOT / "config/m6_csi800_model_attribution_real_release_v1.yaml"
RESULT_PROTOCOL = PROJECT_ROOT / "config/m6_csi800_model_attribution_v1.yaml"
ENGINEERING_MANIFEST = (
    PROJECT_ROOT / "config/m6_csi800_model_attribution_engineering_manifest_v1.json"
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load() -> dict:
    document = yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def test_release_protocol_binds_immutable_predecessors() -> None:
    document = _load()
    predecessors = document["predecessors"]
    assert predecessors["result_protocol"]["sha256"] == _sha(RESULT_PROTOCOL)
    assert predecessors["engineering_manifest"]["sha256"] == _sha(ENGINEERING_MANIFEST)
    assert predecessors["preserve_without_rewrite"] is True
    assert document["stage"] == "RESULT_BLIND_REAL_RELEASE_PREPARATION_ONLY"


def test_preapproval_authority_is_result_blind_and_non_production() -> None:
    authority = _load()["authority"]
    assert authority["result_blind_implementation_authorized"] is True
    assert authority["exact_release_scope_generation_authorized"] is True
    for key in (
        "real_qlib_feature_or_price_read_authorized",
        "real_label_or_effect_read_authorized",
        "real_model_fit_authorized",
        "real_prediction_authorized",
        "real_backtest_authorized",
        "formal_effect_output_write_authorized",
        "experiment_ledger_write_authorized",
        "forward_signal_authorized",
        "paper_portfolio_authorized",
        "external_runtime_network_authorized",
        "env_or_secret_read_authorized",
    ):
        assert authority[key] is False
    assert authority["production_authorization"] == "none"
    assert authority["tushare_calls"] == authority["deepseek_calls"] == 0


def test_real_pipeline_changes_only_model_structure() -> None:
    document = _load()
    pipeline = document["real_pipeline"]
    assert pipeline["windows"] == ["W1", "W2", "W3", "W4", "W5", "W6"]
    assert pipeline["handler"] == {
        "class": "qlib.contrib.data.handler.Alpha158",
        "instruments": "csi800",
        "feature_set": "Alpha158",
        "label_expression": "Ref($open,-11)/Ref($open,-1)-1",
        "fit_end_time": "purged_train_last_signal",
        "train_end": "purged_train_last_signal",
        "valid_end": "purged_valid_last_signal",
        "score_end": "score_last_signal",
        "learn_data_key": "DK_L",
        "inference_data_key": "DK_I",
        "same_fitted_handler_per_window_across_models": True,
    }
    assert pipeline["arms"] == {
        "control": "clean_lgbm_control_v1",
        "alternatives": ["ridge_alpha1_v1", "lgbm_ridge_rank_blend_50_50_v1"],
        "trained_model_count_per_window": 2,
        "blend_trains_third_model": False,
    }
    portfolio = pipeline["portfolio"]
    assert portfolio["topk"] == 30 and portfolio["n_drop"] == 3
    assert portfolio["rebalance_trade_days"] == 10
    assert portfolio["cost_multipliers"] == [1.0, 1.5, 2.0]
    assert portfolio["cost_scenario_method"] == (
        "scale_recorded_base_daily_cost_without_rerunning_trades"
    )


def test_metrics_statistics_stress_and_counting_are_exact() -> None:
    document = _load()
    metrics = document["metric_contract"]
    assert metrics["prediction_key_policy"] == (
        "exact_equal_across_three_arms_no_inner_join_fallback"
    )
    assert metrics["drawdown"] == "maximum_drawdown_of_net_strategy_nav_not_active_nav"
    assert metrics["primary_inference"] == {
        "hac_lags": 10,
        "alternative": "greater",
        "hypothesis_count": 2,
        "multiplicity": "holm",
        "familywise_alpha": 0.05,
    }
    assert document["stress_contract"]["style_shift_2017"]["status"] == (
        "NOT_EVALUABLE_NO_PRE_2017_FROZEN_MODEL"
    )
    counting = document["execution_counting"]
    assert counting["runner_invocation_count"] == 1
    assert counting["complete_internal_passes"] == ["first_pass", "replay"]
    assert counting["alternative_attempt_count_consumed_at_first_real_effect_read"] == 2
    assert counting["no_replacement_or_third_arm"] is True


def test_release_requires_exact_future_user_approval() -> None:
    document = _load()
    release = document["release_and_approval"]
    assert release["release_scope_kind"] == (
        "REAL_EFFECT_RELEASE_READY_NOT_EXECUTION_APPROVAL"
    )
    assert release["approval_must_bind_exact_release_scope_sha256"] is True
    assert release["approval_action"] == (
        "M6_REAL_EFFECT_ONCE_WITH_INTERNAL_REPLAY_AND_INDEPENDENT_AUDIT"
    )
    assert release["prior_authority_inheritance"] is False
    assert release["scope_drift_invalidates_approval"] is True
    stop = document["stop_condition"]
    assert stop["stop_after_exact_release_scope_is_committed_and_pushed"] is True
    assert stop["explicit_user_authorization_of_full_scope_required"] is True
    assert stop["strategy_effective_before_authorized_run"] == "NOT_EVALUATED"


def test_docker_and_artifact_boundaries_are_narrow() -> None:
    document = _load()
    docker = document["docker"]
    assert docker["runtime_network_mode"] == "none"
    assert docker["read_only_root"] is True and docker["run_as_non_root"] is True
    assert docker["cap_drop_all"] is True and docker["no_new_privileges"] is True
    assert docker["env_file_mounted"] is False
    assert docker["docker_socket_mounted"] is False
    assert docker["full_project_root_mounted"] is False
    assert docker["production_ledger_mounted_during_runner_or_audit"] is False
    runner_targets = [row["target"] for row in docker["runner_mounts"]]
    assert runner_targets == ["/qlib", "/inputs/release.json", "/inputs/approval.json", "/outputs"]
    assert document["artifact_contract"]["passes"] == ["first_pass", "replay"]
    assert document["independent_audit"]["imports_primary_inference_module"] is False

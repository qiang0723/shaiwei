from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "config/ts_v5_r3g2_effect_v1.yaml"


def _load() -> dict:
    return yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))


def test_protocol_is_result_blind_and_has_no_execution_authority() -> None:
    document = _load()
    authority = document["authority_at_freeze"]

    assert document["status"] == (
        "RESULT_BLIND_EFFECT_PROTOCOL_FROZEN_PENDING_ENGINEERING_RELEASE"
    )
    assert authority["protocol_and_contract_tests"] is True
    assert {
        key
        for key, value in authority.items()
        if isinstance(value, bool) and value
    } == {"protocol_and_contract_tests"}
    assert authority["deepseek_calls"] == authority["tushare_calls"] == 0
    assert document["production_authorization"] == "none"


def test_only_the_mechanically_selected_breakout_retest_points_are_bound() -> None:
    points = _load()["selected_effect_points"]

    assert points["mechanism"] == "BREAKOUT_RETEST"
    assert points["primary_anchor"]["point_hash"] == (
        "81833a47b1edb59455c997c422bb36b63454f1da84e29696269c9c950e019784"
    )
    assert [point["point_hash"] for point in points["sensitivity_neighbours"]] == [
        "09bceb50259b20a82b8af30c41d24af7e2b543ff78790aa893c814f72dfc2ea5",
        "355926341879e2a55dc3268d9e0f80c3a82bae5c56c96f59516087b365ac8076",
    ]
    assert points["primary_may_not_be_replaced_by_neighbour"] is True
    assert points["extra_mechanism_point_or_parameter_change"] == "forbidden"


def test_roles_are_sequential_and_2026_has_no_effect_authority() -> None:
    roles = _load()["chronological_roles"]

    assert roles["discovery_effect"] == {
        "start": "20210104",
        "end": "20231229",
        "required_calendar_years": [2021, 2022, 2023],
        "selected_density_before_effect": True,
    }
    assert roles["conditional_frozen_holdout_effect"]["start"] == "20240102"
    assert roles["conditional_frozen_holdout_effect"]["end"] == "20251231"
    assert roles["conditional_frozen_holdout_effect"][
        "outcome_unread_until_discovery_gate_passes"
    ]
    monitor = roles["current_partial_year_monitor"]
    assert monitor["role"] == (
        "NOT_FOR_SELECTION_NOT_FOR_VERDICT_NO_FROZEN_W8_RANK_LINEAGE"
    )
    assert monitor["alpha158_score_read"] is False
    assert monitor["post_entry_outcome_read"] is False
    assert roles["cross_partition_position_or_outcome"] == "forbidden"


def test_dirty_legacy_scores_are_forbidden_and_w7_is_uniformly_purged() -> None:
    lineage = _load()["ranking_lineage"]
    legacy = lineage["old_p1_cache"]
    w7 = lineage["frozen_w7_extension"]

    assert legacy["authorized_for_effect"] is False
    assert legacy["reason"] == (
        "predates_uniform_t_plus_11_train_and_valid_label_maturity_purge"
    )
    assert list(lineage["clean_m6_lineage"]["reusable_predictions"]) == [
        "W2",
        "W3",
        "W4",
        "W5",
        "W6",
    ]
    assert w7["train"] == ["2022-01-01", "2024-06-30"]
    assert w7["purged_train_last_signal"] == "2024-06-13"
    assert w7["valid"] == ["2024-07-01", "2024-12-31"]
    assert w7["purged_valid_last_signal"] == "2024-12-16"
    assert w7["test"] == ["2025-01-01", "2025-12-31"]
    assert w7["handler_fit_end"] == w7["purged_train_last_signal"]
    assert lineage["w8"]["use_w7_for_2026"] == "forbidden"


def test_ranking_is_prior_complete_week_and_missing_scores_never_fallback() -> None:
    ranking = _load()["ranking_lineage"]

    assert ranking["score_observation"] == (
        "last_official_open_date_strictly_before_signal_iso_week_monday"
    )
    assert ranking["ordering"] == "score_descending_then_ts_code_ascending"
    assert ranking["same_day_or_current_incomplete_week_score"] == "forbidden"
    assert ranking["missing_score_policy"] == "exclude_event_without_fallback"
    assert ranking["minimum_event_key_score_coverage_each_point_partition"] == 0.95


def test_portfolio_risk_execution_and_costs_are_exact() -> None:
    document = _load()
    portfolio = document["portfolio"]
    exits = document["entry_and_exit"]
    costs = document["costs"]

    assert portfolio["initial_capital_rmb_each_arm_partition"] == 500_000
    assert portfolio["maximum_positions"] == 7
    assert portfolio["maximum_gross_weight_at_new_fill"] == 0.70
    assert portfolio["maximum_security_weight_at_new_fill"] == 0.10
    assert portfolio["maximum_entry_batches"] == 2
    assert portfolio["maximum_each_batch_weight"] == 0.05
    assert portfolio["maximum_portfolio_open_risk_at_new_fill"] == 0.03
    assert exits["first_entry"] == (
        "immediately_next_legal_official_open_without_retry"
    )
    assert exits["averaging_down"] == "forbidden"
    assert exits["stop_may_move_down"] is False
    assert exits["take_profit_adjusted"] == (
        "minimum_of_first_fill_plus_1_5_initial_risk_and_first_fill_times_1_20"
    )
    assert exits["time_exit"] == (
        "open_of_fifteenth_subsequent_official_trade_session_after_first_fill"
    )
    assert costs["scenarios"] == [
        "base_1x",
        "all_costs_2x",
        "base_plus_10bp_slippage_each_side",
    ]
    assert costs["commission_rate_each_side"] == 0.0003
    assert costs["extra_slippage_each_side"] == 0.001


def test_effect_family_has_three_attempts_and_neighbours_cannot_replace_primary() -> None:
    document = _load()
    attempts = document["attempt_and_firewall"]
    discovery = document["discovery_gate"]
    holdout = document["conditional_holdout_gate"]

    assert attempts["strategy_effect_attempt_count_on_first_effect_read"] == 3
    assert attempts["years_cost_scenarios_and_metrics_are_not_additional_attempts"]
    assert attempts["same_scope_effect_rerun"] == "forbidden"
    assert attempts["partial_2026_outcomes"] == "forbidden"
    assert discovery["both_neighbours_must_pass"] is True
    assert discovery["deflated_sharpe"]["trial_count"] == 3
    assert discovery["deflated_sharpe"]["minimum_observations"] == 252
    assert holdout["neighbour_robustness"]["minimum_passing_neighbour_count"] == 1


def test_any_historical_go_only_authorizes_a_separate_forward_review() -> None:
    document = _load()
    verdicts = document["verdicts"]
    future = document["future_execution_not_authorized_here"]

    assert verdicts["historical_pass"] == "GO_TS_V5_R3G2_HISTORICAL_REVIEW_ONLY"
    assert verdicts["historical_pass_authorizes_paper_or_production"] is False
    assert verdicts["production_authorization_for_every_outcome"] == "none"
    assert future["explicit_user_approval_of_bound_release_scope_before_first_effect_read"] == (
        "required"
    )
    assert future["docker_network_mode"] == "none"
    assert future["scheduler_restart_or_change"] == "forbidden"

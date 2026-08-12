from pathlib import Path
from hashlib import sha256

import yaml


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "config/ts_v4_parameter_research_v1.yaml"


def _protocol() -> dict:
    value = yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_v4_changes_only_one_ordered_parameter_axis() -> None:
    protocol = _protocol()
    axis = protocol["single_change_axis"]

    assert protocol["stage"] == "PARAMETER_RESEARCH_PROTOCOL_FROZEN_NOT_EXECUTION_AUTHORIZED"
    assert axis["parameter"] == "previous_complete_week_vwap_pullback_depth_fraction"
    assert [arm["pullback_depth_fraction"] for arm in axis["arms"]] == [
        0.015,
        0.025,
        0.035,
        0.04,
    ]
    assert axis["exact_strategy_attempt_count"] == 4
    assert axis["parameter_grid_expansion"] == "forbidden"
    assert axis["arms"][-1]["role"] == "frozen_v3_control"


def test_v4_keeps_execution_risk_and_exit_rules_fixed() -> None:
    protocol = _protocol()
    scope = protocol["fixed_scope"]
    inherited = protocol["inherited_rules_unchanged"]

    assert scope["initial_capital_rmb"] == 500000
    assert scope["maximum_positions"] == 7
    assert scope["maximum_total_weight"] == 0.70
    assert scope["maximum_security_weight"] == 0.10
    assert scope["maximum_first_batch_weight"] == 0.05
    assert inherited["daily_recovery_confirmation"] == (
        "close_gt_previous_valid_high_and_close_gt_open"
    )
    assert inherited["initial_structure_stop"] == (
        "previous_complete_week_low_adjusted_times_0_98"
    )
    assert inherited["maximum_stop_distance_exclusive"] == 0.15
    assert inherited["take_profit"] == (
        "min_first_fill_plus_1_5_initial_risk_and_first_fill_times_1_20"
    )
    assert inherited["maximum_holding_official_trade_days_after_first_fill"] == 15


def test_v4_chronology_is_locked_and_alpha158_is_not_backfilled() -> None:
    protocol = _protocol()
    inputs = protocol["bound_inputs"]
    clock = protocol["chronological_partition"]

    assert inputs["alpha158_oos_span"] == ["20190102", "20241231"]
    assert inputs["current_model_backfill"] == "forbidden"
    assert clock["discovery"] == {"start": "20190102", "end": "20211231"}
    assert clock["validation"] == {"start": "20220104", "end": "20231229"}
    assert clock["locked_historical_test"] == {
        "start": "20240102",
        "end": "20241231",
    }
    assert clock["maximum_signal_to_final_exit_trade_days"] == 16
    assert clock["validation_unread_until_discovery_selection_locked"] is True
    assert clock["locked_test_unread_until_validation_pass"] is True
    assert clock["locked_test_is_pristine_unseen"] is False
    assert clock["authoritative_unseen_evidence"] == "natural_forward_only"


def test_v4_bound_input_files_match_frozen_hashes() -> None:
    inputs = _protocol()["bound_inputs"]

    assert _sha256(ROOT / inputs["r3_input_manifest_path"]) == inputs[
        "r3_input_manifest_sha256"
    ]
    assert _sha256(ROOT / inputs["alpha158_oos_path"]) == inputs[
        "alpha158_oos_sha256"
    ]


def test_v4_density_gate_is_result_blind_and_cannot_be_relaxed() -> None:
    gate = _protocol()["stage_0_result_blind_density_preflight"]

    assert gate["period"] == "discovery"
    assert gate["all_four_arms_profiled"] is True
    assert gate["post_entry_fields_forbidden"] is True
    assert gate["alpha158_allowed_columns"] == ["ts_code", "trade_date"]
    assert gate["per_arm_minimum_legal_events"] == 30
    assert gate["per_arm_minimum_distinct_signal_days"] == 20
    assert gate["per_arm_minimum_events_each_calendar_year"] == 5
    assert gate["minimum_passing_adjacent_pair_count"] == 1
    assert gate["threshold_change_after_profile"] == "forbidden"


def test_v4_selection_requires_a_plateau_and_counts_all_attempts() -> None:
    discovery = _protocol()["stage_1_discovery_effect"]
    testing = discovery["multiple_testing"]
    plateau = discovery["plateau"]

    assert discovery["arms_run"] == ["TS4-D015", "TS4-D025", "TS4-D035", "TS4-D040"]
    assert testing["trial_count_including_all_proposed_arms"] == 4
    assert testing["selected_arm_minimum_deflated_sharpe_probability"] == 0.95
    assert testing["failed_sparse_or_invalid_arm_still_counts"] is True
    assert plateau["both_arms_must_pass_all_hard_gates"] is True
    assert plateau["minimum_worse_to_better_pooled_net_excess_ratio"] == 0.50
    assert plateau["maximum_absolute_drawdown_difference"] == 0.05
    assert discovery["deterministic_selection_order"] == [
        "maximum_median_calendar_year_h00906_net_excess",
        "minimum_maximum_drawdown",
        "minimum_turnover",
        "maximum_pullback_depth_fraction",
    ]


def test_v4_validation_and_test_forbid_winner_reselection() -> None:
    protocol = _protocol()
    validation = protocol["stage_2_validation"]
    locked_test = protocol["stage_3_locked_historical_test"]
    stop = protocol["stopping_and_successor_control"]

    assert validation["only_selected_discovery_arm"] is True
    assert validation["fallback_to_next_arm_after_failure"] == "forbidden"
    assert locked_test["only_validation_passed_locked_arm"] is True
    assert locked_test["fallback_or_parameter_change"] == "forbidden"
    assert stop["select_validation_or_test_winner"] == "forbidden"
    assert stop["failed_validation_or_test_may_try_next_discovery_arm"] is False
    assert stop["historical_go_authorizes_paper_account"] is False
    assert stop["historical_go_authorizes_web_or_production"] is False


def test_v4_effect_and_external_access_are_not_currently_authorized() -> None:
    authority = _protocol()["current_authority"]

    assert authority["protocol_and_fixture_engineering"] is True
    assert all(
        value is False
        for key, value in authority.items()
        if key != "protocol_and_fixture_engineering"
    )


def test_v4_requires_total_return_benchmark_without_proxy() -> None:
    inputs = _protocol()["bound_inputs"]

    assert inputs["primary_benchmark_logical_identifier"] == "CSI_H00906_TOTAL_RETURN"
    assert inputs["primary_benchmark_status"] == (
        "BLOCKED_UNTIL_SEPARATE_AUDITABLE_LINEAGE_RECOVERY"
    )
    assert inputs["price_index_000906_substitution"] == "forbidden"
    assert inputs["locally_derived_dividend_proxy"] == "forbidden"


def test_v4_costs_follow_historical_transfer_fee_and_stamp_tax_changes() -> None:
    costs = _protocol()["execution_and_cost"]

    assert costs["commission_rate_each_side"] == 0.0003
    assert costs["minimum_commission_rmb"] == 5.0
    assert costs["transfer_fee_rate_each_side_before_2022_04_29"] == 0.00002
    assert costs["transfer_fee_rate_each_side_on_or_after_2022_04_29"] == 0.00001
    assert costs["stamp_tax_sell_rate_before_2023_08_28"] == 0.001
    assert costs["stamp_tax_sell_rate_on_or_after_2023_08_28"] == 0.0005

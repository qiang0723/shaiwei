from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]
PROTOCOL = ROOT / "config/ts_v3_pullback_state_preflight_v1.yaml"


def _protocol() -> dict:
    return yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))


def test_r4_is_strictly_result_blind() -> None:
    authority = _protocol()["authorization"]

    assert authority["offline_engineering_and_fixture"] is True
    assert authority["read_price_and_reference_fields_through_candidate_next_open"] is True
    assert all(
        authority[key] is False
        for key in (
            "read_post_entry_return",
            "read_mae_mfe",
            "read_alpha158_prediction_values",
            "rank_candidates",
            "model_training_or_prediction",
            "strategy_backtest_or_effect",
            "external_network",
            "env_or_secret_read",
            "paper_account",
            "web_or_production_change",
        )
    )


def test_r4_freezes_one_pullback_and_open_contract() -> None:
    protocol = _protocol()
    weekly = protocol["weekly_plan"]
    daily = protocol["daily_state_machine"]
    next_open = protocol["next_open_preflight"]

    assert weekly["pullback_line"] == "previous_complete_week_vwap_adjusted_times_0_96"
    assert weekly["initial_structure_stop"] == (
        "previous_complete_week_low_adjusted_times_0_98"
    )
    assert daily["same_completed_day_touch_and_recovery_allowed"] is True
    assert daily["first_confirmation_only"] is True
    assert daily["failed_next_open_is_not_retried"] is True
    assert next_open["structure_stop_distance"] == {
        "minimum_exclusive": 0.0,
        "maximum_exclusive": 0.15,
    }


def test_r4_sample_gate_and_benchmark_cannot_relax() -> None:
    protocol = _protocol()

    assert protocol["result_blind_evaluability_gate"] == {
        "true_legal_entry_event_count_minimum": 60,
        "distinct_true_legal_entry_day_count_minimum": 40,
        "each_calendar_year_true_legal_entry_event_count_minimum": 3,
        "calendar_years_with_at_least_8_true_legal_entry_events_minimum": 4,
        "required_calendar_years": [2019, 2020, 2021, 2022, 2023, 2024],
        "threshold_change_after_profile": "forbidden",
    }
    assert protocol["benchmark_preflight"]["price_index_000906_substitution"] == "forbidden"
    assert protocol["benchmark_preflight"]["locally_derived_proxy"] == "forbidden"
    assert protocol["attempt_and_change_control"]["strategy_effect_attempt_count"] == 0
    assert protocol["attempt_and_change_control"]["same_scope_profile_rerun"] == "forbidden"

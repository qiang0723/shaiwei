from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]
REVIEW = ROOT / "config/ts_v3_effect_prefreeze_review_v1.yaml"


def _review() -> dict:
    return yaml.safe_load(REVIEW.read_text(encoding="utf-8"))


def test_ts_v3_prefreeze_review_stops_before_effect() -> None:
    review = _review()

    assert review["verdict"] == {
        "ts_1b_effect_protocol": "STOP_BEFORE_FREEZE",
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
    }
    assert review["attempt_control"] == {
        "strategy_effect_attempt_count": 0,
        "alpha158_value_read_count": 0,
        "result_based_threshold_change_count": 0,
        "r3_same_scope_rerun": "forbidden",
    }
    assert all(value is False for value in review["authority"].values())


def test_ts_v3_prefreeze_review_preserves_blocking_findings() -> None:
    review = _review()
    findings = {
        finding["finding_id"]: finding["severity"]
        for finding in review["pre_effect_findings"]
    }

    assert findings == {
        "MISSING_PULLBACK_TOUCHED_STATE": "BLOCKING",
        "EFFECT_SAMPLE_DENOMINATOR_NOT_YET_VALID": "BLOCKING",
        "PRIMARY_TOTAL_RETURN_BENCHMARK_NOT_BOUND": "BLOCKING_BEFORE_REAL_EFFECT",
        "V3_EXIT_SEMANTICS_CONFLICT": "MUST_RESOLVE_BEFORE_FREEZE",
    }
    assert review["required_successor"]["id"] == "TS-1A-R4"
    assert "post_entry_return" in review["required_successor"]["forbidden"]
    assert "strategy_backtest_or_effect" in review["required_successor"]["forbidden"]


def test_ts_v3_successor_recommendation_has_one_risk_and_exit_contract() -> None:
    recommendation = _review()["non_authoritative_result_blind_recommendation_for_successor"]

    assert recommendation["pullback_touch"] == (
        "adjusted_low_lte_weekly_anchor_times_0_96"
    )
    assert recommendation["initial_structure_stop"] == (
        "previous_complete_week_low_times_0_98"
    )
    assert recommendation["next_open_stop_distance"] == "strictly_gt_0_and_lt_0_15"
    assert recommendation["stop_ratchet"] == (
        "max_current_stop_and_latest_complete_week_low_times_0_98"
    )
    assert recommendation["take_profit"] == (
        "min_first_fill_plus_1_5_initial_risk_and_first_fill_times_1_20"
    )

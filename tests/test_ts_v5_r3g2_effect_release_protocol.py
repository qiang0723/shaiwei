from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]


def _load() -> dict:
    return yaml.safe_load(
        (ROOT / "config/ts_v5_r3g2_effect_release_v1.yaml").read_text(encoding="utf-8")
    )


def test_release_protocol_is_result_blind_and_binds_authoritative_w7() -> None:
    document = _load()
    assert document["status"] == "RESULT_BLIND_EFFECT_ENGINEERING_AND_RELEASE_PREPARATION_ONLY"
    assert document["predecessors"]["effect_protocol"]["sha256"] == (
        "c3aa5a2bef199d8745b6e0399085dcf5a60d9f28f29a5426ea0104831f3572bf"
    )
    assert document["predecessors"]["w7_recovery_manifest"]["verdict"] == (
        "GO_W7_SCORE_LINEAGE_DATA_ONLY"
    )
    authority = document["authority"]
    assert authority["result_blind_implementation"] is True
    assert authority["exact_release_scope_generation"] is True
    assert authority["real_event_score_value_or_rank_read"] is False
    assert authority["real_post_entry_price_or_benchmark_value_read"] is False
    assert authority["strategy_effect_or_backtest"] is False
    assert authority["production_authorization"] == "none"


def test_discovery_firewall_and_attempt_count_are_not_ambiguous() -> None:
    document = _load()
    firewall = document["firewall"]
    assert firewall["effect_attempts_consumed_at_first_real_value_read"] == 3
    assert firewall["holdout_input_adapter_may_not_open_outcome_or_benchmark_values_before_discovery_pass"] is True
    assert firewall["discovery_failure_requires_holdout_artifact_absence"] is True
    assert firewall["same_scope_retry"] == "forbidden"
    assert document["stop_condition"]["no_real_effect_value_read_before_exact_approval"] is True


def test_execution_clarifications_preserve_frozen_economic_parameters() -> None:
    document = _load()
    rules = document["execution_clarifications"]
    assert rules["economic_parameter_change"] is False
    assert rules["capacity"]["prior_20_completed_security_bars_only"] is True
    assert rules["capacity"]["sell"] == (
        "partial_fill_up_to_capacity_then_keep_remainder_pending"
    )
    assert rules["lots_and_t_plus_one"]["same_day_second_batch_cannot_be_sold_intraday"] is True
    assert rules["position_rules"]["second_batch_does_not_reset_holding_age_stop_or_target"] is True
    assert rules["cost_scenarios"]["each_scenario_runs_independent_cash_lot_and_capacity_path"] is True
    assert rules["unresolved_exit"]["at_partition_end"] == "BLOCKED_PRE_EFFECT"


def test_independent_auditor_has_no_source_market_or_score_mount() -> None:
    audit = _load()["independent_audit"]
    assert audit["separate_entrypoint"] is True
    assert audit["imports_primary_portfolio_or_gate_modules"] is False
    assert audit["source_market_score_or_benchmark_mount"] is False

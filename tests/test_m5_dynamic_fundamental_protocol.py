from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]
CONFIG_PATH = ROOT / "config/m5_dynamic_fundamental_cross_pool_v1.yaml"
EXPORT_PATH = (
    ROOT / "config/m5_dynamic_fundamental_cross_pool_proposal_export_v1.json"
)
F2_CONFIG_PATH = ROOT / "config/f2_csi800_fundamental_dynamics_v1.yaml"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _config() -> dict[str, object]:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def test_proposal_export_is_bound_and_canonical() -> None:
    config = _config()
    source = config["source_proposal"]
    export = json.loads(EXPORT_PATH.read_text(encoding="utf-8"))

    assert source["proposal_export_sha256"] == _sha256(EXPORT_PATH)
    assert export["canonical_proposal_sha256"] == _canonical_sha256(
        export["canonical_proposal"]
    )
    assert export["proposal_request_sha256"] == _canonical_sha256(
        export["canonical_proposal"]["request"]
    )
    assert source["proposal_id"] == export["proposal_id"]
    assert source["proposal_request_sha256"] == export["proposal_request_sha256"]
    assert source["required_head_event_sha256"] == export["proposal_head_event"][
        "event_sha256"
    ]
    assert export["proposal_state_at_export"] == "REVIEW_REQUIRED"
    assert export["proposal_event_seq_at_export"] == 2

    canonical = export["canonical_proposal"]
    assert canonical["proposal_id"] == export["proposal_id"]
    assert canonical["proposal_request_sha256"] == export["proposal_request_sha256"]
    assert canonical["created_at"] == export["created_at"]
    assert canonical["expires_at"] == export["expires_at"]
    assert canonical["source_identity"] == export["source_identity"]
    assert all(
        value is False
        for value in canonical["authority"].values()
        if isinstance(value, bool)
    )
    created = datetime.fromisoformat(export["created_at"])
    expires = datetime.fromisoformat(export["expires_at"])
    assert (expires - created).total_seconds() == 7 * 24 * 60 * 60
    assert set(export["proposal_head_event"]) == {
        "event_id",
        "event_sha256",
        "prev_event_sha256",
        "payload_sha256",
        "recorded_at",
    }
    assert all(
        len(export["proposal_head_event"][field]) == 64
        for field in ("event_id", "event_sha256", "prev_event_sha256", "payload_sha256")
    )


def test_transfer_universe_filters_are_structured_and_exact() -> None:
    universes = {item["universe_id"]: item for item in _config()["universe_inputs"]}

    for universe_id in (
        "star-board-midcap-pit-v1",
        "star-board-smallcap-pit-v1",
    ):
        assert universes[universe_id]["membership_filter"] == {
            "column": "universe_id",
            "value": universe_id,
        }
        assert universes[universe_id]["universe_kind"] == "CUSTOM_RULE_BASED"


def test_eight_candidates_form_exact_twenty_four_unit_matrix() -> None:
    config = _config()
    scope = config["scope"]
    candidates = config["candidates"]
    universes = config["universe_inputs"]

    candidate_ids = [candidate["candidate_id"] for candidate in candidates]
    universe_ids = [universe["universe_id"] for universe in universes]
    assert len(candidate_ids) == len(set(candidate_ids)) == scope["candidate_count"] == 8
    assert len(universe_ids) == len(set(universe_ids)) == scope["universe_count"] == 3
    assert len(candidate_ids) * len(universe_ids) == scope["evaluation_unit_count"] == 24
    assert {candidate["expected_direction"] for candidate in candidates} <= {-1, 1}


def test_candidates_do_not_repeat_f2_formulas_or_ids() -> None:
    config = _config()
    f2_config = yaml.safe_load(F2_CONFIG_PATH.read_text(encoding="utf-8"))
    candidate_ids = {candidate["candidate_id"] for candidate in config["candidates"]}
    candidate_formulas = {candidate["formula"] for candidate in config["candidates"]}
    f2_ids = {candidate["feature_id"] for candidate in f2_config["features"]}
    f2_formulas = {candidate["formula"] for candidate in f2_config["features"]}

    assert candidate_ids.isdisjoint(f2_ids)
    assert candidate_formulas.isdisjoint(f2_formulas)
    assert set(config["predecessor_boundary"]["forbidden_exact_candidates"]) == f2_ids


def test_multiplicity_and_authority_fail_closed() -> None:
    config = _config()
    multiplicity = config["multiplicity"]
    authority = config["authority"]

    assert multiplicity["generation_attempt_increment_at_protocol_freeze"] == 8
    assert multiplicity["primary_prior_attempt_count"] == 6
    assert multiplicity["primary_after_protocol_freeze"] == 14
    assert multiplicity["sensitivity_prior_attempt_count"] == 12
    assert multiplicity["sensitivity_after_protocol_freeze"] == 20
    assert multiplicity["effect_test_count"] == 0
    assert multiplicity["data_rejected_candidates_still_count_as_generation_attempts"]
    assert multiplicity["no_replacements"]

    assert authority["data_gate_approval_recorded"] is False
    assert authority["engineering_gate_approval_recorded"] is False
    assert authority["data_gate_execution_authorized"] is False
    assert authority["engineering_gate_execution_authorized"] is False
    assert authority["provider_call_count"] == 0
    assert authority["provider_budget_usd"] == "0.00"
    assert authority["label_read_authorized"] is False
    assert authority["sealed_effect_read_authorized"] is False
    assert authority["model_training_authorized"] is False
    assert authority["backtest_authorized"] is False
    assert authority["production_authorization"] == "none"
    true_boolean_authority = {
        key for key, value in authority.items() if isinstance(value, bool) and value
    }
    assert true_boolean_authority == {"protocol_freeze_authorized_by_user_instruction"}


def test_pit_input_validity_and_staleness_are_frozen() -> None:
    config = _config()
    point_in_time = config["point_in_time"]
    policy = config["denominator_and_missing_policy"]

    assert point_in_time["availability"] == "first_open_day_strictly_after_f_ann_date"
    assert point_in_time["predecessor_period"] == (
        "exact_same_month_day_one_calendar_year_earlier"
    )
    assert point_in_time["unrelated_statement_table_requirement_forbidden"]
    assert set(policy["nonnegative_required_fields"]) == {
        "income.total_cogs",
        "income.rd_exp",
        "balancesheet.accounts_receiv",
        "balancesheet.inventories",
        "balancesheet.total_liab",
        "balancesheet.total_cur_assets",
    }
    assert set(policy["signed_fields_explicitly_allowed"]) == {
        "cashflow.n_cash_flows_fnc_act",
        "cashflow.free_cashflow",
    }
    assert policy["current_period_staleness"] == {
        "measure": "formation_date_minus_current_end_date_calendar_days",
        "maximum_days_inclusive": 548,
        "stale_pair_policy": "null_and_count_stale",
        "newer_unpaired_period_may_reuse_prior_pair_within_cap": True,
    }


def test_quality_and_future_windows_are_exact() -> None:
    config = _config()
    half_years = config["data_gate"]["half_year_segments"]
    future = config["future_validation_guardrails_not_authorized"]

    assert [segment["name"] for segment in half_years] == [
        "2021H1",
        "2021H2",
        "2022H1",
        "2022H2",
        "2023H1",
        "2023H2",
        "2024H1",
        "2024H2",
        "2025H1",
        "2025H2",
    ]
    assert {segment["minimum_valid_formation_months"] for segment in half_years} == {5}
    assert future["validation_windows"] == [
        {"name": "M5-W1", "start": "2023-01-03", "end": "2023-06-30"},
        {"name": "M5-W2", "start": "2023-07-03", "end": "2023-12-29"},
        {"name": "M5-W3", "start": "2024-01-02", "end": "2024-06-28"},
        {"name": "M5-W4", "start": "2024-07-01", "end": "2024-12-31"},
        {"name": "M5-W5", "start": "2025-01-02", "end": "2025-06-30"},
        {"name": "M5-W6", "start": "2025-07-01", "end": "2025-12-31"},
    ]
    assert future["validation_signal_maturity_policy"] == (
        "t_plus_11_exit_open_must_be_on_or_before_window_end"
    )
    assert future["cross_window_label_carry_authorized"] is False
    assert future["stress_diagnostics"] == [
        {"name": "microcap_crash_2024", "start": "2024-01-01", "end": "2024-02-29"},
        {"name": "policy_repricing_2024", "start": "2024-09-24", "end": "2024-10-18"},
        {"name": "volume_price_drawdown_2026h1", "start": "2026-01-01", "end": "2026-06-30"},
    ]


def test_correlation_diagnostics_cannot_select_or_relax() -> None:
    diagnostics = _config()["correlation_diagnostics"]

    assert diagnostics["used_for_candidate_screening"] is False
    assert diagnostics["used_to_reduce_multiplicity_n"] is False
    assert diagnostics["cross_pool_factor_rank_correlation"][
        "insufficient_policy"
    ] == "NOT_ESTIMABLE"
    assert diagnostics["within_pool_candidate_rank_correlation"][
        "minimum_eligible_formation_dates"
    ] == 12
    assert diagnostics["future_effect_series_not_authorized"][
        "pairwise_minimum_common_observations"
    ] == 126


def test_partial_data_go_cannot_replace_or_rank_candidates() -> None:
    decision = _config()["data_gate"]["batch_decision"]
    policy = _config()["data_gate"]

    assert decision["all_8_candidate_go"] == "GO_FULL_M5_2_DATA_PREEXECUTION_ONLY"
    assert (
        decision["between_1_and_7_candidate_go"]
        == "GO_PARTIAL_M5_2_DATA_PREEXECUTION_ONLY"
    )
    assert policy["candidate_pass_policy"] == "MUST_PASS_ALL_THREE_UNIVERSES"
    assert policy["candidate_failure_policy"] == (
        "DATA_REJECT_NO_REPLACEMENT_NO_SINGLE_POOL_SHRINK"
    )
    assert policy["partial_go_policy"] == (
        "ALL_DATA_GO_CANDIDATES_MUST_ENTER_ANY_FUTURE_VALIDATION_NO_COVERAGE_RANKING"
    )
    mapping = policy["registry_mapping"]
    assert mapping["GO_FULL_M5_2_DATA_PREEXECUTION_ONLY"]["data_gate_status"] == (
        "DATA_GO_FULL"
    )
    assert mapping["GO_PARTIAL_M5_2_DATA_PREEXECUTION_ONLY"][
        "data_gate_status"
    ] == "DATA_GO_PARTIAL"
    assert mapping["NO_GO_M5_2_DATA_PREEXECUTION"]["lifecycle_state"] == (
        "BLOCKED_DATA"
    )
    projection = policy["registry_candidate_projection"]
    assert projection["candidate_matrix_required"]
    assert projection["empty_or_overlapping_candidate_sets_fail_closed"]


def test_data_and_engineering_approvals_are_distinct() -> None:
    config = _config()
    architecture = config["architecture"]
    source = config["source_proposal"]

    assert architecture["protocol_and_release_scopes_are_separate"]
    assert architecture["data_and_engineering_gate_approvals_are_separate"]
    assert source["required_state_at_data_gate_approval"] == "REVIEW_REQUIRED"
    assert source["expiry_policy"] == (
        "PROTOCOL_SCOPE_AND_DATA_GATE_APPROVAL_MUST_COMPLETE_BEFORE_EXPIRY"
    )
    assert config["synthetic_engineering_gate"][
        "authorized_only_after_data_go_full_or_partial_and_separate_logical_approval"
    ]
    assert "PROPOSAL_NOT_REVIEW_REQUIRED_AT_DATA_GATE_APPROVAL" in config[
        "stop_rules"
    ]
    assert "PROPOSAL_EXPIRED_BEFORE_DATA_GATE_APPROVAL" in config["stop_rules"]
    assert all("LOGICAL_APPROVAL" not in rule for rule in config["stop_rules"])

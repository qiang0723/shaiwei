from __future__ import annotations

import hashlib
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "config/m7_moneyflow_evidence_recovery_v1.yaml"
PROTOCOL_SHA256 = "93a774d8939d443dd5d925e61a7f4727ff9464a969171dcaca58322f9b2b5d53"


def _document() -> dict[str, object]:
    value = yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_evidence_recovery_protocol_identity_is_frozen() -> None:
    assert hashlib.sha256(PROTOCOL.read_bytes()).hexdigest() == PROTOCOL_SHA256


def test_known_results_and_predecessor_no_go_are_explicit() -> None:
    document = _document()
    known = document["known_result_disclosure"]
    predecessor = document["predecessor"]
    assert known["result_blind"] is False
    assert known["unresolved_primary_full_day_suspension_rows"] == 908
    assert known["confirmed_moneyflow_gap_daily_present_rows"] == 541
    assert known["thresholds_or_denominators_changed_after_result"] is False
    assert predecessor["authoritative_verdict"] == "NO_GO_M7_GAP_LINEAGE_INCOMPLETE"
    assert predecessor["original_m7_verdict_unchanged"] == "NO_GO_M7_0_DATA_COMPATIBILITY"
    assert predecessor["scope_closed"] is True
    assert predecessor["same_scope_retry_authorized"] is False


def test_track_a_is_exact_independent_status_evidence_only() -> None:
    document = _document()
    domain = document["frozen_domain"]
    track = document["track_a_independent_trade_status"]
    assert domain["track_a_input_category"] == "PRIMARY_FULL_DAY_SUSPENSION_ONLY_UNRESOLVED"
    assert domain["track_a_expected_member_row_count"] == 908
    assert track["provider"] == "baostock"
    assert track["request_planner"] == "RECOVERY_SPECIFIC_EXACT_TARGET_KEYS"
    assert track["general_s1_status_planner_must_remain_unchanged"] is True
    assert track["numeric_price_or_volume_fields_read"] == 0
    assert track["accepted_status_values"] == ["0", "1"]
    assert track["forward_fill_forbidden"] is True
    assert track["adjacent_date_inference_forbidden"] is True
    assert track["primary_suspend_d_evidence_alone_still_insufficient"] is True


def test_track_b_preserves_primary_moneyflow_semantics() -> None:
    document = _document()
    domain = document["frozen_domain"]
    track = document["track_b_same_semantic_moneyflow"]
    shapes = track["request_shapes"]
    assert domain["track_b_input_category"] == "CONFIRMED_MONEYFLOW_GAP_DAILY_PRESENT"
    assert domain["track_b_expected_member_row_count"] == 541
    assert track["source_api"] == "tushare.moneyflow"
    assert len(track["canonical_fields"]) == 20
    assert [shape["name"] for shape in shapes] == [
        "full_market_by_trade_date",
        "one_security_one_date",
    ]
    assert track["both_request_shapes_required_per_unique_key"] is True
    assert track["canonical_row_sha256_must_match_across_shapes"] is True
    assert track["alternate_sources_forbidden"] == [
        "tushare.moneyflow_ths",
        "tushare.moneyflow_dc",
    ]
    assert track["zero_fill_forbidden"] is True
    assert track["reconstruction_from_daily_amount_or_volume_forbidden"] is True


def test_request_budget_and_claim_semantics_are_bounded() -> None:
    document = _document()
    track_a = document["track_a_independent_trade_status"]
    track_b = document["track_b_same_semantic_moneyflow"]
    execution = document["request_execution_contract"]
    assert track_a["maximum_provider_requests"] == 908
    assert track_b["maximum_provider_requests"] == 1082
    assert execution["maximum_total_provider_requests"] == 1990
    assert execution["sequential_only"] is True
    assert execution["transport_attempts_per_claimed_request"] == 3
    assert execution["semantic_empty_response_retry_authorized"] is False
    assert execution["immutable_request_claim_before_first_attempt"] is True
    assert execution["claimed_failed_request_retry_in_same_release_forbidden"] is True
    assert execution["same_release_semantic_rerun_forbidden"] is True


def test_recovery_go_is_data_only_and_does_not_move_original_gates() -> None:
    document = _document()
    decision = document["decision"]
    successor = document["successor_boundary"]
    assert decision["go"] == "GO_M7_EVIDENCE_RECOVERY_DATA_ONLY"
    assert decision["no_go"] == "NO_GO_M7_EVIDENCE_RECOVERY_INCOMPLETE"
    assert decision["partial_go_for_one_track_forbidden"] is True
    assert decision["go_does_not_change_predecessor_verdicts"] is True
    assert decision["go_does_not_recompute_original_coverage"] is True
    assert decision["strategy_effective"] == "NOT_EVALUATED"
    assert decision["production_authorization"] == "none"
    assert decision["research_attempt_increment"] == 0
    assert successor["original_m7_coverage_thresholds_preserved"] == {
        "overall_min": 0.995,
        "every_complete_half_year_min": 0.99,
        "every_trade_day_min": 0.95,
    }
    assert successor["recovery_data_must_pass_a_separate_successor_m7_data_gate"] is True


def test_protocol_only_authority_stops_before_real_data() -> None:
    document = _document()
    authority = document["construction_authority"]
    stop = document["next_stop"]
    assert authority["protocol_freeze_authorized"] is True
    assert authority["synthetic_fixture_and_machine_contract_authorized"] is True
    assert authority["narrow_engineering_build_authorized"] is False
    assert authority["exact_release_scope_generation_authorized"] is False
    assert authority["external_network_authorized"] is False
    assert authority["tushare_token_read_authorized"] is False
    assert authority["real_security_key_read_authorized"] is False
    assert authority["moneyflow_numeric_value_read_authorized"] is False
    assert authority["data_recovery_execution_authorized"] is False
    assert authority["candidate_generation_authorized"] is False
    assert authority["production_authorization"] == "none"
    assert stop["engineering_requires_a_new_goal"] is True
    assert stop["exact_user_approval_required_before_real_collection"] is True
    assert stop["prior_m7_or_lineage_approval_reuse_forbidden"] is True


def test_direct_sse_runtime_source_is_deferred_not_silently_added() -> None:
    deferred = _document()["deferred_source_boundary"]
    assert deferred["direct_sse_suspension_archive_runtime_source_authorized"] is False
    assert "ADR" in deferred["if_track_a_remains_incomplete"]

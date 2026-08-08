from __future__ import annotations

import hashlib
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "config/m7_moneyflow_recovery_engineering_v1.yaml"
PROTOCOL_SHA256 = "bad3ea9907eaf23258ed54b4b144cab0e86d8b0b1a8c10b0f3afeab9588788e4"


def _document() -> dict[str, object]:
    value = yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_m7_recovery_protocol_identity_is_frozen() -> None:
    assert hashlib.sha256(PROTOCOL.read_bytes()).hexdigest() == PROTOCOL_SHA256


def test_m7_recovery_protocol_preserves_predecessor_no_go() -> None:
    document = _document()
    predecessor = document["predecessor"]
    assert predecessor["authoritative_verdict"] == "NO_GO_M7_0_DATA_COMPATIBILITY"
    assert predecessor["authoritative_scope_closed"] is True
    assert predecessor["same_scope_retry_authorized"] is False
    assert predecessor["strategy_effective"] == "NOT_EVALUATED"
    assert document["known_result_disclosure"]["result_blind"] is False


def test_m7_recovery_protocol_changes_only_successor_engineering_contracts() -> None:
    document = _document()
    domains = document["engineering_changes"]["security_code_domains"]
    assert domains["membership"]["accepted_suffixes"] == ["SH"]
    assert domains["source"]["accepted_suffixes"] == ["SH", "SZ"]
    assert domains["bse"]["accepted"] is False
    frozen = document["frozen_quality_semantics"]
    assert frozen["denominator_changed"] is False
    assert frozen["thresholds_changed"] is False
    assert frozen["half_year_member_key_coverage_minimum_by_universe"] == 0.99


def test_m7_recovery_protocol_stays_synthetic_and_non_authoritative() -> None:
    document = _document()
    authority = document["authority"]
    assert document["stage"] == "SYNTHETIC_RECOVERY_ENGINEERING_PROTOCOL_ONLY"
    assert authority["real_security_key_read_authorized"] is False
    assert authority["numeric_moneyflow_value_read_authorized"] is False
    assert authority["lineage_gap_read_authorized"] is False
    assert authority["candidate_generation_authorized"] is False
    assert authority["effect_read_authorized"] is False
    assert authority["production_authorization"] == "none"
    assert authority["generation_attempt_increment"] == 0


def test_m7_recovery_protocol_requires_pre_read_consumption() -> None:
    document = _document()
    gate = document["engineering_changes"]["pre_read_consumption"]
    assert gate["claim_before_semantic_input_read"] is True
    assert gate["claim_write_mode"] == "ATOMIC_EXCLUSIVE_CREATE"
    assert gate["roles"] == ["runner", "auditor"]
    assert gate["consumed_after_claim_even_if_later_failure"] is True
    assert gate["second_call_must_fail_before_loader_invocation"] is True
    assert gate["current_v1_scope_must_not_be_used_for_retry_test"] is True


def test_m7_recovery_next_stage_needs_new_scope_and_approval() -> None:
    next_stage = _document()["next_legal_stage"]
    assert next_stage["requires_new_protocol"] is True
    assert next_stage["requires_new_release_scope"] is True
    assert next_stage["requires_new_exact_user_approval"] is True
    assert next_stage["may_read_numeric_moneyflow_values"] is False
    assert next_stage["may_generate_candidates"] is False
    assert next_stage["may_change_v1_thresholds"] is False
    assert next_stage["may_reuse_v1_approval"] is False

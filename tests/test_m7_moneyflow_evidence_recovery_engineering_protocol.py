from __future__ import annotations

import hashlib
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "config/m7_moneyflow_evidence_recovery_engineering_v1.yaml"
CONTRACT_SHA256 = "873491b0f3b6b908e4a54c4579c35def3c322ce9adbe033f4f20fdf194a106dd"


def _document() -> dict[str, object]:
    value = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_engineering_contract_identity_is_frozen() -> None:
    assert hashlib.sha256(CONTRACT.read_bytes()).hexdigest() == CONTRACT_SHA256


def test_engineering_contract_binds_pushed_protocol_and_narrow_package() -> None:
    document = _document()
    predecessor = document["frozen_predecessor"]
    boundary = document["implementation_boundary"]
    assert predecessor["protocol_sha256"] == (
        "93a774d8939d443dd5d925e61a7f4727ff9464a969171dcaca58322f9b2b5d53"
    )
    assert predecessor["protocol_commit"] == "efb1f6c49257eb25f20edcced5345d5f160f4b5d"
    assert predecessor["protocol_commit_pushed_before_engineering"] is True
    assert boundary["package"] == "src/shaiwei/research_gates/m7_moneyflow_recovery"
    assert boundary["public_runtime_service_added"] is False
    assert boundary["new_external_dependency_added"] is False
    assert boundary["adr_required"] is False
    assert boundary["module_soft_limit_lines"] == 400


def test_engineering_contract_is_synthetic_only() -> None:
    document = _document()
    authority = document["authority"]
    assert authority["synthetic_engineering_authorized"] is True
    assert authority["docker_image_build_authorized"] is True
    assert authority["exact_release_scope_generation_authorized"] is False
    assert authority["real_security_key_read_authorized"] is False
    assert authority["moneyflow_numeric_value_read_authorized"] is False
    assert authority["tushare_or_baostock_live_call_authorized"] is False
    assert authority["secret_read_authorized"] is False
    assert authority["external_network_authorized"] is False
    assert authority["actual_recovery_authorized"] is False
    assert authority["production_authorization"] == "none"
    assert authority["research_attempt_increment"] == 0


def test_engineering_contract_requires_real_scale_and_bad_paths() -> None:
    fixture = _document()["synthetic_fixture_contract"]
    assert fixture["track_a_member_rows"] == 908
    assert fixture["track_b_member_rows"] == 541
    assert fixture["provider_calls_are_mocks"] is True
    assert fixture["main_and_independent_audit_exact_match_required"] is True
    assert len(fixture["fixture_scenarios"]) == 13
    assert "duplicate_claim_before_loader" in fixture["fixture_scenarios"]
    assert "semantic_failure_no_retry" in fixture["fixture_scenarios"]


def test_engineering_contract_stops_before_release() -> None:
    stop = _document()["next_stop"]
    assert stop["engineering_go_is_not_data_go"] is True
    assert stop["real_recovery_requires_separate_release_scope"] is True
    assert stop["exact_user_approval_required_before_real_recovery"] is True
    assert stop["prior_approval_reuse_forbidden"] is True

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "config/m7_moneyflow_recovery_release_build_v1.yaml"
CONTRACT_SHA256 = "af04ba7353e4d3f6249ad603657d722643b83ef675e30aaf062afc6db15fdc28"


def _document() -> dict[str, object]:
    value = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_release_build_contract_identity_is_frozen() -> None:
    assert hashlib.sha256(CONTRACT.read_bytes()).hexdigest() == CONTRACT_SHA256


def test_release_build_contract_uses_four_separated_roles() -> None:
    document = _document()
    architecture = document["architecture"]
    assert set(architecture["roles"]) == {
        "status_collector",
        "moneyflow_collector",
        "evaluator",
        "auditor",
    }
    assert architecture["collector_and_verdict_process_must_be_separate"] is True
    assert architecture["no_shared_writable_mount_between_collectors"] is True
    assert architecture["evaluator_output_read_only_for_auditor"] is True
    assert architecture["production_ingest_ledger_write_authorized"] is False


def test_release_build_contract_binds_exact_projection_and_same_semantics() -> None:
    document = _document()
    projection = document["target_projection_contract"]
    provider = document["provider_adapter_contract"]
    assert projection["source_core_sha256"] == (
        "df5de399d915ac2cba8533b07a958b5ef06cf7c14a0654c60dc1213cb0d8eeca"
    )
    assert projection["track_a_member_rows"] == 908
    assert projection["track_b_member_rows"] == 541
    assert projection["real_projection_execution_authorized"] is False
    assert provider["clients_must_be_dependency_injected"] is True
    assert provider["project_config_or_env_import_forbidden"] is True
    assert provider["moneyflow_source_api"] == "tushare.moneyflow"
    assert provider["alternate_moneyflow_sources_forbidden"] == [
        "tushare.moneyflow_ths",
        "tushare.moneyflow_dc",
    ]
    assert provider["provider_calls_in_this_stage"] == 0


def test_release_build_contract_stays_before_real_keys_and_network() -> None:
    document = _document()
    authority = document["authority"]
    stop = document["next_stop"]
    assert authority["release_engineering_authorized"] is True
    assert authority["mock_provider_calls_authorized"] is True
    assert authority["real_target_projection_authorized"] is False
    assert authority["real_security_key_read_authorized"] is False
    assert authority["real_moneyflow_numeric_value_read_authorized"] is False
    assert authority["live_provider_call_authorized"] is False
    assert authority["secret_read_authorized"] is False
    assert authority["external_network_authorized"] is False
    assert authority["real_scope_generation_authorized"] is False
    assert authority["approval_envelope_generation_authorized"] is False
    assert authority["recovery_execution_authorized"] is False
    assert authority["production_authorization"] == "none"
    assert stop["real_target_projection_requires_new_exact_authorization"] is True
    assert stop["exact_user_approval_required_before_any_live_provider_call"] is True


def test_release_build_contract_preserves_code_architecture_limits() -> None:
    boundary = _document()["implementation_boundary"]
    assert len(boundary["new_modules"]) == 9
    assert boundary["module_soft_limit_lines"] == 400
    assert boundary["live_cli_or_env_loader_authorized"] is False
    assert boundary["new_external_dependency_or_service_added"] is False
    assert boundary["public_schema_or_ledger_changed"] is False
    assert boundary["adr_required"] is False

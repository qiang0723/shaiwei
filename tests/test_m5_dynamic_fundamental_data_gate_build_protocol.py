from __future__ import annotations

import hashlib
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]
BUILD_PATH = ROOT / "config/m5_dynamic_fundamental_data_gate_build_v1.yaml"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _config() -> dict[str, object]:
    return yaml.safe_load(BUILD_PATH.read_text(encoding="utf-8"))


def test_build_contract_binds_frozen_m5_protocol_scope() -> None:
    config = _config()

    assert config["protocol_scope_sha256"] == (
        "ab8c33968c4ced325ec79524b774163f2991edd0c4d5d7eb7c139b27e9b17557"
    )
    for frozen in config["frozen_inputs"].values():
        assert _sha256(ROOT / frozen["path"]) == frozen["sha256"]


def test_construction_is_fixture_only_and_does_not_authorize_execution() -> None:
    config = _config()
    construction = config["construction"]
    authority = config["authority"]

    assert construction["target_state"] == "RELEASE_READY_NOT_APPROVED"
    assert construction["synthetic_fixture_only"] is True
    assert construction["real_financial_rows_may_be_read"] is False
    assert construction["real_candidate_values_may_be_computed"] is False
    assert construction["formal_registry_may_be_initialized"] is False
    assert construction["formal_gate_events_may_be_written"] is False
    assert authority["data_gate_approval_recorded"] is False
    assert authority["data_gate_execution_authorized"] is False
    assert authority["engineering_gate_execution_authorized"] is False
    assert authority["provider_call_count"] == 0
    assert authority["provider_budget_usd"] == "0.00"
    assert authority["production_authorization"] == "none"
    assert not any(
        value
        for key, value in authority.items()
        if isinstance(value, bool) and key.endswith("_authorized")
    )


def test_membership_uses_next_open_effective_state() -> None:
    clock = _config()["formation_membership_clock"]

    assert clock == {
        "formation_date": "last_sse_open_day_of_month_close",
        "effective_date": "first_sse_open_day_strictly_after_formation_date",
        "membership_date": "exact_effective_date",
        "star50_date_column": "trade_date",
        "custom_pool_date_column": "trade_date",
        "custom_pool_filter_column": "universe_id",
        "custom_pool_source_formation_date_must_equal_formation_date": True,
        "current_member_backfill_forbidden": True,
        "missing_effective_date_membership_is_global_failure": True,
    }


def test_pairing_is_candidate_specific_not_f2_three_table_intersection() -> None:
    pairing = _config()["candidate_pairing"]

    assert pairing["statement_versions_selected_independently"] is True
    assert pairing["join_only_candidate_required_components"] is True
    assert pairing["all_three_statements_common_intersection_forbidden"] is True
    assert pairing["unused_statement_required"] is False
    assert pairing["external_financing_requires_predecessor_cashflow"] is False
    assert pairing[
        "external_financing_requires_current_cashflow_and_two_asset_periods"
    ] is True
    assert pairing["fallback_to_older_consecutive_pair_before_staleness_check"] is True
    assert pairing[
        "fallback_to_older_same_identity_value_for_nonmissing_forbidden"
    ] is True
    assert pairing["future_revision_backfill_forbidden"] is True


def test_panel_has_no_label_effect_or_model_contract() -> None:
    panel = _config()["panel_contract"]

    assert panel["key"] == [
        "formation_date",
        "effective_date",
        "universe_id",
        "candidate_id",
        "ts_code",
    ]
    assert panel["columns"] == [
        "formation_date",
        "effective_date",
        "universe_id",
        "candidate_id",
        "ts_code",
        "current_end_date",
        "predecessor_end_date",
        "candidate_available_date",
        "staleness_days",
        "value",
        "invalid_reason",
    ]
    assert {"label", "return", "rank_ic", "nav", "model", "prediction"} <= set(
        panel["forbidden_column_patterns"]
    )


def test_registry_is_independent_and_has_only_four_tables() -> None:
    registry = _config()["registry"]

    assert registry["tables"] == [
        "gate_cases",
        "gate_events",
        "idempotency_receipts",
        "outbox",
    ]
    assert registry["construction_test_path_policy"] == "temporary_directory_only"
    assert registry["journal_mode"] == "WAL"
    assert registry["synchronous"] == "FULL"
    assert registry["foreign_keys"] is True
    assert registry["begin_mode"] == "IMMEDIATE"
    assert registry["queue_lease_or_heartbeat_forbidden"] is True


def test_docker_boundary_is_offline_narrow_and_non_root() -> None:
    container = _config()["container"]

    assert container["network_mode"] == "none"
    assert container["run_as_non_root"] is True
    assert container["read_only_root"] is True
    assert container["cap_drop_all"] is True
    assert container["no_new_privileges"] is True
    assert container["project_root_mount_forbidden"] is True
    assert container["docker_socket_mount_forbidden"] is True
    assert container["env_file_mount_forbidden"] is True
    assert container["labels_effects_models_mount_forbidden"] is True
    assert container["services"]["runner"]["input_mount"] == "/inputs:ro"
    assert container["services"]["auditor"]["runner_output_mount"] == "/outputs:ro"


def test_release_scope_requires_pushed_implementation_and_exact_approval() -> None:
    release = _config()["release_scope"]

    assert release["implementation_commit_must_be_pushed_first"] is True
    assert release["image_identity_required"] is True
    assert release["input_manifest_metadata_only_before_approval"] is True
    assert release["input_manifest_may_include_values"] is False
    assert release["unrelated_ledger_append_does_not_change_scope"] is True
    assert release["new_relevant_allowed_api_revision_invalidates_scope"] is True
    assert release["auditor_identity_required"] is True
    assert release["user_approval_role"] == "M5_LOCAL_PROTOCOL_APPROVER"
    assert release["approval_must_bind_exact_release_scope_sha256"] is True
    assert release["any_scope_drift_invalidates_approval"] is True

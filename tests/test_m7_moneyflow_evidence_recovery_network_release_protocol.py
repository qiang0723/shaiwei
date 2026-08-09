from __future__ import annotations

import hashlib
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "config/m7_moneyflow_evidence_recovery_network_release_v1.yaml"
PROTOCOL_SHA256 = "3b487b9a58ae7a376cc640899277885897372cac643118290ab59057cf0cf9d3"


def _document() -> dict[str, object]:
    value = yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_network_release_protocol_identity_is_frozen() -> None:
    assert hashlib.sha256(PROTOCOL.read_bytes()).hexdigest() == PROTOCOL_SHA256


def test_network_release_protocol_preserves_old_record_and_corrects_core() -> None:
    document = _document()
    supersession = document["supersession"]
    assert supersession["preserved_protocol_modified"] is False
    assert (
        supersession["incorrect_preserved_core_sha256"]
        == "df5de399d915ac2cba8533b07a958b5ef06cf7c14a0654c60dc1213cb0d8eeca"
    )
    assert (
        supersession["authoritative_core_sha256"]
        == "df5de3990428e630eb2f56380601f3bee12fee2d2220a99c48c286e3701beeca"
    )
    assert supersession["recovery_semantics_changed"] is False


def test_network_release_protocol_binds_exact_projected_targets() -> None:
    predecessors = _document()["frozen_predecessors"]
    assert predecessors["track_a_target"]["member_rows"] == 908
    assert predecessors["track_a_target"]["unique_source_keys"] == 527
    assert predecessors["track_b_target"]["member_rows"] == 541
    assert predecessors["track_b_target"]["unique_source_keys"] == 541
    assert (
        predecessors["target_projection_execution_manifest"]["sha256"]
        == "7abf0889a9dd94364f68df08bb99d9e090e0f5b982000e604fbca50fc686ed5d"
    )


def test_request_plan_is_exact_deterministic_and_aggregate_only_in_git() -> None:
    plan = _document()["request_plan_contract"]
    assert plan["source_columns_allowed"] == ["source_date", "ts_code"]
    assert plan["exact_projected_keys_only"] is True
    assert plan["deduplicate_before_planning"] is True
    assert plan["extra_key_count_must_equal_zero"] is True
    assert plan["missing_key_count_must_equal_zero"] is True
    assert plan["bse_key_count_must_equal_zero"] is True
    assert plan["security_codes_may_exist_only_in_git_ignored_control_outputs"] is True
    assert plan["tracked_manifest_must_be_aggregate_only"] is True
    assert plan["track_a"]["expected_unique_keys"] == 527
    assert plan["track_a"]["each_required_key_covered_exactly_once"] is True
    assert plan["track_b"]["expected_unique_keys"] == 541
    assert plan["track_b"]["both_request_shapes_required_for_every_key"] is True


def test_collection_is_fail_closed_and_not_authorized() -> None:
    collection = _document()["collection_contract"]
    authority = _document()["construction_authority"]
    assert collection["current_collection_authorized"] is False
    assert collection["immutable_claim_before_provider_call"] is True
    assert collection["maximum_transport_attempts_per_claimed_request"] == 3
    assert collection["semantic_empty_response_retry_authorized"] is False
    assert collection["same_release_rerun_authorized"] is False
    assert authority["offline_real_target_key_read_authorized"] is True
    assert authority["exact_request_plan_generation_authorized"] is True
    assert authority["exact_release_scope_generation_authorized"] is True
    assert authority["external_network_authorized"] is False
    assert authority["live_provider_call_authorized"] is False
    assert authority["secret_read_authorized"] is False
    assert authority["production_authorization"] == "none"


def test_roles_are_isolated_and_exact_approval_is_a_hard_stop() -> None:
    roles = _document()["role_isolation"]
    stop = _document()["next_stop"]
    assert roles["project_worktree_mount_forbidden"] is True
    assert roles["production_data_raw_ledger_logs_mounts_forbidden"] is True
    assert roles["moneyflow_collector"]["secret_mounts"] == ["tushare_token_file"]
    assert roles["moneyflow_collector"]["dotenv_mount_forbidden"] is True
    assert roles["evaluator"]["network_mode"] == "none"
    assert roles["auditor"]["network_mode"] == "none"
    assert roles["collectors_share_no_writable_mounts"] is True
    assert stop["protocol_must_be_committed_and_pushed_before_request_plan_or_implementation"] is True
    assert stop["user_must_approve_exact_scope_before_network_secret_or_provider_use"] is True


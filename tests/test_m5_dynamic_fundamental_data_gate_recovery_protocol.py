from __future__ import annotations

import hashlib
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]
RECOVERY_PATH = ROOT / "config/m5_dynamic_fundamental_data_gate_recovery_v2.yaml"
RESEARCH_PATH = ROOT / "config/m5_dynamic_fundamental_cross_pool_v1.yaml"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _recovery() -> dict[str, object]:
    return yaml.safe_load(RECOVERY_PATH.read_text(encoding="utf-8"))


def _research() -> dict[str, object]:
    return yaml.safe_load(RESEARCH_PATH.read_text(encoding="utf-8"))


def test_recovery_binds_real_failure_without_rewriting_old_case() -> None:
    recovery = _recovery()["supersedes_execution_only"]

    assert recovery["prior_release_scope_sha256"] == (
        "49fdc6e79ee7591fb03732fc4fa08430f4049b720d0552cca49ff9e153e05830"
    )
    assert recovery["stopped_case_id"] == (
        "223414f4341a3edca15e5a626a3d0da642c4aa671db6d9cf67c9c870b8eb0a78"
    )
    assert recovery["stopped_event_seq"] == 10
    assert recovery["stopped_event_sha256"] == (
        "e0ca4594e03639212ba6ed5ebe75f651a0d3664da7cad86e232e3cefc0b9b3bd"
    )
    assert _sha256(ROOT / recovery["real_run_acceptance_path"]) == recovery[
        "real_run_acceptance_sha256"
    ]
    assert recovery["prior_case_mutation_authorized"] is False
    assert recovery["prior_release_rerun_authorized"] is False


def test_research_identity_and_attempt_counts_are_unchanged() -> None:
    frozen = _recovery()["frozen_research_identity"]
    research = _research()

    assert _sha256(RESEARCH_PATH) == frozen["research_config_sha256"]
    assert len(research["candidates"]) == frozen["candidate_count"] == 8
    assert len(research["universe_inputs"]) == frozen["universe_count"] == 3
    assert frozen["evaluation_unit_count"] == 24
    assert frozen["primary_attempt_n"] == 14
    assert frozen["sensitivity_attempt_n"] == 20
    assert frozen["effect_test_count"] == 0
    assert frozen["formula_direction_pit_threshold_or_universe_change_authorized"] is False
    assert frozen["candidate_replacement_authorized"] is False


def test_source_conflicts_are_classified_without_source_selection() -> None:
    contract = _recovery()["source_identity_contract"]

    assert contract["identity_fields"] == [
        "ts_code",
        "f_ann_date",
        "end_date",
        "report_type",
        "update_flag",
    ]
    assert contract["categories"] == [
        "EXACT_DUPLICATE_WITHIN_STANDARD",
        "EXACT_DUPLICATE_WITHIN_VIP",
        "CONSISTENT_OVERLAP_STANDARD_VIP",
        "CONFLICT_WITHIN_STANDARD",
        "CONFLICT_WITHIN_VIP",
        "CONFLICT_STANDARD_VIP",
    ]
    assert contract["value_normalization"]["numeric_equivalence"] == "EXACT_FINITE_NUMERIC"
    assert contract["value_normalization"]["tolerance_authorized"] is False
    assert contract["value_normalization"]["rounding_authorized"] is False
    assert contract["value_normalization"]["fill_or_imputation_authorized"] is False
    assert contract["exact_duplicate_policy"] == "DETERMINISTIC_LOSSLESS_COLLAPSE"
    assert contract["conflict_policy"] == "NO_SOURCE_SELECTION_GLOBAL_FAILURE"
    assert contract["source_priority_on_conflict_authorized"] is False


def test_public_conflict_report_is_aggregate_and_non_reversible() -> None:
    evidence = _recovery()["conflict_evidence_contract"]

    assert evidence["schema_version"] == "m5-source-conflict-report-v2"
    assert evidence["conflict_set_commitment_input"] == (
        "normalized_identity_plus_per_field_value_sha256"
    )
    assert evidence["commitment_output_only"] is True
    assert evidence["raw_or_row_level_export_authorized"] is False
    assert {
        "ts_code",
        "f_ann_date",
        "end_date",
        "report_type",
        "update_flag",
        "raw_value",
        "normalized_value",
        "candidate_value",
        "absolute_path",
    } == set(evidence["forbidden_payload_fields"])


def test_global_conflict_seals_auditable_no_go_not_runtime_failure() -> None:
    recovery = _recovery()
    projection = recovery["global_failure_projection"]
    outcomes = recovery["runner_outcomes"]

    assert projection["candidate_matrix_cell_count"] == 24
    assert projection["every_cell_status"] == "FAIL"
    assert projection["eligible_candidate_ids"] == []
    assert projection["rejected_candidate_ids"] == "ORDERED_ALL_EIGHT_PROTOCOL_CANDIDATES"
    assert projection["verdict"] == "NO_GO_M5_2_DATA_PREEXECUTION"
    assert projection["feature_panel_status"] == "NOT_CREATED_GLOBAL_FAILURE"
    assert projection["strategy_effective"] == "NOT_EVALUATED"
    assert projection["production_authorization"] == "none"
    assert outcomes["exit_codes"] == {
        "GO_SEALED": 0,
        "NO_GO_SEALED": 3,
        "UNSEALED_CONTROL_OR_RUNTIME_FAILURE": 2,
    }
    assert outcomes["global_failure_forbidden_files"] == ["feature_panel.parquet"]


def test_auditor_is_independent_and_required_before_registry_record() -> None:
    audit = _recovery()["independent_audit"]
    registry = _recovery()["registry_compatibility"]

    assert audit["imports_runner_conflict_classifier"] is False
    assert audit["imports_runner_candidate_compute"] is False
    assert audit["rereads_same_frozen_allowlist"] is True
    assert audit["audit_pass_required_before_data_gate_recorded"] is True
    assert audit["runner_exit_code_alone_is_authoritative"] is False
    assert registry["schema_version"] == 1
    assert registry["table_migration_authorized"] is False
    assert registry["new_protocol_scope_required"] is True
    assert registry["new_case_id_required"] is True
    assert registry["old_stopped_case_replay_required"] is True
    assert registry["global_failure_event_type"] == "DATA_GATE_RECORDED"
    assert registry["global_failure_lifecycle_state"] == "BLOCKED_DATA"


def test_protocol_only_authority_keeps_every_real_action_closed() -> None:
    authority = _recovery()["construction_authority"]

    assert authority["target_state"] == "RECOVERY_RELEASE_READY_NOT_APPROVED"
    assert authority["recovery_implementation_authorized"] is True
    assert authority["synthetic_fixture_authorized"] is True
    assert authority["formal_registry_initialization_authorized"] is False
    assert authority["formal_gate_event_write_authorized"] is False
    assert authority["real_financial_read_authorized"] is False
    assert authority["real_conflict_diagnosis_authorized"] is False
    assert authority["data_gate_execution_authorized"] is False
    assert authority["source_mutation_authorized"] is False
    assert authority["provider_call_count"] == 0
    assert authority["provider_budget_usd"] == "0.00"
    assert authority["external_network_authorized"] is False
    assert authority["credential_read_authorized"] is False
    assert authority["label_read_authorized"] is False
    assert authority["effect_read_authorized"] is False
    assert authority["model_training_authorized"] is False
    assert authority["backtest_authorized"] is False
    assert authority["engineering_gate_execution_authorized"] is False
    assert authority["web_change_authorized"] is False
    assert authority["scheduler_mutation_authorized"] is False
    assert authority["production_authorization"] == "none"

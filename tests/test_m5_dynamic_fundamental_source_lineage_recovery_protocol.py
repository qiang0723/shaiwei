from __future__ import annotations

import hashlib
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]
LINEAGE_PATH = ROOT / "config/m5_dynamic_fundamental_source_lineage_recovery_v3.yaml"
RESEARCH_PATH = ROOT / "config/m5_dynamic_fundamental_cross_pool_v1.yaml"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _lineage() -> dict[str, object]:
    return yaml.safe_load(LINEAGE_PATH.read_text(encoding="utf-8"))


def _research() -> dict[str, object]:
    return yaml.safe_load(RESEARCH_PATH.read_text(encoding="utf-8"))


def test_r2_binds_authoritative_r1_no_go_without_reopening_it() -> None:
    prior = _lineage()["prior_authoritative_data_no_go"]

    assert prior["release_scope_sha256"] == (
        "8858912f14577a8911e47f0ec338cde82208fe818b4c7a921578e42aeeed6f65"
    )
    assert _sha256(ROOT / prior["release_scope_path"]) == prior["release_scope_physical_sha256"]
    assert prior["case_id"] == ("a2539149d588a0c19f9cb73331f19a66df63e301df03f56fbb2c8e5c74672068")
    assert prior["terminal_event_seq"] == 6
    assert prior["terminal_event_sha256"] == (
        "7c2615a0f9d271b8b898bc8fa2a332edabfac92d48c58f31918c49bffa80917e"
    )
    assert prior["terminal_state"] == "BLOCKED_DATA"
    assert prior["verdict"] == "NO_GO_M5_2_DATA_PREEXECUTION"
    assert _sha256(ROOT / prior["acceptance_path"]) == prior["acceptance_sha256"]
    assert prior["conflict_group_count"] == 23
    assert prior["conflict_groups_by_table"] == {
        "income": 0,
        "balancesheet": 8,
        "cashflow": 15,
    }
    assert prior["prior_case_mutation_authorized"] is False
    assert prior["prior_release_rerun_authorized"] is False


def test_r2_does_not_change_research_semantics_or_attempt_counts() -> None:
    frozen = _lineage()["frozen_research_identity"]
    research = _research()

    assert _sha256(RESEARCH_PATH) == frozen["research_config_sha256"]
    assert len(research["candidates"]) == frozen["candidate_count"] == 8
    assert len(research["universe_inputs"]) == frozen["universe_count"] == 3
    assert frozen["evaluation_unit_count"] == 24
    assert frozen["primary_attempt_n"] == 14
    assert frozen["sensitivity_attempt_n"] == 20
    assert frozen["effect_test_count"] == 0
    assert frozen["strategy_effective"] == "NOT_EVALUATED"
    assert frozen["production_authorization"] == "none"
    assert frozen["formula_direction_pit_threshold_universe_or_history_change_authorized"] is False
    assert frozen["candidate_replacement_or_sample_deletion_authorized"] is False


def test_three_times_are_distinct_and_local_observation_cannot_backfill_history() -> None:
    contract = _lineage()["statement_version_contract"]
    times = contract["time_fields"]

    assert contract["statement_identity_fields"] == [
        "ts_code",
        "f_ann_date",
        "end_date",
        "report_type",
        "update_flag",
    ]
    assert times["statement_f_ann_date"]["availability_policy"] == ("NEXT_SSE_TRADING_DAY")
    assert times["statement_f_ann_date"]["orders_same_identity_variants"] is False
    assert times["provider_revision_effective_at"]["required_for_historical_lineage"] is True
    assert times["provider_revision_effective_at"]["may_be_derived_from_local_observed_at"] is False
    assert times["local_observed_at"]["proves_historical_provider_availability"] is False
    assert times["local_observed_at"]["may_bound_future_use_from_observation_forward"] is True
    assert contract["update_flag_orders_same_identity_variants"] is False
    assert contract["local_latest_batch_is_authoritative"] is False


def test_only_authoritative_version_evidence_can_resolve_historical_lineage() -> None:
    tiers = _lineage()["evidence_tiers"]

    assert tiers["E0_VALUE_VARIANT_ONLY"]["historical_resolution_authority"] is False
    assert tiers["E1_LOCAL_OBSERVATION"]["historical_resolution_authority"] is False
    assert tiers["E1_LOCAL_OBSERVATION"]["forward_lower_bound_only"] is True
    assert tiers["E2_PROVIDER_DECLARED_VERSION"]["historical_resolution_authority"] is True
    assert tiers["E3_AUTHORITATIVE_PRIMARY_DOCUMENT"]["historical_resolution_authority"] is True
    assert tiers["minimum_historical_resolution_tier"] == ("E2_PROVIDER_DECLARED_VERSION")


def test_lineage_dispositions_fail_closed_without_selection_shortcuts() -> None:
    dispositions = _lineage()["lineage_dispositions"]

    assert set(dispositions["historical_pass_dispositions"]) == {
        "LOSSLESS_EXACT_DUPLICATE",
        "PIT_VERSION_CHAIN_RESOLVED",
    }
    assert set(dispositions["historical_fail_dispositions"]) == {
        "FORWARD_ONLY_OBSERVED_VERSION",
        "UNRESOLVED_MISSING_EFFECTIVE_TIME",
        "UNRESOLVED_AMBIGUOUS_ORDER",
        "UNRESOLVED_INCOMPLETE_CHAIN",
    }
    assert dispositions["version_interval"] == "LEFT_CLOSED_RIGHT_OPEN"
    assert dispositions["unique_version_per_formation_date_required"] is True
    assert dispositions["complete_chain_required"] is True
    for key in (
        "latest_wins_authorized",
        "standard_or_vip_priority_authorized",
        "update_flag_priority_authorized",
        "non_null_priority_authorized",
        "majority_vote_authorized",
        "numeric_tolerance_authorized",
        "conflict_group_deletion_authorized",
        "effect_aware_selection_authorized",
    ):
        assert dispositions[key] is False


def test_lineage_feasibility_is_separate_from_network_collection_and_data_gate() -> None:
    separation = _lineage()["execution_separation"]

    assert separation["first_stage"] == "LINEAGE_FEASIBILITY"
    assert separation["first_stage_network_mode"] == "none"
    assert separation["first_stage_candidate_compute_authorized"] is False
    assert separation["first_stage_pit_compute_authorized"] is False
    assert separation["external_evidence_stage"] == ("AUTHORITATIVE_EVIDENCE_ACQUISITION")
    assert separation["external_evidence_requires_separate_protocol_and_release"] is True
    assert separation["external_collection_and_data_gate_same_release_authorized"] is False
    assert separation["current_value_historical_backfill_authorized"] is False


def test_future_reports_are_aggregate_and_do_not_compute_candidates() -> None:
    output = _lineage()["future_output_contract"]

    assert output["required_files"] == [
        "source_lineage_report.json",
        "lineage_gate_report.json",
        "run_manifest.json",
    ]
    assert output["feature_panel_forbidden"] is True
    assert output["candidate_matrix_forbidden"] is True
    assert output["write_once"] is True
    assert output["byte_determinism_required"] is True
    assert output["row_level_export_authorized"] is False
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
        "request_params",
    } == set(output["forbidden_public_fields"])


def test_auditor_and_registry_remain_independent_and_compatible() -> None:
    audit = _lineage()["independent_audit"]
    registry = _lineage()["registry_compatibility"]
    verdict = _lineage()["future_verdict_contract"]

    assert audit["may_import_primary_commitment_normalizer"] is False
    assert audit["may_import_primary_lineage_builder"] is False
    assert audit["rereads_same_frozen_allowlist"] is True
    assert audit["audit_pass_required_before_registry_record"] is True
    assert audit["runner_verdict_or_exit_code_alone_is_authoritative"] is False
    assert registry["schema_version"] == 1
    assert registry["table_migration_authorized"] is False
    assert registry["new_protocol_scope_required"] is True
    assert registry["new_case_id_required"] is True
    assert registry["prior_blocked_case_replay_required"] is True
    assert registry["prior_blocked_case_reopen_authorized"] is False
    assert verdict["pass_verdict"] == "GO_M5_2_SOURCE_LINEAGE_RECOVERABLE"
    assert verdict["fail_verdict"] == "NO_GO_M5_2_SOURCE_LINEAGE_PREEXECUTION"
    assert verdict["pass_authorizes_data_gate_execution"] is False


def test_protocol_only_authority_keeps_all_real_actions_closed() -> None:
    authority = _lineage()["construction_authority"]

    assert authority["target_state"] == "SOURCE_LINEAGE_RELEASE_READY_NOT_APPROVED"
    assert authority["lineage_implementation_authorized"] is True
    assert authority["synthetic_fixture_authorized"] is True
    assert authority["maximum_new_module_lines"] == 400
    assert authority["existing_hotspot_growth_authorized"] is False
    assert authority["provider_call_count"] == 0
    assert authority["provider_budget_usd"] == "0.00"
    assert authority["production_authorization"] == "none"
    for key, value in authority.items():
        if isinstance(value, bool) and key.endswith("_authorized"):
            assert value is (key in {"lineage_implementation_authorized", "synthetic_fixture_authorized"})

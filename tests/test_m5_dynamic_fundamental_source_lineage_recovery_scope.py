from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]
SCOPE_PATH = ROOT / "config/m5_dynamic_fundamental_source_lineage_recovery_protocol_scope_v3.json"
BUILD_PATH = ROOT / "config/m5_dynamic_fundamental_source_lineage_build_v3.yaml"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _scope() -> dict[str, object]:
    return json.loads(SCOPE_PATH.read_text(encoding="utf-8"))


def _build() -> dict[str, object]:
    return yaml.safe_load(BUILD_PATH.read_text(encoding="utf-8"))


def test_lineage_scope_is_canonical_and_binds_pushed_protocol_commit() -> None:
    envelope = _scope()
    scope = envelope["scope"]

    assert envelope["protocol_scope_sha256"] == _canonical_sha256(scope)
    assert envelope["protocol_scope_sha256"] == (
        "96c4f996f2641e6b18c26d8228ee72712b2670d70fe0cdedf95c99cd2e463ccd"
    )
    assert (
        scope["git_freeze"]["protocol_commit"] == (scope["git_freeze"]["local_origin_main_at_scope_creation"])
    )
    assert scope["git_freeze"]["protocol_commit_pushed_before_scope_creation"] is True
    for frozen in scope["frozen_files"]:
        path = Path(frozen["path"])
        assert not path.is_absolute() and ".." not in path.parts
        assert _sha256(ROOT / path) == frozen["sha256"]


def test_lineage_scope_derives_new_case_and_preserves_r1_blocked_case() -> None:
    envelope = _scope()
    scope = envelope["scope"]
    proposal_id = scope["source_proposal"]["proposal_id"]
    protocol_scope = envelope["protocol_scope_sha256"]
    derived = hashlib.sha256(f"m5-gate-case-v1\0{proposal_id}\0{protocol_scope}".encode("utf-8")).hexdigest()

    assert derived == "6b6c849f4ded89f631e1af8127f0e7321898aa7f4ce0c2630806fc8c8ef7be16"
    prior = scope["prior_authoritative_data_no_go"]
    assert derived != prior["case_id"]
    assert prior["terminal_state"] == "BLOCKED_DATA"
    assert prior["prior_case_mutation_authorized"] is False
    assert prior["prior_release_rerun_authorized"] is False
    assert scope["research_identity"]["research_semantics_changed"] is False


def test_scope_freezes_time_semantics_and_no_shortcut_resolution() -> None:
    contract = _scope()["scope"]["source_lineage_contract"]

    assert contract["time_semantics"] == [
        "statement_f_ann_date",
        "provider_revision_effective_at",
        "local_observed_at",
    ]
    assert contract["minimum_historical_resolution_tier"] == ("E2_PROVIDER_DECLARED_VERSION")
    assert contract["local_observation_can_backfill_history"] is False
    assert contract["update_flag_orders_same_identity_variants"] is False
    assert contract["latest_or_source_priority_authorized"] is False
    assert contract["conflict_group_deletion_authorized"] is False
    assert contract["lineage_feasibility_precedes_data_gate"] is True
    assert contract["network_collection_requires_separate_protocol"] is True


def test_scope_allows_only_synthetic_lineage_construction() -> None:
    scope = _scope()["scope"]
    permitted = scope["permitted_next_construction"]
    authority = scope["authority"]

    assert permitted == {
        "lineage_implementation_and_release_only": True,
        "synthetic_fixture_only": True,
        "real_financial_read": False,
        "real_conflict_diagnosis": False,
        "real_lineage_execution": False,
        "external_evidence_acquisition": False,
        "data_gate_execution": False,
        "effect_or_engineering_execution": False,
    }
    assert authority["lineage_release_scope_created"] is False
    assert authority["lineage_approval_recorded"] is False
    assert authority["lineage_execution_authorized"] is False
    assert authority["formal_registry_write_authorized"] is False
    assert authority["real_data_read_authorized"] is False
    assert authority["provider_call_count"] == 0
    assert authority["provider_budget_usd"] == "0.00"
    assert authority["production_authorization"] == "none"
    assert not any(
        value for key, value in authority.items() if isinstance(value, bool) and key.endswith("_authorized")
    )


def test_build_v3_binds_scope_case_and_frozen_inputs() -> None:
    build = _build()

    assert build["protocol_scope_sha256"] == _scope()["protocol_scope_sha256"]
    assert build["derived_case_id"] == ("6b6c849f4ded89f631e1af8127f0e7321898aa7f4ce0c2630806fc8c8ef7be16")
    for frozen in build["frozen_inputs"].values():
        assert _sha256(ROOT / frozen["path"]) == frozen["sha256"]


def test_build_separates_domain_adapter_orchestration_and_independent_audit() -> None:
    responsibilities = _build()["implementation_responsibilities"]

    assert responsibilities["value_commitment"]["layer"] == "domain"
    assert responsibilities["value_commitment"]["exposes_raw_values"] is False
    assert responsibilities["lineage_builder"]["computes_candidates"] is False
    assert responsibilities["lineage_builder"]["selects_unproven_versions"] is False
    assert responsibilities["evidence_adapter"]["external_network"] is False
    assert responsibilities["evidence_adapter"]["may_infer_provider_effective_time_from_ingest_time"] is False
    assert responsibilities["runner_orchestration"]["may_run_data_gate"] is False
    assert responsibilities["independent_lineage_audit"]["may_import_primary_lineage_builder"] is False


def test_build_freezes_aggregate_output_and_audited_no_go() -> None:
    build = _build()
    output = build["output_contract"]
    audit = build["auditor_contract"]
    registry = build["registry"]

    assert output["required_files"] == [
        "source_lineage_report.json",
        "lineage_gate_report.json",
        "run_manifest.json",
    ]
    assert output["forbidden_files"] == [
        "feature_panel.parquet",
        "candidate_matrix.json",
    ]
    assert output["row_level_identity_or_value_output_forbidden"] is True
    assert output["no_go_verdict"] == "NO_GO_M5_2_SOURCE_LINEAGE_PREEXECUTION"
    assert output["strategy_effective"] == "NOT_EVALUATED"
    assert audit["independent_value_commitment_required"] is True
    assert audit["independent_interval_rebuild_required"] is True
    assert audit["audit_pass_required_before_registrar"] is True
    assert registry["schema_version"] == 1
    assert registry["schema_migration_authorized"] is False
    assert registry["prior_case_expected_terminal_state"] == "BLOCKED_DATA"
    assert registry["prior_case_reopen_authorized"] is False
    assert registry["runner_verdict_without_audit_cannot_record"] is True


def test_build_keeps_real_execution_network_and_production_closed() -> None:
    construction = _build()["construction"]
    authority = _build()["authority"]

    assert construction["target_state"] == "SOURCE_LINEAGE_RELEASE_READY_NOT_APPROVED"
    assert construction["maximum_new_module_lines"] == 400
    assert construction["existing_source_conflict_semantics_change_authorized"] is False
    assert construction["real_financial_rows_may_be_read"] is False
    assert construction["real_conflict_rows_may_be_diagnosed"] is False
    assert construction["real_lineage_may_be_executed"] is False
    assert construction["synthetic_fixture_only"] is True
    assert authority["lineage_execution_authorized"] is False
    assert authority["real_data_read_authorized"] is False
    assert authority["external_network_authorized"] is False
    assert authority["credential_read_authorized"] is False
    assert authority["production_authorization"] == "none"

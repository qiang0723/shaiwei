from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]
SCOPE_PATH = ROOT / "config/m5_dynamic_fundamental_data_gate_recovery_protocol_scope_v2.json"
BUILD_PATH = ROOT / "config/m5_dynamic_fundamental_data_gate_build_v2.yaml"


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


def test_recovery_scope_is_canonical_and_binds_pushed_freeze() -> None:
    envelope = _scope()
    scope = envelope["scope"]

    assert envelope["protocol_scope_sha256"] == _canonical_sha256(scope)
    assert envelope["protocol_scope_sha256"] == (
        "6f99c0dfdc5cd75df9bf769fb65318feb4e8e7140082a9dfb924a88a3bb0dc49"
    )
    assert scope["git_freeze"]["protocol_commit"] == (
        scope["git_freeze"]["local_origin_main_at_scope_creation"]
    )
    assert scope["git_freeze"]["protocol_commit_pushed_before_scope_creation"] is True
    for frozen in scope["frozen_files"]:
        path = Path(frozen["path"])
        assert not path.is_absolute() and ".." not in path.parts
        assert _sha256(ROOT / path) == frozen["sha256"]


def test_new_scope_derives_a_new_case_without_mutating_prior_case() -> None:
    scope = _scope()["scope"]
    proposal_id = scope["source_proposal"]["proposal_id"]
    protocol_scope = _scope()["protocol_scope_sha256"]
    derived = hashlib.sha256(
        f"m5-gate-case-v1\0{proposal_id}\0{protocol_scope}".encode("utf-8")
    ).hexdigest()

    assert derived == "a2539149d588a0c19f9cb73331f19a66df63e301df03f56fbb2c8e5c74672068"
    assert derived != scope["prior_failure_identity"]["prior_case_id"]
    assert scope["prior_failure_identity"]["prior_case_mutation_authorized"] is False
    assert scope["prior_failure_identity"]["prior_release_rerun_authorized"] is False
    assert scope["research_identity"]["research_semantics_changed"] is False


def test_scope_allows_only_recovery_construction() -> None:
    scope = _scope()["scope"]
    permitted = scope["permitted_next_construction"]
    authority = scope["authority"]

    assert permitted == {
        "recovery_implementation_and_release_only": True,
        "synthetic_fixture_only": True,
        "real_conflict_diagnosis": False,
        "real_data_gate_execution": False,
        "synthetic_engineering_gate_execution": False,
    }
    assert authority["recovery_release_scope_created"] is False
    assert authority["data_gate_approval_recorded"] is False
    assert authority["data_gate_execution_authorized"] is False
    assert authority["formal_registry_write_authorized"] is False
    assert authority["real_data_read_authorized"] is False
    assert authority["real_conflict_diagnosis_authorized"] is False
    assert authority["provider_call_count"] == 0
    assert authority["production_authorization"] == "none"
    assert not any(
        value
        for key, value in authority.items()
        if isinstance(value, bool) and key.endswith("_authorized")
    )


def test_build_v2_binds_scope_and_all_frozen_inputs() -> None:
    build = _build()

    assert build["protocol_scope_sha256"] == _scope()["protocol_scope_sha256"]
    assert build["derived_case_id"] == (
        "a2539149d588a0c19f9cb73331f19a66df63e301df03f56fbb2c8e5c74672068"
    )
    for frozen in build["frozen_inputs"].values():
        assert _sha256(ROOT / frozen["path"]) == frozen["sha256"]


def test_build_separates_domain_projection_orchestration_and_audit() -> None:
    responsibilities = _build()["implementation_responsibilities"]

    assert responsibilities["source_conflict_classifier"]["layer"] == "domain"
    assert responsibilities["source_conflict_classifier"]["reads_files"] is False
    assert responsibilities["failure_projection"]["candidate_matrix_cell_count"] == 24
    assert responsibilities["runner_orchestration"]["may_select_conflicting_source"] is False
    assert responsibilities["runner_orchestration"]["seals_failure_before_exit"] is True
    assert responsibilities["independent_conflict_audit"]["may_import_runner_classifier"] is False
    assert responsibilities["independent_conflict_audit"]["may_import_runner_candidate_compute"] is False


def test_build_freezes_two_output_modes_and_audited_no_go() -> None:
    build = _build()
    output = build["output_contract"]
    registry = build["registry"]

    assert output["normal_mode"]["required_files"] == [
        "feature_panel.parquet",
        "data_gate_report.json",
        "run_manifest.json",
    ]
    assert output["global_failure_mode"]["required_files"] == [
        "source_conflict_report.json",
        "data_gate_report.json",
        "run_manifest.json",
    ]
    assert output["global_failure_mode"]["forbidden_files"] == ["feature_panel.parquet"]
    assert output["global_failure_mode"]["verdict"] == "NO_GO_M5_2_DATA_PREEXECUTION"
    assert registry["schema_version"] == 1
    assert registry["schema_migration_authorized"] is False
    assert registry["new_case_must_differ_from_prior"] is True
    assert registry["global_failure_event_type"] == "DATA_GATE_RECORDED"
    assert registry["global_failure_target_state"] == "BLOCKED_DATA"
    assert registry["runner_exit_three_without_audit_cannot_record"] is True


def test_build_authorizes_only_synthetic_recovery_implementation() -> None:
    construction = _build()["construction"]
    authority = _build()["authority"]

    assert construction["target_state"] == "RECOVERY_RELEASE_READY_NOT_APPROVED"
    assert construction["maximum_new_module_lines"] == 400
    assert construction["existing_hotspot_growth_authorized"] is False
    assert construction["existing_registry_schema_change_authorized"] is False
    assert construction["real_financial_rows_may_be_read"] is False
    assert construction["real_conflict_rows_may_be_diagnosed"] is False
    assert construction["formal_registry_may_be_initialized"] is False
    assert construction["formal_gate_events_may_be_written"] is False
    assert construction["synthetic_fixture_only"] is True
    assert authority["data_gate_execution_authorized"] is False
    assert authority["real_data_read_authorized"] is False
    assert authority["real_conflict_diagnosis_authorized"] is False
    assert authority["external_network_authorized"] is False
    assert authority["credential_read_authorized"] is False
    assert authority["production_authorization"] == "none"

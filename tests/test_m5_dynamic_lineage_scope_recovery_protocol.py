from __future__ import annotations

import hashlib
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]
RECOVERY_PATH = ROOT / "config/m5_dynamic_fundamental_source_lineage_scope_recovery_v4.yaml"


def _recovery() -> dict[str, object]:
    return yaml.safe_load(RECOVERY_PATH.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_scope_recovery_preserves_failed_release_and_protocol_semantics() -> None:
    recovery = _recovery()
    prior = recovery["superseded_release"]
    inherited = recovery["inherited_protocol"]

    assert prior["release_scope_sha256"] == (
        "b01058b55ff3dd6c06cf0722541214ecbb793de92a3115410c073daab26cf155"
    )
    assert prior["terminal_state"] == "STOPPED"
    assert prior["runner_exit_code"] == 2
    assert prior["output_file_count"] == prior["audit_file_count"] == 0
    assert prior["rerun_authorized"] is False
    assert prior["mutation_authorized"] is False
    assert _sha256(ROOT / prior["acceptance_path"]) == prior["acceptance_sha256"]
    assert _sha256(ROOT / inherited["path"]) == inherited["sha256"]
    assert all(value is False for key, value in inherited.items() if key.endswith("_changed"))


def test_scope_recovery_has_one_exact_annual_scope_and_adversarial_fixture() -> None:
    recovery = _recovery()
    scope = recovery["scope_alignment"]
    fixture = recovery["fixture_contract"]

    assert scope["eligible_end_date_suffix"] == "1231"
    assert scope["eligible_report_types"] == ["1", "5"]
    assert scope["quarterly_or_other_period_rows"] == "EXCLUDED_NOT_CONFLICT_GROUP_DELETION"
    assert scope["missing_identity_in_eligible_row"] == "FAIL_CLOSED"
    assert scope["source_priority_authorized"] is False
    assert scope["value_selection_authorized"] is False
    assert fixture["quarterly_conflicts_do_not_change_anchor_count"] is True
    assert fixture["noneligible_report_type_conflicts_do_not_change_anchor_count"] is True
    assert fixture["annual_report_type_5_conflicts_preserved"] is True
    assert fixture["exact_prior_anchor_count"] == 23
    assert fixture["exact_prior_counts_by_table"] == {
        "income": 0,
        "balancesheet": 8,
        "cashflow": 15,
    }


def test_scope_recovery_authorizes_construction_but_no_real_execution() -> None:
    recovery = _recovery()
    authority = recovery["construction_authority"]
    release = recovery["release_rules"]

    assert authority["target_state"] == "SOURCE_LINEAGE_RELEASE_READY_NOT_APPROVED"
    assert authority["implementation_authorized"] is True
    assert authority["synthetic_fixture_authorized"] is True
    assert authority["metadata_only_inventory_authorized"] is True
    assert authority["image_build_authorized"] is True
    assert authority["release_scope_creation_authorized"] is True
    assert authority["production_authorization"] == "none"
    for key, value in authority.items():
        if isinstance(value, bool) and key.endswith("_authorized"):
            assert value is (
                key
                in {
                    "implementation_authorized",
                    "synthetic_fixture_authorized",
                    "metadata_only_inventory_authorized",
                    "image_build_authorized",
                    "release_scope_creation_authorized",
                }
            )
    assert release["new_protocol_scope_required"] is True
    assert release["new_case_id_required"] is True
    assert release["prior_approval_migrates"] is False
    assert release["real_run_requires_new_exact_user_approval"] is True

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "config/m7_moneyflow_gap_lineage_v1.yaml"
PROTOCOL_SHA256 = "bf5ebac79cb1b81699e5a8f4d1fae13b78dedb35e7ed19672e0c69ea8254ad9e"


def _document() -> dict[str, object]:
    value = yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_gap_lineage_protocol_identity_is_frozen() -> None:
    assert hashlib.sha256(PROTOCOL.read_bytes()).hexdigest() == PROTOCOL_SHA256


def test_gap_lineage_keeps_predecessor_no_go_and_full_domain() -> None:
    document = _document()
    predecessor = document["predecessor"]
    scope = document["scope"]
    known = document["known_result_disclosure"]
    assert predecessor["authoritative_verdict"] == "NO_GO_M7_0_DATA_COMPATIBILITY"
    assert predecessor["scope_closed"] is True
    assert predecessor["retry_authorized"] is False
    assert known["predecessor_result_known"] is True
    assert known["lineage_category_results_inspected"] is False
    assert known["diagnosis_domain_selected_from_failed_cells_only"] is False
    assert scope["failed_cells_are_report_focus_not_input_filter"] is True
    assert len(scope["complete_half_year_segments"]) == 11


def test_gap_lineage_projects_only_keys_and_status_evidence() -> None:
    inputs = _document()["input_contract"]
    predecessor = inputs["predecessor_bundle"]
    additional = inputs["additional_sources"]
    assert predecessor["projected_moneyflow_columns"] == ["ts_code", "trade_date"]
    assert predecessor["numeric_moneyflow_value_columns_read"] == 0
    assert additional["tushare.daily"]["projected_columns"] == ["ts_code", "trade_date"]
    assert additional["tushare.daily"]["numeric_columns_read"] == 0
    assert additional["tushare.suspend_d"]["projected_columns"] == [
        "ts_code",
        "trade_date",
        "suspend_timing",
        "suspend_type",
    ]
    assert additional["baostock.history_k_data_plus"]["projected_columns"] == [
        "ts_code",
        "trade_date",
        "trade_status",
    ]
    assert inputs["external_network_authorized"] is False


def test_gap_lineage_categories_are_exhaustive_and_disjoint_by_contract() -> None:
    lineage = _document()["lineage_classification"]
    priority = lineage["priority"]
    explained = lineage["high_confidence_explained_categories"]
    conflict = lineage["conflict_categories"]
    unresolved = lineage["unresolved_categories"]
    assert len(priority) == 10
    assert "CONFLICTING_INDEPENDENT_TRADE_STATUS" in conflict
    assert set(explained + conflict + unresolved) == set(priority)
    assert not (set(explained) & set(conflict))
    assert not (set(explained) & set(unresolved))
    assert not (set(conflict) & set(unresolved))
    assert lineage["each_missing_row_exactly_one_category_required"] is True


def test_gap_lineage_does_not_recompute_adjusted_coverage() -> None:
    document = _document()
    known = document["known_result_disclosure"]
    output = document["output_contract"]
    decision = document["decision"]
    assert known["post_result_threshold_or_denominator_change_authorized"] is False
    assert output["adjusted_or_counterfactual_coverage_forbidden"] is True
    assert output["security_codes_forbidden"] is True
    assert decision["go_does_not_change_predecessor_no_go"] is True
    assert decision["go_does_not_authorize_denominator_change"] is True


def test_gap_lineage_execution_stays_behind_new_exact_approval() -> None:
    document = _document()
    authority = document["construction_authority"]
    execution = document["execution_contract"]
    stop = document["next_stop"]
    assert authority["metadata_only_inventory_authorized"] is True
    assert authority["synthetic_fixture_authorized"] is True
    assert authority["real_security_key_read_authorized"] is False
    assert authority["lineage_execution_authorized"] is False
    assert authority["numeric_moneyflow_value_read_authorized"] is False
    assert authority["candidate_generation_authorized"] is False
    assert authority["production_authorization"] == "none"
    assert execution["action"] == "M7_MONEYFLOW_GAP_LINEAGE_ONCE"
    assert execution["same_scope_retry_authorized"] is False
    assert execution["pre_read_consumption_roles"] == ["runner", "auditor"]
    assert stop["exact_user_approval_required"] is True
    assert stop["prior_approval_reuse_forbidden"] is True

from pathlib import Path

import yaml

from shaiwei.evaluation.g8 import comparator_codes


PROTOCOL_PATH = Path("config/g8_fund_evidence_source_v1.yaml")


def _protocol() -> dict[str, object]:
    return yaml.safe_load(PROTOCOL_PATH.read_text(encoding="utf-8"))


def test_g8_source_protocol_preserves_frozen_g8_and_product_identity() -> None:
    protocol = _protocol()
    scope = protocol["scope"]
    products = protocol["products"]

    assert protocol["protocol_id"] == "g8-fund-evidence-source-v1"
    assert protocol["status"] == "SOURCE_FEASIBILITY_AUDITED"
    assert scope["changes_g8_formula_or_thresholds"] is False
    assert scope["strategy_results_inspected"] is False
    assert scope["g8_verdict_status"] == "NOT_READY"
    assert tuple(product["code"] for product in products) == comparator_codes()
    assert len({product["fund_id"] for product in products}) == 6
    assert len({product["probe_upload_detail_id"] for product in products}) == 6


def test_g8_source_protocol_cannot_upgrade_http_capture_to_verified() -> None:
    protocol = _protocol()
    source = protocol["primary_source"]
    next_stage = protocol["next_stage_authorization"]

    assert source["origin"] == "http://eid.csrc.gov.cn"
    assert source["official_url_is_http"] is True
    assert source["https_probe_status"] == "FAIL_TLS"
    assert source["authenticated_transport"] is False
    assert source["source_can_be_verified_without_crosscheck"] is False
    assert next_stage["verdict"] == "GO_G8_1_PRIMARY_CAPTURE_ONLY"
    assert next_stage["manager_https_crosscheck_status"] == "NOT_IMPLEMENTED"
    assert next_stage["g8_evaluation_allowed"] is False
    assert next_stage["scheduler_integration_allowed"] is False


def test_g8_source_probe_contains_no_persisted_nav_or_early_verdict() -> None:
    protocol = _protocol()
    probe = protocol["source_probe"]
    next_stage = protocol["next_stage_authorization"]

    assert probe["usable_dates_per_product"] == 8
    assert probe["total_usable_rows"] == 48
    assert probe["duplicate_usable_code_dates"] == 0
    assert probe["immediate_double_fetch_equal"] is True
    assert probe["historical_revision_lineage"] == "NOT_PROVEN"
    assert probe["nav_values_persisted_by_probe"] is False
    assert next_stage["collector_engineering_complete"] is False
    assert next_stage["raw_capture_written"] is False
    assert next_stage["append_only_ledger_written"] is False
    assert next_stage["verified_total_return_series_status"] == "NOT_IMPLEMENTED"

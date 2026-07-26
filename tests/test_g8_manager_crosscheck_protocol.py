from pathlib import Path
from urllib.parse import urlparse

import yaml

from shaiwei.evaluation.g8 import comparator_codes
from shaiwei.ledger import sha256_file


PROTOCOL_PATH = Path("config/g8_fund_manager_crosscheck_v1.yaml")
PRIMARY_PATH = Path("config/g8_fund_primary_capture_recovery_v1.yaml")


def _protocol() -> dict:
    return yaml.safe_load(PROTOCOL_PATH.read_text(encoding="utf-8"))


def test_g8_manager_protocol_binds_primary_capture_and_stays_not_ready() -> None:
    protocol = _protocol()
    binding = protocol["primary_capture_binding"]
    scope = protocol["scope"]
    acceptance = protocol["acceptance"]

    assert protocol["status"] == "RESULT_BEFORE_EXECUTION_FROZEN"
    assert protocol["execution_authorized"] is True
    assert protocol["production_authorization"] == "none"
    assert binding["protocol_sha256"] == sha256_file(PRIMARY_PATH)
    assert binding["prior_verdict"] == "GO_G8_2_CROSSCHECK_AND_FEE_LINEAGE_ONLY"
    assert scope["official_manager_https_crosscheck"] is True
    assert scope["effective_dated_subscription_redemption_fee_lineage"] is True
    assert scope["strategy_results_access"] is False
    assert scope["g8_evaluation"] is False
    assert scope["total_return_construction"] is False
    assert scope["scheduler_integration"] is False
    assert acceptance["g8_status_after_execution"] == "NOT_READY"


def test_g8_manager_protocol_keeps_six_frozen_products_and_https_only() -> None:
    protocol = _protocol()
    products = protocol["products"]

    assert tuple(product["code"] for product in products) == comparator_codes()
    assert len({product["expected_name"] for product in products}) == 6
    for product in products:
        allowed = set(product["allowed_hosts"])
        for key in (
            "nav_request",
            "current_fee_request",
            "legal_document_discovery",
        ):
            parsed = urlparse(product[key]["url"])
            assert parsed.scheme == "https"
            assert parsed.hostname in allowed
        if "identity_request" in product:
            parsed = urlparse(product["identity_request"]["url"])
            assert parsed.scheme == "https"
            assert parsed.hostname in allowed


def test_g8_manager_protocol_has_fail_closed_nav_and_fee_lineage_contracts() -> None:
    protocol = _protocol()
    nav = protocol["nav_crosscheck"]
    fees = protocol["fee_lineage"]
    acceptance = protocol["acceptance"]

    assert len(nav["required_dates"]) == 8
    assert nav["decimal_comparison"] == "exact_numeric_value"
    assert nav["unknown_or_duplicate_row_action"] == "fail_closed"
    assert nav["missing_date_action"] == "fail_closed"
    assert fees["standard_schedule_only"] is True
    assert fees["channel_discount_assumption"] == "forbidden"
    assert fees["required_coverage"]["lineage_start"] == "fund_inception"
    assert fees["required_coverage"]["explicit_effective_date_required_for_change"] is True
    assert "source_document_sha256" in fees["extracted_row_fields"]
    assert "current_fee_backfill" in fees["forbidden"]
    assert acceptance["products_with_authenticated_https_identity"] == 6
    assert acceptance["products_with_exact_eight_date_nav_match"] == 6
    assert acceptance["products_with_complete_fee_lineage"] == 6
    assert acceptance["terminal_verdict_if_any_fail"] == "NO_GO_G8_2"

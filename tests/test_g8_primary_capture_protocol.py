import csv
from pathlib import Path

import yaml

from shaiwei.evaluation.g8 import comparator_codes
from shaiwei.ledger import sha256_file


PROTOCOL_PATH = Path("config/g8_fund_primary_capture_v1.yaml")
LEDGER_PATH = Path("ledger/g8_fund_evidence.csv")
SOURCE_PROTOCOL_PATH = Path("config/g8_fund_evidence_source_v1.yaml")
RESEARCH_COMPOSE_PATH = Path("compose.research.yaml")

EXPECTED_LEDGER_HEADER = (
    "evidence_id",
    "protocol_id",
    "request_id",
    "evidence_kind",
    "product_code",
    "period_start",
    "period_end",
    "parent_request_id",
    "captured_at",
    "first_http_status",
    "second_http_status",
    "first_body_sha256",
    "second_body_sha256",
    "bundle_path",
    "bundle_sha256",
    "parsed_row_count",
    "source_transport",
    "verification_status",
    "revision_of_evidence_id",
    "error_code",
    "operator",
)


def _protocol() -> dict:
    return yaml.safe_load(PROTOCOL_PATH.read_text(encoding="utf-8"))


def test_g8_primary_capture_binds_source_protocol_and_frozen_products() -> None:
    protocol = _protocol()
    binding = protocol["source_feasibility_binding"]

    assert protocol["status"] == "RESULT_BEFORE_EXECUTION_FROZEN"
    assert protocol["execution_authorized"] is True
    assert binding["protocol_sha256"] == sha256_file(SOURCE_PROTOCOL_PATH)
    assert tuple(product["code"] for product in protocol["products"]) == comparator_codes()


def test_g8_primary_capture_cannot_evaluate_g8_or_upgrade_http_source() -> None:
    protocol = _protocol()
    scope = protocol["scope"]
    source = protocol["source"]
    acceptance = protocol["acceptance"]

    assert source["scheme"] == "http"
    assert source["authenticated_transport"] is False
    assert source["trust_environment_proxy"] is False
    assert scope["strategy_results_access"] is False
    assert scope["g8_evaluation"] is False
    assert scope["total_return_construction"] is False
    assert scope["scheduler_integration"] is False
    assert acceptance["verification_status"] == "PRIMARY_CAPTURED_UNAUTHENTICATED"
    assert acceptance["g8_status_after_capture"] == "NOT_READY"


def test_g8_primary_capture_freezes_exact_request_and_acceptance_counts() -> None:
    protocol = _protocol()
    scope = protocol["scope"]
    nav = protocol["nav_request"]
    repeat = protocol["double_fetch"]
    acceptance = protocol["acceptance"]

    assert scope["capture_start"] == "2026-07-15"
    assert scope["capture_end"] == "2026-07-24"
    assert scope["expected_logical_requests"] == 54
    assert scope["expected_http_observations"] == 108
    assert repeat["observations_per_logical_request"] == 2
    assert repeat["compare"] == "exact_response_body_bytes"
    assert nav["expected_usable_rows_per_product"] == 8
    assert acceptance["ledger_rows"] == 54
    assert acceptance["usable_nav_rows"] == 48


def test_g8_primary_capture_ledger_preserves_sanitized_append_only_rows() -> None:
    with LEDGER_PATH.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        rows = list(reader)

    assert rows[0] == list(EXPECTED_LEDGER_HEADER)
    assert len(rows) >= 2
    evidence_id_index = EXPECTED_LEDGER_HEADER.index("evidence_id")
    protocol_id_index = EXPECTED_LEDGER_HEADER.index("protocol_id")
    bundle_path_index = EXPECTED_LEDGER_HEADER.index("bundle_path")
    for row in rows[1:]:
        assert len(row) == len(EXPECTED_LEDGER_HEADER)
        assert len(row[evidence_id_index]) == 64
        assert row[protocol_id_index].startswith("g8-fund-primary-capture-")
        assert row[bundle_path_index].startswith("data/g8/fund_evidence/bundles/")
        assert not Path(row[bundle_path_index]).is_absolute()


def test_g8_primary_capture_container_has_no_secret_or_broad_write_mount() -> None:
    compose = yaml.safe_load(RESEARCH_COMPOSE_PATH.read_text(encoding="utf-8"))
    service = compose["services"]["g8-primary-capture"]

    assert "env_file" not in service
    assert service["read_only"] is True
    assert service["cap_drop"] == ["ALL"]
    assert service["security_opt"] == ["no-new-privileges:true"]
    assert set(service["environment"]) == {"HOME", "MPLCONFIGDIR", "PYTHONPYCACHEPREFIX"}
    sources = {volume["source"]: volume["read_only"] for volume in service["volumes"]}
    assert sources == {
        "./data": True,
        "./data/g8/fund_evidence": False,
        "./ledger": True,
        "./ledger/g8_fund_evidence.csv": False,
    }
    assert all("docker.sock" not in volume["source"] for volume in service["volumes"])

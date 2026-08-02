import csv
import hashlib
import json

import pytest
import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.deepseek_client import TRANSPORT_LEDGER_HEADER_V2
from shaiwei.research.llm_factor import D1ControlError
from shaiwei.research.llm_review_semantics import FAIL, PASS
from shaiwei.research.m3_multi_pool_review_contract import (
    CANDIDATE_IDS,
    M3ReviewProtocol,
    canonical_json,
)
from shaiwei.research.m3_multi_pool_review_evidence import (
    REVIEW_LEDGER_HEADER,
    decide_reviews,
    expected_schedule,
)
from shaiwei.research.m3_multi_pool_review_preexecution import run_preexecution
from shaiwei.research.m3_multi_pool_review_release import M3ReviewRelease
from shaiwei.research.m3_multi_pool_review_request import (
    build_review_request,
    plan_review,
    preflight,
    validate_review_document,
)
from shaiwei.research.m3_multi_pool_review_schema import M3_REVIEW_ROLES


PROTOCOL_PATH = PROJECT_ROOT / "config/m3_multi_pool_factor_review_v1.yaml"
RELEASE_PATH = PROJECT_ROOT / "config/m3_multi_pool_factor_review_execution_v1.yaml"


def _response(candidate_id: str, role: str) -> dict[str, object]:
    return {
        "schema_version": "m3-adversarial-review-response-v1",
        "candidate_id": candidate_id,
        "role": role,
        "role_verdict": "NO_BLOCKER_FOUND",
        "summary": (
            "No blocking construct issue is identified for the exact frozen expression "
            "within this narrowly assigned review role."
        ),
        "findings": [
            {
                "severity": "minor",
                "category": "conditional_mechanism",
                "statement": (
                    "The exact frozen claim remains conditional on its stated market mechanism."
                ),
                "falsification_or_resolution": (
                    "Keep the frozen expression unchanged and test only under a later frozen protocol."
                ),
            }
        ],
        "formula_change_or_new_candidate_proposed": False,
        "performance_claim_made": False,
    }


def _decision_rows(blocked: tuple[str, ...] = ()) -> list[dict[str, str]]:
    rows = []
    for ordinal, candidate_id, role in expected_schedule():
        rows.append(
            {
                "review_ordinal": str(ordinal),
                "candidate_id": candidate_id,
                "role": role,
                "schema_status": "PASS",
                "semantic_status": PASS,
                "role_verdict": (
                    "BLOCKER_FOUND"
                    if candidate_id in blocked and role == "construct_and_units"
                    else "NO_BLOCKER_FOUND"
                ),
            }
        )
    return rows


def test_protocol_binds_exact_top2_without_interpreting_discovery_metrics():
    protocol = M3ReviewProtocol.load(PROTOCOL_PATH)
    assert [candidate.candidate_id for candidate in protocol.candidates] == list(CANDIDATE_IDS)
    assert [candidate.global_ordinal for candidate in protocol.candidates] == [3, 4]
    assert [candidate.expected_direction for candidate in protocol.candidates] == [
        "positive",
        "positive",
    ]
    assert [candidate.expression_tokens for candidate in protocol.candidates] == [7, 7]
    assert all(
        hashlib.sha256(candidate.formula.encode()).hexdigest() == candidate.expression_sha256
        for candidate in protocol.candidates
    )
    report = preflight(PROTOCOL_PATH)
    assert report["discovery_metric_fields_parsed"] is False
    assert report["provider_calls"] == 0
    assert report["review_count"] == 8
    assert report["worst_case_batch_cost_usd"] == pytest.approx(0.07656)


def test_review_schedule_and_payload_are_exact_and_result_blind():
    protocol = M3ReviewProtocol.load(PROTOCOL_PATH)
    plans = [plan_review(protocol, ordinal) for ordinal in range(1, 9)]
    assert [plan.role for plan in plans[:4]] == list(M3_REVIEW_ROLES)
    assert [plan.candidate.candidate_id for plan in plans] == [CANDIDATE_IDS[0]] * 4 + [
        CANDIDATE_IDS[1]
    ] * 4
    assert len({plan.review_id for plan in plans}) == 8
    for plan in plans:
        payload = canonical_json(build_review_request(protocol, plan)).lower()
        for forbidden in (
            "discovery_rank_ic",
            "discovery_coverage",
            "cross_pool_score",
            "minimum_coverage",
            "validation_result",
            "security_list",
            "market_rows",
            "/users/",
            ".bj",
        ):
            assert forbidden not in payload


def test_schema_and_free_text_semantic_gate_run_together():
    protocol = M3ReviewProtocol.load(PROTOCOL_PATH)
    plan = plan_review(protocol, 1)
    document = _response(plan.candidate.candidate_id, plan.role)
    response, semantic = validate_review_document(protocol, plan, document)
    assert response.role_verdict == "NO_BLOCKER_FOUND"
    assert semantic.status == PASS
    changed = json.loads(json.dumps(document))
    changed["findings"][0]["falsification_or_resolution"] = (
        "Replace the formula with a normalized alternative before validation."
    )
    _, changed_semantic = validate_review_document(protocol, plan, changed)
    assert changed_semantic.status == FAIL
    assert "FORMULA_CHANGE_ACTION" in changed_semantic.reason_codes


def test_decision_is_fail_closed_without_repair_or_replacement():
    decisions, gate = decide_reviews(_decision_rows((CANDIDATE_IDS[0],)))
    assert decisions == {
        CANDIDATE_IDS[0]: "REJECT_REVIEW_BLOCKER",
        CANDIDATE_IDS[1]: "PASS_REVIEW",
    }
    assert gate == "GO_FREEZE_M3_4_VALIDATION_PROTOCOL_ONLY"
    decisions, gate = decide_reviews(_decision_rows(CANDIDATE_IDS))
    assert set(decisions.values()) == {"REJECT_REVIEW_BLOCKER"}
    assert gate == "STOP_M3_FAMILY_BEFORE_VALIDATION"
    invalid = _decision_rows()
    invalid[2]["semantic_status"] = "MANUAL_REVIEW_REQUIRED"
    assert decide_reviews(invalid) == ({}, "STOP_M3_3_REVIEW_CONTRACT")
    wrong_order = _decision_rows()
    wrong_order[0], wrong_order[1] = wrong_order[1], wrong_order[0]
    assert decide_reviews(wrong_order) == ({}, "STOP_M3_3_REVIEW_CONTRACT")


def test_release_binds_code_and_refuses_live_authority():
    protocol = M3ReviewProtocol.load(PROTOCOL_PATH)
    release = M3ReviewRelease.load(RELEASE_PATH, protocol)
    assert release.request_bundle_sha256 == preflight(PROTOCOL_PATH)["request_bundle_sha256"]
    assert release.document["execution_authorized"] is False
    with pytest.raises(D1ControlError, match="separate immutable user-authorized live release"):
        release.assert_live_authorized()


def test_release_fails_closed_when_source_binding_changes(tmp_path):
    document = yaml.safe_load(RELEASE_PATH.read_text(encoding="utf-8"))
    document["frozen_contract"]["discovery_report_sha256"] = "0" * 64
    path = tmp_path / "tampered-release.yaml"
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    with pytest.raises(D1ControlError, match="does not bind"):
        M3ReviewRelease.load(path, M3ReviewProtocol.load(PROTOCOL_PATH))


def test_empty_review_ledgers_have_dedicated_exact_schemas():
    for path, header in (
        (PROJECT_ROOT / "ledger/m3_multi_pool_factor_reviews.csv", REVIEW_LEDGER_HEADER),
        (
            PROJECT_ROOT / "ledger/m3_multi_pool_factor_review_transports.csv",
            TRANSPORT_LEDGER_HEADER_V2,
        ),
    ):
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            assert tuple(reader.fieldnames or ()) == header
            assert list(reader) == []


def test_disconnected_preexecution_is_zero_api_and_not_strategy_evaluation():
    report = run_preexecution(PROTOCOL_PATH, RELEASE_PATH)
    assert report["preexecution_gate"] == "GO_M3_3_PREEXECUTION_ONLY"
    assert report["provider_calls"] == 0
    assert report["api_key_read"] is False
    assert report["execution_authorized"] is False
    assert report["review_results_inspected"] is False
    assert report["sealed_validation_read"] is False
    assert report["strategy_effective"] == "NOT_EVALUATED"
    assert report["production_authorization"] == "none"
    assert all(report["fixture_checks"].values())

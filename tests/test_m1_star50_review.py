import csv
import hashlib
import json

import pytest
import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.llm_review_semantics import FAIL, PASS
from shaiwei.research.m1_star50_review_contract import (
    CANDIDATE_IDS,
    ROLES,
    M1ReviewProtocol,
    build_review_request,
    canonical_json,
    plan_review,
    validate_review_document,
    worst_case_cost,
)
from shaiwei.research.m1_star50_review_evidence import decide_reviews
from shaiwei.research.m1_star50_review_live import REVIEW_LEDGER_HEADER


PROTOCOL_PATH = PROJECT_ROOT / "config/m1_star50_factor_review_v1.yaml"


def _response(candidate_id: str, role: str, summary: str) -> dict:
    return {
        "schema_version": "d1-adversarial-review-response-v1",
        "candidate_id": candidate_id,
        "role": role,
        "role_verdict": "NO_BLOCKER_FOUND",
        "summary": summary,
        "findings": [
            {
                "severity": "minor",
                "category": "conditional_mechanism",
                "statement": "The exact frozen claim remains conditional on the specified market state.",
                "falsification_or_resolution": "Keep the frozen expression unchanged and test only under a later frozen protocol.",
            }
        ],
        "formula_change_or_new_candidate_proposed": False,
        "performance_claim_made": False,
    }


def _decision_rows(*, first_blocked: bool = False, second_blocked: bool = False) -> list[dict[str, str]]:
    rows = []
    for ordinal in range(1, 9):
        candidate_id = CANDIDATE_IDS[(ordinal - 1) // 4]
        blocked = first_blocked if candidate_id == CANDIDATE_IDS[0] else second_blocked
        rows.append(
            {
                "candidate_id": candidate_id,
                "schema_status": "PASS",
                "semantic_status": PASS,
                "role_verdict": "BLOCKER_FOUND" if blocked and ordinal % 4 == 1 else "NO_BLOCKER_FOUND",
            }
        )
    return rows


def test_protocol_binds_exact_top2_and_result_blind_scope():
    protocol = M1ReviewProtocol.load(PROTOCOL_PATH)
    assert [candidate.candidate_id for candidate in protocol.candidates] == list(CANDIDATE_IDS)
    assert [candidate.expected_direction for candidate in protocol.candidates] == [
        "positive",
        "negative",
    ]
    assert all(
        hashlib.sha256(candidate.formula.encode()).hexdigest() == candidate.expression_sha256
        for candidate in protocol.candidates
    )
    blindness = protocol.document["blindness"]
    assert blindness["primary_window_may_adjudicate_review"] is False
    assert blindness["primary_window_contamination"]["candidate_ids"] == list(CANDIDATE_IDS)
    assert worst_case_cost(protocol) * 8 == pytest.approx(0.07656)


def test_review_schedule_and_requests_are_exact_and_result_blind():
    protocol = M1ReviewProtocol.load(PROTOCOL_PATH)
    plans = [plan_review(protocol, ordinal) for ordinal in range(1, 9)]
    assert [plan.role for plan in plans[:4]] == list(ROLES)
    assert [plan.candidate.candidate_id for plan in plans] == [CANDIDATE_IDS[0]] * 4 + [
        CANDIDATE_IDS[1]
    ] * 4
    assert len({plan.review_id for plan in plans}) == 8
    for plan in plans:
        request = build_review_request(protocol, plan)
        serialized = canonical_json(request).lower()
        for forbidden in (
            "discovery_rank_ic",
            "discovery_coverage",
            "validation_result",
            "stress_result",
            "g1_result",
            "forward_result",
        ):
            assert forbidden not in serialized


def test_schema_and_free_text_semantic_gate_run_together():
    protocol = M1ReviewProtocol.load(PROTOCOL_PATH)
    plan = plan_review(protocol, 1)
    document = _response(
        plan.candidate.candidate_id,
        plan.role,
        "No blocking construct issue is identified for the exact expression under review.",
    )
    review, semantic = validate_review_document(protocol, plan, document)
    assert review.role_verdict == "NO_BLOCKER_FOUND"
    assert semantic.status == PASS

    changed = json.loads(json.dumps(document))
    changed["findings"][0]["falsification_or_resolution"] = (
        "Replace the formula with a return-normalized alternative before validation."
    )
    _, changed_semantic = validate_review_document(protocol, plan, changed)
    assert changed_semantic.status == FAIL
    assert "FORMULA_CHANGE_ACTION" in changed_semantic.reason_codes


def test_negative_screen_decision_is_fail_closed_and_does_not_repair():
    decisions, gate = decide_reviews(_decision_rows(first_blocked=True))
    assert decisions == {
        CANDIDATE_IDS[0]: "REJECT_REVIEW_BLOCKER",
        CANDIDATE_IDS[1]: "PASS_REVIEW",
    }
    assert gate == "GO_FREEZE_M1_3_VALIDATION_PROTOCOL_ONLY"

    decisions, gate = decide_reviews(
        _decision_rows(first_blocked=True, second_blocked=True)
    )
    assert set(decisions.values()) == {"REJECT_REVIEW_BLOCKER"}
    assert gate == "STOP_M1_FAMILY_BEFORE_VALIDATION"

    invalid = _decision_rows()
    invalid[3]["semantic_status"] = "MANUAL_REVIEW_REQUIRED"
    assert decide_reviews(invalid) == ({}, "STOP_M1_2_REVIEW_CONTRACT")


def test_new_ledgers_have_exact_empty_headers():
    review_path = PROJECT_ROOT / "ledger/m1_star50_factor_reviews.csv"
    with review_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        assert tuple(next(reader)) == REVIEW_LEDGER_HEADER
        assert list(reader) == []
    transport = PROJECT_ROOT / "ledger/m1_star50_factor_review_transports.csv"
    assert transport.read_text(encoding="utf-8").count("\n") == 1


def test_review_compose_profiles_keep_secret_and_write_boundaries_narrow():
    compose = yaml.safe_load((PROJECT_ROOT / "compose.research.yaml").read_text())
    preflight = compose["services"]["m1-star50-review-preflight"]
    assert preflight["network_mode"] == "none"
    assert "DEEPSEEK_API_KEY" not in json.dumps(preflight)
    assert all(volume["read_only"] is True for volume in preflight["volumes"])

    live = compose["services"]["m1-star50-review-live"]
    assert live["image"] == "shaiwei:m1-star50-review-v1"
    assert live["read_only"] is True
    assert live["cap_drop"] == ["ALL"]
    assert live["environment"] == [
        "DEEPSEEK_API_KEY",
        "HOME=/tmp",
        "MPLCONFIGDIR=/tmp/matplotlib",
        "PYTHONPYCACHEPREFIX=/tmp/pycache",
    ]
    serialized = json.dumps(live, sort_keys=True)
    assert ".env" not in serialized
    assert "docker.sock" not in serialized
    writable = {
        volume["target"] for volume in live["volumes"] if volume["read_only"] is False
    }
    assert writable == {
        "/workspace/data/research/m1/m1-star50-price-volume-v1/m1_2_reviews",
        "/workspace/ledger/m1_star50_factor_reviews.csv",
        "/workspace/ledger/m1_star50_factor_review_transports.csv",
    }


def test_new_review_modules_respect_file_size_ratcheting():
    for name in (
        "m1_star50_review_contract.py",
        "m1_star50_review_evidence.py",
        "m1_star50_review_live.py",
        "m1_star50_review_release.py",
        "m1_star50_review_schema.py",
    ):
        path = PROJECT_ROOT / "src/shaiwei/research" / name
        assert len(path.read_text(encoding="utf-8").splitlines()) <= 400

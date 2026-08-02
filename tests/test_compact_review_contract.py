import json

import pytest
import yaml
from pydantic import ValidationError

from shaiwei.research.compact_review_contract import (
    DEFAULT_PROTOCOL_PATH,
    SCHEMA_VERSION,
    SYNTHETIC_CANDIDATE_ID,
    SYNTHETIC_FORMULA,
    CompactReviewProtocol,
    CompactReviewResponse,
    canonical_json,
    validate_response,
)
from shaiwei.research.compact_review_preexecution import maximum_payload, run_preexecution
from shaiwei.research.llm_factor import D1ControlError
from shaiwei.research.llm_review_semantics import AMBIGUOUS, FAIL, PASS


def _document() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "candidate_id": SYNTHETIC_CANDIDATE_ID,
        "role": "construct_and_units",
        "role_verdict": "NO_BLOCKER_FOUND",
        "summary": (
            "The exact frozen construct is dimensionless and coherent within this narrow role."
        ),
        "findings": [
            {
                "severity": "minor",
                "category": "scope_limitation",
                "statement": (
                    "The stated mechanism remains conditional on comparable adjusted price histories."
                ),
                "falsification_condition": (
                    "The frozen claim fails if adjusted histories are not comparable at signal time."
                ),
            }
        ],
        "disposition": "LATER_FROZEN_VALIDATION_ONLY",
        "formula_change_or_new_candidate_proposed": False,
        "performance_or_admission_claim_made": False,
    }


def _validate(document: dict):
    return validate_response(
        CompactReviewProtocol.load(),
        document,
        expected_candidate_id=SYNTHETIC_CANDIDATE_ID,
        expected_role="construct_and_units",
        allowed_formulas=(SYNTHETIC_FORMULA,),
    )


def test_protocol_is_engineering_only_and_disables_thinking():
    protocol = CompactReviewProtocol.load()
    authority = protocol.document["authority_boundary"]
    provider = protocol.document["provider_contract"]
    assert authority["provider_calls_authorized"] is False
    assert authority["api_key_read_authorized"] is False
    assert authority["real_candidate_read_authorized"] is False
    assert authority["prior_batches_reopened"] is False
    assert provider["thinking"] == "disabled"
    assert provider["reasoning_effort_field_present"] is False
    assert provider["maximum_output_tokens"] == 6000
    assert provider["maximum_response_json_bytes"] == 4096


def test_protocol_tampering_fails_closed(tmp_path):
    document = yaml.safe_load(DEFAULT_PROTOCOL_PATH.read_text(encoding="utf-8"))
    document["authority_boundary"]["provider_calls_authorized"] = True
    path = tmp_path / "tampered.yaml"
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    with pytest.raises(D1ControlError, match="controls differ"):
        CompactReviewProtocol.load(path)


def test_valid_response_passes_schema_and_existing_semantic_gate():
    response, semantic = _validate(_document())
    assert isinstance(response, CompactReviewResponse)
    assert semantic.status == PASS
    assert semantic.inspected_field_count == 4


def test_maximum_payload_is_valid_and_has_deterministic_headroom():
    payload = maximum_payload()
    CompactReviewResponse.model_validate(payload)
    size = len(canonical_json(payload).encode("ascii"))
    assert size <= 4096
    assert size < 6000


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        (lambda value: value.update(summary="x" * 321), "at most 320"),
        (lambda value: value.update(role="portfolio_manager"), "Input should be"),
        (lambda value: value.update(candidate_id="not-a-candidate"), "String should match"),
        (
            lambda value: value.update(disposition="REJECT_EXACT_EXPRESSION_AS_IS"),
            "disposition differs",
        ),
        (lambda value: value.update(role_verdict="BLOCKER_FOUND"), "verdict differs"),
    ],
)
def test_schema_identity_length_and_decision_mismatches_fail(mutation, match):
    document = _document()
    mutation(document)
    with pytest.raises((ValidationError, ValueError), match=match):
        CompactReviewResponse.model_validate(document)


def test_finding_count_duplicate_category_and_non_ascii_fail():
    too_many = _document()
    too_many["findings"] *= 4
    duplicate = _document()
    duplicate["findings"] *= 2
    non_ascii = _document()
    non_ascii["summary"] += " \u4e0d"
    for document in (too_many, duplicate, non_ascii):
        with pytest.raises((ValidationError, ValueError)):
            CompactReviewResponse.model_validate(document)


def test_response_byte_ceiling_and_formula_repetition_fail_closed():
    oversized = _document()
    oversized["irrelevant_padding"] = "x" * 5000
    with pytest.raises(D1ControlError, match="byte ceiling"):
        _validate(oversized)
    formula = _document()
    formula["findings"][0]["statement"] = (
        "The repeated Div(Mean($close,5d),Mean($close,20d)) text is not permitted."
    )
    with pytest.raises(D1ControlError, match="repeats DSL"):
        _validate(formula)


@pytest.mark.parametrize(
    ("statement", "expected"),
    [
        ("Replace the formula with another expression before later testing.", FAIL),
        ("The construct backtested with superior return and should be admitted.", FAIL),
        (
            "An alternative moving average could be a preferable option for later work.",
            AMBIGUOUS,
        ),
    ],
)
def test_existing_semantic_gate_still_rejects_change_performance_and_ambiguity(
    statement, expected
):
    document = _document()
    document["findings"][0]["statement"] = statement
    _, semantic = _validate(document)
    assert semantic.status == expected


def test_unknown_fields_and_free_form_resolution_are_forbidden():
    document = _document()
    document["findings"][0]["falsification_or_resolution"] = "Reject as-is."
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CompactReviewResponse.model_validate(document)


def test_preexecution_report_is_result_blind_zero_call_and_deterministic():
    first = run_preexecution()
    second = run_preexecution()
    assert first == second
    assert first["engineering_gate"] == "GO_COMPACT_REVIEW_CONTRACT_V2_ENGINEERING_ONLY"
    assert first["provider_calls"] == 0
    assert first["api_key_read"] is False
    assert first["real_candidate_or_result_read"] is False
    assert first["prior_batches_reopened"] is False
    assert first["maximum_payload_bytes"] <= 4096
    assert all(first["fixture_checks"].values())
    serialized = json.dumps(first, sort_keys=True).lower()
    assert "rank_ic" not in serialized
    assert "sealed_result" not in serialized

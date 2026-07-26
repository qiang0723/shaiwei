import json
from pathlib import Path

import pytest
import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.llm_factor import D1ControlError
from shaiwei.research.llm_review_semantics import (
    FAIL,
    PASS,
    SemanticGateProtocol,
    audit_prior_review_batch,
    evaluate_semantic_contract,
)


PROTOCOL_PATH = PROJECT_ROOT / "config/d1_llm_factor_semantic_gate_v1.yaml"
FIXTURE_PATH = PROJECT_ROOT / "tests/fixtures/d1_review_semantic_cases_v1.json"
FROZEN_FORMULAS = (
    "Std(Log(Div($high,$low)),20d)",
    "Std(Div(Sub($high,$low),$close),20d)",
)


def _response(summary: str, resolution: str) -> dict:
    return {
        "schema_version": "d1-adversarial-review-response-v1",
        "candidate_id": "6ade2d0f6d103613",
        "role": "construct_validity",
        "role_verdict": "BLOCKER_FOUND",
        "summary": summary,
        "findings": [
            {
                "severity": "major",
                "category": "semantic_contract_fixture",
                "statement": "The fixture isolates whether the narrative changes the exact frozen candidate.",
                "falsification_or_resolution": resolution,
            }
        ],
        "formula_change_or_new_candidate_proposed": False,
        "performance_claim_made": False,
    }


def test_semantic_protocol_freezes_authority_and_no_provider_calls():
    protocol = SemanticGateProtocol.load(PROTOCOL_PATH)
    authority = protocol.document["authority_boundary"]
    assert authority["prior_authoritative_gate"] == "STOP_SEMANTIC_CONTRACT_VIOLATION"
    assert authority["prior_batch_may_be_reopened"] is False
    assert authority["prior_response_replacement_allowed"] is False
    assert authority["provider_calls_authorized"] is False
    assert authority["W1_W6_visible"] is False
    assert protocol.document["verdicts"]["fail_or_ambiguous_stops_batch_before_human_gate"] is True


def test_semantic_protocol_tamper_fails_closed(tmp_path: Path):
    document = yaml.safe_load(PROTOCOL_PATH.read_text(encoding="utf-8"))
    document["authority_boundary"]["provider_calls_authorized"] = True
    tampered = tmp_path / "semantic.yaml"
    tampered.write_text(yaml.safe_dump(document), encoding="utf-8")
    with pytest.raises(D1ControlError, match="authority boundary"):
        SemanticGateProtocol.load(tampered)


def test_frozen_semantic_fixture_matrix():
    cases = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert len(cases) == 9
    for case in cases:
        first = evaluate_semantic_contract(
            _response(case["summary"], case["resolution"]),
            allowed_formulas=FROZEN_FORMULAS,
        )
        second = evaluate_semantic_contract(
            _response(case["summary"], case["resolution"]),
            allowed_formulas=FROZEN_FORMULAS,
        )
        assert first.status == case["expected_status"], case["case_id"]
        assert first == second


def test_semantic_gate_crosschecks_structured_fields():
    document = _response(
        "The exact frozen expression does not match its stated construct and must be rejected.",
        "Reject the exact candidate without modifying its formula or expected direction.",
    )
    document["formula_change_or_new_candidate_proposed"] = True
    result = evaluate_semantic_contract(document, allowed_formulas=FROZEN_FORMULAS)
    assert result.status == FAIL
    assert "STRUCTURED_NO_CHANGE_CONTRACT_FAILED" in result.reason_codes


def test_semantic_gate_accepts_exact_frozen_dsl_but_rejects_a_different_one():
    exact = _response(
        "The exact expression Std(Log(Div($high,$low)),20d) measures range instability.",
        "Reject the frozen candidate without modifying its formula.",
    )
    assert (
        evaluate_semantic_contract(exact, allowed_formulas=FROZEN_FORMULAS).status
        == PASS
    )

    different = _response(
        "The current expression does not match the supplied construct.",
        "The proposed expression is Mean(Log(Div($high,$low)),20d).",
    )
    result = evaluate_semantic_contract(different, allowed_formulas=FROZEN_FORMULAS)
    assert result.status == FAIL
    assert "DIFFERENT_DSL_EXPRESSION" in result.reason_codes


def test_semantic_gate_routes_unclear_change_language_to_manual_stop():
    document = _response(
        "The exact construct remains unclear under the supplied economic rationale.",
        "A rolling mean may be a better option, although no formal change is declared.",
    )
    result = evaluate_semantic_contract(document, allowed_formulas=FROZEN_FORMULAS)
    assert result.status == "MANUAL_REVIEW_REQUIRED"
    assert result.reason_codes == ("AMBIGUOUS_CHANGE_LANGUAGE",)

    unparseable = _response(
        "The exact construct remains unclear under the supplied economic rationale.",
        "The text contains Std(Log(Div($high,$low),20d without a complete expression.",
    )
    result = evaluate_semantic_contract(unparseable, allowed_formulas=FROZEN_FORMULAS)
    assert result.status == "MANUAL_REVIEW_REQUIRED"
    assert "UNPARSEABLE_DSL_TEXT" in result.reason_codes


@pytest.mark.parametrize(
    ("resolution", "reason"),
    [
        ("Use a different estimator for the candidate.", "ALTERNATIVE_CONSTRUCT_ACTION"),
        ("One should calculate a rolling mean instead.", "ALTERNATIVE_CONSTRUCT_ACTION"),
        (
            "The candidate should be admitted to production after this review.",
            "ADMISSION_CLAIM_ACTION",
        ),
        (
            "The factor achieved a positive backtested return in the observed sample.",
            "PERFORMANCE_CLAIM_ACTION",
        ),
    ],
)
def test_semantic_gate_rejects_additional_forbidden_claims(resolution: str, reason: str):
    document = _response(
        "The exact construct remains subject to the frozen review contract.",
        resolution,
    )
    result = evaluate_semantic_contract(document, allowed_formulas=FROZEN_FORMULAS)
    assert result.status == FAIL
    assert reason in result.reason_codes


def test_semantic_gate_does_not_return_narrative():
    marker = "sensitive-fixture-narrative-must-not-be-returned"
    result = evaluate_semantic_contract(
        _response(marker * 4, "Reject the frozen candidate without changing it."),
        allowed_formulas=FROZEN_FORMULAS,
    )
    serialized = json.dumps(result.as_dict(), sort_keys=True)
    assert marker not in serialized
    assert result.status == PASS


def test_prior_batch_offline_audit_matches_authoritative_correction():
    if not (PROJECT_ROOT / "data/research/d1/d1-llm-dsl-v1/d1_3_reviews").exists():
        pytest.skip("ignored prior D1 evidence is unavailable")
    first = audit_prior_review_batch()
    second = audit_prior_review_batch()
    assert first == second
    assert first["engineering_gate"] == "GO_SEMANTIC_GATE_ENGINEERING_ONLY"
    assert first["prior_authoritative_gate"] == "STOP_SEMANTIC_CONTRACT_VIOLATION"
    assert first["prior_authoritative_gate_unchanged"] is True
    assert first["provider_calls"] == 0
    assert first["performance_results_read"] is False
    assert first["counts"] == {
        "PASS_SEMANTIC_CONTRACT": 5,
        "FAIL_SEMANTIC_CONTRACT": 3,
        "MANUAL_REVIEW_REQUIRED": 0,
    }
    assert all("summary" not in row and "findings" not in row for row in first["reviews"])


def test_semantic_verify_compose_is_offline_read_only_and_secret_free():
    compose = yaml.safe_load(
        (PROJECT_ROOT / "compose.research.yaml").read_text(encoding="utf-8")
    )
    service = compose["services"]["d1-semantic-verify"]
    assert service["network_mode"] == "none"
    assert service["read_only"] is True
    assert service["cap_drop"] == ["ALL"]
    assert "no-new-privileges:true" in service["security_opt"]
    assert service["environment"] == {
        "HOME": "/tmp",
        "MPLCONFIGDIR": "/tmp/matplotlib",
        "PYTHONPYCACHEPREFIX": "/tmp/pycache",
        "PYTHONPATH": "/workspace/src",
    }
    serialized = json.dumps(service, sort_keys=True)
    assert "DEEPSEEK_API_KEY" not in serialized
    assert ".env" not in serialized
    assert "docker.sock" not in serialized
    assert all(volume["read_only"] is True for volume in service["volumes"])

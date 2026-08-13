from copy import deepcopy

import pytest

from shaiwei.research.trend_swing.v5_contract import V5Bundle
from shaiwei.research.trend_swing.v5_models import MechanismCandidate
from shaiwei.research.trend_swing.v5_prompt import (
    build_request,
    plan_attempt,
    preflight,
    validate_response,
)
from test_trend_swing_v5_candidate_contract import candidate_document


def test_preflight_builds_six_independent_requests_without_live_authority() -> None:
    report = preflight()

    assert report["family_status"] == "TS_FAMILY_ACTIVE"
    assert report["mechanism_count"] == 6
    assert report["planned_completed_responses_exact"] == 12
    assert report["independent_request_count_prepared"] == 6
    assert len(set(report["independent_request_hashes"])) == 6
    assert report["provider_calls"] == 0
    assert report["market_or_effect_rows_read"] == 0
    assert report["secret_read"] is False
    assert report["live_research_authorized"] is False
    assert report["preflight_gate"] == "PASS"


def test_independent_request_contains_no_security_raw_effect_or_path() -> None:
    bundle = V5Bundle.load()
    request = build_request(bundle, plan_attempt(bundle, 1))
    text = str(request)

    assert request["tools"] == []
    assert request["stream"] is False
    assert request["response_format"] == {"type": "json_object"}
    for forbidden in ("000001.SZ", "/Users/", "raw_market_rows", "sealed_validation", "api_key"):
        assert forbidden not in text


def test_revision_requires_same_mechanism_parent_and_allowlisted_feedback() -> None:
    bundle = V5Bundle.load()
    parent = MechanismCandidate.model_validate(candidate_document())
    revision = plan_attempt(bundle, 7)
    request = build_request(
        bundle,
        revision,
        parent=parent,
        parent_attempt_fingerprint=parent.fingerprint(),
        discovery_feedback={
            "parent_candidate_fingerprint": parent.fingerprint(),
            "discovery_event_count": 24,
            "rejection_reason_counts": {"NEXT_OPEN_ABOVE_REFERENCE": 8},
        },
    )
    assert parent.fingerprint() in str(request)

    with pytest.raises(ValueError, match="non-allowlisted"):
        build_request(
            bundle,
            revision,
            parent=parent,
            parent_attempt_fingerprint=parent.fingerprint(),
            discovery_feedback={"locked_test": "PASS"},
        )

    wrong_parent = MechanismCandidate.model_validate(candidate_document("BREAKOUT_RETEST"))
    with pytest.raises(ValueError, match="same-mechanism"):
        build_request(
            bundle,
            revision,
            parent=wrong_parent,
            parent_attempt_fingerprint=wrong_parent.fingerprint(),
        )

    failed_parent = build_request(
        bundle,
        revision,
        parent_attempt_fingerprint="a" * 64,
        parent_failure_class="CANDIDATE_SCHEMA_INVALID",
    )
    assert failed_parent["messages"][1]["content"].find("INVALID_RESPONSE_COUNTED") >= 0


def test_request_guard_rejects_security_secret_and_absolute_path_in_feedback() -> None:
    bundle = V5Bundle.load()
    parent = MechanismCandidate.model_validate(candidate_document())
    revision = plan_attempt(bundle, 7)
    secret_fixture = "sk" + "-1234567890"
    for value in ("000001.SZ", secret_fixture, "/Users/john/file"):
        with pytest.raises(ValueError):
            build_request(
                bundle,
                revision,
                parent=parent,
                parent_attempt_fingerprint=parent.fingerprint(),
                discovery_feedback={"discovery_effect_direction": value},
            )


def test_response_must_match_planned_identity_and_strict_schema() -> None:
    bundle = V5Bundle.load()
    plan = plan_attempt(bundle, 1)
    candidate = validate_response(plan, candidate_document())
    assert candidate.primary_mechanism == plan.mechanism

    mismatch = candidate_document("BREAKOUT_RETEST")
    with pytest.raises(ValueError, match="identity"):
        validate_response(plan, mismatch)

    extra = deepcopy(candidate_document())
    extra["best_parameter"] = "1.0"
    with pytest.raises(ValueError, match="strict schema"):
        validate_response(plan, extra)

    revision = plan_attempt(bundle, 7)
    revised = candidate_document()
    revised["lineage"] = {
        "mode": "ADVERSARIAL_REVISION",
        "parent_candidate_fingerprints": [candidate.fingerprint()],
    }
    assert validate_response(
        revision, revised, expected_parent_fingerprint=candidate.fingerprint()
    ).lineage.mode == "ADVERSARIAL_REVISION"

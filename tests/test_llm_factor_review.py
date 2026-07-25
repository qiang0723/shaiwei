import csv
import json
from pathlib import Path

import httpx
import pytest
import yaml
from pydantic import ValidationError

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.deepseek_client import DeepSeekProvider, TRANSPORT_LEDGER_HEADER_V2
from shaiwei.research.llm_factor import D1ControlError
from shaiwei.research.llm_factor_review import (
    AdversarialReviewResponse,
    D1ReviewProtocol,
    D1ReviewRelease,
    REVIEW_LEDGER_HEADER,
    ROLES,
    _canonical_json,
    _project_path,
    _worst_case_cost,
    build_review_request,
    plan_review,
)


PROTOCOL_PATH = PROJECT_ROOT / "config/d1_llm_factor_review_v1.yaml"
RELEASE_PATH = PROJECT_ROOT / "config/d1_llm_factor_review_execution_v1.yaml"


def _review_payload(*, candidate_id: str, role: str) -> dict:
    return {
        "schema_version": "d1-adversarial-review-response-v1",
        "candidate_id": candidate_id,
        "role": role,
        "role_verdict": "NO_BLOCKER_FOUND",
        "summary": "No blocking issue was identified for this narrowly assigned review role.",
        "findings": [
            {
                "severity": "minor",
                "category": "boundary_condition",
                "statement": "The interpretation remains conditional on the frozen next-open execution clock.",
                "falsification_or_resolution": "The human rationale must preserve this clock and state an explicit failure condition.",
            }
        ],
        "formula_change_or_new_candidate_proposed": False,
        "performance_claim_made": False,
    }


def test_review_protocol_binds_top2_and_blind_scope():
    protocol = D1ReviewProtocol.load(PROTOCOL_PATH)
    assert [item.candidate_id for item in protocol.candidates] == [
        "6ade2d0f6d103613",
        "3bf9d418202afc20",
    ]
    assert [item.expression_tokens for item in protocol.candidates] == [6, 8]
    assert all(item.expected_direction == "negative" for item in protocol.candidates)
    blindness = protocol.document["blindness"]
    assert blindness["discovery_rank_ic_visible"] is False
    assert blindness["W1_W6_visible"] is False
    assert blindness["g1_results_visible"] is False
    assert blindness["deepseek_payloads_are_result_blind"] is True
    assert blindness["primary_window_may_adjudicate_human_gate"] is False
    assert blindness["independent_result_blind_adjudicator_required"] is True
    contamination = blindness["primary_window_contamination"]
    assert contamination["candidate_id"] == "6ade2d0f6d103613"
    assert contamination["W1_W6_or_stress_or_g1_exposed"] is False


def test_review_release_binds_eight_responses_and_quarter_dollar_cap():
    protocol = D1ReviewProtocol.load(PROTOCOL_PATH)
    release = D1ReviewRelease.load(RELEASE_PATH, protocol)
    assert release.release_id == "d1-llm-review-v1-batch-001"
    assert release.batch_hard_ceiling_usd == 0.25
    assert _worst_case_cost(protocol) * 8 < release.batch_hard_ceiling_usd
    assert release.document["scope"]["new_candidate_generation"] is False


def test_review_schedule_is_exact_and_deterministic():
    protocol = D1ReviewProtocol.load(PROTOCOL_PATH)
    plans = [plan_review(protocol, ordinal) for ordinal in range(1, 9)]
    assert [plan.role for plan in plans[:4]] == list(ROLES)
    assert [plan.role for plan in plans[4:]] == list(ROLES)
    assert len({plan.review_id for plan in plans}) == 8
    assert [plan.candidate.candidate_id for plan in plans] == [
        "6ade2d0f6d103613"
    ] * 4 + ["3bf9d418202afc20"] * 4


def test_review_requests_are_result_blind_and_do_not_generate_candidates():
    protocol = D1ReviewProtocol.load(PROTOCOL_PATH)
    for ordinal in range(1, 9):
        request = build_review_request(protocol, plan_review(protocol, ordinal))
        serialized = _canonical_json(request).lower()
        assert "discovery_rank_ic" not in serialized
        assert "discovery_coverage" not in serialized
        assert '"g1_result"' not in serialized
        assert '"forward_result"' not in serialized
        task = json.loads(request["messages"][1]["content"])
        assert task["constraints"] == {
            "no_formula_or_direction_change": True,
            "no_new_candidate_or_variant": True,
            "no_performance_inference": True,
            "no_admission_or_production_decision": True,
        }


def test_review_response_contract_rejects_formula_change_and_verdict_mismatch():
    payload = _review_payload(
        candidate_id="6ade2d0f6d103613", role="construct_validity"
    )
    assert AdversarialReviewResponse.model_validate(payload).role_verdict == "NO_BLOCKER_FOUND"

    changed = dict(payload, formula_change_or_new_candidate_proposed=True)
    with pytest.raises(ValidationError):
        AdversarialReviewResponse.model_validate(changed)

    mismatched = dict(payload)
    mismatched["findings"] = [
        {
            "severity": "major",
            "category": "measurement_mismatch",
            "statement": "The frozen expression measures a different construct than the supplied claim.",
            "falsification_or_resolution": "The human gate must reject the claim without modifying the frozen formula.",
        }
    ]
    with pytest.raises(ValidationError, match="verdict differs"):
        AdversarialReviewResponse.model_validate(mismatched)


def test_review_release_tamper_fails_closed(tmp_path: Path):
    protocol = D1ReviewProtocol.load(PROTOCOL_PATH)
    document = yaml.safe_load(RELEASE_PATH.read_text(encoding="utf-8"))
    document["authorization"]["d1_3a_review_hard_ceiling_usd"] = 1.0
    tampered = tmp_path / "release.yaml"
    tampered.write_text(yaml.safe_dump(document), encoding="utf-8")
    with pytest.raises(D1ControlError, match="budget or response count"):
        D1ReviewRelease.load(tampered, protocol)


def test_review_paths_cannot_escape_project():
    with pytest.raises(D1ControlError, match="must be project-relative"):
        _project_path("/tmp/not-allowed", label="fixture")
    with pytest.raises(D1ControlError, match="escapes the project"):
        _project_path("../not-allowed", label="fixture")


def test_review_transport_reuses_restricted_deepseek_adapter(tmp_path: Path):
    protocol = D1ReviewProtocol.load(PROTOCOL_PATH)
    release = D1ReviewRelease.load(RELEASE_PATH, protocol)
    plan = plan_review(protocol, 1)
    request = build_review_request(protocol, plan)
    completion = {
        "id": "fixture-review",
        "object": "chat.completion",
        "created": 1785000000,
        "model": "deepseek-v4-pro",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": json.dumps(
                        _review_payload(candidate_id=plan.candidate.candidate_id, role=plan.role)
                    ),
                    "reasoning_content": "adversarial fixture reasoning",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 1000,
            "prompt_cache_hit_tokens": 0,
            "prompt_cache_miss_tokens": 1000,
            "completion_tokens": 200,
            "total_tokens": 1200,
        },
    }
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=completion))
    with DeepSeekProvider(
        protocol,  # type: ignore[arg-type]
        attempt_id=plan.review_id,
        api_key="fixture-never-logged",
        transport_ledger_path=tmp_path / "transport.csv",
        artifact_root=tmp_path / "provider",
        transport=transport,
        execution_release=release,  # type: ignore[arg-type]
        operator="test",
    ) as provider:
        response = provider.complete(request)
        assert provider.external_api_calls == 1
    parsed = AdversarialReviewResponse.model_validate_json(response.content)
    assert parsed.candidate_id == plan.candidate.candidate_id
    assert (tmp_path / "transport.csv").read_text(encoding="utf-8").count("\n") == 3


def test_review_ledgers_are_preexecution_empty_or_terminally_complete():
    with (PROJECT_ROOT / "ledger/llm_factor_reviews.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        review_reader = csv.DictReader(handle)
        assert tuple(review_reader.fieldnames or ()) == REVIEW_LEDGER_HEADER
        review_rows = list(review_reader)
    with (PROJECT_ROOT / "ledger/llm_factor_review_transports.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        transport_reader = csv.DictReader(handle)
        assert tuple(transport_reader.fieldnames or ()) == TRANSPORT_LEDGER_HEADER_V2
        transport_rows = list(transport_reader)

    assert len(review_rows) in {0, 8}
    assert len(transport_rows) in {0, 16}
    assert bool(review_rows) == bool(transport_rows)
    if review_rows:
        assert [int(row["global_ordinal"]) for row in review_rows] == list(range(1, 9))
        assert len({row["review_id"] for row in review_rows}) == 8
        assert all(row["schema_status"] == "PASS" for row in review_rows)
        assert [row["event_type"] for row in transport_rows[::2]] == ["STARTED"] * 8
        assert [row["event_type"] for row in transport_rows[1::2]] == ["COMPLETED"] * 8


def test_review_live_compose_has_narrow_secret_and_write_boundary():
    compose = yaml.safe_load(
        (PROJECT_ROOT / "compose.research.yaml").read_text(encoding="utf-8")
    )
    service = compose["services"]["d1-review-live"]
    assert service["image"] == "shaiwei:d1-review-live-v1"
    assert service["pull_policy"] == "never"
    assert service["read_only"] is True
    assert service["cap_drop"] == ["ALL"]
    assert "no-new-privileges:true" in service["security_opt"]
    assert "env_file" not in service
    assert "ports" not in service
    assert service.get("restart") is None
    assert service["environment"] == [
        "DEEPSEEK_API_KEY",
        "HOME=/tmp",
        "MPLCONFIGDIR=/tmp/matplotlib",
        "PYTHONPYCACHEPREFIX=/tmp/pycache",
    ]
    serialized = json.dumps(service, sort_keys=True)
    assert ".env" not in serialized
    assert "docker.sock" not in serialized
    assert "/workspace/src" not in serialized
    writable = {
        volume["target"]
        for volume in service["volumes"]
        if volume.get("read_only") is False
    }
    assert writable == {
        "/workspace/data/research/d1/d1-llm-dsl-v1/d1_3_reviews",
        "/workspace/ledger/llm_factor_reviews.csv",
        "/workspace/ledger/llm_factor_review_transports.csv",
    }

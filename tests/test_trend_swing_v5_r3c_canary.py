from decimal import Decimal
import json
from pathlib import Path

import pytest

from shaiwei.research.provider_contract import D1ControlError, ProviderResponse
from shaiwei.research.trend_swing.v5_models import Mechanism
from shaiwei.research.trend_swing.v5_projection_acceptance import minimal_proposal
from shaiwei.research.trend_swing.v5_r3c_audit import audit_report
from shaiwei.research.trend_swing.v5_r3c_canary import (
    MECHANISMS,
    SCOPE_SHA256,
    R3CCanaryScope,
    batch_gate,
    classify_proposal_response,
    preflight,
    request_bundle,
)


def response(mechanism: Mechanism, **overrides: object) -> ProviderResponse:
    values = {
        "model": "deepseek-v4-pro",
        "content": json.dumps(minimal_proposal(mechanism), ensure_ascii=False),
        "reasoning_content": "",
        "finish_reason": "stop",
        "usage": {
            "prompt_tokens": 1200,
            "prompt_cache_hit_tokens": 0,
            "prompt_cache_miss_tokens": 1200,
            "completion_tokens": 600,
        },
        "completed_at": "2026-08-13T00:00:00+00:00",
        "source_response_sha256": "a" * 64,
    }
    values.update(overrides)
    return ProviderResponse(**values)


def test_r3c_scope_is_frozen_and_not_live_authority() -> None:
    scope = R3CCanaryScope.load()

    assert scope.sha256 == SCOPE_SHA256
    assert scope.completed_responses == 6
    assert scope.hard_ceiling_usd == Decimal("0.15")
    assert scope.document["execution_authorized"] is False
    assert scope.document["attempt_contract"]["mechanism_order"] == [
        mechanism.value for mechanism in MECHANISMS
    ]


def test_r3c_preflight_builds_six_bound_requests_and_audits(tmp_path: Path) -> None:
    report = preflight()
    report_path = tmp_path / "preflight.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")

    assert report["gate"] == "GO_PREEXECUTION_ONLY"
    assert report["request_count"] == 6
    assert len(set(report["request_hashes"])) == 6
    assert max(report["request_bytes"]) <= 48_000
    assert report["planned_worst_case_usd"] == "0.051156"
    assert report["batch_hard_ceiling_usd"] == "0.15"
    assert all(report["checks"].values())
    assert report["provider_calls"] == 0
    assert report["secret_read"] is False
    assert audit_report(report_path)["verdict"] == "PASS"


def test_each_request_exposes_only_its_assigned_mechanism() -> None:
    for mechanism, request in zip(MECHANISMS, request_bundle(), strict=True):
        task = json.loads(request["messages"][1]["content"])
        projection = task["mechanism_projection"]
        schema_projection = task["proposal_schema"]["x-ts-mechanism-projection"]
        assert projection["primary_mechanism"] == mechanism.value
        assert projection == schema_projection
        assert "primary_mechanism" not in task["proposal_schema"]["properties"]
        assert task["instructions"]["do_not_emit_deterministic_fields"] is True


@pytest.mark.parametrize("mechanism", list(MECHANISMS))
def test_valid_proposal_compiles_for_all_six_mechanisms(mechanism: Mechanism) -> None:
    result = classify_proposal_response(mechanism, response(mechanism))

    assert result["parse_status"] == "PASS"
    assert result["schema_status"] == "PASS"
    assert result["duplicate_status"] == "UNIQUE"
    assert result["failure_class"] == ""
    assert result["candidate"].primary_mechanism == mechanism


@pytest.mark.parametrize(
    ("mutation", "failure"),
    [
        ({"finish_reason": "length", "content": "", "reasoning_content": "draft"},
         "PROVIDER_OUTPUT_TRUNCATED"),
        ({"finish_reason": "tool_calls"}, "PROVIDER_FINISH_REASON_INVALID"),
        ({"content": ""}, "PROVIDER_EMPTY_FINAL_CONTENT"),
        ({"content": "{"}, "PROPOSAL_JSON_INVALID"),
        ({"model": "unexpected-model"}, "PROVIDER_MODEL_IDENTITY_MISMATCH"),
        ({"sensitive_output_detected": True}, "PROVIDER_SENSITIVE_OUTPUT"),
        ({"usage": None}, "PROVIDER_USAGE_INVALID_WORST_CASE_RESERVED"),
    ],
)
def test_terminal_and_parse_failures_stop_before_compile(
    mutation: dict[str, object], failure: str
) -> None:
    mechanism = Mechanism.VOLATILITY_ADAPTIVE_PULLBACK
    result = classify_proposal_response(mechanism, response(mechanism, **mutation))
    assert result["failure_class"] == failure
    assert result["candidate"] is None


def test_cross_mechanism_and_duplicate_candidate_fail_closed() -> None:
    expected = Mechanism.WEEKLY_STRUCTURE_QUANTILE
    wrong = response(expected, content=json.dumps(
        minimal_proposal(Mechanism.VOLATILITY_ADAPTIVE_PULLBACK), ensure_ascii=False
    ))
    invalid = classify_proposal_response(expected, wrong)
    assert invalid["failure_class"] == "PROPOSAL_SCHEMA_OR_COMPILER_INVALID"

    valid = classify_proposal_response(expected, response(expected))
    duplicate = classify_proposal_response(
        expected,
        response(expected),
        prior_semantic_signatures={valid["candidate"].semantic_signature()},
    )
    assert duplicate["failure_class"] == "SEMANTIC_DUPLICATE"
    assert duplicate["duplicate_status"] == "DUPLICATE"


@pytest.mark.parametrize(
    ("completed", "valid", "expected"),
    [
        (5, 5, "STOP_INCOMPLETE_BATCH"),
        (6, 6, "GO_CONTRACT_PROJECTION_CANARY_ONLY"),
        (6, 5, "STOP_PARTIAL_CONTRACT_COMPLIANCE"),
        (6, 4, "STOP_PARTIAL_CONTRACT_COMPLIANCE"),
        (6, 3, "STOP_WEAK_CONTRACT_COMPLIANCE"),
        (6, 1, "STOP_WEAK_CONTRACT_COMPLIANCE"),
        (6, 0, "STOP_NO_VALID_CANDIDATES"),
    ],
)
def test_batch_gate_is_exhaustive(completed: int, valid: int, expected: str) -> None:
    assert batch_gate(completed, valid) == expected


def test_scope_path_escape_or_report_tamper_fails_closed(tmp_path: Path) -> None:
    scope_path = tmp_path / "scope.yaml"
    scope_path.write_text("execution_authorized: true\n", encoding="utf-8")
    with pytest.raises(D1ControlError, match="outside the project"):
        R3CCanaryScope.load(scope_path)

    report = preflight()
    report["provider_calls"] = 1
    report_path = tmp_path / "tampered.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(D1ControlError, match="audit failed"):
        audit_report(report_path)


def test_r3c_modules_stay_below_architecture_limit() -> None:
    root = Path(__file__).resolve().parents[1] / "src/shaiwei/research/trend_swing"
    assert len((root / "v5_r3c_canary.py").read_text().splitlines()) <= 300
    assert len((root / "v5_r3c_audit.py").read_text().splitlines()) <= 100

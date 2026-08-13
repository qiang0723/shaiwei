import json
from pathlib import Path
from types import SimpleNamespace

from shaiwei.research.provider_contract import ProviderResponse
from shaiwei.research.trend_swing.v5_contract import V5Bundle
from shaiwei.research.trend_swing.v5_evidence import classify_response
from shaiwei.research.trend_swing.v5_prompt import build_request, plan_attempt
from shaiwei.research.trend_swing.v5_response_contract import (
    CONTRACT_SHA256,
    V5ResponseContract,
    build_request_v2,
)
from shaiwei.research.trend_swing.v5_response_recovery import audit_legacy_responses


def response(
    *,
    finish_reason: str = "stop",
    content: str = "{}",
    reasoning: str = "",
    completion_tokens: int = 200,
) -> ProviderResponse:
    return ProviderResponse(
        model="deepseek-v4-pro",
        content=content,
        reasoning_content=reasoning,
        finish_reason=finish_reason,
        usage={
            "prompt_tokens": 1000,
            "prompt_cache_hit_tokens": 0,
            "prompt_cache_miss_tokens": 1000,
            "completion_tokens": completion_tokens,
        },
        completed_at="2026-08-13T00:00:00+00:00",
        source_response_sha256="a" * 64,
    )


def test_v2_changes_only_the_explicit_response_profile() -> None:
    bundle = V5Bundle.load()
    plan = plan_attempt(bundle, 1)
    legacy = build_request(bundle, plan)
    recovered = build_request_v2(bundle, plan)

    assert V5ResponseContract.load().sha256 == CONTRACT_SHA256
    assert recovered["thinking"] == {"type": "disabled"}
    assert "reasoning_effort" not in recovered
    assert legacy["thinking"] == {"type": "enabled"}
    assert legacy["reasoning_effort"] == "high"
    for key in set(legacy) - {"thinking", "reasoning_effort"}:
        assert recovered[key] == legacy[key]


def test_terminal_gate_never_admits_truncated_or_empty_content() -> None:
    contract = V5ResponseContract.load()

    assert contract.terminal_failure(response()) == ""
    assert (
        contract.terminal_failure(
            response(finish_reason="length", content="", reasoning="bounded", completion_tokens=1800)
        )
        == "OUTPUT_BUDGET_EXHAUSTED_IN_REASONING"
    )
    assert (
        contract.terminal_failure(response(finish_reason="length", content="{", completion_tokens=1800))
        == "PROVIDER_OUTPUT_TRUNCATED"
    )
    assert contract.terminal_failure(response(content="   ")) == "PROVIDER_EMPTY_FINAL_CONTENT"
    assert (
        contract.terminal_failure(response(finish_reason="content_filter"))
        == "PROVIDER_FINISH_REASON_INVALID"
    )


def test_candidate_classifier_uses_v2_terminal_failure_before_json() -> None:
    bundle = V5Bundle.load()
    plan = plan_attempt(bundle, 1)
    classified = classify_response(
        SimpleNamespace(),
        SimpleNamespace(response_model_identity="deepseek-v4-pro"),
        plan,
        response(
            finish_reason="length", content="", reasoning="bounded", completion_tokens=1800
        ),
        parent_fingerprint=None,
        prior_semantic_signatures=set(),
        response_contract=V5ResponseContract.load(),
    )

    assert classified["failure_class"] == "OUTPUT_BUDGET_EXHAUSTED_IN_REASONING"
    assert classified["parse_status"] == "NOT_EVALUATED"
    assert classified["candidate"] is None


def test_offline_audit_reproduces_the_frozen_twelve_response_root_cause(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    raw = project / "raw"
    raw.mkdir(parents=True)
    for ordinal in range(1, 13):
        item = response(
            finish_reason="length", content="", reasoning=f"bounded-{ordinal}", completion_tokens=1800
        )
        document = {
            "model": item.model,
            "content": item.content,
            "reasoning_content": item.reasoning_content,
            "finish_reason": item.finish_reason,
            "usage": item.usage,
            "completed_at": item.completed_at,
            "sensitive_output_detected": item.sensitive_output_detected,
            "source_response_sha256": item.source_response_sha256,
        }
        (raw / f"{ordinal:02d}.json").write_text(json.dumps(document), encoding="utf-8")

    report = audit_legacy_responses(raw, project_root=project)

    assert report["verdict"] == "PASS"
    assert report["failure_class_counts"] == {"OUTPUT_BUDGET_EXHAUSTED_IN_REASONING": 12}
    assert report["external_api_calls"] == 0
    assert report["candidate_content_admitted"] is False

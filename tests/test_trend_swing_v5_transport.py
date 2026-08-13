import csv
import json
from pathlib import Path

import httpx
import pytest

from shaiwei.research.deepseek_client import DeepSeekProvider
from shaiwei.research.llm_factor_contract import D1ControlError
from shaiwei.research.trend_swing.v5_prompt import build_request, plan_attempt, validate_response
from shaiwei.research.trend_swing.v5_transport import (
    V5TransportProtocol,
    create_live_provider,
)
from test_trend_swing_v5_candidate_contract import candidate_document


def completion(content: dict[str, object]) -> dict[str, object]:
    return {
        "id": "fixture-ts-v5-response",
        "object": "chat.completion",
        "created": 1786579200,
        "model": "DeepSeek-V4-Pro",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": json.dumps(content, ensure_ascii=False),
                    "reasoning_content": "synthetic TS-v5 transport fixture",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 1200,
            "prompt_cache_hit_tokens": 0,
            "prompt_cache_miss_tokens": 1200,
            "completion_tokens": 600,
            "total_tokens": 1800,
        },
    }


def provider(
    tmp_path: Path,
    protocol: V5TransportProtocol,
    transport: httpx.MockTransport,
    *,
    attempt_id: str,
) -> DeepSeekProvider:
    return DeepSeekProvider(
        protocol,  # type: ignore[arg-type]
        attempt_id=attempt_id,
        api_key="fixture-key-never-logged",
        transport_ledger_path=tmp_path / attempt_id / "transport.csv",
        artifact_root=tmp_path / attempt_id / "artifacts",
        transport=transport,
        clock=lambda: "2026-08-13T00:00:00+00:00",
        sleeper=lambda _: None,
        operator="fixture-ts-v5",
    )


def read_events(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_mock_transport_success_is_replayable_and_validates_candidate(tmp_path: Path) -> None:
    protocol = V5TransportProtocol.load()
    plan = plan_attempt(protocol.bundle, 1)
    request = build_request(protocol.bundle, plan)
    calls = 0

    def handler(http_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=completion(candidate_document()), request=http_request)

    path = tmp_path / plan.attempt_id / "transport.csv"
    with provider(
        tmp_path, protocol, httpx.MockTransport(handler), attempt_id=plan.attempt_id
    ) as adapter:
        first = adapter.complete(request)
        replay = adapter.complete(request)
    candidate = validate_response(plan, json.loads(first.content))

    assert candidate.primary_mechanism == plan.mechanism
    assert first == replay
    assert calls == 1
    assert [row["event_type"] for row in read_events(path)] == ["STARTED", "COMPLETED"]
    assert "fixture-key-never-logged" not in path.read_text(encoding="utf-8")


def test_mock_transport_retries_only_known_unbilled_status(tmp_path: Path) -> None:
    protocol = V5TransportProtocol.load()
    plan = plan_attempt(protocol.bundle, 2)
    request = build_request(protocol.bundle, plan)
    calls = 0

    def handler(http_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, json={"error": "fixture"}, request=http_request)
        return httpx.Response(
            200,
            json=completion(candidate_document("WEEKLY_STRUCTURE_QUANTILE")),
            request=http_request,
        )

    path = tmp_path / plan.attempt_id / "transport.csv"
    with provider(
        tmp_path, protocol, httpx.MockTransport(handler), attempt_id=plan.attempt_id
    ) as adapter:
        response = adapter.complete(request)

    assert response.finish_reason == "stop"
    assert calls == 2
    assert [row["event_type"] for row in read_events(path)] == [
        "STARTED",
        "RETRYABLE_ERROR",
        "STARTED",
        "COMPLETED",
    ]


def test_mock_transport_stops_on_uncertain_billing(tmp_path: Path) -> None:
    protocol = V5TransportProtocol.load()
    plan = plan_attempt(protocol.bundle, 3)
    request = build_request(protocol.bundle, plan)

    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("fixture uncertain")

    path = tmp_path / plan.attempt_id / "transport.csv"
    with provider(
        tmp_path, protocol, httpx.MockTransport(handler), attempt_id=plan.attempt_id
    ) as adapter:
        with pytest.raises(D1ControlError, match="billing is uncertain"):
            adapter.complete(request)

    assert [row["event_type"] for row in read_events(path)] == ["STARTED", "BILLING_UNCERTAIN"]


def test_live_factory_stops_before_secret_or_network_without_release(tmp_path: Path) -> None:
    protocol = V5TransportProtocol.load()
    with pytest.raises(D1ControlError, match="not authorized"):
        create_live_provider(
            protocol,
            release=None,
            attempt_id="fixture-no-release",
            transport_ledger_path=tmp_path / "transport.csv",
            artifact_root=tmp_path / "artifacts",
        )
    assert not any(tmp_path.iterdir())

import csv
import json
from types import SimpleNamespace
from pathlib import Path

import httpx
import pytest

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.deepseek_client import (
    TRANSPORT_LEDGER_HEADER,
    DeepSeekProvider,
    create_live_deepseek_provider,
)
from shaiwei.research.llm_factor import D1ControlError, D1Protocol, build_request, plan_attempt


PROTOCOL_PATH = PROJECT_ROOT / "config/d1_llm_factor_research_v1.yaml"
FIXED_TIME = "2026-07-25T14:30:00+00:00"


def _completion(protocol: D1Protocol, *, content: str = '{"schema_version":"d1-candidate-v1"}'):
    return {
        "id": "response-id-is-hashed",
        "object": "chat.completion",
        "created": 1784989800,
        "model": protocol.returned_model_identity,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content,
                    "reasoning_content": "bounded synthetic reasoning",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 800,
            "prompt_cache_hit_tokens": 200,
            "prompt_cache_miss_tokens": 600,
            "completion_tokens": 120,
            "total_tokens": 920,
        },
    }


def _provider(
    tmp_path: Path,
    handler,
    *,
    attempt_id: str = "attempt-1",
) -> tuple[D1Protocol, DeepSeekProvider, dict]:
    protocol = D1Protocol.load(PROTOCOL_PATH)
    provider = DeepSeekProvider(
        protocol,
        attempt_id=attempt_id,
        api_key="fixture-key-never-logged",
        transport_ledger_path=tmp_path / "ledger/llm_factor_transports.csv",
        artifact_root=tmp_path / "artifacts",
        transport=httpx.MockTransport(handler),
        clock=lambda: FIXED_TIME,
        sleeper=lambda _: None,
        operator="test",
    )
    request = build_request(protocol, plan_attempt(protocol, 1))
    return protocol, provider, request


def _events(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_success_is_persisted_before_completion_and_recovered_without_second_http(tmp_path: Path):
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.headers["authorization"] == "Bearer fixture-key-never-logged"
        payload = json.loads(request.content)
        assert payload["stream"] is False
        assert payload["tools"] == []
        return httpx.Response(200, json=_completion(protocol), request=request)

    protocol, provider, request = _provider(tmp_path, handler)
    first = provider.complete(request)
    second = provider.complete(request)
    provider.close()
    assert first == second
    assert calls == 1
    assert provider.external_api_calls == 1
    events = _events(tmp_path / "ledger/llm_factor_transports.csv")
    assert [event["event_type"] for event in events] == ["STARTED", "COMPLETED"]
    assert events[-1]["billing_status"] == "COMPLETED_USAGE_RECORDED"
    assert events[-1]["response_artifact_sha256"]
    assert events[-1]["response_id_sha256"]
    assert "response-id-is-hashed" not in (
        tmp_path / "ledger/llm_factor_transports.csv"
    ).read_text(encoding="utf-8")


def test_429_and_connect_error_are_bounded_retries_then_success(tmp_path: Path):
    for kind in ("http", "connect"):
        calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            if calls == 1 and kind == "http":
                return httpx.Response(429, json={"error": {"message": "do not persist"}}, request=request)
            if calls == 1:
                raise httpx.ConnectError("synthetic connect failure", request=request)
            return httpx.Response(200, json=_completion(protocol), request=request)

        protocol, provider, request = _provider(
            tmp_path / kind,
            handler,
            attempt_id=f"attempt-{kind}",
        )
        response = provider.complete(request)
        provider.close()
        assert response.model == protocol.returned_model_identity
        assert calls == 2
        event_types = [
            row["event_type"]
            for row in _events(tmp_path / kind / "ledger/llm_factor_transports.csv")
        ]
        assert event_types == ["STARTED", "RETRYABLE_ERROR", "STARTED", "COMPLETED"]


def test_read_timeout_is_billing_uncertain_and_never_retried_on_resume(tmp_path: Path):
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("synthetic read timeout", request=request)

    protocol, provider, request = _provider(tmp_path, handler)
    with pytest.raises(D1ControlError, match="billing is uncertain"):
        provider.complete(request)
    assert calls == 1
    provider.close()

    _, resumed, same_request = _provider(tmp_path, handler)
    with pytest.raises(D1ControlError, match="billing is uncertain"):
        resumed.complete(same_request)
    resumed.close()
    assert calls == 1
    assert [row["event_type"] for row in _events(tmp_path / "ledger/llm_factor_transports.csv")] == [
        "STARTED",
        "BILLING_UNCERTAIN",
    ]


def test_dangling_started_is_treated_as_unknown_billing_without_http(tmp_path: Path):
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=_completion(protocol), request=request)

    protocol, provider, request = _provider(tmp_path, handler)
    request_sha = __import__("hashlib").sha256(
        json.dumps(request, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    from shaiwei.research.deepseek_client import initialize_transport_ledger

    initialize_transport_ledger(tmp_path / "ledger/llm_factor_transports.csv")
    provider._append_event(
        request_sha256=request_sha,
        sequence=1,
        event_type="STARTED",
        billing_status="UNKNOWN_UNTIL_TERMINAL",
    )
    with pytest.raises(D1ControlError, match="dangling STARTED"):
        provider.complete(request)
    provider.close()
    assert calls == 0


def test_terminal_http_and_malformed_200_never_persist_provider_body(tmp_path: Path):
    secret_body = "sk-" + "Z" * 24

    def terminal(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text=secret_body, request=request)

    _, provider, request = _provider(tmp_path / "terminal", terminal, attempt_id="terminal")
    with pytest.raises(D1ControlError, match="HTTP status 401") as captured:
        provider.complete(request)
    provider.close()
    assert secret_body not in str(captured.value)
    assert secret_body not in (
        tmp_path / "terminal/ledger/llm_factor_transports.csv"
    ).read_text(encoding="utf-8")

    def malformed(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": secret_body}, request=request)

    _, malformed_provider, malformed_request = _provider(
        tmp_path / "malformed",
        malformed,
        attempt_id="malformed",
    )
    with pytest.raises(D1ControlError, match="schema is invalid"):
        malformed_provider.complete(malformed_request)
    malformed_provider.close()
    ledger_text = (
        tmp_path / "malformed/ledger/llm_factor_transports.csv"
    ).read_text(encoding="utf-8")
    assert secret_body not in ledger_text
    assert "BILLING_UNCERTAIN" in ledger_text


def test_sensitive_completed_response_is_redacted_and_recoverable(tmp_path: Path):
    secret = "sk-" + "A" * 24
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=_completion(protocol, content=secret), request=request)

    protocol, provider, request = _provider(tmp_path, handler, attempt_id="sensitive")
    first = provider.complete(request)
    assert first.sensitive_output_detected
    assert first.content == ""
    artifact_text = next((tmp_path / "artifacts/responses").glob("*.json")).read_text(
        encoding="utf-8"
    )
    assert secret not in artifact_text
    recovered = provider.complete(request)
    provider.close()
    assert recovered.sensitive_output_detected
    assert recovered.source_response_sha256 == first.source_response_sha256
    assert calls == 1


def test_live_factory_is_blocked_before_environment_or_network(monkeypatch, tmp_path: Path):
    protocol = D1Protocol.load(PROTOCOL_PATH)

    class ExplodingEnvironment:
        def get(self, *_: object, **__: object) -> str:
            raise AssertionError("environment must not be inspected")

    from shaiwei.research import deepseek_client

    monkeypatch.setattr(
        deepseek_client,
        "os",
        SimpleNamespace(environ=ExplodingEnvironment()),
    )
    with pytest.raises(D1ControlError, match="not authorized"):
        create_live_deepseek_provider(
            protocol,
            attempt_id="blocked",
            transport_ledger_path=tmp_path / "ledger.csv",
            artifact_root=tmp_path / "artifacts",
        )
    assert not (tmp_path / "ledger.csv").exists()


def test_non_mock_transport_is_rejected_while_execution_is_unauthorized(tmp_path: Path):
    protocol = D1Protocol.load(PROTOCOL_PATH)
    transport = httpx.HTTPTransport(retries=0)
    with pytest.raises(D1ControlError, match="only MockTransport"):
        DeepSeekProvider(
            protocol,
            attempt_id="blocked-transport",
            api_key="fixture",
            transport_ledger_path=tmp_path / "ledger.csv",
            artifact_root=tmp_path / "artifacts",
            transport=transport,
        )
    transport.close()
    assert not (tmp_path / "ledger.csv").exists()


def test_tracked_transport_ledger_is_header_only_and_exact():
    tracked = PROJECT_ROOT / "ledger/llm_factor_transports.csv"
    assert tuple(tracked.read_text(encoding="utf-8").strip().split(",")) == TRANSPORT_LEDGER_HEADER
    assert tracked.read_text(encoding="utf-8").count("\n") == 1

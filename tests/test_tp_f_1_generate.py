"""TP-F-1 生成段（G）：串行调用、三类停止条件、预算熔断、批内去重、模型不得替换、单次认领，以及经真实传输层（MockTransport）的接线（不联网）。"""

from contextlib import contextmanager
import csv
from decimal import Decimal
import json

import httpx
import pytest

from shaiwei.research.deepseek_client import TRANSPORT_LEDGER_HEADER_V2, DeepSeekProvider
from shaiwei.research.provider_contract import ProviderResponse
from shaiwei.research.tp_f_0b.contract import TPFScope
from shaiwei.research.tp_f_0b.signature import SignatureRule
from shaiwei.research.tp_f_1.candidate import IdentityIndex
from shaiwei.research.tp_f_1.contract import TPF1Error, TPF1Scope
from shaiwei.research.tp_f_1.generate import ATTEMPT_HEADER, run_generation
from shaiwei.research.tp_f_1.prompt import PromptBundle
from shaiwei.research.tp_f_1.transport import Prices, TPF1ExecutionRelease, TPF1TransportProtocol

RATIONALE = "中期趋势向上而短期回踩被吸收，收盘回到区间高位，延续概率更高。"
A = "Mul(Div($close,Mean($close,30d)),Div(Sub($close,$low),Sub($high,$low)))"
A_COMMUTED = "Mul(Div(Sub($close,$low),Sub($high,$low)),Div($close,Mean($close,30d)))"
B = "Sub(Div($close,Mean($close,40d)),Div($close,Mean($close,5d)))"
C = "Mul(Div($close,Ref($close,20d)),Div(Mean($volume,5d),Mean($volume,20d)))"
TREND_ONLY = "Div($close,Mean($close,20d))"
PRICES = Prices(Decimal("0.003625"), Decimal("0.435"), Decimal("0.87"))
USAGE = {"prompt_cache_hit_tokens": 100, "prompt_cache_miss_tokens": 1000, "completion_tokens": 2000, "prompt_tokens": 1100}
SCOPE_SHA = "c" * 64


@pytest.fixture(scope="module")
def parts():
    scope = TPF1Scope.load()
    rule = SignatureRule.from_protocol(TPFScope.load().document["identity_registry"]["joint_state_signature"])
    index = IdentityIndex(frozenset(), frozenset(), frozenset(), {"synthetic": 0})
    return scope, PromptBundle.load(scope), index, rule


def _ledger(tmp_path):
    path = tmp_path / "attempts.csv"
    path.write_text(",".join(ATTEMPT_HEADER) + "\n", encoding="utf-8")
    return path


def _content(expression: str | None) -> str:
    return "not json" if expression is None else json.dumps({"expression": expression, "economic_rationale": RATIONALE})


def _fake(contents: list[str], *, model: str = "deepseek-v4-pro"):
    calls = []

    class Fake:
        def complete(self, request):
            calls.append(request)
            return ProviderResponse(model, contents[len(calls) - 1], "", "stop", USAGE, "2026-11-19T10:00:00+00:00",
                                    False, f"{len(calls):064x}")

    @contextmanager
    def provider_for(_attempt_id):
        yield Fake()

    return provider_for, calls


def test_stops_at_three_qualified_and_dedups_within_the_batch(tmp_path, parts):
    scope, prompt, index, rule = parts
    provider_for, calls = _fake([_content(None), _content(TREND_ONLY), _content(A), _content(A_COMMUTED), _content(B), _content(C)])
    ledger = _ledger(tmp_path)
    summary = run_generation(scope, prompt, index, rule, scope_sha256=SCOPE_SHA, provider_for=provider_for, prices=PRICES,
                             output_dir=tmp_path / "out", attempt_ledger=ledger)
    assert summary["completed_responses"] == 6 and summary["stop_reason"] == "QUALIFIED_CANDIDATE_MAXIMUM"
    assert summary["status_counts"] == {"DUPLICATE_WITHIN_BATCH": 1, "NOT_JOINT_STATE": 1, "QUALIFIED": 3, "RESPONSE_SCHEMA": 1}
    rows = list(csv.DictReader(ledger.open(encoding="utf-8")))
    assert [row["ordinal"] for row in rows] == [str(i) for i in range(1, 7)]
    assert Decimal(summary["spent_usd"]) == sum(Decimal(row["estimated_cost_usd"]) for row in rows)
    proposed = json.loads(calls[-1]["messages"][1]["content"])["already_proposed_in_this_batch"]
    assert len(proposed) == 4  # 只回传已提出的规范表达式，不回传任何结果
    packet = json.loads((tmp_path / "out/blind_review_packet.json").read_text())
    assert [item["candidate_id"] for item in packet["candidates"]] == summary["qualified_candidates"]
    assert "rank" not in json.dumps(packet).lower() and packet["contains_market_numbers"] is False
    with pytest.raises(TPF1Error, match="same-scope rerun"):
        run_generation(scope, prompt, index, rule, scope_sha256=SCOPE_SHA, provider_for=provider_for, prices=PRICES,
                       output_dir=tmp_path / "out", attempt_ledger=ledger)


def test_exhausts_eight_responses_and_closes_without_candidates(tmp_path, parts):
    scope, prompt, index, rule = parts
    provider_for, calls = _fake([_content(TREND_ONLY)] * 8)
    summary = run_generation(scope, prompt, index, rule, scope_sha256=SCOPE_SHA, provider_for=provider_for, prices=PRICES,
                             output_dir=tmp_path / "out", attempt_ledger=_ledger(tmp_path))
    assert len(calls) == 8 and summary["stop_reason"] == "COMPLETED_RESPONSE_MAXIMUM"
    assert summary["verdict_if_no_candidate"] == "REJECT_TP_F_AND_CLOSE" and not (tmp_path / "out/blind_review_packet.json").exists()


def test_budget_breaker_and_model_substitution_fail_closed(tmp_path, parts):
    scope, prompt, index, rule = parts
    provider_for, calls = _fake([_content(A)])
    expensive = Prices(Decimal("1"), Decimal("100"), Decimal("100"))
    summary = run_generation(scope, prompt, index, rule, scope_sha256=SCOPE_SHA, provider_for=provider_for, prices=expensive,
                             output_dir=tmp_path / "budget", attempt_ledger=_ledger(tmp_path))
    assert calls == [] and summary["stop_reason"] == "BUDGET_CEILING" and summary["completed_responses"] == 0
    other, _ = _fake([_content(A)], model="deepseek-chat")
    with pytest.raises(TPF1Error, match="no substitution"):
        run_generation(scope, prompt, index, rule, scope_sha256=SCOPE_SHA, provider_for=other, prices=PRICES,
                       output_dir=tmp_path / "model", attempt_ledger=_ledger(tmp_path))


def test_generation_through_the_audited_transport_with_a_mock_route(tmp_path, parts):
    scope, prompt, index, rule = parts
    protocol = TPF1TransportProtocol.load(scope, prompt)
    release = TPF1ExecutionRelease(release_id="tp-f-1-synthetic", sha256=SCOPE_SHA, protocol_sha256=protocol.sha256)
    transports = tmp_path / "transports.csv"
    transports.write_text(",".join(TRANSPORT_LEDGER_HEADER_V2) + "\n", encoding="utf-8")
    answers = iter([A, B, C])

    def handler(request: httpx.Request) -> httpx.Response:
        body = {"id": "synthetic", "object": "chat.completion", "created": 1795000000, "model": "deepseek-v4-pro",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": _content(next(answers)), "reasoning_content": ""},
                             "finish_reason": "stop"}], "usage": USAGE}
        return httpx.Response(200, json=body, request=request)

    @contextmanager
    def provider_for(attempt_id):
        provider = DeepSeekProvider(protocol, attempt_id=attempt_id, api_key="synthetic-key", transport_ledger_path=transports,  # type: ignore[arg-type]
                                    artifact_root=tmp_path / "responses", transport=httpx.MockTransport(handler),
                                    execution_release=release, sleeper=lambda _: None)  # type: ignore[arg-type]
        try:
            yield provider
        finally:
            provider.close()

    summary = run_generation(scope, prompt, index, rule, scope_sha256=SCOPE_SHA, provider_for=provider_for, prices=PRICES,
                             output_dir=tmp_path / "out", attempt_ledger=_ledger(tmp_path))
    assert summary["completed_responses"] == 3 and len(summary["qualified_candidates"]) == 3
    events = list(csv.DictReader(transports.open(encoding="utf-8")))
    assert {event["event_type"] for event in events} == {"STARTED", "COMPLETED"} and len(events) == 6
    assert all(event["execution_release_sha256"] == SCOPE_SHA and event["model"] == "deepseek-v4-pro" for event in events)


def test_in_image_fixture_passes_under_a_released_runtime(monkeypatch):
    """已发布运行时拒绝非正式账本路径的锁：镜像内 fixture 必须不走真实账本写入口也能全绿。"""
    from shaiwei.research.tp_f_1.fixture import fixture

    monkeypatch.setenv("SHAIWEI_RELEASE_MANIFEST", "/opt/shaiwei/release-manifest.json")
    monkeypatch.delenv("SHAIWEI_LOCK_AUTHORITY", raising=False)
    result = fixture()
    assert result["fixture_pass"] is True and result["generation_responses"] == 4 and result["network"] is False

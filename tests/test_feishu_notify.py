import json
from pathlib import Path
from urllib.error import HTTPError, URLError

from pydantic import SecretStr

from shaiwei.config import Notifications
from shaiwei.notify.feishu import FeishuNotifier, generate_sign


class Response:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return b'{"code": 0, "msg": "success"}'


def _config(**overrides) -> Notifications:
    values = {
        "feishu_enabled": True,
        "feishu_webhook_url": SecretStr(
            "https://open.feishu.cn/open-apis/bot/v2/hook/test-webhook-id"
        ),
        "feishu_signing_secret": SecretStr("test-secret"),
        "timeout_seconds": 10,
        "max_attempts": 3,
        "retry_base_seconds": 1.0,
        "heartbeat_seconds": 1800,
    }
    values.update(overrides)
    return Notifications(**values)


def test_signature_matches_frozen_official_formula_vector():
    assert generate_sign("test-secret", 1599360473) == "wSds2BzzFIIGf/WrhUO+NI1q/9j+FRJd3JNHKAq0NZY="


def test_delivery_is_signed_and_local_log_is_redacted(tmp_path: Path):
    captured = {}

    def opener(request, *, timeout):
        captured["timeout"] = timeout
        captured["payload"] = json.loads(request.data)
        return Response()

    notifier = FeishuNotifier(_config(), log_dir=tmp_path, opener=opener)
    result = notifier.send(
        "pipeline_failed",
        "流水线失败",
        {"step": "market", "webhook_url": "must-not-appear", "token": "must-not-appear"},
    )
    assert result.status == "PASS"
    assert captured["timeout"] == 10
    assert captured["payload"]["timestamp"]
    assert captured["payload"]["sign"]
    text = captured["payload"]["content"]["text"]
    assert "market" in text
    assert f"消息ID：{result.message_id}" in text
    assert "must-not-appear" not in text
    log_text = next(tmp_path.glob("*.jsonl")).read_text(encoding="utf-8")
    assert "test-secret" not in log_text
    assert "test-webhook-id" not in log_text


def test_disabled_delivery_does_not_touch_network_or_create_log(tmp_path: Path):
    def opener(*_args, **_kwargs):
        raise AssertionError("network must not be used")

    config = _config(feishu_enabled=False)
    result = FeishuNotifier(config, log_dir=tmp_path, opener=opener).send("test", "test")
    assert result.status == "DISABLED"
    assert not list(tmp_path.glob("*"))


def test_non_official_webhook_is_rejected_without_leaking_value(tmp_path: Path):
    config = _config(feishu_webhook_url=SecretStr("https://example.com/hook/private"))
    result = FeishuNotifier(config, log_dir=tmp_path).send("test", "test")
    assert result.status == "FAIL"
    assert result.error_type == "ValueError"
    assert result.attempt == 1
    assert "example.com" not in next(tmp_path.glob("*.jsonl")).read_text(encoding="utf-8")


def test_transient_failure_retries_with_stable_identity_and_records_recovery(tmp_path: Path):
    calls = []
    sleeps = []

    def opener(request, *, timeout):
        calls.append(json.loads(request.data))
        if len(calls) == 1:
            raise URLError(TimeoutError("transient"))
        return Response()

    result = FeishuNotifier(
        _config(),
        log_dir=tmp_path,
        opener=opener,
        sleeper=sleeps.append,
    ).send("daily_catchup_passed", "日增量完成", {"trade_date": "20260722"})

    assert result.status == "PASS"
    assert result.attempt == 2
    assert result.recovered
    assert sleeps == [1.0]
    assert calls[0]["content"]["text"] == calls[1]["content"]["text"]
    records = [json.loads(line) for line in next(tmp_path.glob("*.jsonl")).read_text().splitlines()]
    assert [record["status"] for record in records] == ["FAIL", "PASS"]
    assert [record["attempt"] for record in records] == [1, 2]
    assert {record["message_id"] for record in records} == {result.message_id}
    assert records[0]["retryable"]
    assert records[1]["recovered"]


def test_retryable_failures_stop_at_bound_and_preserve_every_attempt(tmp_path: Path):
    sleeps = []

    def opener(_request, *, timeout):
        raise HTTPError("https://open.feishu.cn", 503, "unavailable", {}, None)

    result = FeishuNotifier(
        _config(),
        log_dir=tmp_path,
        opener=opener,
        sleeper=sleeps.append,
    ).send("pipeline_failed", "流水线失败")

    assert result.status == "FAIL"
    assert result.error_type == "HTTP_503"
    assert result.attempt == 3
    assert result.retryable
    assert sleeps == [1.0, 2.0]
    records = [json.loads(line) for line in next(tmp_path.glob("*.jsonl")).read_text().splitlines()]
    assert [record["attempt"] for record in records] == [1, 2, 3]
    assert len({record["message_id"] for record in records}) == 1


def test_permanent_api_failure_is_not_retried(tmp_path: Path):
    sleeps = []

    class RejectedResponse(Response):
        def read(self):
            return b'{"code": 19024, "msg": "invalid signature"}'

    result = FeishuNotifier(
        _config(),
        log_dir=tmp_path,
        opener=lambda *_args, **_kwargs: RejectedResponse(),
        sleeper=sleeps.append,
    ).send("test", "test")

    assert result.status == "FAIL"
    assert result.error_type == "RuntimeError"
    assert result.attempt == 1
    assert not result.retryable
    assert sleeps == []

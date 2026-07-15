import json
from pathlib import Path

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
    assert "example.com" not in next(tmp_path.glob("*.jsonl")).read_text(encoding="utf-8")

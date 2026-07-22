"""Signed Feishu custom-bot delivery without leaking webhook credentials."""

import base64
import hashlib
import hmac
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import time
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from shaiwei.config import Notifications, PROJECT_ROOT


@dataclass(frozen=True)
class DeliveryResult:
    event: str
    status: str
    delivered_at: str
    error_type: str = ""
    message_id: str = ""
    attempt: int = 1
    max_attempts: int = 1
    recovered: bool = False
    retryable: bool = False


def generate_sign(secret: str, timestamp: int) -> str:
    """Generate the Feishu signature: HMAC-SHA256(empty, timestamp + newline + secret)."""
    string_to_sign = f"{timestamp}\n{secret}".encode()
    digest = hmac.new(string_to_sign, digestmod=hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def _validate_webhook(webhook: str) -> None:
    parsed = urlparse(webhook)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "open.feishu.cn"
        or not parsed.path.startswith("/open-apis/bot/v2/hook/")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Feishu webhook must be an official signed custom-bot HTTPS endpoint")


def _safe_fields(fields: dict[str, object] | None) -> dict[str, object]:
    blocked = ("secret", "token", "webhook", "sign", "url")
    return {
        str(key): value
        for key, value in (fields or {}).items()
        if not any(marker in str(key).lower() for marker in blocked)
    }


def _message_id(event: str, title: str, fields: dict[str, object] | None) -> str:
    identity = json.dumps(
        {"event": event, "fields": _safe_fields(fields), "title": title},
        ensure_ascii=False,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]


def _message(
    title: str,
    event: str,
    fields: dict[str, object] | None,
    *,
    message_id: str,
    created_at: str,
) -> str:
    lines = [f"【筛微】{title}", f"事件：{event}", f"消息ID：{message_id}"]
    lines.extend(f"{key}：{value}" for key, value in _safe_fields(fields).items())
    lines.append(f"时间：{created_at}")
    return "\n".join(lines)[:3500]


def _failure_details(error: Exception) -> tuple[str, bool]:
    if isinstance(error, HTTPError):
        return f"HTTP_{error.code}", error.code in {408, 425, 429} or error.code >= 500
    if isinstance(error, URLError):
        return f"NETWORK_{type(error.reason).__name__}", True
    if isinstance(error, (TimeoutError, ConnectionError, json.JSONDecodeError)):
        return type(error).__name__, True
    if isinstance(error, OSError):
        return type(error).__name__, True
    return type(error).__name__, False


class FeishuNotifier:
    def __init__(
        self,
        config: Notifications,
        *,
        log_dir: Path | None = None,
        opener: Callable[..., object] = urlopen,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config
        self.log_dir = log_dir or PROJECT_ROOT / "logs" / "notifications"
        self._opener = opener
        self._sleeper = sleeper

    @property
    def enabled(self) -> bool:
        return self.config.feishu_enabled

    def _record(self, result: DeliveryResult) -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        day = result.delivered_at[:10].replace("-", "")
        path = self.log_dir / f"feishu_{day}.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(result), ensure_ascii=False, sort_keys=True) + "\n")

    def _record_safely(self, result: DeliveryResult) -> None:
        try:
            self._record(result)
        except OSError:
            pass

    def send(self, event: str, title: str, fields: dict[str, object] | None = None) -> DeliveryResult:
        now = datetime.now(timezone.utc).isoformat()
        message_id = _message_id(event, title, fields)
        if not self.enabled:
            return DeliveryResult(
                event=event,
                status="DISABLED",
                delivered_at=now,
                message_id=message_id,
                max_attempts=self.config.max_attempts,
            )
        webhook = self.config.feishu_webhook_url.get_secret_value()  # type: ignore[union-attr]
        secret = self.config.feishu_signing_secret.get_secret_value()  # type: ignore[union-attr]
        try:
            _validate_webhook(webhook)
        except ValueError as error:
            result = DeliveryResult(
                event=event,
                status="FAIL",
                delivered_at=now,
                error_type=type(error).__name__,
                message_id=message_id,
                max_attempts=self.config.max_attempts,
            )
            self._record_safely(result)
            return result

        created_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        message = _message(
            title,
            event,
            fields,
            message_id=message_id,
            created_at=created_at,
        )
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                timestamp = int(time.time())
                payload = {
                    "timestamp": str(timestamp),
                    "sign": generate_sign(secret, timestamp),
                    "msg_type": "text",
                    "content": {"text": message},
                }
                request = Request(
                    webhook,
                    data=json.dumps(payload, ensure_ascii=False).encode(),
                    headers={"Content-Type": "application/json; charset=utf-8"},
                    method="POST",
                )
                with self._opener(request, timeout=self.config.timeout_seconds) as response:
                    document = json.loads(response.read().decode("utf-8"))
                code = document.get("code", document.get("StatusCode", -1))
                if code != 0:
                    raise RuntimeError(f"FeishuAPIError:{code}")
                result = DeliveryResult(
                    event=event,
                    status="PASS",
                    delivered_at=datetime.now(timezone.utc).isoformat(),
                    message_id=message_id,
                    attempt=attempt,
                    max_attempts=self.config.max_attempts,
                    recovered=attempt > 1,
                )
                self._record_safely(result)
                return result
            except (HTTPError, URLError, OSError, TypeError, ValueError, RuntimeError) as error:
                error_type, retryable = _failure_details(error)
                result = DeliveryResult(
                    event=event,
                    status="FAIL",
                    delivered_at=datetime.now(timezone.utc).isoformat(),
                    error_type=error_type,
                    message_id=message_id,
                    attempt=attempt,
                    max_attempts=self.config.max_attempts,
                    retryable=retryable,
                )
                self._record_safely(result)
                if not retryable or attempt == self.config.max_attempts:
                    return result
                self._sleeper(self.config.retry_base_seconds * (2 ** (attempt - 1)))

        raise AssertionError("unreachable Feishu retry state")

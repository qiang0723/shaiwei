from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

import pytest

from shaiwei.web.notification_evidence import notification_records
from shaiwei.web.query import WebQueryError


MESSAGE_ID = "0123456789abcdef"


def _row(
    when: datetime,
    *,
    attempt: int = 1,
    max_attempts: int = 3,
    event: str = "daily_scheduler_cycle_completed",
    status: str = "PASS",
    recovered: bool = False,
) -> dict[str, object]:
    return {
        "attempt": attempt,
        "delivered_at": when.isoformat(),
        "error_type": "" if status == "PASS" else "NETWORK_TimeoutError",
        "event": event,
        "max_attempts": max_attempts,
        "message_id": MESSAGE_ID,
        "recovered": recovered,
        "retryable": status == "FAIL",
        "status": status,
    }


def _payload(*rows: dict[str, object]) -> bytes:
    return "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows).encode()


def test_reused_content_identity_across_twenty_days_is_not_one_retry_occurrence() -> None:
    start = datetime(2026, 7, 23, 10, tzinfo=timezone.utc)
    payloads = {
        f"logs/notifications/feishu_{(start + timedelta(days=index)):%Y%m%d}.jsonl": _payload(
            _row(start + timedelta(days=index))
        )
        for index in range(20)
    }

    summaries, attempts, sources, legacy = notification_records(
        payloads,
        actual_as_of="20260811",
    )

    assert len(attempts) == len(sources) == 20
    assert legacy == 0
    assert summaries[MESSAGE_ID]["attempt_count"] == 1
    assert summaries[MESSAGE_ID]["attempts"][0]["source_ref"].endswith("20260811.jsonl")


def test_latest_occurrence_replaces_prior_retry_summary_without_losing_attempts() -> None:
    start = datetime(2026, 8, 1, 10, tzinfo=timezone.utc)
    payloads = {
        "logs/notifications/feishu_20260801.jsonl": _payload(
            _row(start, attempt=1, status="FAIL"),
            _row(start + timedelta(seconds=1), attempt=2, status="PASS", recovered=True),
        ),
        "logs/notifications/feishu_20260802.jsonl": _payload(
            _row(start + timedelta(days=1), attempt=1, status="PASS")
        ),
    }

    summaries, attempts, _, _ = notification_records(payloads, actual_as_of="20260802")

    assert len(attempts) == 3
    assert summaries[MESSAGE_ID]["status"] == "PASS"
    assert summaries[MESSAGE_ID]["attempt_count"] == 1
    assert summaries[MESSAGE_ID]["failed_attempt_count"] == 0
    assert summaries[MESSAGE_ID]["recovered"] is False


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        (
            [_row(datetime(2026, 8, 1, tzinfo=timezone.utc), attempt=2)],
            "必须从attempt=1开始",
        ),
        (
            [
                _row(datetime(2026, 8, 1, tzinfo=timezone.utc), attempt=1),
                _row(datetime(2026, 8, 1, 0, 0, 1, tzinfo=timezone.utc), attempt=3),
            ],
            "attempt序列无效",
        ),
        (
            [_row(datetime(2026, 8, 1, tzinfo=timezone.utc), max_attempts=17)],
            "尝试状态无效",
        ),
    ],
)
def test_occurrence_sequence_and_hard_limit_remain_fail_closed(rows, message: str) -> None:
    payloads = {"logs/notifications/feishu_20260801.jsonl": _payload(*rows)}
    with pytest.raises(WebQueryError, match=message):
        notification_records(payloads, actual_as_of="20260801")


def test_same_content_identity_cannot_bind_different_events() -> None:
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    payloads = {
        "logs/notifications/feishu_20260801.jsonl": _payload(
            _row(start),
            _row(start + timedelta(seconds=1), event="different_event"),
        )
    }
    with pytest.raises(WebQueryError, match="绑定多个事件"):
        notification_records(payloads, actual_as_of="20260801")


def test_attempt_schema_and_duplicate_identity_remain_fail_closed() -> None:
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    row = _row(start)
    invalid = dict(row, unexpected="value")
    with pytest.raises(WebQueryError, match="字段超出脱敏白名单"):
        notification_records(
            {"logs/notifications/feishu_20260801.jsonl": _payload(invalid)},
            actual_as_of="20260801",
        )
    with pytest.raises(WebQueryError, match="身份重复"):
        notification_records(
            {"logs/notifications/feishu_20260801.jsonl": _payload(row, row)},
            actual_as_of="20260801",
        )

"""Fail-closed projection of retry occurrences from append-only notification evidence."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from typing import Mapping

from shaiwei.web.query import WebQueryError


MESSAGE_ID_PATTERN = re.compile(r"^[0-9a-f]{16}$")
SAFE_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{0,128}$")
NOTIFICATION_FIELDS = (
    "attempt",
    "delivered_at",
    "error_type",
    "event",
    "max_attempts",
    "message_id",
    "recovered",
    "retryable",
    "status",
)
NOTIFICATION_STATUSES = {"PASS", "FAIL"}
MAX_OCCURRENCE_ATTEMPTS = 16
_NOTIFICATION_PATH = re.compile(r"logs/notifications/feishu_(\d{8})\.jsonl")


def _timestamp(value: object) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as error:
        raise WebQueryError("EVIDENCE_MISMATCH", "通知时间格式无效") from error
    if parsed.tzinfo is None:
        raise WebQueryError("EVIDENCE_MISMATCH", "通知时间缺少时区")
    return parsed.astimezone(timezone.utc)


def _rows(payloads: Mapping[str, bytes], actual_as_of: str) -> tuple[list[tuple[str, dict]], set[str]]:
    selected: list[tuple[str, dict]] = []
    used_sources: set[str] = set()
    for relative_path in sorted(payloads):
        match = _NOTIFICATION_PATH.fullmatch(relative_path)
        if match is None or match.group(1) > actual_as_of:
            continue
        try:
            lines = payloads[relative_path].decode("utf-8").splitlines()
        except UnicodeDecodeError as error:
            raise WebQueryError("EVIDENCE_MISMATCH", "通知证据编码无效") from error
        for line in lines:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                raise WebQueryError("EVIDENCE_MISMATCH", "通知证据格式无效") from error
            if not isinstance(row, dict):
                raise WebQueryError("EVIDENCE_MISMATCH", "通知证据格式无效")
            selected.append((relative_path, row))
            used_sources.add(relative_path)
    return selected, used_sources


def _project_attempt(relative_path: str, row: dict) -> dict[str, object]:
    if set(row) != set(NOTIFICATION_FIELDS):
        raise WebQueryError("EVIDENCE_MISMATCH", "通知证据字段超出脱敏白名单")
    try:
        attempt = int(row["attempt"])
        max_attempts = int(row["max_attempts"])
    except (TypeError, ValueError) as error:
        raise WebQueryError("EVIDENCE_MISMATCH", "通知尝试字段无效") from error
    status, event, error_type = str(row["status"]), str(row["event"]), str(row["error_type"])
    if (
        attempt < 1
        or max_attempts < attempt
        or max_attempts > MAX_OCCURRENCE_ATTEMPTS
        or status not in NOTIFICATION_STATUSES
        or not isinstance(row["recovered"], bool)
        or not isinstance(row["retryable"], bool)
        or not SAFE_TOKEN_PATTERN.fullmatch(event)
        or not SAFE_TOKEN_PATTERN.fullmatch(error_type)
    ):
        raise WebQueryError("EVIDENCE_MISMATCH", "通知尝试状态无效")
    projected = {field: row[field] for field in NOTIFICATION_FIELDS}
    projected["attempt"] = attempt
    projected["max_attempts"] = max_attempts
    projected["source_ref"] = relative_path
    return projected


def _occurrences(attempts: list[dict[str, object]]) -> list[list[dict[str, object]]]:
    occurrences: list[list[dict[str, object]]] = []
    current: list[dict[str, object]] = []
    for attempt in attempts:
        number = int(attempt["attempt"])
        if number == 1:
            if current:
                occurrences.append(current)
            current = [attempt]
        elif not current:
            raise WebQueryError("EVIDENCE_MISMATCH", "通知投递必须从attempt=1开始")
        else:
            current.append(attempt)
    if current:
        occurrences.append(current)
    for occurrence in occurrences:
        numbers = [int(row["attempt"]) for row in occurrence]
        declared = {int(row["max_attempts"]) for row in occurrence}
        if (
            numbers != list(range(1, len(occurrence) + 1))
            or len(declared) != 1
            or len(occurrence) > MAX_OCCURRENCE_ATTEMPTS
        ):
            raise WebQueryError("EVIDENCE_MISMATCH", "单次通知投递的attempt序列无效")
    return occurrences


def notification_records(
    payloads: Mapping[str, bytes],
    *,
    actual_as_of: str,
) -> tuple[dict[str, dict[str, object]], list[dict[str, object]], set[str], int]:
    """Project latest delivery per content identity while preserving every attempt."""
    selected, used_sources = _rows(payloads, actual_as_of)
    grouped: dict[str, list[tuple[str, dict]]] = {}
    legacy_unaddressable_count = 0
    for relative_path, row in selected:
        message_id = str(row.get("message_id", ""))
        file_date = relative_path.removesuffix(".jsonl").rsplit("_", maxsplit=1)[-1]
        if not message_id:
            if file_date < "20260723":
                legacy_unaddressable_count += 1
                continue
            raise WebQueryError("EVIDENCE_MISMATCH", "当前通知证据缺少消息身份")
        if not MESSAGE_ID_PATTERN.fullmatch(message_id):
            raise WebQueryError("EVIDENCE_MISMATCH", "通知消息身份格式无效")
        grouped.setdefault(message_id, []).append((relative_path, row))

    summaries: dict[str, dict[str, object]] = {}
    all_attempts: list[dict[str, object]] = []
    for message_id in sorted(grouped):
        projected = [_project_attempt(path, row) for path, row in grouped[message_id]]
        projected.sort(key=lambda row: (_timestamp(row["delivered_at"]), int(row["attempt"])))
        events = {str(row["event"]) for row in projected}
        if len(events) != 1 or "" in events:
            raise WebQueryError("EVIDENCE_MISMATCH", "同一通知消息绑定多个事件")
        identities = {
            (str(row["source_ref"]), int(row["attempt"]), str(row["delivered_at"]))
            for row in projected
        }
        if len(identities) != len(projected):
            raise WebQueryError("EVIDENCE_MISMATCH", "通知尝试身份重复")
        occurrences = _occurrences(projected)
        latest = occurrences[-1]
        terminal = latest[-1]
        failed_count = sum(row["status"] == "FAIL" for row in latest)
        summaries[message_id] = {
            "message_id": message_id,
            "event": next(iter(events)),
            "status": terminal["status"],
            "attempt_count": len(latest),
            "failed_attempt_count": failed_count,
            "recovered": terminal["status"] == "PASS"
            and (bool(terminal["recovered"]) or failed_count > 0),
            "duplicate_delivery_risk": len(latest) > 1,
            "attempts": latest,
        }
        all_attempts.extend(projected)
    all_attempts.sort(key=lambda row: (_timestamp(row["delivered_at"]), int(row["attempt"])))
    return summaries, all_attempts, used_sources, legacy_unaddressable_count

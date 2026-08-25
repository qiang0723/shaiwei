"""Schema and independent verification for scheduler timeline events."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import TextIO

from shaiwei.pipeline.scheduler_timeline_contract import TimelineContract, TimelineError
from shaiwei.storage.interprocess_lock import LockMode, logical_lock
from shaiwei.storage.lock_resources import timeline_resource

ZERO_HASH = "0" * 64
EVENT_FIELDS = {
    "schema_version",
    "event_kind",
    "cycle_id",
    "sequence",
    "recorded_at",
    "cycle_started_local_date",
    "phase",
    "status",
    "target_trade_date",
    "account_id",
    "elapsed_seconds",
    "budget_seconds",
    "error_type",
    "outcome",
    "previous_event_sha256",
    "event_sha256",
}
SAFE_ERROR_TYPE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]{0,127}$")


def canonical_payload(event: dict[str, object]) -> bytes:
    payload = {key: value for key, value in event.items() if key != "event_sha256"}
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def event_hash(event: dict[str, object]) -> str:
    return hashlib.sha256(canonical_payload(event)).hexdigest()


def safe_error_type(error: BaseException | str | None) -> str:
    value = error if isinstance(error, str) else type(error).__name__ if error else ""
    return value if not value or SAFE_ERROR_TYPE.fullmatch(value) else "UnsafeErrorType"


def _validate_target(value: object) -> None:
    if not isinstance(value, str) or (value and (len(value) != 8 or not value.isdigit())):
        raise TimelineError("target_trade_date must be blank or YYYYMMDD")


def validate_event(
    event: dict[str, object],
    contract: TimelineContract,
    *,
    previous_hash: str,
    expected_sequence: int,
) -> None:
    if set(event) != EVENT_FIELDS:
        raise TimelineError("timeline event fields differ from schema")
    if event["schema_version"] != contract.event_schema_version:
        raise TimelineError("timeline event schema version mismatch")
    if not isinstance(event["cycle_id"], str) or not re.fullmatch(
        r"[0-9a-f]{24}", event["cycle_id"]
    ):
        raise TimelineError("invalid timeline cycle_id")
    if event["sequence"] != expected_sequence:
        raise TimelineError("timeline cycle sequence is not contiguous")
    try:
        recorded = datetime.fromisoformat(str(event["recorded_at"]))
    except ValueError as error:
        raise TimelineError("timeline recorded_at is invalid") from error
    if recorded.tzinfo is None:
        raise TimelineError("timeline recorded_at must be timezone-aware")
    local_date = event["cycle_started_local_date"]
    if not isinstance(local_date, str) or not re.fullmatch(r"\d{8}", local_date):
        raise TimelineError("invalid cycle_started_local_date")
    phase = event["phase"]
    if phase not in contract.phases:
        raise TimelineError("unknown scheduler phase")
    account = event["account_id"]
    if not isinstance(account, str):
        raise TimelineError("account_id must be a string")
    rule = contract.phases[str(phase)]
    if rule.account_required and account not in contract.accounts:
        raise TimelineError("paper phase requires a frozen account")
    if not rule.account_required and account:
        raise TimelineError("non-paper phase forbids account_id")
    _validate_target(event["target_trade_date"])
    elapsed = event["elapsed_seconds"]
    if not isinstance(elapsed, (int, float)) or isinstance(elapsed, bool) or elapsed < 0:
        raise TimelineError("elapsed_seconds must be non-negative")
    if event["budget_seconds"] != rule.warn_after_seconds:
        raise TimelineError("event budget differs from frozen phase budget")
    error_type = event["error_type"]
    if not isinstance(error_type, str) or (
        error_type and not SAFE_ERROR_TYPE.fullmatch(error_type)
    ):
        raise TimelineError("unsafe timeline error_type")

    kind = event["event_kind"]
    status = event["status"]
    outcome = event["outcome"]
    if kind not in contract.event_kinds:
        raise TimelineError("unknown timeline event kind")
    if kind == "PHASE":
        if status not in contract.phase_statuses:
            raise TimelineError("invalid phase status")
        allowed = contract.cycle_outcomes if phase == "CYCLE" else contract.phase_outcomes
        if not isinstance(outcome, str) or (outcome and outcome not in allowed):
            raise TimelineError("invalid phase outcome")
        if status == "STARTED" and (outcome or error_type or elapsed != 0):
            raise TimelineError("STARTED event contains completion fields")
        if status == "FAILED" and not error_type:
            raise TimelineError("FAILED event requires error_type")
    else:
        if status not in contract.notification_statuses:
            raise TimelineError("invalid notification status")
        if outcome:
            raise TimelineError("notification event forbids outcome")
        if status == "FAIL" and not error_type:
            raise TimelineError("failed notification requires error_type")
        if status != "FAIL" and error_type:
            raise TimelineError("non-failed notification forbids error_type")
    if event["previous_event_sha256"] != previous_hash:
        raise TimelineError("timeline SHA-256 predecessor mismatch")
    if event["event_sha256"] != event_hash(event):
        raise TimelineError("timeline event SHA-256 mismatch")


def read_and_verify(handle: TextIO, contract: TimelineContract) -> tuple[str, dict[str, int]]:
    handle.seek(0)
    previous_hash = ZERO_HASH
    sequences: dict[str, int] = {}
    for line_number, raw_line in enumerate(handle, start=1):
        if not raw_line.endswith("\n"):
            raise TimelineError(f"timeline has a truncated tail at line {line_number}")
        try:
            event = json.loads(raw_line)
        except json.JSONDecodeError as error:
            raise TimelineError(f"timeline JSON is invalid at line {line_number}") from error
        if not isinstance(event, dict):
            raise TimelineError("timeline event must be an object")
        cycle_id = str(event.get("cycle_id", ""))
        expected = sequences.get(cycle_id, 0) + 1
        validate_event(event, contract, previous_hash=previous_hash, expected_sequence=expected)
        if expected == 1 and not (
            event["event_kind"] == "PHASE"
            and event["phase"] == "CYCLE"
            and event["status"] == "STARTED"
        ):
            raise TimelineError("cycle does not start with CYCLE STARTED")
        sequences[cycle_id] = expected
        previous_hash = str(event["event_sha256"])
    return previous_hash, sequences


def verify_timeline(path: Path, contract: TimelineContract) -> list[dict[str, object]]:
    """Independently verify a complete timeline file and return its events."""
    if not path.is_file():
        raise TimelineError("timeline file is missing")
    with logical_lock(timeline_resource(path), mode=LockMode.SHARED):
        with path.open("r", encoding="utf-8") as handle:
            read_and_verify(handle, contract)
            handle.seek(0)
            return [json.loads(line) for line in handle]

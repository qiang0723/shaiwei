"""Whole-registry bidirectional replay for cases, events, receipts, and outbox."""

from __future__ import annotations

import json
from typing import Any

from .event import (
    build_event,
    event_from_row,
    ledger_payload_for_event,
    response_for_event,
    route_for_event,
)
from .models import (
    AxisState,
    GateIdentity,
    RegistryError,
    canonical_json,
    require_sha256,
    sha256_json,
    sha256_text,
)
from .state import transition
from .validation import validate_event_payload


APPROVER_SHA256 = sha256_text("M5_LOCAL_PROTOCOL_APPROVER")
ZERO_SHA256 = "0" * 64


def identity_from_case(case: Any) -> GateIdentity:
    candidates = json.loads(case["candidate_ids_json"])
    if not isinstance(candidates, list):
        raise RegistryError("case candidate identity is not a list")
    identity = GateIdentity(
        proposal_id=case["proposal_id"],
        proposal_request_sha256=case["proposal_request_sha256"],
        canonical_proposal_sha256=case["canonical_proposal_sha256"],
        proposal_head_event_sha256=case["proposal_head_event_sha256"],
        proposal_export_sha256=case["proposal_export_sha256"],
        protocol_scope_sha256=case["protocol_scope_sha256"],
        protocol_sha256=case["protocol_sha256"],
        proposal_expires_at=case["proposal_expires_at"],
        candidate_ids=tuple(candidates),
    )
    if identity.case_id != case["case_id"]:
        raise RegistryError("case ID differs from immutable proposal/protocol identity")
    return identity


def _canonical_row_json(row: Any, field: str) -> Any:
    value = json.loads(row[field])
    if canonical_json(value) != row[field]:
        raise RegistryError(f"{field} is not canonical JSON")
    return value


def _verify_receipt(connection: Any, event: dict[str, Any]) -> None:
    rows = connection.execute(
        "SELECT * FROM idempotency_receipts WHERE case_id=? AND event_seq=?",
        (event["case_id"], event["event_seq"]),
    ).fetchall()
    if len(rows) != 1:
        raise RegistryError("event must reverse-map to one idempotency receipt")
    receipt = rows[0]
    require_sha256(receipt["actor_sha256"], "receipt actor")
    require_sha256(receipt["idempotency_key_sha256"], "receipt key")
    require_sha256(receipt["request_sha256"], "receipt request")
    response = _canonical_row_json(receipt, "response_json")
    expected = response_for_event(event)
    if (
        receipt["actor_sha256"] != event["actor_sha256"]
        or receipt["route"] != route_for_event(event["case_id"], event["event_type"])
        or receipt["request_sha256"] != event["request_sha256"]
        or int(receipt["response_status"]) != (201 if event["event_type"] == "IMPORT" else 200)
        or response != expected
        or receipt["response_sha256"] != sha256_json(response)
        or receipt["created_at"] != event["recorded_at"]
    ):
        raise RegistryError("idempotency receipt differs from its event")


def _verify_outbox(connection: Any, event: dict[str, Any]) -> None:
    rows = connection.execute(
        "SELECT * FROM outbox WHERE case_id=? AND event_seq=?",
        (event["case_id"], event["event_seq"]),
    ).fetchall()
    if len(rows) != 1:
        raise RegistryError("event must reverse-map to one outbox record")
    row = rows[0]
    payload = _canonical_row_json(row, "ledger_payload_json")
    expected = ledger_payload_for_event(event)
    expected_id = sha256_text("m5-gate-outbox-v1\0" + event["event_sha256"])
    if (
        row["outbox_id"] != expected_id
        or payload != expected
        or row["ledger_payload_sha256"] != sha256_json(payload)
        or row["created_at"] != event["recorded_at"]
    ):
        raise RegistryError("outbox record differs from its event")
    if row["status"] == "PENDING":
        if row["published_at"] is not None or row["ledger_line_sha256"] is not None:
            raise RegistryError("pending outbox contains publication evidence")
    elif row["status"] == "PUBLISHED":
        require_sha256(str(row["ledger_line_sha256"]), "ledger line")
        if row["published_at"] is None:
            raise RegistryError("published outbox lacks publication time")
    else:
        raise RegistryError("outbox status is unknown")


def _verify_case(connection: Any, case: Any) -> None:
    identity = identity_from_case(case)
    events = connection.execute(
        "SELECT * FROM gate_events WHERE case_id=? ORDER BY event_seq", (identity.case_id,)
    ).fetchall()
    if not events or len(events) != int(case["current_event_seq"]):
        raise RegistryError("case event count differs from current sequence")
    before: AxisState | None = None
    previous_sha = ZERO_SHA256
    active_data_release: str | None = None
    active_engineering_release: str | None = None
    for expected_seq, row in enumerate(events, start=1):
        if int(row["event_seq"]) != expected_seq:
            raise RegistryError("case event sequence is not contiguous")
        stored = event_from_row(row)
        for name in (
            "event_id",
            "actor_sha256",
            "command_sha256",
            "request_sha256",
            "payload_sha256",
            "prev_event_sha256",
            "event_sha256",
        ):
            require_sha256(str(stored[name]), name)
        if stored["prev_event_sha256"] != previous_sha:
            raise RegistryError("gate event hash chain is broken")
        from_state = {} if before is None else before.as_dict()
        if stored["from_state"] != from_state:
            raise RegistryError("event from-state differs from replay")
        after = transition(before, stored["event_type"], stored["payload"])
        if stored["to_state"] != after.as_dict():
            raise RegistryError("event to-state differs from replay")
        active_data_release, active_engineering_release = validate_event_payload(
            stored["event_type"],
            stored["payload"],
            identity,
            active_data_release_scope=active_data_release,
            active_engineering_release_scope=active_engineering_release,
            recorded_at=stored["recorded_at"],
            actor_sha256=stored["actor_sha256"],
            approver_sha256=APPROVER_SHA256,
        )
        rebuilt = build_event(
            case_id=identity.case_id,
            event_seq=expected_seq,
            event_type=stored["event_type"],
            before=before,
            after=after,
            actor_sha256=stored["actor_sha256"],
            command_sha256=stored["command_sha256"],
            request_sha256=stored["request_sha256"],
            payload=stored["payload"],
            prev_event_sha256=previous_sha,
            recorded_at=stored["recorded_at"],
        )
        if rebuilt != stored:
            raise RegistryError("persisted gate event differs from canonical reconstruction")
        _verify_receipt(connection, stored)
        _verify_outbox(connection, stored)
        before = after
        previous_sha = stored["event_sha256"]
    if before is None:
        raise RegistryError("case has no replayed state")
    persisted = AxisState(
        case["lifecycle_state"],
        case["data_gate_status"],
        case["engineering_gate_status"],
        case["evidence_tier"],
        case["authoritative_outcome"],
        case["production_authorization"],
    )
    if persisted != before or case["created_at"] != events[0]["recorded_at"]:
        raise RegistryError("gate case projection differs from event replay")


def verify_registry_integrity(connection: Any) -> None:
    cases = connection.execute("SELECT * FROM gate_cases ORDER BY case_id").fetchall()
    for case in cases:
        _verify_case(connection, case)
    counts = {
        table: int(connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0])
        for table in ("gate_events", "idempotency_receipts", "outbox")
    }
    if len(set(counts.values())) != 1:
        raise RegistryError("events, receipts, and outbox are not one-to-one")

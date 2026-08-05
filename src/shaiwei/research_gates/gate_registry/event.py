"""Canonical event, response, and ledger-projection construction."""

from __future__ import annotations

from typing import Any

from .models import AxisState, canonical_json, sha256_json, sha256_text


def route_for_event(case_id: str, event_type: str) -> str:
    if event_type == "IMPORT":
        return "/gates/v1/cases/import"
    return f"/gates/v1/cases/{case_id}/events/{event_type.lower().replace('_', '-')}"


def build_event(
    *,
    case_id: str,
    event_seq: int,
    event_type: str,
    before: AxisState | None,
    after: AxisState,
    actor_sha256: str,
    command_sha256: str,
    request_sha256: str,
    payload: dict[str, Any],
    prev_event_sha256: str,
    recorded_at: str,
) -> dict[str, Any]:
    payload_sha256 = sha256_json(payload)
    body = {
        "case_id": case_id,
        "event_seq": event_seq,
        "event_type": event_type,
        "from_state": {} if before is None else before.as_dict(),
        "to_state": after.as_dict(),
        "actor_sha256": actor_sha256,
        "command_sha256": command_sha256,
        "request_sha256": request_sha256,
        "payload_sha256": payload_sha256,
        "prev_event_sha256": prev_event_sha256,
        "payload": payload,
        "recorded_at": recorded_at,
    }
    event_sha256 = sha256_json(body)
    return {
        "event_id": sha256_text("m5-gate-event-v1\0" + event_sha256),
        **body,
        "event_sha256": event_sha256,
    }


def response_for_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": event["case_id"],
        "event_id": event["event_id"],
        "event_seq": event["event_seq"],
        "event_type": event["event_type"],
        "event_sha256": event["event_sha256"],
        "state": event["to_state"],
        "recorded_at": event["recorded_at"],
    }


def ledger_payload_for_event(event: dict[str, Any]) -> dict[str, Any]:
    payload = event["payload"]
    return {
        "schema_version": "m5-gate-event-ledger-v1",
        "case_id": event["case_id"],
        "event_id": event["event_id"],
        "event_seq": event["event_seq"],
        "event_type": event["event_type"],
        "event_sha256": event["event_sha256"],
        "payload_sha256": event["payload_sha256"],
        "recorded_at": event["recorded_at"],
        "lifecycle_state": event["to_state"]["lifecycle_state"],
        "data_gate_status": event["to_state"]["data_gate_status"],
        "engineering_gate_status": event["to_state"]["engineering_gate_status"],
        "evidence_tier": event["to_state"]["evidence_tier"],
        "release_scope_sha256": payload.get("release_scope_sha256", ""),
        "evidence_manifest_sha256": payload.get("evidence_manifest_sha256", ""),
        "audit_manifest_sha256": payload.get("audit_manifest_sha256", ""),
        "verdict": payload.get("verdict", ""),
    }


def event_from_row(row: Any) -> dict[str, Any]:
    import json

    return {
        "event_id": row["event_id"],
        "case_id": row["case_id"],
        "event_seq": int(row["event_seq"]),
        "event_type": row["event_type"],
        "from_state": json.loads(row["from_state_json"]),
        "to_state": json.loads(row["to_state_json"]),
        "actor_sha256": row["actor_sha256"],
        "command_sha256": row["command_sha256"],
        "request_sha256": row["request_sha256"],
        "payload_sha256": row["payload_sha256"],
        "prev_event_sha256": row["prev_event_sha256"],
        "event_sha256": row["event_sha256"],
        "payload": json.loads(row["payload_json"]),
        "recorded_at": row["recorded_at"],
    }


def event_row_values(event: dict[str, Any]) -> tuple[Any, ...]:
    return (
        event["event_id"],
        event["case_id"],
        event["event_seq"],
        event["event_type"],
        canonical_json(event["from_state"]),
        canonical_json(event["to_state"]),
        event["actor_sha256"],
        event["command_sha256"],
        event["request_sha256"],
        event["payload_sha256"],
        event["prev_event_sha256"],
        event["event_sha256"],
        canonical_json(event["payload"]),
        event["recorded_at"],
    )

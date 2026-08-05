"""Explicit M5-2 gate transitions; this is not a generic workflow engine."""

from __future__ import annotations

from typing import Any

from .models import AxisState, INITIAL_STATE, RegistryError


EVENT_TYPES = {
    "IMPORT",
    "PROTOCOL_FROZEN",
    "DATA_GATE_RELEASE_READY",
    "DATA_GATE_APPROVED",
    "DATA_GATE_STARTED",
    "DATA_GATE_RECORDED",
    "ENGINEERING_GATE_RELEASE_READY",
    "ENGINEERING_GATE_APPROVED",
    "ENGINEERING_GATE_STARTED",
    "ENGINEERING_GATE_RECORDED",
    "REVOKED",
    "STOPPED",
    "CLOSED",
}


def _state(lifecycle: str, data: str, engineering: str, evidence: str) -> AxisState:
    return AxisState(lifecycle, data, engineering, evidence)


def transition(current: AxisState | None, event_type: str, payload: dict[str, Any]) -> AxisState:
    if event_type not in EVENT_TYPES:
        raise RegistryError("event type is not in the frozen M5-2 state machine")
    if current is None:
        if event_type != "IMPORT":
            raise RegistryError("the first event must be IMPORT")
        return INITIAL_STATE
    if event_type == "IMPORT":
        raise RegistryError("IMPORT cannot be repeated")
    if event_type in {"REVOKED", "STOPPED"}:
        if current.lifecycle_state in {"CLOSED", "REVOKED", "STOPPED"}:
            raise RegistryError("terminal case cannot transition")
        return AxisState(
            lifecycle_state=event_type,
            data_gate_status=current.data_gate_status,
            engineering_gate_status=current.engineering_gate_status,
            evidence_tier=current.evidence_tier,
        )
    if event_type == "CLOSED":
        if current.lifecycle_state not in {"ENGINEERING_GO", "BLOCKED_ENGINEERING", "BLOCKED_DATA"}:
            raise RegistryError("case can close only after a recorded gate result")
        return AxisState(
            lifecycle_state="CLOSED",
            data_gate_status=current.data_gate_status,
            engineering_gate_status=current.engineering_gate_status,
            evidence_tier=current.evidence_tier,
        )
    simple = {
        ("IMPORTED", "PROTOCOL_FROZEN"): _state(
            "PROTOCOL_FROZEN", "NOT_READY", "NOT_READY", "PROTOCOL_ONLY"
        ),
        ("PROTOCOL_FROZEN", "DATA_GATE_RELEASE_READY"): _state(
            "DATA_GATE_RELEASE_READY", "RELEASE_READY", "NOT_READY", "PROTOCOL_ONLY"
        ),
        ("DATA_GATE_RELEASE_READY", "DATA_GATE_APPROVED"): _state(
            "DATA_GATE_APPROVED", "APPROVED", "NOT_READY", "PROTOCOL_ONLY"
        ),
        ("DATA_GATE_APPROVED", "DATA_GATE_STARTED"): _state(
            "DATA_GATE_RUNNING", "RUNNING", "NOT_READY", "PROTOCOL_ONLY"
        ),
        ("DATA_GO", "ENGINEERING_GATE_RELEASE_READY"): _state(
            "ENGINEERING_GATE_RELEASE_READY",
            current.data_gate_status,
            "RELEASE_READY",
            "DATA_GO_ONLY",
        ),
        ("ENGINEERING_GATE_RELEASE_READY", "ENGINEERING_GATE_APPROVED"): _state(
            "ENGINEERING_GATE_APPROVED",
            current.data_gate_status,
            "APPROVED",
            "DATA_GO_ONLY",
        ),
        ("ENGINEERING_GATE_APPROVED", "ENGINEERING_GATE_STARTED"): _state(
            "ENGINEERING_GATE_RUNNING",
            current.data_gate_status,
            "RUNNING",
            "DATA_GO_ONLY",
        ),
    }
    if result := simple.get((current.lifecycle_state, event_type)):
        return result
    if current.lifecycle_state == "DATA_GATE_RUNNING" and event_type == "DATA_GATE_RECORDED":
        verdict = payload.get("verdict")
        if verdict == "GO_FULL_M5_2_DATA_PREEXECUTION_ONLY":
            return _state("DATA_GO", "DATA_GO_FULL", "NOT_READY", "DATA_GO_ONLY")
        if verdict == "GO_PARTIAL_M5_2_DATA_PREEXECUTION_ONLY":
            return _state("DATA_GO", "DATA_GO_PARTIAL", "NOT_READY", "DATA_GO_ONLY")
        if verdict == "NO_GO_M5_2_DATA_PREEXECUTION":
            return _state("BLOCKED_DATA", "BLOCKED_DATA", "NOT_READY", "PROTOCOL_ONLY")
        raise RegistryError("data gate verdict is not frozen")
    if (
        current.lifecycle_state == "ENGINEERING_GATE_RUNNING"
        and event_type == "ENGINEERING_GATE_RECORDED"
    ):
        verdict = payload.get("verdict")
        if verdict == "GO_M5_2_ENGINEERING_ONLY":
            return _state(
                "ENGINEERING_GO", current.data_gate_status, "ENGINEERING_GO", "ENGINEERING_GO_ONLY"
            )
        if verdict == "NO_GO_M5_2_ENGINEERING":
            return _state(
                "BLOCKED_ENGINEERING",
                current.data_gate_status,
                "BLOCKED_ENGINEERING",
                "DATA_GO_ONLY",
            )
        raise RegistryError("engineering gate verdict is not frozen")
    raise RegistryError(f"illegal transition: {current.lifecycle_state} -> {event_type}")

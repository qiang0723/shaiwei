"""Verified read projection for M5 proposals and chained events."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Callable

from pydantic import ValidationError

from .authority import AuthorityBundle
from .factory import RequestBindingError, build_canonical_proposal, validate_request_binding
from .models import (
    CancelCommand,
    ProposalCreate,
    SHA256_RE,
    SubmitReviewCommand,
    canonical_json,
    sha256_text,
)

ZERO_SHA256 = "0" * 64
VALID_TRANSITIONS = {
    ("PROPOSAL_CREATED", "NONE", "DRAFT"),
    ("SUBMITTED_FOR_REVIEW", "DRAFT", "REVIEW_REQUIRED"),
    ("CANCELLED_BY_PROPOSER", "DRAFT", "CANCELLED"),
    ("CANCELLED_BY_PROPOSER", "REVIEW_REQUIRED", "CANCELLED"),
}


class ProjectionError(RuntimeError):
    """Stored proposal evidence cannot be trusted."""


def _stored_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ProjectionError("stored timestamp is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ProjectionError("stored timestamp is not UTC-aware")
    if parsed.isoformat(timespec="seconds") != value:
        raise ProjectionError("stored timestamp is not canonical")
    return parsed


class ProposalProjector:
    def __init__(self, authority: AuthorityBundle, clock: Callable[[], datetime]) -> None:
        self.authority = authority
        self.clock = clock

    @staticmethod
    def proposal_row(connection: Any, proposal_id: str, actor: str) -> Any | None:
        return connection.execute(
            "SELECT * FROM proposals WHERE proposal_id=? AND actor_sha256=?", (proposal_id, actor)
        ).fetchone()

    def view(self, connection: Any, row: Any, *, include_events: bool) -> dict[str, Any]:
        events = self.events(connection, row["proposal_id"]) if include_events else []
        return {
            "proposal_id": row["proposal_id"],
            "current_state": row["current_state"],
            "current_event_seq": row["current_event_seq"],
            "available_actions": self.available_actions(row),
            "proposal_request_sha256": row["proposal_request_sha256"],
            "canonical_proposal": json.loads(row["canonical_proposal_json"]),
            "events": events,
        }

    def available_actions(self, row: Any) -> list[str]:
        return self._actions_for(row["current_state"], row, self.clock())

    @staticmethod
    def _actions_for(state: str, row: Any, at_time: datetime) -> list[str]:
        if state == "CANCELLED":
            return []
        if state == "REVIEW_REQUIRED":
            return ["CANCEL"]
        if at_time >= datetime.fromisoformat(row["expires_at"]):
            return ["CANCEL"]
        return ["SUBMIT_FOR_REVIEW", "CANCEL"]

    @staticmethod
    def events(connection: Any, proposal_id: str) -> list[dict[str, Any]]:
        rows = connection.execute(
            "SELECT * FROM proposal_events WHERE proposal_id=? ORDER BY event_seq", (proposal_id,)
        ).fetchall()
        return [{key: row[key] for key in row.keys() if key != "payload_json"} for row in rows]

    def historical_view(self, connection: Any, row: Any, event_seq: int) -> dict[str, Any]:
        events = connection.execute(
            "SELECT * FROM proposal_events WHERE proposal_id=? AND event_seq<=? ORDER BY event_seq",
            (row["proposal_id"], event_seq),
        ).fetchall()
        if len(events) != event_seq:
            raise ProjectionError("receipt event prefix is incomplete")
        target = events[-1]
        recorded_at = _stored_datetime(target["recorded_at"])
        return {
            "proposal_id": row["proposal_id"],
            "current_state": target["to_state"],
            "current_event_seq": event_seq,
            "available_actions": self._actions_for(target["to_state"], row, recorded_at),
            "proposal_request_sha256": row["proposal_request_sha256"],
            "canonical_proposal": json.loads(row["canonical_proposal_json"]),
            "events": [
                {key: event[key] for key in event.keys() if key != "payload_json"} for event in events
            ],
        }

    def _rebuild_canonical(self, row: Any) -> ProposalCreate:
        if not SHA256_RE.fullmatch(row["proposal_id"]) or not SHA256_RE.fullmatch(row["actor_sha256"]):
            raise ProjectionError("stored proposal identities are invalid")
        if (
            row["config_sha256"] != self.authority.config_sha256
            or row["authority_bundle_sha256"] != self.authority.authority_bundle_sha256
            or row["source_snapshot_id"] != self.authority.snapshot_id
            or row["source_snapshot_sha256"] != self.authority.snapshot_sha256
        ):
            raise ProjectionError("proposal row authority is stale")
        try:
            canonical = json.loads(row["canonical_proposal_json"])
            request = ProposalCreate.model_validate(canonical["request"])
            validate_request_binding(self.authority, request)
        except (json.JSONDecodeError, KeyError, TypeError, ValidationError, RequestBindingError) as exc:
            raise ProjectionError("stored proposal request is invalid") from exc
        request_json = canonical_json(request.model_dump(mode="json"))
        if canonical_json(canonical) != row["canonical_proposal_json"] or request_json != canonical_json(
            canonical["request"]
        ):
            raise ProjectionError("stored proposal is not canonical")
        request_sha = sha256_text(request_json)
        if request_sha != row["proposal_request_sha256"]:
            raise ProjectionError("proposal request hash is invalid")
        created_at = _stored_datetime(row["created_at"])
        expires_at = _stored_datetime(row["expires_at"])
        if expires_at != created_at + timedelta(days=request.valid_days):
            raise ProjectionError("proposal expiry does not match the request")
        rebuilt = build_canonical_proposal(
            self.authority,
            row["proposal_id"],
            row["actor_sha256"],
            request,
            request_sha,
            row["created_at"],
            row["expires_at"],
        )
        if canonical_json(rebuilt) != row["canonical_proposal_json"]:
            raise ProjectionError("canonical proposal cannot be independently rebuilt")
        return request

    @staticmethod
    def _decode_command(event: Any, expected_seq: int, request_sha: str) -> str:
        try:
            payload = json.loads(event["payload_json"])
            command_type = (
                SubmitReviewCommand if event["event_type"] == "SUBMITTED_FOR_REVIEW" else CancelCommand
            )
            command = command_type.model_validate(payload)
        except (json.JSONDecodeError, TypeError, ValidationError) as exc:
            raise ProjectionError("transition command payload is invalid") from exc
        if canonical_json(command.model_dump(mode="json")) != event["payload_json"]:
            raise ProjectionError("transition command payload is not canonical")
        if command.expected_event_seq != expected_seq - 1 or command.proposal_request_sha256 != request_sha:
            raise ProjectionError("transition command targets the wrong proposal version")
        return sha256_text(command.command_id)

    def _verify_event(
        self,
        event: Any,
        row: Any,
        canonical_json_value: str,
        expected_seq: int,
        previous_sha: str,
        previous_state: str,
        previous_time: datetime | None,
    ) -> tuple[str, str, datetime]:
        transition = (event["event_type"], event["from_state"], event["to_state"])
        recorded_at = _stored_datetime(event["recorded_at"])
        if transition not in VALID_TRANSITIONS or event["from_state"] != previous_state:
            raise ProjectionError("event transition is not in the frozen state machine")
        if previous_time is not None and recorded_at < previous_time:
            raise ProjectionError("event time moved backwards")
        if expected_seq == 1:
            if (
                event["payload_json"] != canonical_json_value
                or recorded_at.isoformat(timespec="seconds") != row["created_at"]
            ):
                raise ProjectionError("creation event does not bind the canonical proposal")
            command_sha = sha256_text(f"m5-create-v1\0{row['proposal_id']}\0{row['proposal_request_sha256']}")
        else:
            command_sha = self._decode_command(event, expected_seq, row["proposal_request_sha256"])
            if event["event_type"] == "SUBMITTED_FOR_REVIEW" and recorded_at >= _stored_datetime(
                row["expires_at"]
            ):
                raise ProjectionError("expired proposal has a submit event")
        values = {key: event[key] for key in event.keys() if key not in {"event_sha256", "payload_json"}}
        expected_id = sha256_text(f"m5-event-v1\0{row['proposal_id']}\0{expected_seq}\0{command_sha}")
        if (
            event["event_seq"] != expected_seq
            or event["proposal_id"] != row["proposal_id"]
            or event["actor_sha256"] != row["actor_sha256"]
            or event["request_sha256"] != row["proposal_request_sha256"]
            or event["command_sha256"] != command_sha
            or event["event_id"] != expected_id
            or event["prev_event_sha256"] != previous_sha
            or sha256_text(event["payload_json"]) != event["payload_sha256"]
            or sha256_text(canonical_json(values)) != event["event_sha256"]
        ):
            raise ProjectionError("proposal event hash or identity is invalid")
        return event["event_sha256"], event["to_state"], recorded_at

    @staticmethod
    def _verify_receipt_links(connection: Any, row: Any, events: list[Any]) -> None:
        collection_route = "/control/v1/research/proposals"
        create_receipts = connection.execute(
            "SELECT * FROM idempotency_receipts WHERE actor_sha256=? AND route=? AND request_sha256=?",
            (row["actor_sha256"], collection_route, row["proposal_request_sha256"]),
        ).fetchall()
        if len(create_receipts) != 1:
            raise ProjectionError("creation event does not have exactly one receipt")
        create_receipt = create_receipts[0]
        expected_id = sha256_text(
            f"m5-proposal-v1\0{row['actor_sha256']}\0{collection_route}\0"
            f"{create_receipt['idempotency_key_sha256']}"
        )
        if expected_id != row["proposal_id"]:
            raise ProjectionError("creation receipt does not derive the proposal identity")
        command_routes = {
            "SUBMITTED_FOR_REVIEW": (
                f"/control/v1/research/proposals/{row['proposal_id']}/commands/submit-review"
            ),
            "CANCELLED_BY_PROPOSER": f"/control/v1/research/proposals/{row['proposal_id']}/commands/cancel",
        }
        matched_receipts: set[tuple[str, str]] = set()
        for event in events[1:]:
            route = command_routes[event["event_type"]]
            receipts = connection.execute(
                "SELECT * FROM idempotency_receipts WHERE actor_sha256=? AND route=? AND request_sha256=?",
                (row["actor_sha256"], route, event["payload_sha256"]),
            ).fetchall()
            if len(receipts) != 1:
                raise ProjectionError("transition event does not have exactly one receipt")
            receipt = receipts[0]
            payload = json.loads(event["payload_json"])
            if payload["command_id"] != f"m5cmd-{receipt['idempotency_key_sha256']}":
                raise ProjectionError("transition receipt does not derive its command identity")
            matched_receipts.add((receipt["route"], receipt["idempotency_key_sha256"]))
        command_receipts = connection.execute(
            "SELECT route,idempotency_key_sha256 FROM idempotency_receipts "
            "WHERE actor_sha256=? AND route LIKE ?",
            (row["actor_sha256"], f"/control/v1/research/proposals/{row['proposal_id']}/commands/%"),
        ).fetchall()
        actual = {(receipt["route"], receipt["idempotency_key_sha256"]) for receipt in command_receipts}
        if actual != matched_receipts:
            raise ProjectionError("proposal has an extra or mismatched command receipt")

    def verify_integrity(self, connection: Any, row: Any) -> None:
        self._rebuild_canonical(row)
        events = connection.execute(
            "SELECT * FROM proposal_events WHERE proposal_id=? ORDER BY event_seq", (row["proposal_id"],)
        ).fetchall()
        previous_sha, previous_state, previous_time = ZERO_SHA256, "NONE", None
        for expected_seq, event in enumerate(events, start=1):
            previous_sha, previous_state, previous_time = self._verify_event(
                event,
                row,
                row["canonical_proposal_json"],
                expected_seq,
                previous_sha,
                previous_state,
                previous_time,
            )
        if not events or len(events) != row["current_event_seq"] or previous_state != row["current_state"]:
            raise ProjectionError("proposal projection does not match events")
        self._verify_receipt_links(connection, row, events)

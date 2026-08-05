"""Independent reconstruction of persisted idempotency responses."""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from .models import CancelCommand, StoredResponse, SubmitReviewCommand, canonical_json, sha256_text
from .projection import ProjectionError, ProposalProjector


class ReceiptIntegrityError(RuntimeError):
    """A receipt cannot be reproduced from its immutable event prefix."""


def _target_event(connection: Any, row: Any, receipt: Any, route: str) -> tuple[Any, int]:
    if route == "/control/v1/research/proposals":
        event = connection.execute(
            "SELECT * FROM proposal_events WHERE proposal_id=? AND event_seq=1", (row["proposal_id"],)
        ).fetchone()
        if event is None or event["event_type"] != "PROPOSAL_CREATED":
            raise ReceiptIntegrityError("create receipt has no creation event")
        expected_proposal_id = sha256_text(
            f"m5-proposal-v1\0{row['actor_sha256']}\0{route}\0{receipt['idempotency_key_sha256']}"
        )
        if (
            expected_proposal_id != row["proposal_id"]
            or receipt["request_sha256"] != row["proposal_request_sha256"]
        ):
            raise ReceiptIntegrityError("create receipt identity is invalid")
        return event, 201
    expected_type = (
        "SUBMITTED_FOR_REVIEW" if route.endswith("/commands/submit-review") else "CANCELLED_BY_PROPOSER"
    )
    events = connection.execute(
        "SELECT * FROM proposal_events WHERE proposal_id=? AND payload_sha256=?",
        (row["proposal_id"], receipt["request_sha256"]),
    ).fetchall()
    if len(events) != 1 or events[0]["event_type"] != expected_type:
        raise ReceiptIntegrityError("command receipt does not identify one matching event")
    event = events[0]
    try:
        payload = json.loads(event["payload_json"])
        command_type = SubmitReviewCommand if expected_type == "SUBMITTED_FOR_REVIEW" else CancelCommand
        command = command_type.model_validate(payload)
    except (json.JSONDecodeError, TypeError, ValidationError) as exc:
        raise ReceiptIntegrityError("receipt command payload is invalid") from exc
    if command.command_id != f"m5cmd-{receipt['idempotency_key_sha256']}":
        raise ReceiptIntegrityError("receipt command does not match its idempotency key")
    return event, 200


def verify_replay_receipt(
    connection: Any,
    row: Any,
    receipt: Any,
    route: str,
    projector: ProposalProjector,
) -> StoredResponse:
    try:
        event, expected_status = _target_event(connection, row, receipt, route)
        expected_body = canonical_json(projector.historical_view(connection, row, event["event_seq"]))
        decoded = json.loads(receipt["response_json"])
    except (json.JSONDecodeError, ProjectionError) as exc:
        raise ReceiptIntegrityError("receipt response cannot be reconstructed") from exc
    if (
        receipt["actor_sha256"] != row["actor_sha256"]
        or receipt["route"] != route
        or receipt["response_status"] != expected_status
        or receipt["created_at"] != event["recorded_at"]
        or canonical_json(decoded) != receipt["response_json"]
        or receipt["response_json"] != expected_body
    ):
        raise ReceiptIntegrityError("receipt differs from the reconstructed historical response")
    return StoredResponse(status_code=expected_status, body_json=expected_body, replayed=True)

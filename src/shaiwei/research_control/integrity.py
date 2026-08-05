"""Whole-database bidirectional proposal, event, and receipt integrity."""

from __future__ import annotations

import re
from typing import Any

from .models import SHA256_RE, sha256_text
from .projection import ProjectionError, ProposalProjector
from .receipts import ReceiptIntegrityError, verify_replay_receipt

COLLECTION_ROUTE = "/control/v1/research/proposals"
COMMAND_ROUTE_RE = re.compile(
    r"^/control/v1/research/proposals/(?P<proposal_id>[0-9a-f]{64})/commands/"
    r"(?P<command>submit-review|cancel)$"
)


class ControlIntegrityError(RuntimeError):
    """The operational database is not a complete bidirectional evidence graph."""


def _proposal_for_receipt(connection: Any, receipt: Any) -> Any:
    route = receipt["route"]
    key_sha = receipt["idempotency_key_sha256"]
    request_sha = receipt["request_sha256"]
    if not SHA256_RE.fullmatch(key_sha) or not SHA256_RE.fullmatch(request_sha):
        raise ControlIntegrityError("receipt hashes are malformed")
    if route == COLLECTION_ROUTE:
        proposal_id = sha256_text(f"m5-proposal-v1\0{receipt['actor_sha256']}\0{route}\0{key_sha}")
    else:
        match = COMMAND_ROUTE_RE.fullmatch(route)
        if match is None:
            raise ControlIntegrityError("receipt route is not in the frozen API")
        proposal_id = match.group("proposal_id")
    rows = connection.execute(
        "SELECT * FROM proposals WHERE proposal_id=? AND actor_sha256=?",
        (proposal_id, receipt["actor_sha256"]),
    ).fetchall()
    if len(rows) != 1:
        raise ControlIntegrityError("receipt does not reverse-map to one proposal")
    return rows[0]


def verify_control_integrity(connection: Any, projector: ProposalProjector) -> None:
    """Prove both directions and reconstruct every persisted write response."""
    proposals = connection.execute("SELECT * FROM proposals ORDER BY proposal_id").fetchall()
    try:
        for proposal in proposals:
            projector.verify_integrity(connection, proposal)
        receipts = connection.execute(
            "SELECT * FROM idempotency_receipts ORDER BY actor_sha256,route,idempotency_key_sha256"
        ).fetchall()
        for receipt in receipts:
            proposal = _proposal_for_receipt(connection, receipt)
            verify_replay_receipt(connection, proposal, receipt, receipt["route"], projector)
    except (ProjectionError, ReceiptIntegrityError) as exc:
        raise ControlIntegrityError("control evidence graph failed reconstruction") from exc

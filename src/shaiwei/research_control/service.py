"""Proposal domain service, state machine, audit chain, and idempotency."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from .authority import AuthorityBundle, AuthorityError, load_authority
from .factory import RequestBindingError, build_canonical_proposal, validate_request_binding
from .integrity import ControlIntegrityError, verify_control_integrity
from .models import (
    CancelCommand,
    ProposalCreate,
    StoredResponse,
    SubmitReviewCommand,
    canonical_json,
    sha256_text,
)
from .projection import ProjectionError, ProposalProjector
from .receipts import ReceiptIntegrityError, verify_replay_receipt
from .storage import SQLiteStore, StorageError

ZERO_SHA256 = "0" * 64


class ControlError(RuntimeError):
    def __init__(self, code: str, status_code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.message = message


@dataclass(frozen=True)
class EventSpec:
    event_type: str
    from_state: str
    to_state: str


class ProposalService:
    def __init__(
        self,
        authority: AuthorityBundle,
        store: SQLiteStore,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.authority = authority
        self.store = store
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.projector = ProposalProjector(authority, self._now)

    def _now(self) -> datetime:
        now = self.clock()
        if now.tzinfo is None:
            raise ControlError("CONTROL_NOT_READY", 503, "control clock must be timezone-aware")
        return now.astimezone(timezone.utc)

    def _assert_authority_current(self) -> None:
        try:
            current = load_authority(self.authority.project_root)
        except AuthorityError as exc:
            raise ControlError("CONTROL_NOT_READY", 503, "frozen authority is unavailable") from exc
        if current.authority_bundle_sha256 != self.authority.authority_bundle_sha256:
            raise ControlError("CONTROL_NOT_READY", 503, "frozen authority identity drifted")

    def ready(self) -> None:
        self._assert_authority_current()
        try:
            with self.store.read() as connection:
                self._verify_all(connection)
        except StorageError as exc:
            raise ControlError("CONTROL_NOT_READY", 503, "control storage is unavailable") from exc

    def _verify_all(self, connection: Any) -> None:
        try:
            verify_control_integrity(connection, self.projector)
        except ControlIntegrityError as exc:
            raise ControlError("CONTROL_NOT_READY", 503, "control evidence graph is invalid") from exc

    def _validate_request(self, request: ProposalCreate) -> None:
        try:
            validate_request_binding(self.authority, request)
        except RequestBindingError as exc:
            code = "UNIVERSE_NOT_ELIGIBLE" if "universe" in str(exc) else "CONTRACT_INVALID"
            raise ControlError(code, 422, str(exc)) from exc

    @staticmethod
    def _receipt(connection: Any, actor: str, route: str, key_sha: str, request_sha: str) -> Any | None:
        row = connection.execute(
            "SELECT * FROM idempotency_receipts "
            "WHERE actor_sha256=? AND route=? AND idempotency_key_sha256=?",
            (actor, route, key_sha),
        ).fetchone()
        if row is None:
            return None
        if row["request_sha256"] != request_sha:
            raise ControlError("IDEMPOTENCY_CONFLICT", 409, "idempotency key was used with another request")
        return row

    def _verified_replay(self, connection: Any, row: Any, receipt: Any, route: str) -> StoredResponse:
        self._verify_all(connection)
        try:
            return verify_replay_receipt(connection, row, receipt, route, self.projector)
        except ReceiptIntegrityError as exc:
            raise ControlError("CONTROL_NOT_READY", 503, "stored receipt failed reconstruction") from exc

    @staticmethod
    def _insert_receipt(
        connection: Any,
        actor: str,
        route: str,
        key_sha: str,
        request_sha: str,
        response: StoredResponse,
        created_at: str,
    ) -> None:
        connection.execute(
            "INSERT INTO idempotency_receipts VALUES (?,?,?,?,?,?,?)",
            (actor, route, key_sha, request_sha, response.status_code, response.body_json, created_at),
        )

    @staticmethod
    def _event_row(
        *,
        proposal_id: str,
        event_seq: int,
        spec: EventSpec,
        actor: str,
        command_sha: str,
        proposal_request_sha: str,
        payload_json: str,
        prev_event_sha: str,
        recorded_at: str,
    ) -> dict[str, Any]:
        payload_sha = sha256_text(payload_json)
        event_id = sha256_text(f"m5-event-v1\0{proposal_id}\0{event_seq}\0{command_sha}")
        values = {
            "event_id": event_id,
            "proposal_id": proposal_id,
            "event_seq": event_seq,
            "event_type": spec.event_type,
            "from_state": spec.from_state,
            "to_state": spec.to_state,
            "actor_sha256": actor,
            "command_sha256": command_sha,
            "request_sha256": proposal_request_sha,
            "payload_sha256": payload_sha,
            "prev_event_sha256": prev_event_sha,
            "recorded_at": recorded_at,
        }
        return {**values, "event_sha256": sha256_text(canonical_json(values)), "payload_json": payload_json}

    @staticmethod
    def _insert_event(connection: Any, event: dict[str, Any]) -> None:
        columns = tuple(event)
        connection.execute(
            f"INSERT INTO proposal_events ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
            tuple(event[column] for column in columns),
        )

    def create(self, actor: str, idempotency_key: str, request: ProposalCreate) -> StoredResponse:
        self._assert_authority_current()
        self._validate_request(request)
        route = "/control/v1/research/proposals"
        key_sha = sha256_text(idempotency_key)
        request_json = canonical_json(request.model_dump(mode="json"))
        request_sha = sha256_text(request_json)
        proposal_id = sha256_text(f"m5-proposal-v1\0{actor}\0{route}\0{key_sha}")
        now = self._now()
        created_at = now.isoformat(timespec="seconds")
        expires_at = (now + timedelta(days=request.valid_days)).isoformat(timespec="seconds")
        canonical = build_canonical_proposal(
            self.authority, proposal_id, actor, request, request_sha, created_at, expires_at
        )
        canonical_proposal_json = canonical_json(canonical)
        try:
            with self.store.immediate() as connection:
                self._verify_all(connection)
                replay = self._receipt(connection, actor, route, key_sha, request_sha)
                if replay:
                    row = self._require_proposal(connection, proposal_id, actor)
                    return self._verified_replay(connection, row, replay, route)
                connection.execute(
                    "INSERT INTO proposals VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        proposal_id,
                        actor,
                        request_sha,
                        canonical_proposal_json,
                        self.authority.config_sha256,
                        self.authority.authority_bundle_sha256,
                        self.authority.snapshot_id,
                        self.authority.snapshot_sha256,
                        created_at,
                        expires_at,
                        "DRAFT",
                        1,
                    ),
                )
                event = self._event_row(
                    proposal_id=proposal_id,
                    event_seq=1,
                    spec=EventSpec("PROPOSAL_CREATED", "NONE", "DRAFT"),
                    actor=actor,
                    command_sha=sha256_text(f"m5-create-v1\0{proposal_id}\0{request_sha}"),
                    proposal_request_sha=request_sha,
                    payload_json=canonical_proposal_json,
                    prev_event_sha=ZERO_SHA256,
                    recorded_at=created_at,
                )
                self._insert_event(connection, event)
                row = self._require_proposal(connection, proposal_id, actor)
                body = self.projector.view(connection, row, include_events=True)
                response = StoredResponse(status_code=201, body_json=canonical_json(body))
                self._insert_receipt(connection, actor, route, key_sha, request_sha, response, created_at)
                self._verify_all(connection)
                return response
        except StorageError as exc:
            raise ControlError("CONTROL_NOT_READY", 503, "control storage is unavailable") from exc

    def transition(
        self,
        proposal_id: str,
        actor: str,
        idempotency_key: str,
        command: SubmitReviewCommand | CancelCommand,
        *,
        kind: str,
    ) -> StoredResponse:
        self._assert_authority_current()
        if command.command_id != f"m5cmd-{sha256_text(idempotency_key)}":
            raise ControlError("CONTRACT_INVALID", 422, "command_id does not match Idempotency-Key")
        route = f"/control/v1/research/proposals/{proposal_id}/commands/{kind}"
        key_sha = sha256_text(idempotency_key)
        payload_json = canonical_json(command.model_dump(mode="json"))
        payload_sha = sha256_text(payload_json)
        now = self._now()
        recorded_at = now.isoformat(timespec="seconds")
        try:
            with self.store.immediate() as connection:
                self._verify_all(connection)
                replay = self._receipt(connection, actor, route, key_sha, payload_sha)
                if replay:
                    row = self._require_proposal(connection, proposal_id, actor)
                    return self._verified_replay(connection, row, replay, route)
                row = self._require_proposal(connection, proposal_id, actor)
                self._verify_integrity(connection, row)
                spec = self._transition_spec(row, command, kind, now)
                previous = connection.execute(
                    "SELECT event_sha256 FROM proposal_events WHERE proposal_id=? AND event_seq=?",
                    (proposal_id, row["current_event_seq"]),
                ).fetchone()
                event = self._event_row(
                    proposal_id=proposal_id,
                    event_seq=row["current_event_seq"] + 1,
                    spec=spec,
                    actor=actor,
                    command_sha=sha256_text(command.command_id),
                    proposal_request_sha=row["proposal_request_sha256"],
                    payload_json=payload_json,
                    prev_event_sha=previous["event_sha256"],
                    recorded_at=recorded_at,
                )
                self._insert_event(connection, event)
                changed = connection.execute(
                    "UPDATE proposals SET current_state=?,current_event_seq=? "
                    "WHERE proposal_id=? AND actor_sha256=? AND current_event_seq=?",
                    (spec.to_state, event["event_seq"], proposal_id, actor, row["current_event_seq"]),
                ).rowcount
                if changed != 1:
                    raise ControlError("STATE_CONFLICT", 409, "proposal changed concurrently")
                updated = self._require_proposal(connection, proposal_id, actor)
                body = self.projector.view(connection, updated, include_events=True)
                response = StoredResponse(status_code=200, body_json=canonical_json(body))
                self._insert_receipt(connection, actor, route, key_sha, payload_sha, response, recorded_at)
                self._verify_all(connection)
                return response
        except StorageError as exc:
            raise ControlError("CONTROL_NOT_READY", 503, "control storage is unavailable") from exc

    def _transition_spec(
        self,
        row: Any,
        command: SubmitReviewCommand | CancelCommand,
        kind: str,
        now: datetime,
    ) -> EventSpec:
        if command.expected_event_seq != row["current_event_seq"]:
            raise ControlError("STATE_CONFLICT", 409, "expected_event_seq is stale")
        if command.proposal_request_sha256 != row["proposal_request_sha256"]:
            raise ControlError("STATE_CONFLICT", 409, "proposal request identity mismatch")
        state = row["current_state"]
        if kind == "submit-review":
            if state != "DRAFT":
                raise ControlError("STATE_CONFLICT", 409, "proposal cannot be submitted from this state")
            if now >= datetime.fromisoformat(row["expires_at"]):
                raise ControlError("STATE_CONFLICT", 409, "expired proposal cannot be submitted")
            return EventSpec("SUBMITTED_FOR_REVIEW", "DRAFT", "REVIEW_REQUIRED")
        if kind == "cancel" and state in {"DRAFT", "REVIEW_REQUIRED"}:
            return EventSpec("CANCELLED_BY_PROPOSER", state, "CANCELLED")
        raise ControlError("STATE_CONFLICT", 409, "proposal cannot be cancelled from this state")

    def get(self, proposal_id: str, actor: str) -> dict[str, Any]:
        self._assert_authority_current()
        try:
            with self.store.read() as connection:
                self._verify_all(connection)
                row = self._require_proposal(connection, proposal_id, actor)
                return self.projector.view(connection, row, include_events=True)
        except StorageError as exc:
            raise ControlError("CONTROL_NOT_READY", 503, "control storage is unavailable") from exc

    def list(self, actor: str) -> dict[str, Any]:
        self._assert_authority_current()
        try:
            with self.store.read() as connection:
                self._verify_all(connection)
                rows = connection.execute(
                    "SELECT * FROM proposals WHERE actor_sha256=? ORDER BY created_at DESC,proposal_id DESC",
                    (actor,),
                ).fetchall()
                items = []
                for row in rows:
                    items.append(self.projector.view(connection, row, include_events=False))
                return {"count": len(items), "items": items}
        except StorageError as exc:
            raise ControlError("CONTROL_NOT_READY", 503, "control storage is unavailable") from exc

    def _require_proposal(self, connection: Any, proposal_id: str, actor: str) -> Any:
        row = self.projector.proposal_row(connection, proposal_id, actor)
        if row is None:
            raise ControlError("PROPOSAL_NOT_FOUND", 404, "proposal was not found")
        return row

    def _verify_integrity(self, connection: Any, row: Any) -> None:
        try:
            self.projector.verify_integrity(connection, row)
        except ProjectionError as exc:
            raise ControlError("CONTROL_NOT_READY", 503, str(exc)) from exc

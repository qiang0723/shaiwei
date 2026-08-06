"""Transactional commands for the independent M5-2 gate registry."""

from __future__ import annotations

import json
from typing import Any

from .event import (
    build_event,
    event_row_values,
    ledger_payload_for_event,
    response_for_event,
    route_for_event,
)
from .integrity import APPROVER_SHA256, identity_from_case, verify_registry_integrity
from .models import (
    AxisState,
    GateIdentity,
    RegistryError,
    canonical_json,
    require_utc_iso,
    sha256_json,
    sha256_text,
)
from .state import transition
from .storage import GateRegistryStore
from .validation import validate_event_payload


EVENT_INSERT_SQL = """
INSERT INTO gate_events(
    event_id,case_id,event_seq,event_type,from_state_json,to_state_json,
    actor_sha256,command_sha256,request_sha256,payload_sha256,prev_event_sha256,
    event_sha256,payload_json,recorded_at
) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
"""


class GateRegistryService:
    def __init__(self, store: GateRegistryStore) -> None:
        self.store = store

    @staticmethod
    def _actor(actor: str) -> str:
        if not isinstance(actor, str) or not actor.strip() or len(actor) > 120:
            raise RegistryError("actor role is empty or too long")
        return sha256_text(actor)

    @staticmethod
    def _key(value: str) -> str:
        if not isinstance(value, str) or not value.strip() or len(value) > 200:
            raise RegistryError("idempotency key is empty or too long")
        return sha256_text(value)

    @staticmethod
    def _state_from_case(case: Any) -> AxisState:
        return AxisState(
            case["lifecycle_state"],
            case["data_gate_status"],
            case["engineering_gate_status"],
            case["evidence_tier"],
            case["authoritative_outcome"],
            case["production_authorization"],
        )

    @staticmethod
    def _active_release_scopes(connection: Any, case_id: str) -> tuple[str | None, str | None, str | None]:
        data_scope = None
        engineering_scope = None
        lineage_scope = None
        rows = connection.execute(
            "SELECT event_type,payload_json FROM gate_events WHERE case_id=? ORDER BY event_seq",
            (case_id,),
        ).fetchall()
        for row in rows:
            payload = json.loads(row["payload_json"])
            if row["event_type"] == "DATA_GATE_RELEASE_READY":
                data_scope = payload["release_scope_sha256"]
            elif row["event_type"] == "ENGINEERING_GATE_RELEASE_READY":
                engineering_scope = payload["release_scope_sha256"]
            elif row["event_type"] == "LINEAGE_GATE_RELEASE_READY":
                lineage_scope = payload["release_scope_sha256"]
        return data_scope, engineering_scope, lineage_scope

    @staticmethod
    def _replay_receipt(
        connection: Any,
        *,
        actor_sha256: str,
        route: str,
        key_sha256: str,
        request_sha256: str,
    ) -> dict[str, Any] | None:
        row = connection.execute(
            "SELECT * FROM idempotency_receipts "
            "WHERE actor_sha256=? AND route=? AND idempotency_key_sha256=?",
            (actor_sha256, route, key_sha256),
        ).fetchone()
        if row is None:
            return None
        if row["request_sha256"] != request_sha256:
            raise RegistryError("idempotency key was reused with a different request")
        response = json.loads(row["response_json"])
        if (
            canonical_json(response) != row["response_json"]
            or sha256_json(response) != row["response_sha256"]
        ):
            raise RegistryError("stored idempotency response is not canonical")
        return response

    @staticmethod
    def _insert_event_evidence(
        connection: Any,
        event: dict[str, Any],
        *,
        route: str,
        key_sha256: str,
        response_status: int,
    ) -> None:
        connection.execute(EVENT_INSERT_SQL, event_row_values(event))
        response = response_for_event(event)
        connection.execute(
            "INSERT INTO idempotency_receipts VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                event["actor_sha256"],
                route,
                key_sha256,
                event["request_sha256"],
                response_status,
                canonical_json(response),
                sha256_json(response),
                event["case_id"],
                event["event_seq"],
                event["recorded_at"],
            ),
        )
        ledger_payload = ledger_payload_for_event(event)
        outbox_id = sha256_text("m5-gate-outbox-v1\0" + event["event_sha256"])
        connection.execute(
            "INSERT INTO outbox VALUES (?,?,?,?,?,'PENDING',?,NULL,NULL)",
            (
                outbox_id,
                event["case_id"],
                event["event_seq"],
                canonical_json(ledger_payload),
                sha256_json(ledger_payload),
                event["recorded_at"],
            ),
        )

    def import_case(
        self,
        identity: GateIdentity,
        *,
        actor: str,
        idempotency_key: str,
        recorded_at: str,
    ) -> dict[str, Any]:
        actor_sha = self._actor(actor)
        key_sha = self._key(idempotency_key)
        recorded = require_utc_iso(recorded_at, "recorded_at")
        payload = {"identity": identity.as_dict()}
        route = route_for_event(identity.case_id, "IMPORT")
        command = {
            "case_id": identity.case_id,
            "event_type": "IMPORT",
            "expected_event_seq": 0,
            "payload": payload,
        }
        command_sha = sha256_json(command)
        request_sha = sha256_json({"actor_sha256": actor_sha, "command": command, "recorded_at": recorded})
        with self.store.immediate() as connection:
            verify_registry_integrity(connection)
            if replay := self._replay_receipt(
                connection,
                actor_sha256=actor_sha,
                route=route,
                key_sha256=key_sha,
                request_sha256=request_sha,
            ):
                return replay
            if connection.execute("SELECT 1 FROM gate_cases WHERE case_id=?", (identity.case_id,)).fetchone():
                raise RegistryError("gate case already exists under another command")
            after = transition(None, "IMPORT", payload)
            validate_event_payload(
                "IMPORT",
                payload,
                identity,
                active_data_release_scope=None,
                active_engineering_release_scope=None,
                active_lineage_release_scope=None,
                recorded_at=recorded,
                actor_sha256=actor_sha,
                approver_sha256=APPROVER_SHA256,
            )
            event = build_event(
                case_id=identity.case_id,
                event_seq=1,
                event_type="IMPORT",
                before=None,
                after=after,
                actor_sha256=actor_sha,
                command_sha256=command_sha,
                request_sha256=request_sha,
                payload=payload,
                prev_event_sha256="0" * 64,
                recorded_at=recorded,
            )
            connection.execute(
                "INSERT INTO gate_cases VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    identity.case_id,
                    identity.proposal_id,
                    identity.proposal_request_sha256,
                    identity.canonical_proposal_sha256,
                    identity.proposal_head_event_sha256,
                    identity.proposal_export_sha256,
                    identity.protocol_scope_sha256,
                    identity.protocol_sha256,
                    identity.proposal_expires_at,
                    canonical_json(list(identity.candidate_ids)),
                    recorded,
                    after.lifecycle_state,
                    after.data_gate_status,
                    after.engineering_gate_status,
                    after.evidence_tier,
                    after.authoritative_outcome,
                    after.production_authorization,
                    1,
                ),
            )
            self._insert_event_evidence(
                connection, event, route=route, key_sha256=key_sha, response_status=201
            )
            verify_registry_integrity(connection)
            return response_for_event(event)

    def advance(
        self,
        case_id: str,
        event_type: str,
        payload: dict[str, Any],
        *,
        expected_event_seq: int,
        actor: str,
        idempotency_key: str,
        recorded_at: str,
    ) -> dict[str, Any]:
        actor_sha = self._actor(actor)
        key_sha = self._key(idempotency_key)
        recorded = require_utc_iso(recorded_at, "recorded_at")
        route = route_for_event(case_id, event_type)
        command = {
            "case_id": case_id,
            "event_type": event_type,
            "expected_event_seq": expected_event_seq,
            "payload": payload,
        }
        command_sha = sha256_json(command)
        request_sha = sha256_json({"actor_sha256": actor_sha, "command": command, "recorded_at": recorded})
        with self.store.immediate() as connection:
            verify_registry_integrity(connection)
            if replay := self._replay_receipt(
                connection,
                actor_sha256=actor_sha,
                route=route,
                key_sha256=key_sha,
                request_sha256=request_sha,
            ):
                return replay
            case = connection.execute("SELECT * FROM gate_cases WHERE case_id=?", (case_id,)).fetchone()
            if case is None:
                raise RegistryError("gate case does not exist")
            if int(case["current_event_seq"]) != expected_event_seq:
                raise RegistryError("stale gate case event sequence")
            identity = identity_from_case(case)
            before = self._state_from_case(case)
            after = transition(before, event_type, payload)
            data_scope, engineering_scope, lineage_scope = self._active_release_scopes(connection, case_id)
            validate_event_payload(
                event_type,
                payload,
                identity,
                active_data_release_scope=data_scope,
                active_engineering_release_scope=engineering_scope,
                active_lineage_release_scope=lineage_scope,
                recorded_at=recorded,
                actor_sha256=actor_sha,
                approver_sha256=APPROVER_SHA256,
            )
            previous = connection.execute(
                "SELECT event_sha256 FROM gate_events WHERE case_id=? AND event_seq=?",
                (case_id, expected_event_seq),
            ).fetchone()
            if previous is None:
                raise RegistryError("gate case projection lacks its current event")
            event = build_event(
                case_id=case_id,
                event_seq=expected_event_seq + 1,
                event_type=event_type,
                before=before,
                after=after,
                actor_sha256=actor_sha,
                command_sha256=command_sha,
                request_sha256=request_sha,
                payload=payload,
                prev_event_sha256=previous["event_sha256"],
                recorded_at=recorded,
            )
            connection.execute(
                "UPDATE gate_cases SET lifecycle_state=?,data_gate_status=?,"
                "engineering_gate_status=?,evidence_tier=?,authoritative_outcome=?,"
                "production_authorization=?,current_event_seq=? WHERE case_id=?",
                (
                    after.lifecycle_state,
                    after.data_gate_status,
                    after.engineering_gate_status,
                    after.evidence_tier,
                    after.authoritative_outcome,
                    after.production_authorization,
                    expected_event_seq + 1,
                    case_id,
                ),
            )
            self._insert_event_evidence(
                connection, event, route=route, key_sha256=key_sha, response_status=200
            )
            verify_registry_integrity(connection)
            return response_for_event(event)

    def get_case(self, case_id: str) -> dict[str, Any]:
        with self.store.read() as connection:
            verify_registry_integrity(connection)
            case = connection.execute("SELECT * FROM gate_cases WHERE case_id=?", (case_id,)).fetchone()
            if case is None:
                raise RegistryError("gate case does not exist")
            return dict(case)

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
import yaml

from shaiwei.research_gates.gate_registry import (
    GateIdentity,
    GateRegistryService,
    GateRegistryStore,
    RegistryError,
)
from shaiwei.research_gates.gate_registry.integrity import verify_registry_integrity
from shaiwei.research_gates.gate_registry.schema import (
    EXPECTED_SCHEMA_FINGERPRINT,
    schema_fingerprint,
)


ROOT = Path(__file__).parents[1]
APPROVER = "M5_LOCAL_PROTOCOL_APPROVER"
RELEASE_SHA = "d" * 64


def _identity() -> GateIdentity:
    config = yaml.safe_load(
        (ROOT / "config/m5_dynamic_fundamental_cross_pool_v1.yaml").read_text(encoding="utf-8")
    )
    return GateIdentity(
        proposal_id=config["source_proposal"]["proposal_id"],
        proposal_request_sha256=config["source_proposal"]["proposal_request_sha256"],
        canonical_proposal_sha256=config["source_proposal"]["canonical_proposal_sha256"],
        proposal_head_event_sha256=config["source_proposal"]["required_head_event_sha256"],
        proposal_export_sha256=config["source_proposal"]["proposal_export_sha256"],
        protocol_scope_sha256=(
            "ab8c33968c4ced325ec79524b774163f2991edd0c4d5d7eb7c139b27e9b17557"
        ),
        protocol_sha256="ce5cb6390df37baa553e470487c3cd319937a6d017bb43af3d874b5c41696b79",
        proposal_expires_at=config["source_proposal"]["expires_at"],
        candidate_ids=tuple(candidate["candidate_id"] for candidate in config["candidates"]),
    )


def _service(tmp_path: Path) -> GateRegistryService:
    return GateRegistryService(GateRegistryStore(tmp_path / "registry.sqlite3"))


def _matrix(identity: GateIdentity, failed: set[tuple[str, str]] | None = None) -> list[dict[str, str]]:
    failed = failed or set()
    pools = (
        "star50-official-pit-v2",
        "star-board-midcap-pit-v1",
        "star-board-smallcap-pit-v1",
    )
    return [
        {
            "candidate_id": candidate,
            "universe_id": pool,
            "status": "FAIL" if (candidate, pool) in failed else "PASS",
        }
        for candidate in identity.candidate_ids
        for pool in pools
    ]


def _import_and_freeze(service: GateRegistryService, identity: GateIdentity) -> int:
    imported = service.import_case(
        identity,
        actor=APPROVER,
        idempotency_key="import-1",
        recorded_at="2026-08-05T12:00:00+00:00",
    )
    assert imported["state"]["lifecycle_state"] == "IMPORTED"
    frozen = service.advance(
        identity.case_id,
        "PROTOCOL_FROZEN",
        {
            "protocol_scope_sha256": identity.protocol_scope_sha256,
            "protocol_sha256": identity.protocol_sha256,
        },
        expected_event_seq=1,
        actor=APPROVER,
        idempotency_key="freeze-1",
        recorded_at="2026-08-05T12:01:00+00:00",
    )
    assert frozen["state"]["evidence_tier"] == "PROTOCOL_ONLY"
    return 2


def _approve_and_start(service: GateRegistryService, identity: GateIdentity) -> int:
    sequence = _import_and_freeze(service, identity)
    service.advance(
        identity.case_id,
        "DATA_GATE_RELEASE_READY",
        {"release_scope_sha256": RELEASE_SHA},
        expected_event_seq=sequence,
        actor=APPROVER,
        idempotency_key="release-1",
        recorded_at="2026-08-05T12:02:00+00:00",
    )
    service.advance(
        identity.case_id,
        "DATA_GATE_APPROVED",
        {
            "release_scope_sha256": RELEASE_SHA,
            "decision": "APPROVE",
            "proposal_state": "REVIEW_REQUIRED",
            "proposal_event_seq": 2,
            "proposal_head_event_sha256": identity.proposal_head_event_sha256,
        },
        expected_event_seq=3,
        actor=APPROVER,
        idempotency_key="approve-1",
        recorded_at="2026-08-05T12:03:00+00:00",
    )
    started = service.advance(
        identity.case_id,
        "DATA_GATE_STARTED",
        {"release_scope_sha256": RELEASE_SHA},
        expected_event_seq=4,
        actor=APPROVER,
        idempotency_key="start-1",
        recorded_at="2026-08-05T12:04:00+00:00",
    )
    assert started["state"]["data_gate_status"] == "RUNNING"
    return 5


def _record_payload(identity: GateIdentity, failed: set[tuple[str, str]] | None = None) -> dict:
    matrix = _matrix(identity, failed)
    failed_candidates = {
        candidate for candidate, _ in (failed or set())
    }
    eligible = [candidate for candidate in identity.candidate_ids if candidate not in failed_candidates]
    rejected = [candidate for candidate in identity.candidate_ids if candidate in failed_candidates]
    verdict = (
        "GO_FULL_M5_2_DATA_PREEXECUTION_ONLY"
        if len(eligible) == 8
        else "GO_PARTIAL_M5_2_DATA_PREEXECUTION_ONLY"
        if eligible
        else "NO_GO_M5_2_DATA_PREEXECUTION"
    )
    return {
        "verdict": verdict,
        "eligible_candidate_ids": eligible,
        "rejected_candidate_ids": rejected,
        "candidate_matrix": matrix,
        "evidence_manifest_sha256": "e" * 64,
        "audit_manifest_sha256": "a" * 64,
        "audit_status": "PASS",
    }


def test_registry_full_data_chain_is_replayable_and_one_to_one(tmp_path: Path) -> None:
    service = _service(tmp_path)
    identity = _identity()
    sequence = _approve_and_start(service, identity)
    response = service.advance(
        identity.case_id,
        "DATA_GATE_RECORDED",
        _record_payload(identity),
        expected_event_seq=sequence,
        actor=APPROVER,
        idempotency_key="record-1",
        recorded_at="2026-08-05T12:05:00+00:00",
    )

    assert response["state"] == {
        "lifecycle_state": "DATA_GO",
        "data_gate_status": "DATA_GO_FULL",
        "engineering_gate_status": "NOT_READY",
        "evidence_tier": "DATA_GO_ONLY",
        "authoritative_outcome": "NOT_EVALUATED",
        "production_authorization": "none",
    }
    with service.store.read() as connection:
        verify_registry_integrity(connection)
        assert [
            connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in ("gate_events", "idempotency_receipts", "outbox")
        ] == [6, 6, 6]
        assert connection.execute("SELECT count(*) FROM outbox WHERE status='PENDING'").fetchone()[0] == 6


def test_presemantic_failure_is_auditable_and_returns_to_protocol_frozen(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    identity = _identity()
    sequence = _approve_and_start(service, identity)
    failed = service.advance(
        identity.case_id,
        "DATA_GATE_PREEXECUTION_FAILED",
        {
            "release_scope_sha256": RELEASE_SHA,
            "failure_code": "INPUT_BUNDLE_CONTROL_MISSING",
            "runner_exit_code": 2,
            "semantic_rows_read": False,
        },
        expected_event_seq=sequence,
        actor=APPROVER,
        idempotency_key="presemantic-failure-1",
        recorded_at="2026-08-05T12:05:00+00:00",
    )
    assert failed["state"] == {
        "lifecycle_state": "PROTOCOL_FROZEN",
        "data_gate_status": "NOT_READY",
        "engineering_gate_status": "NOT_READY",
        "evidence_tier": "PROTOCOL_ONLY",
        "authoritative_outcome": "NOT_EVALUATED",
        "production_authorization": "none",
    }
    next_release = service.advance(
        identity.case_id,
        "DATA_GATE_RELEASE_READY",
        {"release_scope_sha256": "e" * 64},
        expected_event_seq=sequence + 1,
        actor=APPROVER,
        idempotency_key="recovery-release-1",
        recorded_at="2026-08-05T12:06:00+00:00",
    )
    assert next_release["state"]["lifecycle_state"] == "DATA_GATE_RELEASE_READY"
    with service.store.read() as connection:
        verify_registry_integrity(connection)
        assert connection.execute("SELECT count(*) FROM gate_events").fetchone()[0] == 7


def test_idempotent_replay_returns_same_response_and_does_not_append(tmp_path: Path) -> None:
    service = _service(tmp_path)
    identity = _identity()
    first = service.import_case(
        identity,
        actor=APPROVER,
        idempotency_key="same-key",
        recorded_at="2026-08-05T12:00:00+00:00",
    )
    second = service.import_case(
        identity,
        actor=APPROVER,
        idempotency_key="same-key",
        recorded_at="2026-08-05T12:00:00+00:00",
    )
    assert first == second
    with service.store.read() as connection:
        assert connection.execute("SELECT count(*) FROM gate_events").fetchone()[0] == 1


def test_same_idempotency_key_with_different_request_fails(tmp_path: Path) -> None:
    service = _service(tmp_path)
    identity = _identity()
    service.import_case(
        identity,
        actor=APPROVER,
        idempotency_key="same-key",
        recorded_at="2026-08-05T12:00:00+00:00",
    )
    with pytest.raises(RegistryError, match="different request"):
        service.import_case(
            identity,
            actor=APPROVER,
            idempotency_key="same-key",
            recorded_at="2026-08-05T12:00:01+00:00",
        )


def test_illegal_skip_stale_sequence_and_nonapprover_fail_closed(tmp_path: Path) -> None:
    service = _service(tmp_path)
    identity = _identity()
    _import_and_freeze(service, identity)
    with pytest.raises(RegistryError, match="illegal transition"):
        service.advance(
            identity.case_id,
            "DATA_GATE_APPROVED",
            {},
            expected_event_seq=2,
            actor=APPROVER,
            idempotency_key="skip",
            recorded_at="2026-08-05T12:02:00+00:00",
        )
    service.advance(
        identity.case_id,
        "DATA_GATE_RELEASE_READY",
        {"release_scope_sha256": RELEASE_SHA},
        expected_event_seq=2,
        actor=APPROVER,
        idempotency_key="release",
        recorded_at="2026-08-05T12:02:00+00:00",
    )
    with pytest.raises(RegistryError, match="stale"):
        service.advance(
            identity.case_id,
            "DATA_GATE_APPROVED",
            {},
            expected_event_seq=2,
            actor=APPROVER,
            idempotency_key="stale",
            recorded_at="2026-08-05T12:03:00+00:00",
        )
    with pytest.raises(RegistryError, match="local approver"):
        service.advance(
            identity.case_id,
            "DATA_GATE_APPROVED",
            {
                "release_scope_sha256": RELEASE_SHA,
                "decision": "APPROVE",
                "proposal_state": "REVIEW_REQUIRED",
                "proposal_event_seq": 2,
                "proposal_head_event_sha256": identity.proposal_head_event_sha256,
            },
            expected_event_seq=3,
            actor="FAKE_SECOND_PERSON",
            idempotency_key="fake-approver",
            recorded_at="2026-08-05T12:03:00+00:00",
        )


def test_expired_proposal_cannot_be_approved(tmp_path: Path) -> None:
    service = _service(tmp_path)
    identity = _identity()
    _import_and_freeze(service, identity)
    service.advance(
        identity.case_id,
        "DATA_GATE_RELEASE_READY",
        {"release_scope_sha256": RELEASE_SHA},
        expected_event_seq=2,
        actor=APPROVER,
        idempotency_key="release",
        recorded_at="2026-08-05T12:02:00+00:00",
    )
    with pytest.raises(RegistryError, match="expiry"):
        service.advance(
            identity.case_id,
            "DATA_GATE_APPROVED",
            {
                "release_scope_sha256": RELEASE_SHA,
                "decision": "APPROVE",
                "proposal_state": "REVIEW_REQUIRED",
                "proposal_event_seq": 2,
                "proposal_head_event_sha256": identity.proposal_head_event_sha256,
            },
            expected_event_seq=3,
            actor=APPROVER,
            idempotency_key="expired",
            recorded_at="2026-08-12T10:48:16+00:00",
        )


def test_partial_matrix_is_ordered_and_invalid_matrix_rolls_back(tmp_path: Path) -> None:
    service = _service(tmp_path)
    identity = _identity()
    sequence = _approve_and_start(service, identity)
    failed = {(identity.candidate_ids[0], "star-board-midcap-pit-v1")}
    invalid = _record_payload(identity, failed)
    invalid["candidate_matrix"] = invalid["candidate_matrix"][:-1]
    with pytest.raises(RegistryError, match="complete 8x3"):
        service.advance(
            identity.case_id,
            "DATA_GATE_RECORDED",
            invalid,
            expected_event_seq=sequence,
            actor=APPROVER,
            idempotency_key="invalid-record",
            recorded_at="2026-08-05T12:05:00+00:00",
        )
    assert service.get_case(identity.case_id)["current_event_seq"] == sequence
    response = service.advance(
        identity.case_id,
        "DATA_GATE_RECORDED",
        _record_payload(identity, failed),
        expected_event_seq=sequence,
        actor=APPROVER,
        idempotency_key="valid-record",
        recorded_at="2026-08-05T12:05:00+00:00",
    )
    assert response["state"]["data_gate_status"] == "DATA_GO_PARTIAL"


def test_schema_fingerprint_and_table_set_are_exact(tmp_path: Path) -> None:
    store = GateRegistryStore(tmp_path / "registry.sqlite3")
    with store.read() as connection:
        assert schema_fingerprint(connection) == EXPECTED_SCHEMA_FINGERPRINT
        assert {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        } == {"gate_cases", "gate_events", "idempotency_receipts", "outbox"}
    raw = sqlite3.connect(store.database_path)
    raw.execute("CREATE TABLE drift(value TEXT)")
    raw.commit()
    raw.close()
    with pytest.raises(RegistryError, match="unknown or incomplete"):
        GateRegistryStore(store.database_path)

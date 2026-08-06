from __future__ import annotations

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
from shaiwei.research_gates.m5_dynamic.lineage_contract import (
    PROTOCOL_SCOPE_SHA256,
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
        protocol_scope_sha256=PROTOCOL_SCOPE_SHA256,
        protocol_sha256=("badfac341ae1ecd65536a809789c1e1f7f4ad7c0e1b42d6faa6f60dc0adb6673"),
        proposal_expires_at=config["source_proposal"]["expires_at"],
        candidate_ids=tuple(item["candidate_id"] for item in config["candidates"]),
    )


def _service(tmp_path: Path) -> GateRegistryService:
    return GateRegistryService(GateRegistryStore(tmp_path / "registry.sqlite3"))


def _start(service: GateRegistryService, identity: GateIdentity) -> None:
    service.import_case(
        identity,
        actor=APPROVER,
        idempotency_key="lineage-import",
        recorded_at="2026-08-06T03:00:00+00:00",
    )
    service.advance(
        identity.case_id,
        "PROTOCOL_FROZEN",
        {
            "protocol_scope_sha256": identity.protocol_scope_sha256,
            "protocol_sha256": identity.protocol_sha256,
        },
        expected_event_seq=1,
        actor=APPROVER,
        idempotency_key="lineage-freeze",
        recorded_at="2026-08-06T03:01:00+00:00",
    )
    service.advance(
        identity.case_id,
        "LINEAGE_GATE_RELEASE_READY",
        {"release_scope_sha256": RELEASE_SHA},
        expected_event_seq=2,
        actor=APPROVER,
        idempotency_key="lineage-release",
        recorded_at="2026-08-06T03:02:00+00:00",
    )
    service.advance(
        identity.case_id,
        "LINEAGE_GATE_APPROVED",
        {
            "release_scope_sha256": RELEASE_SHA,
            "decision": "APPROVE",
            "proposal_state": "REVIEW_REQUIRED",
            "proposal_event_seq": 2,
            "proposal_head_event_sha256": identity.proposal_head_event_sha256,
        },
        expected_event_seq=3,
        actor=APPROVER,
        idempotency_key="lineage-approve",
        recorded_at="2026-08-06T03:03:00+00:00",
    )
    service.advance(
        identity.case_id,
        "LINEAGE_GATE_STARTED",
        {"release_scope_sha256": RELEASE_SHA},
        expected_event_seq=4,
        actor=APPROVER,
        idempotency_key="lineage-start",
        recorded_at="2026-08-06T03:04:00+00:00",
    )


def _counts(*, resolved: int, forward_only: int) -> dict[str, int]:
    return {
        "LOSSLESS_EXACT_DUPLICATE": 0,
        "PIT_VERSION_CHAIN_RESOLVED": resolved,
        "FORWARD_ONLY_OBSERVED_VERSION": forward_only,
        "UNRESOLVED_MISSING_EFFECTIVE_TIME": 0,
        "UNRESOLVED_AMBIGUOUS_ORDER": 0,
        "UNRESOLVED_INCOMPLETE_CHAIN": 0,
    }


def _record_payload(*, resolved: int, blocked: int) -> dict[str, object]:
    return {
        "verdict": (
            "GO_M5_2_SOURCE_LINEAGE_RECOVERABLE" if blocked == 0 else "NO_GO_M5_2_SOURCE_LINEAGE_PREEXECUTION"
        ),
        "identity_group_count": resolved + blocked,
        "conflicting_identity_group_count": resolved + blocked,
        "resolved_conflicting_group_count": resolved,
        "blocked_conflicting_group_count": blocked,
        "disposition_counts": _counts(resolved=resolved, forward_only=blocked),
        "evidence_manifest_sha256": "e" * 64,
        "audit_manifest_sha256": "a" * 64,
        "audit_status": "PASS",
    }


@pytest.mark.parametrize(
    ("resolved", "blocked", "expected_state", "expected_tier"),
    [
        (1, 0, "LINEAGE_GO", "LINEAGE_GO_ONLY"),
        (0, 1, "BLOCKED_DATA", "LINEAGE_NO_GO_ONLY"),
    ],
)
def test_lineage_result_is_audited_idempotent_and_replayable(
    tmp_path: Path,
    resolved: int,
    blocked: int,
    expected_state: str,
    expected_tier: str,
) -> None:
    service = _service(tmp_path)
    identity = _identity()
    _start(service, identity)
    payload = _record_payload(resolved=resolved, blocked=blocked)
    first = service.advance(
        identity.case_id,
        "LINEAGE_GATE_RECORDED",
        payload,
        expected_event_seq=5,
        actor=APPROVER,
        idempotency_key="lineage-record",
        recorded_at="2026-08-06T03:05:00+00:00",
    )
    second = service.advance(
        identity.case_id,
        "LINEAGE_GATE_RECORDED",
        payload,
        expected_event_seq=5,
        actor=APPROVER,
        idempotency_key="lineage-record",
        recorded_at="2026-08-06T03:05:00+00:00",
    )

    assert first == second
    assert first["state"]["lifecycle_state"] == expected_state
    assert first["state"]["evidence_tier"] == expected_tier
    assert first["state"]["authoritative_outcome"] == "NOT_EVALUATED"
    assert first["state"]["production_authorization"] == "none"
    with service.store.read() as connection:
        verify_registry_integrity(connection)
        assert connection.execute("SELECT count(*) FROM gate_events").fetchone()[0] == 6


def test_lineage_result_count_or_verdict_mismatch_fails_closed(tmp_path: Path) -> None:
    service = _service(tmp_path)
    identity = _identity()
    _start(service, identity)
    payload = _record_payload(resolved=1, blocked=0)
    payload["verdict"] = "NO_GO_M5_2_SOURCE_LINEAGE_PREEXECUTION"

    with pytest.raises(RegistryError, match="verdict differs"):
        service.advance(
            identity.case_id,
            "LINEAGE_GATE_RECORDED",
            payload,
            expected_event_seq=5,
            actor=APPROVER,
            idempotency_key="bad-lineage-record",
            recorded_at="2026-08-06T03:05:00+00:00",
        )


def test_lineage_preexecution_failure_returns_to_frozen_protocol(tmp_path: Path) -> None:
    service = _service(tmp_path)
    identity = _identity()
    _start(service, identity)
    result = service.advance(
        identity.case_id,
        "LINEAGE_GATE_PREEXECUTION_FAILED",
        {
            "release_scope_sha256": RELEASE_SHA,
            "failure_code": "INPUT_BUNDLE_CONTROL_MISSING",
            "runner_exit_code": 2,
            "semantic_rows_read": False,
        },
        expected_event_seq=5,
        actor=APPROVER,
        idempotency_key="lineage-preexecution-failure",
        recorded_at="2026-08-06T03:05:00+00:00",
    )

    assert result["state"]["lifecycle_state"] == "PROTOCOL_FROZEN"
    assert result["state"]["data_gate_status"] == "NOT_READY"

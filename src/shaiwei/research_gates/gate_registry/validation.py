"""Event payload invariants shared by the writer and whole-store auditor."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .models import GateIdentity, RegistryError, require_sha256


UNIVERSE_IDS = (
    "star50-official-pit-v2",
    "star-board-midcap-pit-v1",
    "star-board-smallcap-pit-v1",
)
DATA_VERDICTS = {
    "GO_FULL_M5_2_DATA_PREEXECUTION_ONLY",
    "GO_PARTIAL_M5_2_DATA_PREEXECUTION_ONLY",
    "NO_GO_M5_2_DATA_PREEXECUTION",
}
PREEXECUTION_FAILURE_CODES = {"INPUT_BUNDLE_CONTROL_MISSING"}


def _release_scope(payload: dict[str, Any]) -> str:
    return require_sha256(str(payload.get("release_scope_sha256", "")), "release_scope_sha256")


def validate_candidate_matrix(payload: dict[str, Any], identity: GateIdentity) -> None:
    matrix = payload.get("candidate_matrix")
    if not isinstance(matrix, list) or len(matrix) != 24:
        raise RegistryError("data event must contain the complete 8x3 matrix")
    expected = {(candidate, universe) for candidate in identity.candidate_ids for universe in UNIVERSE_IDS}
    actual: set[tuple[str, str]] = set()
    pass_by_candidate = {candidate: True for candidate in identity.candidate_ids}
    for cell in matrix:
        if not isinstance(cell, dict) or set(cell) != {"candidate_id", "universe_id", "status"}:
            raise RegistryError("candidate matrix cell has unknown fields")
        key = (str(cell["candidate_id"]), str(cell["universe_id"]))
        if key in actual or key not in expected or cell["status"] not in {"PASS", "FAIL"}:
            raise RegistryError("candidate matrix is duplicated or outside the frozen scope")
        actual.add(key)
        pass_by_candidate[key[0]] &= cell["status"] == "PASS"
    if actual != expected:
        raise RegistryError("candidate matrix is incomplete")
    eligible = payload.get("eligible_candidate_ids")
    rejected = payload.get("rejected_candidate_ids")
    if not isinstance(eligible, list) or not isinstance(rejected, list):
        raise RegistryError("candidate projections must be ordered lists")
    expected_eligible = [candidate for candidate in identity.candidate_ids if pass_by_candidate[candidate]]
    expected_rejected = [candidate for candidate in identity.candidate_ids if not pass_by_candidate[candidate]]
    if eligible != expected_eligible or rejected != expected_rejected:
        raise RegistryError("candidate projections differ from the complete matrix")
    verdict = payload.get("verdict")
    expected_verdict = (
        "GO_FULL_M5_2_DATA_PREEXECUTION_ONLY"
        if len(eligible) == 8
        else "GO_PARTIAL_M5_2_DATA_PREEXECUTION_ONLY"
        if eligible
        else "NO_GO_M5_2_DATA_PREEXECUTION"
    )
    if verdict != expected_verdict or verdict not in DATA_VERDICTS:
        raise RegistryError("batch verdict differs from candidate matrix")


def validate_event_payload(
    event_type: str,
    payload: dict[str, Any],
    identity: GateIdentity,
    *,
    active_data_release_scope: str | None,
    active_engineering_release_scope: str | None,
    recorded_at: str,
    actor_sha256: str,
    approver_sha256: str,
) -> tuple[str | None, str | None]:
    if not isinstance(payload, dict):
        raise RegistryError("event payload must be an object")
    if event_type == "IMPORT":
        if payload != {"identity": identity.as_dict()}:
            raise RegistryError("IMPORT payload differs from immutable identity")
    elif event_type == "PROTOCOL_FROZEN":
        if payload != {
            "protocol_scope_sha256": identity.protocol_scope_sha256,
            "protocol_sha256": identity.protocol_sha256,
        }:
            raise RegistryError("protocol freeze payload differs from case identity")
    elif event_type == "DATA_GATE_RELEASE_READY":
        active_data_release_scope = _release_scope(payload)
        if set(payload) != {"release_scope_sha256"}:
            raise RegistryError("data release-ready payload has unknown fields")
    elif event_type == "DATA_GATE_APPROVED":
        if actor_sha256 != approver_sha256:
            raise RegistryError("only the frozen local approver role can approve")
        if _release_scope(payload) != active_data_release_scope:
            raise RegistryError("data approval release scope differs")
        if payload.get("decision") != "APPROVE" or payload.get("proposal_state") != "REVIEW_REQUIRED":
            raise RegistryError("data approval does not bind the required proposal state")
        if payload.get("proposal_event_seq") != 2:
            raise RegistryError("data approval proposal event sequence differs")
        if payload.get("proposal_head_event_sha256") != identity.proposal_head_event_sha256:
            raise RegistryError("data approval proposal head differs")
        if datetime.fromisoformat(recorded_at) >= datetime.fromisoformat(identity.proposal_expires_at):
            raise RegistryError("data approval occurred after proposal expiry")
        if set(payload) != {
            "release_scope_sha256",
            "decision",
            "proposal_state",
            "proposal_event_seq",
            "proposal_head_event_sha256",
        }:
            raise RegistryError("data approval payload has unknown fields")
    elif event_type == "DATA_GATE_STARTED":
        if payload != {"release_scope_sha256": active_data_release_scope}:
            raise RegistryError("data start does not bind the approved release")
    elif event_type == "DATA_GATE_PREEXECUTION_FAILED":
        if payload != {
            "release_scope_sha256": active_data_release_scope,
            "failure_code": "INPUT_BUNDLE_CONTROL_MISSING",
            "runner_exit_code": 2,
            "semantic_rows_read": False,
        } or payload["failure_code"] not in PREEXECUTION_FAILURE_CODES:
            raise RegistryError("data preexecution failure evidence differs")
    elif event_type == "DATA_GATE_RECORDED":
        for name in ("evidence_manifest_sha256", "audit_manifest_sha256"):
            require_sha256(str(payload.get(name, "")), name)
        if payload.get("audit_status") != "PASS":
            raise RegistryError("data result requires independent audit PASS")
        validate_candidate_matrix(payload, identity)
        if set(payload) != {
            "verdict",
            "eligible_candidate_ids",
            "rejected_candidate_ids",
            "candidate_matrix",
            "evidence_manifest_sha256",
            "audit_manifest_sha256",
            "audit_status",
        }:
            raise RegistryError("data result payload has unknown fields")
    elif event_type == "ENGINEERING_GATE_RELEASE_READY":
        active_engineering_release_scope = _release_scope(payload)
        if set(payload) != {"release_scope_sha256"}:
            raise RegistryError("engineering release-ready payload has unknown fields")
    elif event_type == "ENGINEERING_GATE_APPROVED":
        if actor_sha256 != approver_sha256:
            raise RegistryError("only the frozen local approver role can approve")
        if _release_scope(payload) != active_engineering_release_scope or payload.get("decision") != "APPROVE":
            raise RegistryError("engineering approval differs from release scope")
        if set(payload) != {"release_scope_sha256", "decision"}:
            raise RegistryError("engineering approval payload has unknown fields")
    elif event_type == "ENGINEERING_GATE_STARTED":
        if payload != {"release_scope_sha256": active_engineering_release_scope}:
            raise RegistryError("engineering start does not bind the approved release")
    elif event_type == "ENGINEERING_GATE_RECORDED":
        if payload.get("verdict") not in {"GO_M5_2_ENGINEERING_ONLY", "NO_GO_M5_2_ENGINEERING"}:
            raise RegistryError("engineering verdict is not frozen")
        if payload.get("audit_status") != "PASS":
            raise RegistryError("engineering result requires independent audit PASS")
        for name in ("evidence_manifest_sha256", "audit_manifest_sha256"):
            require_sha256(str(payload.get(name, "")), name)
        if set(payload) != {
            "verdict",
            "evidence_manifest_sha256",
            "audit_manifest_sha256",
            "audit_status",
        }:
            raise RegistryError("engineering result payload has unknown fields")
    elif event_type in {"REVOKED", "STOPPED", "CLOSED"}:
        if set(payload) != {"reason"} or not str(payload["reason"]).strip():
            raise RegistryError("terminal event requires one nonempty reason")
    return active_data_release_scope, active_engineering_release_scope

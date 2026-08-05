from __future__ import annotations

import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from shaiwei.research_control.api import create_app
from shaiwei.research_control.authority import load_authority
from shaiwei.research_control.models import canonical_json, sha256_text
from shaiwei.research_control.service import ProposalService

ROOT = Path(__file__).parents[1]
TOKEN = "local-test-proxy-token-that-is-long-enough"
ACTOR = hashlib.sha256(b"m5-local-research-proposer-v1").hexdigest()
OTHER_ACTOR = hashlib.sha256(b"other-logical-actor").hexdigest()
NOW = datetime(2026, 8, 5, 10, 0, tzinfo=timezone.utc)


def payload(*, family: str = "moneyflow", llm: bool = False) -> dict:
    authority = load_authority(ROOT)
    family_rule = authority.families[family]
    mode = "LLM_BOUNDED_DSL" if llm else "DETERMINISTIC_CODE"
    return {
        "template_id": "bounded-research-proposal-v1",
        "template_version": 2,
        "universe_ids": ["csi800-pit-v1", "star50-official-pit-v2"],
        "home_universe_id": "csi800-pit-v1",
        "family_id": family,
        "hypothesis_id": family_rule.hypothesis_id,
        "falsification_rule_id": family_rule.falsification_rule_id,
        "generation_mode": mode,
        "generation_attempt_cap": 8,
        "candidate_cap": 4,
        "provider_identity": "TO_BE_REVIEWED_NOT_AUTHORIZED" if llm else "NONE_NOT_APPLICABLE",
        "provider_call_intent_count": 8 if llm else 0,
        "completed_response_target": 8 if llm else 0,
        "provider_budget_usd": "0.25" if llm else "0.00",
        "valid_days": 7,
        "authority": authority.fixed_authority.model_dump(mode="json"),
    }


def headers(key: str = "idempotency-key-0001", actor: str = ACTOR) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {TOKEN}",
        "X-M5-Control-Actor": actor,
        "Idempotency-Key": key,
    }


def command_id(key: str) -> str:
    return f"m5cmd-{hashlib.sha256(key.encode('utf-8')).hexdigest()}"


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "research_control.sqlite3"


@pytest.fixture
def client(db_path: Path) -> TestClient:
    app = create_app(project_root=ROOT, database_path=db_path, proxy_token=TOKEN, clock=lambda: NOW)
    with TestClient(app) as value:
        yield value


def db_counts(path: Path) -> tuple[int, int, int]:
    connection = sqlite3.connect(path)
    try:
        return tuple(
            connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in ("proposals", "proposal_events", "idempotency_receipts")
        )
    finally:
        connection.close()


def test_create_submit_cancel_and_exact_idempotent_replay(client: TestClient, db_path: Path):
    create = client.post("/control/v1/research/proposals", headers=headers(), json=payload())
    assert create.status_code == 201
    body = create.json()
    assert body["current_state"] == "DRAFT"
    assert body["current_event_seq"] == 1
    assert body["available_actions"] == ["SUBMIT_FOR_REVIEW", "CANCEL"]
    assert body["canonical_proposal"]["authority"]["approval_authorized"] is False
    assert body["canonical_proposal"]["authority"]["provider_spend_authorized"] is False
    primary = body["canonical_proposal"]["derived"]["multiplicity_context"]["primary"]
    assert (primary["prior_attempt_count"], primary["primary_planned_after"]) == (18, 26)
    proposal_id = body["proposal_id"]
    request_sha = body["proposal_request_sha256"]
    assert db_counts(db_path) == (1, 1, 1)

    replay = client.post("/control/v1/research/proposals", headers=headers(), json=payload())
    assert replay.status_code == 201
    assert replay.content == create.content
    assert replay.headers["Idempotent-Replayed"] == "true"
    assert db_counts(db_path) == (1, 1, 1)

    changed = payload()
    changed["candidate_cap"] = 3
    conflict = client.post("/control/v1/research/proposals", headers=headers(), json=changed)
    assert (conflict.status_code, conflict.json()["error"]["code"]) == (409, "IDEMPOTENCY_CONFLICT")
    assert db_counts(db_path) == (1, 1, 1)

    submit_key = "idempotency-submit-0001"
    submit_payload = {
        "command_id": command_id(submit_key),
        "expected_event_seq": 1,
        "proposal_request_sha256": request_sha,
        "reason_code": "READY_FOR_HUMAN_REVIEW",
    }
    route = f"/control/v1/research/proposals/{proposal_id}/commands/submit-review"
    submit = client.post(route, headers=headers(submit_key), json=submit_payload)
    assert submit.status_code == 200
    assert submit.json()["current_state"] == "REVIEW_REQUIRED"
    assert [event["event_type"] for event in submit.json()["events"]] == [
        "PROPOSAL_CREATED",
        "SUBMITTED_FOR_REVIEW",
    ]
    submit_replay = client.post(route, headers=headers(submit_key), json=submit_payload)
    assert submit_replay.content == submit.content
    assert db_counts(db_path) == (1, 2, 2)

    cancel_key = "idempotency-cancel-0001"
    stale_cancel = {
        "command_id": command_id(cancel_key),
        "expected_event_seq": 1,
        "proposal_request_sha256": request_sha,
        "reason_code": "NO_LONGER_NEEDED",
    }
    cancel_route = f"/control/v1/research/proposals/{proposal_id}/commands/cancel"
    stale = client.post(cancel_route, headers=headers(cancel_key), json=stale_cancel)
    assert (stale.status_code, stale.json()["error"]["code"]) == (409, "STATE_CONFLICT")
    assert db_counts(db_path) == (1, 2, 2)

    stale_cancel["expected_event_seq"] = 2
    cancel_key = "idempotency-cancel-0002"
    stale_cancel["command_id"] = command_id(cancel_key)
    cancelled = client.post(cancel_route, headers=headers(cancel_key), json=stale_cancel)
    assert cancelled.status_code == 200
    assert cancelled.json()["current_state"] == "CANCELLED"
    assert cancelled.json()["available_actions"] == []
    late_create_replay = client.post("/control/v1/research/proposals", headers=headers(), json=payload())
    assert late_create_replay.content == create.content
    late_submit_replay = client.post(route, headers=headers(submit_key), json=submit_payload)
    assert late_submit_replay.content == submit.content
    terminal_key = "idempotency-submit-0002"
    terminal = client.post(
        route,
        headers=headers(terminal_key),
        json={**submit_payload, "command_id": command_id(terminal_key), "expected_event_seq": 3},
    )
    assert (terminal.status_code, terminal.json()["error"]["code"]) == (409, "STATE_CONFLICT")
    assert db_counts(db_path) == (1, 3, 3)


def test_get_list_fixed_actor_and_restart_recovery(client: TestClient, db_path: Path):
    created = client.post(
        "/control/v1/research/proposals", headers=headers(), json=payload(family="residual_risk")
    )
    proposal_id = created.json()["proposal_id"]
    context = created.json()["canonical_proposal"]["derived"]["multiplicity_context"]
    assert context["primary"]["prior_attempt_count"] == 3
    assert context["sensitivity"]["prior_attempt_count"] == 273
    assert client.get("/control/v1/research/proposals", headers=headers()).json()["count"] == 1
    assert client.get(f"/control/v1/research/proposals/{proposal_id}", headers=headers()).status_code == 200
    denied = client.get("/control/v1/research/proposals", headers=headers(actor=OTHER_ACTOR))
    assert (denied.status_code, denied.json()["error"]["code"]) == (403, "ROLE_NOT_ALLOWED")

    restarted = create_app(project_root=ROOT, database_path=db_path, proxy_token=TOKEN, clock=lambda: NOW)
    with TestClient(restarted) as fresh:
        restored = fresh.get(f"/control/v1/research/proposals/{proposal_id}", headers=headers())
        assert restored.status_code == 200
        assert (
            restored.content
            == client.get(f"/control/v1/research/proposals/{proposal_id}", headers=headers()).content
        )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda body: body.update({"unknown": "field"}),
        lambda body: body.update({"universe_ids": ["star100-official-pit-v1"]}),
        lambda body: body.update({"universe_ids": ["430047.BJ"]}),
        lambda body: body["authority"].update({"provider_spend_authorized": True}),
        lambda body: body.update({"hypothesis_id": "https://invalid.example"}),
        lambda body: body.update({"candidate_cap": 24, "generation_attempt_cap": 8}),
    ],
)
def test_invalid_or_unauthorized_create_is_zero_write(client: TestClient, db_path: Path, mutation: object):
    body = payload()
    mutation(body)
    response = client.post("/control/v1/research/proposals", headers=headers(), json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] in {"CONTRACT_INVALID", "UNIVERSE_NOT_ELIGIBLE"}
    assert db_counts(db_path) == (0, 0, 0)


def test_internal_auth_body_limit_and_forbidden_routes(client: TestClient, db_path: Path):
    missing = client.get("/control/v1/research/proposals")
    assert (missing.status_code, missing.json()["error"]["code"]) == (401, "SESSION_REQUIRED")
    raw_actor = headers(actor="john")
    denied = client.get("/control/v1/research/proposals", headers=raw_actor)
    assert (denied.status_code, denied.json()["error"]["code"]) == (403, "ROLE_NOT_ALLOWED")
    wrong = headers()
    wrong["Authorization"] = "Bearer wrong-token-that-is-long-enough-value"
    assert client.get("/control/v1/research/proposals", headers=wrong).status_code == 401
    oversized = client.post(
        "/control/v1/research/proposals",
        headers={**headers(), "Content-Type": "application/json"},
        content=json.dumps({"padding": "x" * 17000}),
    )
    assert (oversized.status_code, oversized.json()["error"]["code"]) == (413, "CONTRACT_INVALID")
    for suffix in ("freeze", "release", "enqueue", "run", "retry", "delete"):
        response = client.post(
            f"/control/v1/research/proposals/not-a-proposal/{suffix}", headers=headers(), json={}
        )
        assert response.status_code == 404
    assert db_counts(db_path) == (0, 0, 0)


def test_concurrent_old_seq_allows_exactly_one_command(db_path: Path):
    app = create_app(project_root=ROOT, database_path=db_path, proxy_token=TOKEN, clock=lambda: NOW)
    with TestClient(app) as setup:
        created = setup.post("/control/v1/research/proposals", headers=headers(), json=payload()).json()
    proposal_id = created["proposal_id"]
    route = f"/control/v1/research/proposals/{proposal_id}/commands/submit-review"

    def submit(key: str) -> int:
        command = {
            "command_id": command_id(key),
            "expected_event_seq": 1,
            "proposal_request_sha256": created["proposal_request_sha256"],
            "reason_code": "READY_FOR_HUMAN_REVIEW",
        }
        with TestClient(app) as concurrent_client:
            return concurrent_client.post(route, headers=headers(key), json=command).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(submit, ["concurrent-submit-0001", "concurrent-submit-0002"]))
    assert sorted(statuses) == [200, 409]
    assert db_counts(db_path) == (1, 2, 2)


def test_mutation_rate_limit_is_fail_closed(db_path: Path):
    app = create_app(project_root=ROOT, database_path=db_path, proxy_token=TOKEN, clock=lambda: NOW)
    with TestClient(app) as limited:
        first = None
        first_body = None
        for index in range(12):
            body = payload()
            body["valid_days"] = index + 1
            response = limited.post(
                "/control/v1/research/proposals",
                headers=headers(f"rate-limited-create-{index:04d}"),
                json=body,
            )
            assert response.status_code == 201
            first = first or response
            first_body = first_body or body
        replay = limited.post(
            "/control/v1/research/proposals",
            headers=headers("rate-limited-create-0000"),
            json=first_body,
        )
        assert replay.content == first.content
        blocked_body = payload()
        blocked_body["valid_days"] = 13
        blocked = limited.post(
            "/control/v1/research/proposals",
            headers=headers("rate-limited-create-0012"),
            json=blocked_body,
        )
        assert (blocked.status_code, blocked.json()["error"]["code"]) == (429, "RATE_LIMITED")
    assert db_counts(db_path) == (12, 12, 12)


def test_health_is_minimal_and_has_no_authority_or_secret(client: TestClient):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "PASS"}
    assert TOKEN not in response.text


def test_offline_canonical_or_authority_tamper_fails_closed(client: TestClient, db_path: Path):
    created = client.post("/control/v1/research/proposals", headers=headers(), json=payload()).json()
    connection = sqlite3.connect(db_path)
    try:
        trigger_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='trigger' AND name='proposals_immutable_columns'"
        ).fetchone()[0]
        connection.execute("DROP TRIGGER proposals_immutable_columns")
        stored = connection.execute(
            "SELECT canonical_proposal_json FROM proposals WHERE proposal_id=?", (created["proposal_id"],)
        ).fetchone()[0]
        canonical = json.loads(stored)
        canonical["derived"]["multiplicity_context"]["primary"]["prior_attempt_count"] = 0
        connection.execute(
            "UPDATE proposals SET canonical_proposal_json=? WHERE proposal_id=?",
            (json.dumps(canonical, sort_keys=True, separators=(",", ":")), created["proposal_id"]),
        )
        connection.execute(trigger_sql)
        connection.commit()
    finally:
        connection.close()

    response = client.get(f"/control/v1/research/proposals/{created['proposal_id']}", headers=headers())
    assert (response.status_code, response.json()["error"]["code"]) == (503, "CONTROL_NOT_READY")


def test_self_consistent_but_illegal_event_chain_fails_closed(client: TestClient, db_path: Path):
    created = client.post("/control/v1/research/proposals", headers=headers(), json=payload()).json()
    route = f"/control/v1/research/proposals/{created['proposal_id']}/commands/submit-review"
    tamper_key = "tamper-submit-0001"
    submitted = client.post(
        route,
        headers=headers(tamper_key),
        json={
            "command_id": command_id(tamper_key),
            "expected_event_seq": 1,
            "proposal_request_sha256": created["proposal_request_sha256"],
            "reason_code": "READY_FOR_HUMAN_REVIEW",
        },
    )
    assert submitted.status_code == 200
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        trigger_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='trigger' AND name='events_no_update'"
        ).fetchone()[0]
        connection.execute("DROP TRIGGER events_no_update")
        event = dict(
            connection.execute(
                "SELECT * FROM proposal_events WHERE proposal_id=? AND event_seq=2", (created["proposal_id"],)
            ).fetchone()
        )
        event["from_state"] = "REVIEW_REQUIRED"
        values = {key: value for key, value in event.items() if key not in {"event_sha256", "payload_json"}}
        event["event_sha256"] = sha256_text(canonical_json(values))
        connection.execute(
            "UPDATE proposal_events SET from_state=?,event_sha256=? WHERE proposal_id=? AND event_seq=2",
            (event["from_state"], event["event_sha256"], created["proposal_id"]),
        )
        connection.execute(trigger_sql)
        connection.commit()
    finally:
        connection.close()
    response = client.get(f"/control/v1/research/proposals/{created['proposal_id']}", headers=headers())
    assert (response.status_code, response.json()["error"]["code"]) == (503, "CONTROL_NOT_READY")


def test_offline_row_authority_identity_tamper_fails_closed(client: TestClient, db_path: Path):
    created = client.post("/control/v1/research/proposals", headers=headers(), json=payload()).json()
    connection = sqlite3.connect(db_path)
    try:
        trigger_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='trigger' AND name='proposals_immutable_columns'"
        ).fetchone()[0]
        connection.execute("DROP TRIGGER proposals_immutable_columns")
        connection.execute(
            "UPDATE proposals SET authority_bundle_sha256=? WHERE proposal_id=?",
            ("f" * 64, created["proposal_id"]),
        )
        connection.execute(trigger_sql)
        connection.commit()
    finally:
        connection.close()
    response = client.get(f"/control/v1/research/proposals/{created['proposal_id']}", headers=headers())
    assert (response.status_code, response.json()["error"]["code"]) == (503, "CONTROL_NOT_READY")


def test_expired_proposal_cannot_submit_but_can_cancel(db_path: Path):
    current = [NOW]
    app = create_app(project_root=ROOT, database_path=db_path, proxy_token=TOKEN, clock=lambda: current[0])
    with TestClient(app) as expiring:
        body = payload()
        body["valid_days"] = 1
        created = expiring.post("/control/v1/research/proposals", headers=headers(), json=body).json()
        current[0] = NOW + timedelta(days=2)
        expired_key = "expired-submit-0001"
        submit = expiring.post(
            f"/control/v1/research/proposals/{created['proposal_id']}/commands/submit-review",
            headers=headers(expired_key),
            json={
                "command_id": command_id(expired_key),
                "expected_event_seq": 1,
                "proposal_request_sha256": created["proposal_request_sha256"],
                "reason_code": "READY_FOR_HUMAN_REVIEW",
            },
        )
        assert (submit.status_code, submit.json()["error"]["code"]) == (409, "STATE_CONFLICT")
        assert db_counts(db_path) == (1, 1, 1)


def test_database_busy_rolls_back_without_receipt(db_path: Path):
    app = create_app(project_root=ROOT, database_path=db_path, proxy_token=TOKEN, clock=lambda: NOW)
    blocker = sqlite3.connect(db_path)
    blocker.execute("BEGIN IMMEDIATE")
    try:
        with TestClient(app) as busy:
            response = busy.post("/control/v1/research/proposals", headers=headers(), json=payload())
            assert (response.status_code, response.json()["error"]["code"]) == (503, "CONTROL_NOT_READY")
    finally:
        blocker.rollback()
        blocker.close()
    assert db_counts(db_path) == (0, 0, 0)


@pytest.mark.parametrize("kind", ["submit-review", "cancel"])
def test_secret_shaped_transition_command_id_is_zero_write(client: TestClient, db_path: Path, kind: str):
    created = client.post("/control/v1/research/proposals", headers=headers(), json=payload()).json()
    reason = "READY_FOR_HUMAN_REVIEW" if kind == "submit-review" else "NO_LONGER_NEEDED"
    response = client.post(
        f"/control/v1/research/proposals/{created['proposal_id']}/commands/{kind}",
        headers=headers(f"secret-command-{kind}"),
        json={
            "command_id": "sk-1234567890abcdef",
            "expected_event_seq": 1,
            "proposal_request_sha256": created["proposal_request_sha256"],
            "reason_code": reason,
        },
    )
    assert (response.status_code, response.json()["error"]["code"]) == (422, "CONTRACT_INVALID")
    assert db_counts(db_path) == (1, 1, 1)


@pytest.mark.parametrize("kind", ["submit-review", "cancel"])
def test_structured_command_id_must_match_current_idempotency_key(
    client: TestClient, db_path: Path, kind: str
):
    created = client.post("/control/v1/research/proposals", headers=headers(), json=payload()).json()
    request_key = f"mismatched-command-{kind}"
    another_key = f"different-command-{kind}"
    reason = "READY_FOR_HUMAN_REVIEW" if kind == "submit-review" else "NO_LONGER_NEEDED"
    response = client.post(
        f"/control/v1/research/proposals/{created['proposal_id']}/commands/{kind}",
        headers=headers(request_key),
        json={
            "command_id": command_id(another_key),
            "expected_event_seq": 1,
            "proposal_request_sha256": created["proposal_request_sha256"],
            "reason_code": reason,
        },
    )
    assert (response.status_code, response.json()["error"]["code"]) == (422, "CONTRACT_INVALID")
    assert db_counts(db_path) == (1, 1, 1)


def test_rate_replay_exemption_requires_same_route_key_and_request(db_path: Path):
    app = create_app(project_root=ROOT, database_path=db_path, proxy_token=TOKEN, clock=lambda: NOW)
    shared_key = "shared-rate-key-0001"
    with TestClient(app) as bounded:
        first = bounded.post("/control/v1/research/proposals", headers=headers(shared_key), json=payload())
        assert first.status_code == 201
        exact = bounded.post("/control/v1/research/proposals", headers=headers(shared_key), json=payload())
        assert exact.content == first.content

        changed = payload()
        changed["candidate_cap"] = 3
        conflict = bounded.post("/control/v1/research/proposals", headers=headers(shared_key), json=changed)
        assert conflict.status_code == 409

        created = first.json()
        cancel = bounded.post(
            f"/control/v1/research/proposals/{created['proposal_id']}/commands/cancel",
            headers=headers(shared_key),
            json={
                "command_id": command_id(shared_key),
                "expected_event_seq": 1,
                "proposal_request_sha256": created["proposal_request_sha256"],
                "reason_code": "NO_LONGER_NEEDED",
            },
        )
        assert cancel.status_code == 200

        for index, valid_days in enumerate([1, 2, 3, 4, 5, 6, 8, 9, 10]):
            body = payload()
            body["valid_days"] = valid_days
            response = bounded.post(
                "/control/v1/research/proposals",
                headers=headers(f"adversarial-rate-{index:04d}"),
                json=body,
            )
            assert response.status_code == 201
        assert (
            bounded.post(
                "/control/v1/research/proposals", headers=headers(shared_key), json=payload()
            ).content
            == first.content
        )
        blocked_body = payload()
        blocked_body["valid_days"] = 11
        blocked = bounded.post(
            "/control/v1/research/proposals",
            headers=headers("adversarial-rate-9999"),
            json=blocked_body,
        )
        assert (blocked.status_code, blocked.json()["error"]["code"]) == (429, "RATE_LIMITED")


def test_runtime_schema_drift_blocks_health_read_and_write(client: TestClient, db_path: Path):
    connection = sqlite3.connect(db_path)
    connection.execute("DROP TRIGGER receipts_no_delete")
    connection.commit()
    connection.close()
    assert client.get("/healthz").status_code == 503
    read = client.get("/control/v1/research/proposals", headers=headers())
    write = client.post("/control/v1/research/proposals", headers=headers(), json=payload())
    assert read.json()["error"]["code"] == "CONTROL_NOT_READY"
    assert write.json()["error"]["code"] == "CONTROL_NOT_READY"


def test_canonical_but_forged_receipt_response_fails_reconstruction(client: TestClient, db_path: Path):
    create_body = payload()
    created = client.post("/control/v1/research/proposals", headers=headers(), json=create_body)
    assert created.status_code == 201
    connection = sqlite3.connect(db_path)
    try:
        trigger_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='trigger' AND name='receipts_no_update'"
        ).fetchone()[0]
        connection.execute("DROP TRIGGER receipts_no_update")
        forged = created.json()
        forged["available_actions"] = []
        connection.execute(
            "UPDATE idempotency_receipts SET response_json=? WHERE route=?",
            (canonical_json(forged), "/control/v1/research/proposals"),
        )
        connection.execute(trigger_sql)
        connection.commit()
    finally:
        connection.close()
    assert client.get("/healthz").status_code == 503
    read = client.get("/control/v1/research/proposals", headers=headers())
    assert (read.status_code, read.json()["error"]["code"]) == (503, "CONTROL_NOT_READY")
    replay = client.post("/control/v1/research/proposals", headers=headers(), json=create_body)
    assert (replay.status_code, replay.json()["error"]["code"]) == (503, "CONTROL_NOT_READY")


def test_missing_creation_receipt_breaks_proposal_integrity(client: TestClient, db_path: Path):
    created = client.post("/control/v1/research/proposals", headers=headers(), json=payload()).json()
    connection = sqlite3.connect(db_path)
    try:
        trigger_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='trigger' AND name='receipts_no_delete'"
        ).fetchone()[0]
        connection.execute("DROP TRIGGER receipts_no_delete")
        connection.execute(
            "DELETE FROM idempotency_receipts WHERE route=?",
            ("/control/v1/research/proposals",),
        )
        connection.execute(trigger_sql)
        connection.commit()
    finally:
        connection.close()
    response = client.get(f"/control/v1/research/proposals/{created['proposal_id']}", headers=headers())
    assert (response.status_code, response.json()["error"]["code"]) == (503, "CONTROL_NOT_READY")


def test_mismatched_transition_receipt_breaks_proposal_integrity(client: TestClient, db_path: Path):
    created = client.post("/control/v1/research/proposals", headers=headers(), json=payload()).json()
    cancel_key = "receipt-link-cancel-0001"
    route = f"/control/v1/research/proposals/{created['proposal_id']}/commands/cancel"
    cancelled = client.post(
        route,
        headers=headers(cancel_key),
        json={
            "command_id": command_id(cancel_key),
            "expected_event_seq": 1,
            "proposal_request_sha256": created["proposal_request_sha256"],
            "reason_code": "NO_LONGER_NEEDED",
        },
    )
    assert cancelled.status_code == 200
    connection = sqlite3.connect(db_path)
    try:
        trigger_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='trigger' AND name='receipts_no_update'"
        ).fetchone()[0]
        connection.execute("DROP TRIGGER receipts_no_update")
        connection.execute(
            "UPDATE idempotency_receipts SET request_sha256=? WHERE route=?",
            ("f" * 64, route),
        )
        connection.execute(trigger_sql)
        connection.commit()
    finally:
        connection.close()
    response = client.get(f"/control/v1/research/proposals/{created['proposal_id']}", headers=headers())
    assert (response.status_code, response.json()["error"]["code"]) == (503, "CONTROL_NOT_READY")


@pytest.mark.parametrize(
    "route",
    [
        "/control/v1/research/proposals",
        f"/control/v1/research/proposals/{'a' * 64}/commands/submit-review",
    ],
)
def test_orphan_create_or_command_receipt_blocks_health_read_and_write(db_path: Path, route: str):
    app = create_app(project_root=ROOT, database_path=db_path, proxy_token=TOKEN, clock=lambda: NOW)
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            "INSERT INTO idempotency_receipts VALUES (?,?,?,?,?,?,?)",
            (ACTOR, route, "b" * 64, "c" * 64, 201, canonical_json({"forged": True}), NOW.isoformat()),
        )
        connection.commit()
    finally:
        connection.close()
    with TestClient(app) as orphaned:
        assert orphaned.get("/healthz").status_code == 503
        read = orphaned.get("/control/v1/research/proposals", headers=headers())
        write = orphaned.post("/control/v1/research/proposals", headers=headers(), json=payload())
        assert (read.status_code, read.json()["error"]["code"]) == (503, "CONTROL_NOT_READY")
        assert (write.status_code, write.json()["error"]["code"]) == (503, "CONTROL_NOT_READY")
    assert db_counts(db_path) == (0, 0, 1)


@pytest.mark.parametrize("corruption", ["response", "status", "time"])
def test_bad_receipt_insert_rolls_back_entire_create_transaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, corruption: str
):
    db_path = tmp_path / f"bad-{corruption}.sqlite3"

    def insert_bad_receipt(
        connection: sqlite3.Connection,
        actor: str,
        route: str,
        key_sha: str,
        request_sha: str,
        response: object,
        created_at: str,
    ) -> None:
        status = 500 if corruption == "status" else response.status_code
        body = canonical_json({"forged": True}) if corruption == "response" else response.body_json
        timestamp = "2026-08-05T09:59:59+00:00" if corruption == "time" else created_at
        connection.execute(
            "INSERT INTO idempotency_receipts VALUES (?,?,?,?,?,?,?)",
            (actor, route, key_sha, request_sha, status, body, timestamp),
        )

    monkeypatch.setattr(ProposalService, "_insert_receipt", staticmethod(insert_bad_receipt))
    app = create_app(project_root=ROOT, database_path=db_path, proxy_token=TOKEN, clock=lambda: NOW)
    with TestClient(app) as corrupted:
        response = corrupted.post("/control/v1/research/proposals", headers=headers(), json=payload())
        assert (response.status_code, response.json()["error"]["code"]) == (503, "CONTROL_NOT_READY")
    assert db_counts(db_path) == (0, 0, 0)

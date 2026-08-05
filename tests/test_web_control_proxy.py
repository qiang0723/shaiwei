import json
from pathlib import Path

from fastapi.testclient import TestClient
import httpx

from shaiwei.web.control_proxy import STABLE_ACTOR_HASH, allowed_control_path
from shaiwei.web.ui import create_app


ORIGIN = "http://127.0.0.1:8080"
TOKEN = "fixture-proxy-token-123456"
PROPOSAL_ID = "proposal_01234567"


def _static_fixture(root: Path) -> Path:
    dist = root / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(
        '<meta name="csp-nonce" content="__P3_STYLE_NONCE__"><div id="root"></div>',
        encoding="utf-8",
    )
    return dist


def _client(tmp_path: Path, handler) -> TestClient:
    return TestClient(
        create_app(
            static_root=_static_fixture(tmp_path),
            control_base_url="http://control.internal",
            control_proxy_token=TOKEN,
            control_allowed_origin=ORIGIN,
            control_transport=httpx.MockTransport(handler),
        )
    )


def test_control_get_establishes_short_session_and_replaces_identity_headers(
    tmp_path: Path,
) -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(request.headers)
        return httpx.Response(200, json={"data": {"items": []}})

    client = _client(tmp_path, handler)
    response = client.get(
        "/control/v1/research/proposals",
        headers={"Authorization": "Bearer browser-value", "X-M5-Control-Actor": "plain"},
    )
    assert response.status_code == 200
    assert response.headers["x-csrf-token"]
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie
    assert captured["authorization"] == f"Bearer {TOKEN}"
    assert captured["x-m5-control-actor"] == STABLE_ACTOR_HASH
    assert len(STABLE_ACTOR_HASH) == 64


def test_control_write_requires_session_exact_origin_and_csrf(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(201, json={"data": {"proposal_id": PROPOSAL_ID}})

    client = _client(tmp_path, handler)
    route = "/control/v1/research/proposals"
    body = {"home_universe_id": "csi800-pit-v1"}
    assert client.post(route, json=body, headers={"Origin": ORIGIN}).status_code == 401

    session = client.get(route)
    csrf = session.headers["x-csrf-token"]
    wrong_origin = client.post(
        route,
        json=body,
        headers={"Origin": "http://localhost:8080", "X-CSRF-Token": csrf},
    )
    assert wrong_origin.status_code == 403
    assert wrong_origin.json()["error"]["code"] == "ORIGIN_REJECTED"
    trailing_slash_origin = client.post(
        route,
        json=body,
        headers={"Origin": f"{ORIGIN}/", "X-CSRF-Token": csrf},
    )
    assert trailing_slash_origin.status_code == 403
    bad_csrf = client.post(
        route,
        json=body,
        headers={"Origin": ORIGIN, "X-CSRF-Token": "wrong"},
    )
    assert bad_csrf.status_code == 403
    assert bad_csrf.json()["error"]["code"] == "CSRF_REJECTED"

    accepted = client.post(
        route,
        content=json.dumps(body),
        headers={
            "Content-Type": "application/json",
            "Origin": ORIGIN,
            "X-CSRF-Token": csrf,
            "Idempotency-Key": "0123456789abcdef",
            "Authorization": "Bearer browser-value",
            "X-M5-Control-Actor": "plain",
        },
    )
    assert accepted.status_code == 201
    assert requests[-1].headers["idempotency-key"] == "0123456789abcdef"
    assert requests[-1].headers["authorization"] == f"Bearer {TOKEN}"
    assert requests[-1].headers["x-m5-control-actor"] == STABLE_ACTOR_HASH


def test_control_routes_body_limit_and_rate_limit_fail_closed(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"status": "DRAFT"}})

    client = _client(tmp_path, handler)
    collection = "/control/v1/research/proposals"
    session = client.get(collection)
    headers = {
        "Content-Type": "application/json",
        "Origin": ORIGIN,
        "X-CSRF-Token": session.headers["x-csrf-token"],
        "Idempotency-Key": "0123456789abcdef",
    }
    oversized = client.post(collection, content=b'"' + b"x" * (16 * 1024) + b'"', headers=headers)
    assert oversized.status_code == 413
    assert oversized.json()["error"]["code"] == "CONTRACT_INVALID"

    for index in range(11):
        response = client.post(
            collection,
            json={"index": index},
            headers={**headers, "Idempotency-Key": f"fixture-key-{index:04d}"},
        )
        assert response.status_code == 200
    limited = client.post(
        collection,
        json={"index": 12},
        headers={**headers, "Idempotency-Key": "fixture-key-0012"},
    )
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "RATE_LIMITED"

    for forbidden in ("freeze", "release", "enqueue", "run", "delete"):
        response = client.post(
            f"{collection}/{PROPOSAL_ID}/commands/{forbidden}",
            json={},
            headers=headers,
        )
        assert response.status_code == 404


def test_control_path_allowlist_is_exact() -> None:
    collection = "/control/v1/research/proposals"
    detail = f"{collection}/{PROPOSAL_ID}"
    assert allowed_control_path(collection, "GET")
    assert allowed_control_path(collection, "POST")
    assert allowed_control_path(detail, "GET")
    assert allowed_control_path(f"{detail}/commands/submit-review", "POST")
    assert allowed_control_path(f"{detail}/commands/cancel", "POST")
    assert not allowed_control_path(detail, "POST")
    assert not allowed_control_path(f"{detail}/commands/run", "POST")
    assert not allowed_control_path(f"{collection}/../../.env", "GET")

"""FastAPI surface for the internal M5 proposal-only control plane."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import Response

from .authority import AuthorityError, load_authority
from .models import CancelCommand, ProposalCreate, SubmitReviewCommand, canonical_json, sha256_text
from .security import InternalSecurity, SecurityError, read_proxy_token, require_idempotency_key
from .service import ControlError, ProposalService
from .storage import SQLiteStore, StorageError


def _error_response(code: str, status_code: int, message: str) -> Response:
    return Response(
        canonical_json({"error": {"code": code, "message": message}}),
        status_code=status_code,
        media_type="application/json",
    )


def _stored_response(stored: object) -> Response:
    headers = {"Idempotent-Replayed": "true"} if stored.replayed else {}
    return Response(
        stored.body_json, status_code=stored.status_code, media_type="application/json", headers=headers
    )


def _admit_write(security: InternalSecurity, request: Request, route: str, payload: object) -> str:
    key = require_idempotency_key(request)
    identity = sha256_text(canonical_json(payload.model_dump(mode="json")))
    security.admit_mutation(request.state.actor, route, key, identity)
    return key


def _default_project_root() -> Path:
    return Path(__file__).parents[3]


def _install_boundary(app: FastAPI, security: InternalSecurity, maximum_request_bytes: int) -> None:
    @app.middleware("http")
    async def enforce_internal_boundary(request: Request, call_next: Callable) -> Response:
        if request.url.path.startswith("/control/"):
            try:
                request.state.actor = security.actor(request)
            except SecurityError as exc:
                return _error_response(exc.code, exc.status_code, exc.message)
        if request.method == "POST" and request.url.path.startswith("/control/"):
            content_length = request.headers.get("content-length")
            if content_length and (
                not content_length.isdigit() or int(content_length) > maximum_request_bytes
            ):
                return _error_response("CONTRACT_INVALID", 413, "request body exceeds 16 KiB")
            body = await request.body()
            if len(body) > maximum_request_bytes:
                return _error_response("CONTRACT_INVALID", 413, "request body exceeds 16 KiB")
        return await call_next(request)


def _install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, __: RequestValidationError) -> Response:
        return _error_response("CONTRACT_INVALID", 422, "request does not match the frozen proposal contract")

    @app.exception_handler(ControlError)
    async def control_error(_: Request, exc: ControlError) -> Response:
        return _error_response(exc.code, exc.status_code, exc.message)

    @app.exception_handler(SecurityError)
    async def security_error(_: Request, exc: SecurityError) -> Response:
        return _error_response(exc.code, exc.status_code, exc.message)


def _install_routes(app: FastAPI, service: ProposalService, security: InternalSecurity) -> None:
    @app.api_route("/healthz", methods=["GET", "HEAD"])
    async def health() -> Response:
        service.ready()
        return Response(canonical_json({"status": "PASS"}), media_type="application/json")

    @app.get("/control/v1/research/proposals")
    async def list_proposals(request: Request) -> Response:
        return Response(canonical_json(service.list(request.state.actor)), media_type="application/json")

    @app.get("/control/v1/research/proposals/{proposal_id}")
    async def get_proposal(proposal_id: str, request: Request) -> Response:
        return Response(
            canonical_json(service.get(proposal_id, request.state.actor)), media_type="application/json"
        )

    @app.post("/control/v1/research/proposals")
    async def create_proposal(payload: ProposalCreate, request: Request) -> Response:
        route = "/control/v1/research/proposals"
        key = _admit_write(security, request, route, payload)
        return _stored_response(service.create(request.state.actor, key, payload))

    @app.post("/control/v1/research/proposals/{proposal_id}/commands/submit-review")
    async def submit_review(proposal_id: str, payload: SubmitReviewCommand, request: Request) -> Response:
        route = f"/control/v1/research/proposals/{proposal_id}/commands/submit-review"
        key = _admit_write(security, request, route, payload)
        return _stored_response(
            service.transition(proposal_id, request.state.actor, key, payload, kind="submit-review")
        )

    @app.post("/control/v1/research/proposals/{proposal_id}/commands/cancel")
    async def cancel(proposal_id: str, payload: CancelCommand, request: Request) -> Response:
        route = f"/control/v1/research/proposals/{proposal_id}/commands/cancel"
        key = _admit_write(security, request, route, payload)
        return _stored_response(
            service.transition(proposal_id, request.state.actor, key, payload, kind="cancel")
        )


def create_app(
    *,
    project_root: Path | None = None,
    database_path: Path | None = None,
    proxy_token: str | None = None,
    clock: Callable[[], datetime] | None = None,
) -> FastAPI:
    """Create a fail-closed internal app; no environment variables are read."""
    root = (project_root or _default_project_root()).resolve(strict=True)
    try:
        authority = load_authority(root)
        storage = authority.storage
        if storage != {
            "schema_version": 1,
            "relative_database_path": "data/control/m5/research_control.sqlite3",
            "busy_timeout_ms": 2000,
            "journal_mode": "WAL",
            "synchronous": "FULL",
        }:
            raise AuthorityError("storage policy differs from the frozen contract")
        security_config = authority.browser_security
        token = proxy_token or read_proxy_token(Path(security_config["proxy_secret_path"]))
        target = database_path or root / storage["relative_database_path"]
        store = SQLiteStore(Path(target), busy_timeout_ms=storage["busy_timeout_ms"])
        service = ProposalService(authority, store, clock=clock)
        security = InternalSecurity(
            token,
            mutation_limit_per_minute=int(security_config["mutation_limit_per_minute"]),
        )
    except (AuthorityError, SecurityError, StorageError) as exc:
        raise RuntimeError("research-control refused to start") from exc

    app = FastAPI(title="Shaiwei M5 Research Control", version="1", docs_url=None, redoc_url=None)
    _install_boundary(app, security, int(security_config["maximum_request_bytes"]))
    _install_error_handlers(app)
    _install_routes(app, service, security)
    return app

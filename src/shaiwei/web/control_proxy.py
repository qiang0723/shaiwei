"""Narrow browser-to-control proxy for the M5 proposal-only surface."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import re
import secrets
import time
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.responses import Response
import httpx


CONTROL_PREFIX = "/control/v1/research/proposals"
PROPOSAL_ID_PATTERN = r"[a-z0-9][a-z0-9_-]{7,127}"
CONTROL_DETAIL_PATH = re.compile(rf"^{CONTROL_PREFIX}/{PROPOSAL_ID_PATTERN}$")
CONTROL_COMMAND_PATH = re.compile(
    rf"^{CONTROL_PREFIX}/{PROPOSAL_ID_PATTERN}/commands/(?:submit-review|cancel)$"
)
MAX_CONTROL_BODY_BYTES = 16 * 1024
MAX_CONTROL_RESPONSE_BYTES = 1_048_576
SESSION_COOKIE = "shaiwei_m5_control_session"
SESSION_TTL_SECONDS = 30 * 60
WRITE_LIMIT = 12
WRITE_WINDOW_SECONDS = 60
ACTOR_DOMAIN = b"m5-local-research-proposer-v1"
STABLE_ACTOR_HASH = hashlib.sha256(ACTOR_DOMAIN).hexdigest()


def allowed_control_path(path: str, method: str) -> bool:
    if path == CONTROL_PREFIX:
        return method in {"GET", "POST"}
    if CONTROL_DETAIL_PATH.fullmatch(path) is not None:
        return method == "GET"
    if CONTROL_COMMAND_PATH.fullmatch(path) is not None:
        return method == "POST"
    return False


@dataclass
class _Session:
    csrf_token: str
    expires_at: float
    writes: deque[float] = field(default_factory=deque)


def _error(code: str, message: str, status_code: int) -> Response:
    content = json.dumps(
        {
            "error": {
                "code": code,
                "message": message,
                "available_actions": [],
            }
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return Response(content, status_code=status_code, media_type="application/json")


def _read_token(path: Path | None, explicit: str | None) -> str | None:
    if explicit is not None:
        token = explicit.strip()
    elif path is not None:
        try:
            token = path.read_text(encoding="utf-8").strip()
        except OSError:
            return None
    else:
        return None
    return token if 16 <= len(token) <= 512 else None


class ProposalControlProxy:
    """Enforce the local session boundary before forwarding exact control routes."""

    def __init__(
        self,
        *,
        base_url: str,
        allowed_origin: str,
        token: str | None = None,
        token_path: Path | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.allowed_origin = allowed_origin.rstrip("/")
        self.token = _read_token(token_path, token)
        self.transport = transport
        self.clock = clock
        self.sessions: dict[str, _Session] = {}

    def _prune(self, now: float) -> None:
        expired = [key for key, item in self.sessions.items() if item.expires_at <= now]
        for key in expired:
            self.sessions.pop(key, None)
        if len(self.sessions) > 256:
            oldest = sorted(self.sessions, key=lambda key: self.sessions[key].expires_at)
            for key in oldest[: len(self.sessions) - 256]:
                self.sessions.pop(key, None)

    def _session(self, request: Request, *, create: bool) -> tuple[str, _Session] | None:
        now = self.clock()
        self._prune(now)
        session_id = request.cookies.get(SESSION_COOKIE, "")
        current = self.sessions.get(session_id)
        if current is not None and current.expires_at > now:
            return session_id, current
        if not create:
            return None
        session_id = secrets.token_urlsafe(32)
        current = _Session(
            csrf_token=secrets.token_urlsafe(32),
            expires_at=now + SESSION_TTL_SECONDS,
        )
        self.sessions[session_id] = current
        return session_id, current

    def _origin_allowed(self, request: Request, *, required: bool) -> bool:
        origin = request.headers.get("origin")
        if origin is None:
            return not required
        return secrets.compare_digest(origin, self.allowed_origin)

    def _write_allowed(self, session: _Session) -> bool:
        now = self.clock()
        while session.writes and session.writes[0] <= now - WRITE_WINDOW_SECONDS:
            session.writes.popleft()
        if len(session.writes) >= WRITE_LIMIT:
            return False
        session.writes.append(now)
        return True

    @staticmethod
    async def _body(request: Request) -> bytes | Response:
        declared = request.headers.get("content-length")
        if declared is not None:
            try:
                if int(declared) > MAX_CONTROL_BODY_BYTES:
                    return _error("CONTRACT_INVALID", "请求内容超过16 KiB", 413)
            except ValueError:
                return _error("CONTRACT_INVALID", "请求长度无效", 422)
        chunks: list[bytes] = []
        size = 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > MAX_CONTROL_BODY_BYTES:
                return _error("CONTRACT_INVALID", "请求内容超过16 KiB", 413)
            chunks.append(chunk)
        return b"".join(chunks)

    @staticmethod
    def _session_headers(response: Response, session_id: str, session: _Session) -> None:
        response.headers["X-CSRF-Token"] = session.csrf_token
        response.set_cookie(
            SESSION_COOKIE,
            session_id,
            max_age=SESSION_TTL_SECONDS,
            httponly=True,
            samesite="strict",
            path="/control",
        )

    async def forward(self, request: Request) -> Response:
        is_write = request.method == "POST"
        if not self._origin_allowed(request, required=is_write):
            return _error("ORIGIN_REJECTED", "仅允许本机同源访问", 403)

        found = self._session(request, create=not is_write)
        if found is None:
            return _error("SESSION_REQUIRED", "请刷新提案目录以建立短会话", 401)
        session_id, session = found
        if is_write:
            if not self._write_allowed(session):
                return _error("RATE_LIMITED", "一分钟内最多提交12次写请求", 429)
            supplied = request.headers.get("x-csrf-token", "")
            if not supplied or not secrets.compare_digest(supplied, session.csrf_token):
                return _error("CSRF_REJECTED", "安全会话已失效，请刷新后重试", 403)
            idempotency_key = request.headers.get("idempotency-key", "")
            if not 16 <= len(idempotency_key) <= 128:
                return _error("CONTRACT_INVALID", "写请求缺少有效幂等键", 422)

        if self.token is None:
            response = _error("CONTROL_NOT_READY", "提案控制服务尚未就绪", 503)
            if not is_write:
                self._session_headers(response, session_id, session)
            return response

        body: bytes | None = None
        if is_write:
            if request.headers.get("content-type", "").split(";", 1)[0] != "application/json":
                return _error("CONTRACT_INVALID", "写请求必须使用JSON", 422)
            bounded = await self._body(request)
            if isinstance(bounded, Response):
                return bounded
            body = bounded

        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.token}",
            "X-M5-Control-Actor": STABLE_ACTOR_HASH,
        }
        if is_write:
            headers["Content-Type"] = "application/json"
            headers["Idempotency-Key"] = request.headers["idempotency-key"]
        try:
            async with httpx.AsyncClient(
                timeout=5.0,
                follow_redirects=False,
                trust_env=False,
                transport=self.transport,
            ) as client:
                upstream = await client.request(
                    request.method,
                    f"{self.base_url}{request.url.path}",
                    params=list(request.query_params.multi_items()),
                    headers=headers,
                    content=body,
                )
        except httpx.HTTPError:
            response = _error("CONTROL_NOT_READY", "提案控制服务当前不可用", 503)
            if not is_write:
                self._session_headers(response, session_id, session)
            return response
        if len(upstream.content) > MAX_CONTROL_RESPONSE_BYTES:
            return _error("CONTROL_NOT_READY", "提案控制服务响应超限", 503)
        response = Response(
            upstream.content,
            status_code=upstream.status_code,
            media_type="application/json",
            headers={"Cache-Control": "no-store"},
        )
        if not is_write:
            self._session_headers(response, session_id, session)
        return response


def register_proposal_control_routes(app: FastAPI, proxy: ProposalControlProxy) -> None:
    """Register only the five proposal routes frozen for M5-1."""

    @app.api_route(CONTROL_PREFIX, methods=["GET", "POST"])
    async def proposal_collection(request: Request) -> Response:
        return await proxy.forward(request)

    @app.api_route(f"{CONTROL_PREFIX}/{{proposal_id}}", methods=["GET"])
    async def proposal_detail(request: Request, proposal_id: str) -> Response:
        if not allowed_control_path(request.url.path, request.method):
            return Response("Not found", status_code=404, media_type="text/plain")
        return await proxy.forward(request)

    @app.api_route(
        f"{CONTROL_PREFIX}/{{proposal_id}}/commands/submit-review",
        methods=["POST"],
    )
    @app.api_route(
        f"{CONTROL_PREFIX}/{{proposal_id}}/commands/cancel",
        methods=["POST"],
    )
    async def proposal_command(request: Request, proposal_id: str) -> Response:
        if not allowed_control_path(request.url.path, request.method):
            return Response("Not found", status_code=404, media_type="text/plain")
        return await proxy.forward(request)

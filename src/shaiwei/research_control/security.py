"""Internal proxy authentication and bounded mutation admission."""

from __future__ import annotations

import hmac
import hashlib
import re
import threading
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Callable

from starlette.requests import Request

ACTOR_RE = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_ACTOR_SHA256 = hashlib.sha256(b"m5-local-research-proposer-v1").hexdigest()
IDEMPOTENCY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{15,127}$")


class SecurityError(RuntimeError):
    def __init__(self, code: str, status_code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.message = message


def read_proxy_token(path: Path) -> str:
    """Read the Docker secret without consulting environment variables."""
    try:
        if path.is_symlink() or not path.is_file():
            raise SecurityError("CONTROL_NOT_READY", 503, "proxy token is unavailable")
        token = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise SecurityError("CONTROL_NOT_READY", 503, "proxy token is unavailable") from exc
    if not 32 <= len(token) <= 512 or any(char.isspace() for char in token):
        raise SecurityError("CONTROL_NOT_READY", 503, "proxy token is invalid")
    return token


class MutationLimiter:
    def __init__(self, limit: int, *, clock: Callable[[], float] = time.monotonic) -> None:
        self.limit = limit
        self.clock = clock
        self._events: dict[str, deque[tuple[float, str, str, str]]] = defaultdict(deque)
        self._lock = threading.Lock()

    def admit(self, actor: str, route: str, idempotency_key: str, request_sha256: str) -> None:
        now = float(self.clock())
        with self._lock:
            events = self._events[actor]
            while events and events[0][0] <= now - 60:
                events.popleft()
            identity = (route, idempotency_key, request_sha256)
            if any(stored[1:] == identity for stored in events):
                return
            if len(events) >= self.limit:
                raise SecurityError("RATE_LIMITED", 429, "mutation rate limit exceeded")
            events.append((now, *identity))


class InternalSecurity:
    """Trust only a private proxy token and a pre-hashed logical actor."""

    def __init__(self, proxy_token: str, *, mutation_limit_per_minute: int) -> None:
        if not 32 <= len(proxy_token) <= 512:
            raise SecurityError("CONTROL_NOT_READY", 503, "proxy token is invalid")
        self._proxy_token = proxy_token
        self._limiter = MutationLimiter(mutation_limit_per_minute)

    def actor(self, request: Request) -> str:
        authorization = request.headers.get("authorization", "")
        expected = f"Bearer {self._proxy_token}"
        if not hmac.compare_digest(authorization, expected):
            raise SecurityError("SESSION_REQUIRED", 401, "trusted proxy authentication is required")
        actor = request.headers.get("x-m5-control-actor", "")
        if not ACTOR_RE.fullmatch(actor) or not hmac.compare_digest(actor, EXPECTED_ACTOR_SHA256):
            raise SecurityError("ROLE_NOT_ALLOWED", 403, "a hashed research proposer actor is required")
        return actor

    def admit_mutation(self, actor: str, route: str, idempotency_key: str, request_sha256: str) -> None:
        self._limiter.admit(actor, route, idempotency_key, request_sha256)


def require_idempotency_key(request: Request) -> str:
    value = request.headers.get("idempotency-key", "")
    if not IDEMPOTENCY_RE.fullmatch(value):
        raise SecurityError("CONTRACT_INVALID", 422, "Idempotency-Key must contain 16-128 safe characters")
    return value

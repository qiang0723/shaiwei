"""Local-only Web 1.0 static UI and narrow reverse proxy for the query service."""

from __future__ import annotations

import mimetypes
import os
from pathlib import Path
import re
import secrets
from typing import Awaitable, Callable

from fastapi import FastAPI, Request
import httpx
from fastapi.responses import FileResponse, Response


MAX_RESPONSE_BYTES = 1_048_576
MAX_STATIC_BYTES = 3_145_728
ALLOWED_METHODS = {"GET", "HEAD"}
ALLOWED_UI_PATHS = {
    "/",
    "/overview",
    "/paper",
    "/signals",
    "/data-quality",
    "/system-runs",
}
ALLOWED_API_PATHS = {
    "/api/v1/overview",
    "/api/v1/paper/portfolio",
    "/api/v1/paper/nav",
    "/api/v1/paper/forward",
    "/api/v1/paper/replay",
    "/api/v1/signals/latest",
    "/api/v1/signals/reconciliation",
    "/api/v1/data-quality",
    "/api/v1/system/runs",
}
ALLOWED_NOTIFICATION_PATH = re.compile(r"^/api/v1/notifications/[0-9a-f]{16}$")
ASSET_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
STYLE_NONCE_PLACEHOLDER = b"__P3_STYLE_NONCE__"


def _allowed_api_path(path: str) -> bool:
    return path in ALLOWED_API_PATHS or ALLOWED_NOTIFICATION_PATH.fullmatch(path) is not None


def _default_static_root() -> Path:
    return Path(__file__).resolve().parents[3] / "web-ui" / "dist"


def _security_headers(response: Response, *, style_nonce: str) -> Response:
    if "Cache-Control" not in response.headers:
        response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = (
        "camera=(), geolocation=(), microphone=(), payment=(), usb=()"
    )
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        f"style-src 'self' 'nonce-{style_nonce}' 'report-sample'; "
        "connect-src 'self'; "
        "img-src 'self' data:; "
        "font-src 'self' data:; "
        "object-src 'none'; "
        "base-uri 'none'; "
        "form-action 'none'; "
        "frame-ancestors 'none'"
    )
    return response


def _static_response(path: Path, *, head: bool, immutable: bool = False) -> Response:
    if not path.is_file() or path.is_symlink():
        return Response("Not found", status_code=404, media_type="text/plain")
    size = path.stat().st_size
    if size > MAX_STATIC_BYTES:
        return Response("Static asset too large", status_code=502, media_type="text/plain")
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    headers = {
        "Cache-Control": (
            "public, max-age=31536000, immutable" if immutable else "no-store"
        )
    }
    if head:
        headers["Content-Length"] = str(size)
        return Response(status_code=200, media_type=media_type, headers=headers)
    return FileResponse(path, media_type=media_type, headers=headers)


def _index_response(path: Path, *, head: bool, style_nonce: str) -> Response:
    if not path.is_file() or path.is_symlink():
        return Response("Not found", status_code=404, media_type="text/plain")
    if path.stat().st_size > MAX_STATIC_BYTES:
        return Response("Static asset too large", status_code=502, media_type="text/plain")
    content = path.read_bytes()
    if content.count(STYLE_NONCE_PLACEHOLDER) != 1:
        return Response("Static entry invalid", status_code=503, media_type="text/plain")
    content = content.replace(STYLE_NONCE_PLACEHOLDER, style_nonce.encode("ascii"))
    headers = {"Cache-Control": "no-store"}
    if head:
        headers["Content-Length"] = str(len(content))
        return Response(status_code=200, media_type="text/html", headers=headers)
    return Response(content, media_type="text/html", headers=headers)


def create_app(
    query_base_url: str | None = None,
    static_root: Path | None = None,
) -> FastAPI:
    base_url = (query_base_url or os.getenv("WEB_QUERY_BASE_URL", "http://web-query:8000")).rstrip(
        "/"
    )
    root = (
        Path(static_root).resolve()
        if static_root is not None
        else Path(os.getenv("WEB_UI_STATIC_DIR", _default_static_root())).resolve()
    )
    index_path = root / "index.html"
    assets_root = root / "assets"
    app = FastAPI(
        title="",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        redirect_slashes=False,
    )

    @app.middleware("http")
    async def local_read_only_boundary(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        style_nonce = secrets.token_urlsafe(18)
        request.state.style_nonce = style_nonce
        if request.method not in ALLOWED_METHODS:
            return _security_headers(
                Response("GET/HEAD only", status_code=405, media_type="text/plain"),
                style_nonce=style_nonce,
            )
        return _security_headers(await call_next(request), style_nonce=style_nonce)

    @app.api_route("/", methods=["GET", "HEAD"])
    @app.api_route("/overview", methods=["GET", "HEAD"])
    @app.api_route("/paper", methods=["GET", "HEAD"])
    @app.api_route("/signals", methods=["GET", "HEAD"])
    @app.api_route("/data-quality", methods=["GET", "HEAD"])
    @app.api_route("/system-runs", methods=["GET", "HEAD"])
    async def page(request: Request) -> Response:
        if request.url.path not in ALLOWED_UI_PATHS:
            return Response("Not found", status_code=404, media_type="text/plain")
        return _index_response(
            index_path,
            head=request.method == "HEAD",
            style_nonce=request.state.style_nonce,
        )

    @app.api_route("/assets/{filename}", methods=["GET", "HEAD"])
    async def asset(request: Request, filename: str) -> Response:
        if not ASSET_NAME.fullmatch(filename):
            return Response("Not found", status_code=404, media_type="text/plain")
        return _static_response(
            assets_root / filename,
            head=request.method == "HEAD",
            immutable=True,
        )

    @app.api_route("/healthz", methods=["GET", "HEAD"])
    async def health(request: Request) -> Response:
        status = "PASS" if index_path.is_file() else "FAIL"
        code = 200 if status == "PASS" else 503
        content = "" if request.method == "HEAD" else (
            f'{{"status":"{status}","service":"web-ui","static_ready":'
            f'{str(index_path.is_file()).lower()}}}'
        )
        return Response(content, status_code=code, media_type="application/json")

    @app.api_route("/api/{path:path}", methods=["GET", "HEAD"])
    async def proxy(request: Request, path: str) -> Response:
        api_path = f"/api/{path}"
        if not _allowed_api_path(api_path):
            return Response("Not found", status_code=404, media_type="text/plain")
        try:
            async with httpx.AsyncClient(
                timeout=5.0,
                follow_redirects=False,
                trust_env=False,
            ) as client:
                upstream = await client.request(
                    request.method,
                    f"{base_url}{api_path}",
                    params=list(request.query_params.multi_items()),
                    headers={
                        "Accept": "application/json",
                        **(
                            {"If-None-Match": request.headers["if-none-match"]}
                            if "if-none-match" in request.headers
                            else {}
                        ),
                    },
                )
        except httpx.HTTPError:
            return Response(
                '{"error":{"code":"UPSTREAM_UNAVAILABLE",'
                '"message":"只读查询服务不可用"}}',
                status_code=503,
                media_type="application/json",
            )
        if len(upstream.content) > MAX_RESPONSE_BYTES:
            return Response(
                '{"error":{"code":"UPSTREAM_RESPONSE_TOO_LARGE",'
                '"message":"上游响应超限"}}',
                status_code=502,
                media_type="application/json",
            )
        headers = {
            key: value
            for key, value in upstream.headers.items()
            if key.lower() in {"content-type", "etag", "cache-control"}
        }
        content = b"" if request.method == "HEAD" else upstream.content
        return Response(content, status_code=upstream.status_code, headers=headers)

    return app


app = create_app()

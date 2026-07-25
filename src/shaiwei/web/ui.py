"""Local-only P3-0 shell and narrow reverse proxy for the query service."""

from __future__ import annotations

import os
from typing import Awaitable, Callable

from fastapi import FastAPI, Request
import httpx
from fastapi.responses import HTMLResponse, Response


MAX_RESPONSE_BYTES = 1_048_576
ALLOWED_METHODS = {"GET", "HEAD"}
ALLOWED_API_PATHS = {
    "/api/v1/overview",
    "/api/v1/paper/portfolio",
    "/api/v1/paper/nav",
    "/api/v1/paper/forward",
    "/api/v1/paper/replay",
    "/api/v1/signals/latest",
    "/api/v1/signals/reconciliation",
}

INDEX_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>筛微 · Web 1.0 查询底座</title>
  <style>
    :root { color-scheme: light; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }
    * { box-sizing: border-box; }
    body { margin: 0; background: #f5f7fa; color: #172033; }
    main { max-width: 1120px; margin: 0 auto; padding: 48px 24px; }
    header { margin-bottom: 24px; }
    h1 { margin: 0 0 8px; font-size: 28px; letter-spacing: -.02em; }
    p { margin: 0; color: #657087; }
    .notice { margin-top: 16px; padding: 12px 16px; border: 1px solid #d9e1ec;
      border-radius: 10px; background: white; color: #48566d; }
    .grid { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 16px;
      margin-top: 24px; }
    .card { min-height: 132px; padding: 18px; border: 1px solid #e1e6ef;
      border-radius: 12px; background: white; box-shadow: 0 4px 18px rgba(38,51,77,.04); }
    .label { font-size: 13px; color: #758198; }
    .value { margin-top: 16px; font-size: 24px; font-variant-numeric: tabular-nums; }
    .sub { margin-top: 8px; font-size: 12px; color: #758198; }
    .pass { color: #137a4b; } .warn { color: #a55b00; } .fail { color: #b42318; }
    @media (max-width: 820px) { .grid { grid-template-columns: repeat(2,minmax(0,1fr)); } }
    @media (max-width: 480px) { main { padding: 28px 16px; }
      .grid { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
<main>
  <header>
    <h1>筛微 · Web 1.0 查询底座</h1>
    <p>只读、证据优先。本页仅用于 P3-0 连接与口径验收，不是最终界面。</p>
    <div class="notice" id="notice">正在读取原子总览快照…</div>
  </header>
  <section class="grid">
    <article class="card"><div class="label">综合状态</div><div class="value" id="status">—</div>
      <div class="sub" id="asof">—</div></article>
    <article class="card"><div class="label">模拟净资产</div><div class="value" id="nav">—</div>
      <div class="sub" id="accountday">—</div></article>
    <article class="card"><div class="label">最新目标</div><div class="value" id="targets">—</div>
      <div class="sub" id="signal">—</div></article>
    <article class="card"><div class="label">FORWARD 观察</div><div class="value" id="forward">—</div>
      <div class="sub" id="maturity">—</div></article>
  </section>
</main>
<script>
const safe = (value) => String(value ?? "—");
fetch("/api/v1/overview", {cache:"no-store"})
  .then(r => r.json().then(body => ({ok:r.ok, body})))
  .then(({ok, body}) => {
    if (!ok) throw new Error(body.error?.code || "QUERY_FAILED");
    const d = body.data;
    const status = document.querySelector("#status");
    status.textContent = safe(d.overall_status);
    status.className = "value " + (d.overall_status === "PASS" ? "pass" :
      d.overall_status === "FAIL" ? "fail" : "warn");
    document.querySelector("#asof").textContent = "截至 " + safe(d.as_of);
    document.querySelector("#nav").textContent =
      "¥" + Number(d.paper.net_asset).toLocaleString("zh-CN", {minimumFractionDigits:2});
    document.querySelector("#accountday").textContent = safe(d.paper.account_day);
    document.querySelector("#targets").textContent = safe(d.action.target_count) + " 只";
    document.querySelector("#signal").textContent = safe(d.action.signal_date);
    document.querySelector("#forward").textContent =
      safe(d.forward.forward_observation_count) + " 日";
    document.querySelector("#maturity").textContent = safe(d.forward.performance_maturity);
    document.querySelector("#notice").textContent =
      "原子快照 " + safe(d.snapshot_id).slice(0,12) + " · 账本重放 " +
      safe(d.paper.replay_status) + " · 北交所 0";
  })
  .catch(error => {
    const notice = document.querySelector("#notice");
    notice.textContent = "查询失败：" + safe(error.message);
    notice.className = "notice fail";
  });
</script>
</body>
</html>
"""


def _security_headers(response: Response) -> Response:
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; connect-src 'self'; "
        "img-src 'self' data:; frame-ancestors 'none'"
    )
    return response


def create_app(query_base_url: str | None = None) -> FastAPI:
    base_url = (query_base_url or os.getenv("WEB_QUERY_BASE_URL", "http://web-query:8000")).rstrip(
        "/"
    )
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
        if request.method not in ALLOWED_METHODS:
            return _security_headers(
                Response("GET/HEAD only", status_code=405, media_type="text/plain")
            )
        return _security_headers(await call_next(request))

    @app.api_route("/", methods=["GET", "HEAD"])
    async def index(request: Request) -> Response:
        if request.method == "HEAD":
            return HTMLResponse()
        return HTMLResponse(INDEX_HTML)

    @app.api_route("/healthz", methods=["GET", "HEAD"])
    async def health(request: Request) -> Response:
        content = "" if request.method == "HEAD" else '{"status":"PASS","service":"web-ui"}'
        return Response(content, media_type="application/json")

    @app.api_route("/api/{path:path}", methods=["GET", "HEAD"])
    async def proxy(request: Request, path: str) -> Response:
        api_path = f"/api/{path}"
        if api_path not in ALLOWED_API_PATHS:
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
                '{"error":{"code":"UPSTREAM_UNAVAILABLE","message":"只读查询服务不可用"}}',
                status_code=503,
                media_type="application/json",
            )
        if len(upstream.content) > MAX_RESPONSE_BYTES:
            return Response(
                '{"error":{"code":"UPSTREAM_RESPONSE_TOO_LARGE","message":"上游响应超限"}}',
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

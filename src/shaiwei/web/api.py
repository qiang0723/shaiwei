"""FastAPI transport for the P3-0 read-only query contracts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Awaitable, Callable, Literal

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import Response

from shaiwei.web.operations import (
    OperationsBundle,
    build_operations_snapshot,
    notification_for,
)
from shaiwei.web.query import (
    DEFAULT_ACCOUNT_ID,
    SCHEMA_VERSION,
    SnapshotBundle,
    WebQueryError,
    build_snapshot,
    nav_range,
    reconciliation_for,
)
from shaiwei.web.research_projection import (
    ResearchProjectionBundle,
    experiment_catalog,
    experiment_summary,
    factor_admission_history,
    factor_catalog,
    factor_compare,
    factor_detail,
    load_research_projection,
)
from shaiwei.web.strategy_factory import StrategyFactoryBundle, load_strategy_factory


MAX_RESPONSE_BYTES = 1_048_576
ALLOWED_METHODS = {"GET", "HEAD"}
PaperAccountId = Literal["model_baseline", "model_top20"]


def _request_id(request: Request, snapshot_id: str = "") -> str:
    payload = (
        f"{request.method}|{request.url.path}|{request.url.query}|{snapshot_id}"
    ).encode()
    return hashlib.sha256(payload).hexdigest()[:20]


def _json_response(
    request: Request,
    payload: dict[str, object],
    *,
    status_code: int = 200,
    etag: str | None = None,
) -> Response:
    body = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if len(body) > MAX_RESPONSE_BYTES:
        raise WebQueryError("CONFLICT", "响应超过 P3-0 固定上限")
    headers = {
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    }
    if etag is not None:
        headers["ETag"] = f'"{etag}"'
    if request.method == "HEAD":
        return Response(
            status_code=status_code,
            headers=headers,
            media_type="application/json",
        )
    return Response(
        content=body,
        status_code=status_code,
        headers=headers,
        media_type="application/json",
    )


def _success(
    request: Request,
    bundle: SnapshotBundle | OperationsBundle | ResearchProjectionBundle | StrategyFactoryBundle,
    data: dict[str, object],
    *,
    meta: dict[str, object] | None = None,
) -> Response:
    return _json_response(
        request,
        {
            "schema_version": SCHEMA_VERSION,
            "request_id": _request_id(request, bundle.snapshot_id),
            "data": data,
            "meta": bundle.meta if meta is None else meta,
        },
        etag=bundle.snapshot_id,
    )


def _error(request: Request, error: WebQueryError) -> Response:
    return _json_response(
        request,
        {
            "schema_version": SCHEMA_VERSION,
            "request_id": _request_id(request),
            "error": {
                "code": error.code,
                "message": error.message,
                "retryable": error.retryable,
            },
        },
        status_code=error.status_code,
    )


def create_app(project_root: Path | None = None) -> FastAPI:
    root = None if project_root is None else Path(project_root).resolve()
    app = FastAPI(
        title="",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        redirect_slashes=False,
    )

    @app.middleware("http")
    async def read_only_boundary(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.method not in ALLOWED_METHODS:
            return _error(
                request,
                WebQueryError(
                    "INVALID_ARGUMENT",
                    "P3-0 只允许 GET/HEAD",
                    status_code=405,
                ),
            )
        return await call_next(request)

    @app.exception_handler(WebQueryError)
    async def web_query_error(request: Request, error: WebQueryError) -> Response:
        return _error(request, error)

    @app.exception_handler(RequestValidationError)
    async def validation_error(
        request: Request,
        _error_value: RequestValidationError,
    ) -> Response:
        return _error(
            request,
            WebQueryError(
                "INVALID_ARGUMENT",
                "查询参数无效或缺失",
                status_code=422,
            ),
        )

    @app.exception_handler(Exception)
    async def internal_error(request: Request, _error_value: Exception) -> Response:
        return _error(
            request,
            WebQueryError(
                "INTERNAL_ERROR",
                "只读查询发生内部错误",
                status_code=500,
            ),
        )

    def snapshot(
        as_of: str | None,
        account_id: PaperAccountId = DEFAULT_ACCOUNT_ID,
    ) -> SnapshotBundle:
        return build_snapshot(as_of, account_id=account_id, project_root=root)

    def operations_snapshot(as_of: str | None) -> OperationsBundle:
        return build_operations_snapshot(as_of, project_root=root)

    def research_snapshot() -> ResearchProjectionBundle:
        return load_research_projection(project_root=root)

    def strategy_factory_snapshot() -> StrategyFactoryBundle:
        return load_strategy_factory(project_root=root)

    @app.api_route("/healthz", methods=["GET", "HEAD"])
    async def health(request: Request) -> Response:
        return _json_response(
            request,
            {
                "schema_version": SCHEMA_VERSION,
                "request_id": _request_id(request),
                "data": {
                    "status": "PASS",
                    "service": "web-query",
                    "read_only": True,
                },
            },
        )

    @app.api_route("/api/v1/overview", methods=["GET", "HEAD"])
    async def overview(request: Request, as_of: str | None = None) -> Response:
        bundle = snapshot(as_of)
        return _success(request, bundle, bundle.overview)

    @app.api_route("/api/v1/paper/portfolio", methods=["GET", "HEAD"])
    async def paper_portfolio(
        request: Request,
        as_of: str | None = None,
        account_id: PaperAccountId = DEFAULT_ACCOUNT_ID,
    ) -> Response:
        bundle = snapshot(as_of, account_id)
        return _success(request, bundle, bundle.paper_portfolio)

    @app.api_route("/api/v1/paper/nav", methods=["GET", "HEAD"])
    async def paper_nav(
        request: Request,
        as_of: str | None = None,
        start: str | None = None,
        end: str | None = None,
        account_id: PaperAccountId = DEFAULT_ACCOUNT_ID,
    ) -> Response:
        bundle = snapshot(as_of, account_id)
        return _success(request, bundle, nav_range(bundle, start=start, end=end))

    @app.api_route("/api/v1/paper/forward", methods=["GET", "HEAD"])
    async def paper_forward(
        request: Request,
        as_of: str | None = None,
        account_id: PaperAccountId = DEFAULT_ACCOUNT_ID,
    ) -> Response:
        bundle = snapshot(as_of, account_id)
        return _success(request, bundle, bundle.paper_forward)

    @app.api_route("/api/v1/paper/replay", methods=["GET", "HEAD"])
    async def paper_replay(
        request: Request,
        as_of: str | None = None,
        account_id: PaperAccountId = DEFAULT_ACCOUNT_ID,
    ) -> Response:
        bundle = snapshot(as_of, account_id)
        return _success(request, bundle, bundle.paper_replay)

    @app.api_route("/api/v1/signals/latest", methods=["GET", "HEAD"])
    async def latest_signal(request: Request, as_of: str | None = None) -> Response:
        bundle = snapshot(as_of)
        return _success(request, bundle, bundle.latest_signal)

    @app.api_route("/api/v1/signals/reconciliation", methods=["GET", "HEAD"])
    async def signal_reconciliation(
        request: Request,
        signal_sha256: str = Query(..., min_length=64, max_length=64),
        as_of: str | None = None,
    ) -> Response:
        bundle = snapshot(as_of)
        return _success(
            request,
            bundle,
            reconciliation_for(bundle, signal_sha256),
        )

    @app.api_route("/api/v1/factors", methods=["GET", "HEAD"])
    async def factors(
        request: Request,
        status: str | None = None,
        family: str | None = None,
        data_category: str | None = None,
        as_of: str | None = None,
    ) -> Response:
        bundle = research_snapshot()
        return _success(
            request,
            bundle,
            factor_catalog(
                bundle,
                status=status,
                family=family,
                data_category=data_category,
                as_of=as_of,
            ),
            meta=bundle.meta_for(as_of),
        )

    @app.api_route("/api/v1/strategy-factory", methods=["GET", "HEAD"])
    async def strategy_factory(request: Request) -> Response:
        if request.query_params:
            raise WebQueryError(
                "INVALID_ARGUMENT",
                "策略工厂当前不接受查询参数",
                status_code=422,
            )
        bundle = strategy_factory_snapshot()
        return _success(request, bundle, bundle.data)

    @app.api_route("/api/v1/factors/compare", methods=["GET", "HEAD"])
    async def factors_compare(
        request: Request,
        version: list[str] = Query(..., min_length=2, max_length=3),
    ) -> Response:
        bundle = research_snapshot()
        return _success(request, bundle, factor_compare(bundle, version))

    @app.api_route("/api/v1/factors/{factor_id}/admissions", methods=["GET", "HEAD"])
    async def factor_admissions(
        request: Request,
        factor_id: str,
        as_of: str | None = None,
    ) -> Response:
        bundle = research_snapshot()
        return _success(
            request,
            bundle,
            factor_admission_history(bundle, factor_id, as_of=as_of),
            meta=bundle.meta_for(as_of),
        )

    @app.api_route("/api/v1/factors/{factor_id}", methods=["GET", "HEAD"])
    async def factor_by_id(
        request: Request,
        factor_id: str,
        version: str | None = None,
        as_of: str | None = None,
    ) -> Response:
        bundle = research_snapshot()
        return _success(
            request,
            bundle,
            factor_detail(bundle, factor_id, version=version, as_of=as_of),
            meta=bundle.meta_for(as_of),
        )

    @app.api_route(
        "/api/v1/experiments",
        methods=["GET", "HEAD"],
    )
    async def experiments_catalog(
        request: Request,
        experiment_kind: str | None = None,
        research_family: str | None = None,
        evidence_tier: str | None = None,
        authority_status: str | None = None,
        lifecycle_status: str | None = None,
        outcome_status: str | None = None,
        evidence_status: str | None = None,
        as_of: str | None = None,
        offset: int = Query(0, ge=0),
        limit: int = Query(25, ge=1, le=100),
    ) -> Response:
        allowed_parameters = {
            "experiment_kind",
            "research_family",
            "evidence_tier",
            "authority_status",
            "lifecycle_status",
            "outcome_status",
            "evidence_status",
            "as_of",
            "offset",
            "limit",
        }
        if set(request.query_params) - allowed_parameters or any(
            len(request.query_params.getlist(key)) > 1 for key in allowed_parameters
        ):
            raise WebQueryError(
                "INVALID_ARGUMENT",
                "实验目录包含未知或重复查询参数",
                status_code=422,
            )
        bundle = research_snapshot()
        return _success(
            request,
            bundle,
            experiment_catalog(
                bundle,
                experiment_kind=experiment_kind,
                research_family=research_family,
                evidence_tier=evidence_tier,
                authority_status=authority_status,
                lifecycle_status=lifecycle_status,
                outcome_status=outcome_status,
                evidence_status=evidence_status,
                as_of=as_of,
                offset=offset,
                limit=limit,
            ),
            meta=bundle.meta_for(as_of),
        )

    @app.api_route(
        "/api/v1/experiments/{experiment_kind}/{experiment_id}",
        methods=["GET", "HEAD"],
    )
    async def experiment_by_id(
        request: Request,
        experiment_kind: str,
        experiment_id: str,
        as_of: str | None = None,
    ) -> Response:
        if set(request.query_params) - {"as_of"} or len(
            request.query_params.getlist("as_of")
        ) > 1:
            raise WebQueryError(
                "INVALID_ARGUMENT",
                "实验详情包含未知或重复查询参数",
                status_code=422,
            )
        bundle = research_snapshot()
        return _success(
            request,
            bundle,
            experiment_summary(
                bundle,
                experiment_kind,
                experiment_id,
                as_of=as_of,
            ),
            meta=bundle.meta_for(as_of),
        )

    @app.api_route("/api/v1/data-quality", methods=["GET", "HEAD"])
    async def data_quality(request: Request, as_of: str | None = None) -> Response:
        bundle = operations_snapshot(as_of)
        return _success(request, bundle, bundle.data_quality)

    @app.api_route("/api/v1/system/runs", methods=["GET", "HEAD"])
    async def system_runs(request: Request, as_of: str | None = None) -> Response:
        bundle = operations_snapshot(as_of)
        return _success(request, bundle, bundle.system_run)

    @app.api_route("/api/v1/notifications/{message_id}", methods=["GET", "HEAD"])
    async def notification_delivery(
        request: Request,
        message_id: str,
        as_of: str | None = None,
    ) -> Response:
        bundle = operations_snapshot(as_of)
        return _success(request, bundle, notification_for(bundle, message_id))

    return app


app = create_app()

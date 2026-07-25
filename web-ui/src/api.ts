import type {
  ApiEnvelope,
  ApiErrorEnvelope,
  ApiMeta,
  ForwardData,
  NavData,
  OverviewData,
  PaperBundle,
  PortfolioData,
  ReplayData,
  SignalData
} from "./types";
import {
  assertEnvelope,
  assertForward,
  assertNav,
  assertOverview,
  assertPortfolio,
  assertReplay,
  assertSignal
} from "./validation";

export class UiQueryError extends Error {
  readonly code: string;
  readonly requestId?: string;
  readonly retryable: boolean;

  constructor(
    code: string,
    message: string,
    options: { requestId?: string; retryable?: boolean } = {}
  ) {
    super(message);
    this.name = "UiQueryError";
    this.code = code;
    this.requestId = options.requestId;
    this.retryable = options.retryable ?? false;
  }
}

function endpoint(path: string, asOf?: string): string {
  if (!asOf) return path;
  const search = new URLSearchParams({ as_of: asOf });
  return `${path}?${search.toString()}`;
}

async function getEnvelope<T>(
  path: string,
  asOf: string | undefined,
  signal: AbortSignal,
  validate: (value: unknown) => asserts value is T
): Promise<ApiEnvelope<T>> {
  let response: Response;
  try {
    response = await fetch(endpoint(path, asOf), {
      method: "GET",
      cache: "no-store",
      headers: { Accept: "application/json" },
      signal
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new UiQueryError("UPSTREAM_UNAVAILABLE", "只读查询服务当前不可用", {
      retryable: true
    });
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new UiQueryError("INVALID_RESPONSE", "查询服务返回了无效响应");
  }

  if (!response.ok) {
    const failure = body as ApiErrorEnvelope;
    throw new UiQueryError(
      failure.error?.code ?? "QUERY_FAILED",
      failure.error?.message ?? "只读查询失败",
      {
        requestId: failure.request_id,
        retryable: failure.error?.retryable
      }
    );
  }

  try {
    assertEnvelope(body);
    validate(body.data);
  } catch (error) {
    const message = error instanceof Error ? error.message : "响应证据校验失败";
    throw new UiQueryError("EVIDENCE_MISMATCH", message, {
      requestId: (body as Partial<ApiEnvelope<T>>).request_id
    });
  }
  return body as ApiEnvelope<T>;
}

export async function fetchOverview(
  asOf: string | undefined,
  signal: AbortSignal
): Promise<ApiEnvelope<OverviewData>> {
  return getEnvelope("/api/v1/overview", asOf, signal, assertOverview);
}

function assertSameSnapshot(envelopes: Array<ApiEnvelope<unknown>>): ApiMeta {
  const first = envelopes[0]?.meta;
  if (!first) throw new UiQueryError("CONFLICT", "组合响应缺少一致性身份");
  const consistent = envelopes.every(
    (item) =>
      item.schema_version === "web-v1" &&
      item.meta.snapshot_id === first.snapshot_id &&
      item.meta.as_of === first.as_of
  );
  if (!consistent) {
    throw new UiQueryError("CONFLICT", "组合查询跨越了不同证据快照，请重新读取");
  }
  return first;
}

export async function fetchPaperBundle(
  asOf: string | undefined,
  signal: AbortSignal
): Promise<PaperBundle> {
  const [portfolio, nav, forward, replay] = await Promise.all([
    getEnvelope("/api/v1/paper/portfolio", asOf, signal, assertPortfolio),
    getEnvelope("/api/v1/paper/nav", asOf, signal, assertNav),
    getEnvelope("/api/v1/paper/forward", asOf, signal, assertForward),
    getEnvelope("/api/v1/paper/replay", asOf, signal, assertReplay)
  ]);
  const meta = assertSameSnapshot([portfolio, nav, forward, replay]);
  return {
    snapshotId: meta.snapshot_id,
    asOf: meta.as_of,
    generatedAt: meta.generated_at,
    meta,
    portfolio: portfolio.data as PortfolioData,
    nav: nav.data as NavData,
    forward: forward.data as ForwardData,
    replay: replay.data as ReplayData
  };
}

export async function fetchSignal(
  asOf: string | undefined,
  signal: AbortSignal
): Promise<ApiEnvelope<SignalData>> {
  return getEnvelope("/api/v1/signals/latest", asOf, signal, assertSignal);
}

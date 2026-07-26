import type {
  ApiEnvelope,
  ApiErrorEnvelope,
  ApiMeta,
  DataQualityData,
  FactorAdmissionHistoryData,
  FactorCatalogData,
  FactorCompareData,
  FactorDetailData,
  ExperimentCatalogData,
  ExperimentDetailData,
  ExperimentKind,
  ForwardData,
  NavData,
  NotificationData,
  OverviewData,
  PaperAccountId,
  PaperBundle,
  PortfolioData,
  ReplayData,
  SignalData,
  SystemRunData
} from "./types";
import {
  assertDataQuality,
  assertEnvelope,
  assertFactorAdmissionHistory,
  assertFactorCatalog,
  assertFactorCompare,
  assertFactorDetail,
  assertExperimentCatalog,
  assertExperimentDetail,
  assertForward,
  assertNav,
  assertNotification,
  assertOverview,
  assertPortfolio,
  assertReplay,
  assertSignal,
  assertSystemRun
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

function endpoint(path: string, asOf?: string, parameters?: URLSearchParams): string {
  const search = new URLSearchParams(parameters);
  if (asOf) search.set("as_of", asOf);
  return search.size ? `${path}?${search.toString()}` : path;
}

async function getEnvelope<T>(
  path: string,
  asOf: string | undefined,
  signal: AbortSignal,
  validate: (value: unknown) => asserts value is T,
  parameters?: URLSearchParams
): Promise<ApiEnvelope<T>> {
  let response: Response;
  try {
    response = await fetch(endpoint(path, asOf, parameters), {
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
  signal: AbortSignal,
  accountId: PaperAccountId = "model_baseline"
): Promise<PaperBundle> {
  const parameters = new URLSearchParams({ account_id: accountId });
  const [portfolio, nav, forward, replay] = await Promise.all([
    getEnvelope("/api/v1/paper/portfolio", asOf, signal, assertPortfolio, parameters),
    getEnvelope("/api/v1/paper/nav", asOf, signal, assertNav, parameters),
    getEnvelope("/api/v1/paper/forward", asOf, signal, assertForward, parameters),
    getEnvelope("/api/v1/paper/replay", asOf, signal, assertReplay, parameters)
  ]);
  const meta = assertSameSnapshot([portfolio, nav, forward, replay]);
  if (
    portfolio.data.account_id !== accountId ||
    nav.data.account_id !== accountId ||
    replay.data.account_id !== accountId
  ) {
    throw new UiQueryError("EVIDENCE_MISMATCH", "组合响应与所选账户身份不一致");
  }
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

export async function fetchDataQuality(
  asOf: string | undefined,
  signal: AbortSignal
): Promise<ApiEnvelope<DataQualityData>> {
  return getEnvelope("/api/v1/data-quality", asOf, signal, assertDataQuality);
}

export async function fetchSystemRuns(
  asOf: string | undefined,
  signal: AbortSignal
): Promise<ApiEnvelope<SystemRunData>> {
  return getEnvelope("/api/v1/system/runs", asOf, signal, assertSystemRun);
}

export async function fetchNotification(
  messageId: string,
  asOf: string | undefined,
  signal: AbortSignal
): Promise<ApiEnvelope<NotificationData>> {
  if (!/^[0-9a-f]{16}$/.test(messageId)) {
    throw new UiQueryError("INVALID_ARGUMENT", "通知消息身份格式无效");
  }
  const envelope = await getEnvelope(
    `/api/v1/notifications/${messageId}`,
    asOf,
    signal,
    assertNotification
  );
  if (envelope.data.message_id !== messageId) {
    throw new UiQueryError("EVIDENCE_MISMATCH", "通知响应与请求身份不一致", {
      requestId: envelope.request_id
    });
  }
  return envelope;
}

const FACTOR_ID = /^[0-9a-f]{64}$/;
const FACTOR_VERSION = /^[0-9a-f]{12}$/;
const FACTOR_FILTER = /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/;

function requireFactorId(value: string): void {
  if (!FACTOR_ID.test(value)) throw new UiQueryError("INVALID_ARGUMENT", "因子身份格式无效");
}

function requireFactorVersion(value: string): void {
  if (!FACTOR_VERSION.test(value)) throw new UiQueryError("INVALID_ARGUMENT", "因子版本格式无效");
}

export async function fetchFactorCatalog(
  filters: {
    status: "ALL" | "ADMITTED" | "REJECTED" | "HISTORICAL_ONLY";
    family?: string;
    dataCategory?: string;
    asOf?: string;
  },
  signal: AbortSignal
): Promise<ApiEnvelope<FactorCatalogData>> {
  if (filters.family && !FACTOR_FILTER.test(filters.family)) {
    throw new UiQueryError("INVALID_ARGUMENT", "研究家族筛选格式无效");
  }
  if (filters.dataCategory && !FACTOR_FILTER.test(filters.dataCategory)) {
    throw new UiQueryError("INVALID_ARGUMENT", "数据类别筛选格式无效");
  }
  const parameters = new URLSearchParams({ status: filters.status });
  if (filters.family) parameters.set("family", filters.family);
  if (filters.dataCategory) parameters.set("data_category", filters.dataCategory);
  return getEnvelope(
    "/api/v1/factors",
    filters.asOf,
    signal,
    assertFactorCatalog,
    parameters
  );
}

export async function fetchFactorDetail(
  factorId: string,
  version: string | undefined,
  asOf: string | undefined,
  signal: AbortSignal
): Promise<ApiEnvelope<FactorDetailData>> {
  requireFactorId(factorId);
  const parameters = new URLSearchParams();
  if (version) {
    requireFactorVersion(version);
    parameters.set("version", version);
  }
  const envelope = await getEnvelope(
    `/api/v1/factors/${factorId}`,
    asOf,
    signal,
    assertFactorDetail,
    parameters
  );
  if (envelope.data.factor_id !== factorId || (version && envelope.data.factor_version !== version)) {
    throw new UiQueryError("EVIDENCE_MISMATCH", "因子详情响应与请求身份不一致", {
      requestId: envelope.request_id
    });
  }
  return envelope;
}

export async function fetchFactorAdmissionHistory(
  factorId: string,
  asOf: string | undefined,
  signal: AbortSignal
): Promise<ApiEnvelope<FactorAdmissionHistoryData>> {
  requireFactorId(factorId);
  const envelope = await getEnvelope(
    `/api/v1/factors/${factorId}/admissions`,
    asOf,
    signal,
    assertFactorAdmissionHistory
  );
  if (envelope.data.factor_id !== factorId) {
    throw new UiQueryError("EVIDENCE_MISMATCH", "准入历史响应与请求身份不一致", {
      requestId: envelope.request_id
    });
  }
  return envelope;
}

export async function fetchFactorCompare(
  versions: string[],
  signal: AbortSignal
): Promise<ApiEnvelope<FactorCompareData>> {
  if (versions.length < 2 || versions.length > 3 || new Set(versions).size !== versions.length) {
    throw new UiQueryError("INVALID_ARGUMENT", "比较必须选择 2—3 个不同版本");
  }
  const parameters = new URLSearchParams();
  versions.forEach((version) => {
    requireFactorVersion(version);
    parameters.append("version", version);
  });
  const envelope = await getEnvelope(
    "/api/v1/factors/compare",
    undefined,
    signal,
    assertFactorCompare,
    parameters
  );
  if (envelope.data.factor_versions.some((version, index) => version !== versions[index])) {
    throw new UiQueryError("EVIDENCE_MISMATCH", "因子比较响应改变了选择顺序", {
      requestId: envelope.request_id
    });
  }
  return envelope;
}

const EXPERIMENT_ID = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/;
const EXPERIMENT_FILTER = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/;
const EXPERIMENT_KINDS = new Set<ExperimentKind>([
  "research_experiment",
  "p2_engineering_run",
  "p2_effect_original",
  "p2_effect_correction"
]);

function requireExperimentKind(value: string): asserts value is ExperimentKind {
  if (!EXPERIMENT_KINDS.has(value as ExperimentKind)) {
    throw new UiQueryError("INVALID_ARGUMENT", "实验类型格式无效");
  }
}

function requireExperimentId(value: string): void {
  if (!EXPERIMENT_ID.test(value)) {
    throw new UiQueryError("INVALID_ARGUMENT", "实验身份格式无效");
  }
}

export async function fetchExperimentCatalog(
  filters: {
    experimentKind?: string;
    researchFamily?: string;
    evidenceTier?: string;
    authorityStatus?: string;
    lifecycleStatus?: string;
    outcomeStatus?: string;
    evidenceStatus?: string;
    asOf?: string;
    offset: number;
  },
  signal: AbortSignal
): Promise<ApiEnvelope<ExperimentCatalogData>> {
  if (!Number.isInteger(filters.offset) || filters.offset < 0) {
    throw new UiQueryError("INVALID_ARGUMENT", "实验目录 offset 无效");
  }
  const parameters = new URLSearchParams({
    offset: String(filters.offset),
    limit: "25"
  });
  const values: Array<[string, string | undefined]> = [
    ["experiment_kind", filters.experimentKind],
    ["research_family", filters.researchFamily],
    ["evidence_tier", filters.evidenceTier],
    ["authority_status", filters.authorityStatus],
    ["lifecycle_status", filters.lifecycleStatus],
    ["outcome_status", filters.outcomeStatus],
    ["evidence_status", filters.evidenceStatus]
  ];
  for (const [key, value] of values) {
    if (!value) continue;
    if (!EXPERIMENT_FILTER.test(value)) {
      throw new UiQueryError("INVALID_ARGUMENT", `${key} 筛选格式无效`);
    }
    parameters.set(key, value);
  }
  const envelope = await getEnvelope(
    "/api/v1/experiments",
    filters.asOf,
    signal,
    assertExperimentCatalog,
    parameters
  );
  const expectedFilters: Record<string, string | null> = {
    experiment_kind: filters.experimentKind ?? null,
    research_family: filters.researchFamily ?? null,
    evidence_tier: filters.evidenceTier ?? null,
    authority_status: filters.authorityStatus ?? null,
    lifecycle_status: filters.lifecycleStatus ?? null,
    outcome_status: filters.outcomeStatus ?? null,
    evidence_status: filters.evidenceStatus ?? null,
    as_of: filters.asOf || null
  };
  if (
    envelope.data.page.offset !== filters.offset ||
    envelope.data.page.limit !== 25 ||
    Object.entries(expectedFilters).some(
      ([key, expected]) => envelope.data.filters[key] !== expected
    )
  ) {
    throw new UiQueryError("EVIDENCE_MISMATCH", "实验目录响应改变了筛选或分页身份", {
      requestId: envelope.request_id
    });
  }
  return envelope;
}

export async function fetchExperimentDetail(
  kind: string,
  experimentId: string,
  asOf: string | undefined,
  signal: AbortSignal
): Promise<ApiEnvelope<ExperimentDetailData>> {
  requireExperimentKind(kind);
  requireExperimentId(experimentId);
  const envelope = await getEnvelope(
    `/api/v1/experiments/${kind}/${encodeURIComponent(experimentId)}`,
    asOf,
    signal,
    assertExperimentDetail
  );
  if (
    envelope.data.experiment_kind !== kind ||
    envelope.data.experiment_id !== experimentId
  ) {
    throw new UiQueryError("EVIDENCE_MISMATCH", "实验详情响应与请求身份不一致", {
      requestId: envelope.request_id
    });
  }
  return envelope;
}

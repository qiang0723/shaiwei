import type {
  ApiEnvelope,
  DomainStatus,
  ExperimentAuthorityStatus,
  ExperimentEvidenceStatus,
  ExperimentEvidenceTier,
  ExperimentKind,
  ExperimentLifecycleStatus,
  ExperimentOutcome,
  FactorAuthorityStatus,
  FactorLifecycleStatus
} from "../types";

const SHA256 = /^[0-9a-f]{64}$/;
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
export const MESSAGE_ID = /^[0-9a-f]{16}$/;
export const IMAGE_SHA256 = /^sha256:[0-9a-f]{64}$/;
const FACTOR_VERSION = /^[0-9a-f]{12}$/;
const EXPERIMENT_ID = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/;
const STATUS_VALUES = new Set<DomainStatus>([
  "PASS",
  "WARN",
  "FAIL",
  "STALE",
  "NOT_READY",
  "NOT_APPLICABLE",
  "NO_DATA",
  "OBSERVING",
  "NOT_DUE",
  "NOT_EVALUATED"
]);
const FACTOR_LIFECYCLE_VALUES = new Set<FactorLifecycleStatus>([
  "CANDIDATE",
  "TESTING",
  "REJECTED",
  "ADMITTED",
  "RETIRED"
]);
const FACTOR_AUTHORITY_VALUES = new Set<FactorAuthorityStatus>([
  "AUTHORITATIVE_CURRENT",
  "HISTORICAL_NON_AUTHORITATIVE",
  "SUPERSEDED_ENGINEERING_GENERATION",
  "INVALIDATED"
]);
export const EXPERIMENT_KIND_VALUES = new Set<ExperimentKind>([
  "research_experiment",
  "p2_engineering_run",
  "p2_effect_original",
  "p2_effect_correction"
]);
const EXPERIMENT_OUTCOME_VALUES = new Set<ExperimentOutcome>([
  "RECORDED",
  "FAILED",
  "DISCOVERY_ONLY",
  "DISCOVERY_REJECTED",
  "G1_REJECTED",
  "G1_ADMITTED",
  "REVIEW_STOPPED",
  "ENGINEERING_GO_ONLY",
  "HISTORICAL_EFFECT_REJECTED",
  "INVALIDATED_METHOD"
]);
const EXPERIMENT_TIER_VALUES = new Set<ExperimentEvidenceTier>([
  "BASELINE_BACKTEST",
  "SHADOW_SIGNAL",
  "FORWARD_SHADOW_SIGNAL",
  "G1_FACTOR_DECISION",
  "GP_DISCOVERY_ATTEMPT",
  "GP_STAGE1_ATTEMPT",
  "D1_DISCOVERY_ATTEMPT_WITH_REVIEW_OVERLAY",
  "P2_ENGINEERING",
  "P2_EFFECT_AUTHORITATIVE",
  "P2_EFFECT_INVALIDATED"
]);
const EXPERIMENT_AUTHORITY_VALUES = new Set<ExperimentAuthorityStatus>([
  "AUTHORITATIVE_CURRENT",
  "AUTHORITATIVE_STOP",
  "DISCOVERY_ONLY",
  "HISTORICAL_NON_AUTHORITATIVE",
  "INVALIDATED_METHOD",
  "PROVISIONAL_HISTORICAL",
  "RECORDED_EXPERIMENT",
  "SUPERSEDED_ENGINEERING_GENERATION"
]);
const EXPERIMENT_LIFECYCLE_VALUES = new Set<ExperimentLifecycleStatus>([
  "COMPLETED",
  "DISCOVERY_ATTEMPT",
  "DISCOVERY_EVALUATED",
  "ENGINEERING_GO_ONLY",
  "FAILED",
  "REJECT",
  "REJECTED",
  "REVIEW_STOPPED"
]);
const EXPERIMENT_EVIDENCE_VALUES = new Set<ExperimentEvidenceStatus>([
  "VERIFIED",
  "LEDGER_RECORDED_PROVISIONAL"
]);
export const DECISION_KEYS: Record<ExperimentEvidenceTier, Set<string>> = {
  BASELINE_BACKTEST: new Set(["status", "prediction_rows"]),
  SHADOW_SIGNAL: new Set(["score_rows", "signal_sha256"]),
  FORWARD_SHADOW_SIGNAL: new Set(["rebalance_due", "score_rows", "signal_sha256"]),
  G1_FACTOR_DECISION: new Set(["status", "recorded_decision", "trial_count", "all_gates"]),
  GP_DISCOVERY_ATTEMPT: new Set(["decision", "rank_ic"]),
  GP_STAGE1_ATTEMPT: new Set(["decision", "rank_ic"]),
  D1_DISCOVERY_ATTEMPT_WITH_REVIEW_OVERLAY: new Set([
    "discovery_status",
    "g1_run",
    "strategy_effective",
    "review_overlay",
    "human_gate_ready",
    "production_authorization",
    "review_roles"
  ]),
  P2_ENGINEERING: new Set([
    "verdict",
    "engineering_complete",
    "strategy_results_inspected",
    "strategy_effective",
    "production_authorization",
    "pipeline_fixture_pass",
    "idempotency_pass",
    "artifact_file_count"
  ]),
  P2_EFFECT_AUTHORITATIVE: new Set([
    "historical_effect_gate",
    "strategy_effective",
    "production_authorization",
    "window_gate_pass",
    "cost_gate_pass",
    "drawdown_gate_pass",
    "diversification_gate_status",
    "determinism_pass",
    "window_metrics",
    "pooled",
    "original_p2_2_model_valid",
    "original_p2_2_execution_valid",
    "results_known_before_correction"
  ]),
  P2_EFFECT_INVALIDATED: new Set([
    "historical_effect_gate",
    "strategy_effective",
    "production_authorization",
    "window_gate_pass",
    "cost_gate_pass",
    "drawdown_gate_pass",
    "diversification_gate_status",
    "determinism_pass",
    "window_metrics",
    "pooled",
    "numeric_results_status",
    "authoritative_successor_kind",
    "authoritative_successor_id"
  ])
};
export const TIER_OUTCOMES: Record<ExperimentEvidenceTier, Set<ExperimentOutcome>> = {
  BASELINE_BACKTEST: new Set(["RECORDED", "FAILED"]),
  SHADOW_SIGNAL: new Set(["RECORDED", "FAILED"]),
  FORWARD_SHADOW_SIGNAL: new Set(["RECORDED", "FAILED"]),
  G1_FACTOR_DECISION: new Set(["RECORDED", "FAILED", "G1_REJECTED", "G1_ADMITTED"]),
  GP_DISCOVERY_ATTEMPT: new Set(["DISCOVERY_ONLY", "FAILED"]),
  GP_STAGE1_ATTEMPT: new Set(["DISCOVERY_ONLY", "FAILED"]),
  D1_DISCOVERY_ATTEMPT_WITH_REVIEW_OVERLAY: new Set([
    "DISCOVERY_ONLY",
    "DISCOVERY_REJECTED",
    "REVIEW_STOPPED",
    "FAILED"
  ]),
  P2_ENGINEERING: new Set(["ENGINEERING_GO_ONLY"]),
  P2_EFFECT_AUTHORITATIVE: new Set(["HISTORICAL_EFFECT_REJECTED"]),
  P2_EFFECT_INVALIDATED: new Set(["INVALIDATED_METHOD"])
};

export function record(value: unknown, name: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`${name} 缺失或格式错误`);
  }
  return value as Record<string, unknown>;
}

export function text(value: unknown, name: string): string {
  if (typeof value !== "string" || !value) throw new Error(`${name} 缺失`);
  return value;
}

export function date(value: unknown, name: string): string {
  const result = text(value, name);
  if (!ISO_DATE.test(result)) throw new Error(`${name} 日期格式错误`);
  return result;
}

export function sha(value: unknown, name: string): string {
  const result = text(value, name);
  if (!SHA256.test(result)) throw new Error(`${name} 证据哈希格式错误`);
  return result;
}

export function numberLike(value: unknown, name: string): number {
  if ((typeof value !== "string" && typeof value !== "number") || !Number.isFinite(Number(value))) {
    throw new Error(`${name} 数值无效`);
  }
  return Number(value);
}

export function integer(value: unknown, name: string): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value < 0) {
    throw new Error(`${name} 计数无效`);
  }
  return value;
}

export function booleanValue(value: unknown, name: string): boolean {
  if (typeof value !== "boolean") throw new Error(`${name} 布尔值缺失`);
  return value;
}

export function timestamp(value: unknown, name: string): string {
  const result = text(value, name);
  if (!Number.isFinite(Date.parse(result)) || !/(?:Z|[+-]\d{2}:\d{2})$/.test(result)) {
    throw new Error(`${name} 时间格式错误`);
  }
  return result;
}

export function nullableText(value: unknown, name: string): string | null {
  if (value === null) return null;
  if (typeof value !== "string") throw new Error(`${name} 格式错误`);
  return value;
}

export function stringArray(value: unknown, name: string): string[] {
  if (!Array.isArray(value) || !value.every((item) => typeof item === "string")) {
    throw new Error(`${name} 格式错误`);
  }
  return value;
}

export function safeReference(value: unknown, name: string): string {
  const result = text(value, name);
  if (result.startsWith("/") || result.includes("..") || result.includes("://")) {
    throw new Error(`${name} 不是脱敏相对引用`);
  }
  return result;
}

export function status(value: unknown, name: string): DomainStatus {
  if (typeof value !== "string" || !STATUS_VALUES.has(value as DomainStatus)) {
    throw new Error(`${name} 返回未知状态`);
  }
  return value as DomainStatus;
}

export function noBse(value: unknown): void {
  if (typeof value === "string" && /\.BJ(?:\b|$)/i.test(value)) {
    throw new Error("查询返回禁止的北交所证券");
  }
  if (Array.isArray(value)) {
    value.forEach(noBse);
  } else if (typeof value === "object" && value !== null) {
    Object.values(value).forEach(noBse);
  }
}

export function hashMap(value: unknown, name: string): void {
  const hashes = record(value, name);
  Object.entries(hashes).forEach(([key, item]) => sha(item, `${name}.${key}`));
}

export function factorVersion(value: unknown, name: string): string {
  const result = text(value, name);
  if (!FACTOR_VERSION.test(result)) throw new Error(`${name} 因子版本格式错误`);
  return result;
}

export function factorLifecycle(value: unknown, name: string): FactorLifecycleStatus {
  if (typeof value !== "string" || !FACTOR_LIFECYCLE_VALUES.has(value as FactorLifecycleStatus)) {
    throw new Error(`${name} 返回未知生命周期`);
  }
  return value as FactorLifecycleStatus;
}

export function factorAuthority(value: unknown, name: string): FactorAuthorityStatus {
  if (typeof value !== "string" || !FACTOR_AUTHORITY_VALUES.has(value as FactorAuthorityStatus)) {
    throw new Error(`${name} 返回未知权威状态`);
  }
  return value as FactorAuthorityStatus;
}

export function experimentKind(value: unknown, name: string): ExperimentKind {
  if (typeof value !== "string" || !EXPERIMENT_KIND_VALUES.has(value as ExperimentKind)) {
    throw new Error(`${name} 返回未知实验类型`);
  }
  return value as ExperimentKind;
}

export function experimentId(value: unknown, name: string): string {
  const result = text(value, name);
  if (!EXPERIMENT_ID.test(result)) throw new Error(`${name} 实验身份格式错误`);
  return result;
}

export function experimentOutcome(value: unknown, name: string): ExperimentOutcome {
  if (typeof value !== "string" || !EXPERIMENT_OUTCOME_VALUES.has(value as ExperimentOutcome)) {
    throw new Error(`${name} 返回未知实验结论`);
  }
  return value as ExperimentOutcome;
}

export function experimentTier(value: unknown, name: string): ExperimentEvidenceTier {
  if (typeof value !== "string" || !EXPERIMENT_TIER_VALUES.has(value as ExperimentEvidenceTier)) {
    throw new Error(`${name} 返回未知证据层级`);
  }
  return value as ExperimentEvidenceTier;
}

export function experimentAuthority(value: unknown, name: string): ExperimentAuthorityStatus {
  if (
    typeof value !== "string" ||
    !EXPERIMENT_AUTHORITY_VALUES.has(value as ExperimentAuthorityStatus)
  ) {
    throw new Error(`${name} 返回未知权威状态`);
  }
  return value as ExperimentAuthorityStatus;
}

export function experimentLifecycle(value: unknown, name: string): ExperimentLifecycleStatus {
  if (
    typeof value !== "string" ||
    !EXPERIMENT_LIFECYCLE_VALUES.has(value as ExperimentLifecycleStatus)
  ) {
    throw new Error(`${name} 返回未知生命周期`);
  }
  return value as ExperimentLifecycleStatus;
}

export function experimentEvidence(value: unknown, name: string): ExperimentEvidenceStatus {
  if (
    typeof value !== "string" ||
    !EXPERIMENT_EVIDENCE_VALUES.has(value as ExperimentEvidenceStatus)
  ) {
    throw new Error(`${name} 返回未知证据状态`);
  }
  return value as ExperimentEvidenceStatus;
}

export function recordedDecision(value: unknown, name: string): "ADMITTED" | "REJECTED" {
  if (value !== "ADMITTED" && value !== "REJECTED") {
    throw new Error(`${name} 返回未知记录判决`);
  }
  return value;
}

export function finiteRecord(value: unknown, name: string): Record<string, number> {
  const result = record(value, name);
  Object.entries(result).forEach(([key, item]) => numberLike(item, `${name}.${key}`));
  return result as Record<string, number>;
}

export function jsonMetric(value: unknown, name: string): void {
  if (value === null || typeof value === "string" || typeof value === "boolean") return;
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new Error(`${name} 数值无效`);
    return;
  }
  if (Array.isArray(value)) {
    value.forEach((item, index) => jsonMetric(item, `${name}[${index}]`));
    return;
  }
  const result = record(value, name);
  Object.entries(result).forEach(([key, item]) => jsonMetric(item, `${name}.${key}`));
}

export function noForbiddenResearchPayload(value: unknown): void {
  if (Array.isArray(value)) {
    value.forEach(noForbiddenResearchPayload);
    return;
  }
  if (typeof value !== "object" || value === null) return;
  Object.entries(value).forEach(([key, item]) => {
    if (["params_json", "result_json", "daily_series", "predictions", "holdings"].includes(key)) {
      throw new Error(`研究响应包含禁止字段 ${key}`);
    }
    noForbiddenResearchPayload(item);
  });
}

export function unavailableSection(value: unknown, name: string): void {
  const section = record(value, name);
  if (section.status !== "NOT_EVALUATED" || section.recomputed !== false) {
    throw new Error(`${name} 不得补算或补零`);
  }
}

export function validateSixWindows(value: unknown, name: string): void {
  const windows = finiteRecord(value, name);
  const keys = Object.keys(windows).sort();
  if (keys.join("|") !== "W1|W2|W3|W4|W5|W6") {
    throw new Error(`${name} 必须完整包含六个冻结窗口`);
  }
}

export function validatePortfolio(value: unknown, name: string): void {
  const portfolio = record(value, name);
  for (const key of [
    "baseline_net_excess",
    "baseline_net_icir",
    "baseline_turnover",
    "candidate_net_excess",
    "candidate_net_icir",
    "candidate_turnover"
  ]) {
    numberLike(portfolio[key], `${name}.${key}`);
  }
}

export function validateCosts(value: unknown, name: string): void {
  const costs = record(value, name);
  numberLike(costs.cost_2x_net_excess, `${name}.cost_2x_net_excess`);
  numberLike(costs.slippage_2x_net_excess, `${name}.slippage_2x_net_excess`);
}

export function validateStatistics(value: unknown, name: string): void {
  const statistics = finiteRecord(value, name);
  for (const key of [
    "direction",
    "dsr_probability",
    "hac_t",
    "mean_oriented_oos_rank_ic",
    "positive_oos_windows",
    "rank_ic_retention",
    "trial_count",
    "turnover_ratio",
    "valid_trial_sharpes"
  ]) {
    if (!(key in statistics)) throw new Error(`${name}.${key} 缺失`);
  }
}

export function assertEnvelope(value: unknown): asserts value is ApiEnvelope<unknown> {
  const root = record(value, "响应");
  if (root.schema_version !== "web-v1") throw new Error("响应 schema_version 不受支持");
  text(root.request_id, "request_id");
  const meta = record(root.meta, "meta");
  date(meta.as_of, "meta.as_of");
  text(meta.generated_at, "meta.generated_at");
  if (meta.timezone !== "Asia/Shanghai") throw new Error("meta.timezone 不受支持");
  status(meta.freshness_status, "meta.freshness_status");
  sha(meta.snapshot_id, "meta.snapshot_id");
  if (!Array.isArray(meta.source_refs) || !meta.source_refs.every((item) => typeof item === "string")) {
    throw new Error("meta.source_refs 格式错误");
  }
  hashMap(meta.evidence_hashes, "meta.evidence_hashes");
  noBse(root.data);
}

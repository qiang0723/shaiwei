import type {
  ApiEnvelope,
  DataQualityData,
  DomainStatus,
  FactorAdmissionHistoryData,
  FactorAuthorityStatus,
  FactorCatalogData,
  FactorCompareData,
  FactorDetailData,
  FactorLifecycleStatus,
  ForwardData,
  NavData,
  NotificationData,
  OverviewData,
  PortfolioData,
  ReplayData,
  SignalData,
  SystemRunData
} from "./types";

const SHA256 = /^[0-9a-f]{64}$/;
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
const MESSAGE_ID = /^[0-9a-f]{16}$/;
const IMAGE_SHA256 = /^sha256:[0-9a-f]{64}$/;
const FACTOR_VERSION = /^[0-9a-f]{12}$/;
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

function record(value: unknown, name: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`${name} 缺失或格式错误`);
  }
  return value as Record<string, unknown>;
}

function text(value: unknown, name: string): string {
  if (typeof value !== "string" || !value) throw new Error(`${name} 缺失`);
  return value;
}

function date(value: unknown, name: string): string {
  const result = text(value, name);
  if (!ISO_DATE.test(result)) throw new Error(`${name} 日期格式错误`);
  return result;
}

function sha(value: unknown, name: string): string {
  const result = text(value, name);
  if (!SHA256.test(result)) throw new Error(`${name} 证据哈希格式错误`);
  return result;
}

function numberLike(value: unknown, name: string): number {
  if ((typeof value !== "string" && typeof value !== "number") || !Number.isFinite(Number(value))) {
    throw new Error(`${name} 数值无效`);
  }
  return Number(value);
}

function integer(value: unknown, name: string): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value < 0) {
    throw new Error(`${name} 计数无效`);
  }
  return value;
}

function booleanValue(value: unknown, name: string): boolean {
  if (typeof value !== "boolean") throw new Error(`${name} 布尔值缺失`);
  return value;
}

function timestamp(value: unknown, name: string): string {
  const result = text(value, name);
  if (!Number.isFinite(Date.parse(result)) || !/(?:Z|[+-]\d{2}:\d{2})$/.test(result)) {
    throw new Error(`${name} 时间格式错误`);
  }
  return result;
}

function nullableText(value: unknown, name: string): string | null {
  if (value === null) return null;
  if (typeof value !== "string") throw new Error(`${name} 格式错误`);
  return value;
}

function stringArray(value: unknown, name: string): string[] {
  if (!Array.isArray(value) || !value.every((item) => typeof item === "string")) {
    throw new Error(`${name} 格式错误`);
  }
  return value;
}

function safeReference(value: unknown, name: string): string {
  const result = text(value, name);
  if (result.startsWith("/") || result.includes("..") || result.includes("://")) {
    throw new Error(`${name} 不是脱敏相对引用`);
  }
  return result;
}

function status(value: unknown, name: string): DomainStatus {
  if (typeof value !== "string" || !STATUS_VALUES.has(value as DomainStatus)) {
    throw new Error(`${name} 返回未知状态`);
  }
  return value as DomainStatus;
}

function noBse(value: unknown): void {
  if (typeof value === "string" && /\.BJ(?:\b|$)/i.test(value)) {
    throw new Error("查询返回禁止的北交所证券");
  }
  if (Array.isArray(value)) {
    value.forEach(noBse);
  } else if (typeof value === "object" && value !== null) {
    Object.values(value).forEach(noBse);
  }
}

function hashMap(value: unknown, name: string): void {
  const hashes = record(value, name);
  Object.entries(hashes).forEach(([key, item]) => sha(item, `${name}.${key}`));
}

function factorVersion(value: unknown, name: string): string {
  const result = text(value, name);
  if (!FACTOR_VERSION.test(result)) throw new Error(`${name} 因子版本格式错误`);
  return result;
}

function factorLifecycle(value: unknown, name: string): FactorLifecycleStatus {
  if (typeof value !== "string" || !FACTOR_LIFECYCLE_VALUES.has(value as FactorLifecycleStatus)) {
    throw new Error(`${name} 返回未知生命周期`);
  }
  return value as FactorLifecycleStatus;
}

function factorAuthority(value: unknown, name: string): FactorAuthorityStatus {
  if (typeof value !== "string" || !FACTOR_AUTHORITY_VALUES.has(value as FactorAuthorityStatus)) {
    throw new Error(`${name} 返回未知权威状态`);
  }
  return value as FactorAuthorityStatus;
}

function recordedDecision(value: unknown, name: string): "ADMITTED" | "REJECTED" {
  if (value !== "ADMITTED" && value !== "REJECTED") {
    throw new Error(`${name} 返回未知记录判决`);
  }
  return value;
}

function finiteRecord(value: unknown, name: string): Record<string, number> {
  const result = record(value, name);
  Object.entries(result).forEach(([key, item]) => numberLike(item, `${name}.${key}`));
  return result as Record<string, number>;
}

function jsonMetric(value: unknown, name: string): void {
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

function noForbiddenResearchPayload(value: unknown): void {
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

function unavailableSection(value: unknown, name: string): void {
  const section = record(value, name);
  if (section.status !== "NOT_EVALUATED" || section.recomputed !== false) {
    throw new Error(`${name} 不得补算或补零`);
  }
}

function validateSixWindows(value: unknown, name: string): void {
  const windows = finiteRecord(value, name);
  const keys = Object.keys(windows).sort();
  if (keys.join("|") !== "W1|W2|W3|W4|W5|W6") {
    throw new Error(`${name} 必须完整包含六个冻结窗口`);
  }
}

function validatePortfolio(value: unknown, name: string): void {
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

function validateCosts(value: unknown, name: string): void {
  const costs = record(value, name);
  numberLike(costs.cost_2x_net_excess, `${name}.cost_2x_net_excess`);
  numberLike(costs.slippage_2x_net_excess, `${name}.slippage_2x_net_excess`);
}

function validateStatistics(value: unknown, name: string): void {
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

export function assertOverview(value: unknown): asserts value is OverviewData {
  const root = record(value, "总览");
  if (root.schema_version !== "web-v1") throw new Error("总览 schema_version 不受支持");
  sha(root.snapshot_id, "总览 snapshot_id");
  date(root.as_of, "总览 as_of");
  status(root.overall_status, "总览 overall_status");
  status(root.operational_status, "总览 operational_status");
  status(root.evidence_status, "总览 evidence_status");
  status(root.performance_observation_status, "总览 performance_observation_status");
  status(root.notification_status, "总览 notification_status");
  if (typeof root.required_evidence_complete !== "boolean") {
    throw new Error("总览 required_evidence_complete 缺失");
  }
  const action = record(root.action, "总览 action");
  date(action.signal_date, "总览 signal_date");
  sha(action.signal_sha256, "总览 signal_sha256");
  status(action.execution_evidence_status, "总览 execution_evidence_status");
  integer(action.target_count, "总览 target_count");
  integer(action.planned_trade_leg_count, "总览 planned_trade_leg_count");
  if (typeof action.rebalance_due !== "boolean") throw new Error("总览 rebalance_due 缺失");
  const paper = record(root.paper, "总览 paper");
  numberLike(paper.net_asset, "总览 net_asset");
  numberLike(paper.cash, "总览 cash");
  integer(paper.position_count, "总览 position_count");
  status(paper.replay_status, "总览 replay_status");
  const forward = record(root.forward, "总览 forward");
  status(forward.status, "总览 forward.status");
  status(forward.performance_maturity, "总览 performance_maturity");
  status(forward.coverage_status, "总览 coverage_status");
  integer(forward.forward_observation_count, "总览 forward_observation_count");
  if (forward.latest !== null) {
    const latest = record(forward.latest, "总览 forward.latest");
    numberLike(latest.forward_portfolio_nav, "总览 forward_portfolio_nav");
    numberLike(latest.forward_benchmark_nav, "总览 forward_benchmark_nav");
    numberLike(latest.forward_net_excess, "总览 forward_net_excess");
    numberLike(latest.forward_drawdown, "总览 forward_drawdown");
  }
  const runtime = record(root.runtime, "总览 runtime");
  status(runtime.task_status, "总览 task_status");
  const notification = record(runtime.notification, "总览 notification");
  status(notification.status, "总览 notification.status");
  const evidence = record(root.evidence, "总览 evidence");
  if (evidence.bse_count !== 0) throw new Error("总览北交所计数非零");
  sha(evidence.controlled_code_snapshot, "总览 controlled_code_snapshot");
  sha(evidence.data_snapshot_sha256, "总览 data_snapshot_sha256");
  sha(evidence.signal_sha256, "总览 evidence.signal_sha256");
  hashMap(evidence.evidence_hashes, "总览 evidence_hashes");
  noBse(value);
}

export function assertPortfolio(value: unknown): asserts value is PortfolioData {
  const root = record(value, "组合");
  if (root.bse_count !== 0) throw new Error("组合北交所计数非零");
  date(root.as_of, "组合 as_of");
  status(root.freshness_status, "组合 freshness_status");
  if (root.mode !== "BACKFILL" && root.mode !== "FORWARD") throw new Error("组合 mode 无效");
  ["cash", "market_value", "net_asset", "cash_ratio", "normalized_nav", "benchmark_nav", "drawdown"].forEach(
    (name) => numberLike(root[name], `组合 ${name}`)
  );
  hashMap(root.evidence_hashes, "组合 evidence_hashes");
  if (!Array.isArray(root.positions)) throw new Error("组合 positions 缺失");
  root.positions.forEach((item, index) => {
    const position = record(item, `组合 position[${index}]`);
    text(position.ts_code, `组合 position[${index}].ts_code`);
    ["actual_weight", "market_value", "cost_basis", "unrealized_pnl", "realized_pnl"].forEach(
      (name) => numberLike(position[name], `组合 position[${index}].${name}`)
    );
    integer(position.stale_trade_days, `组合 position[${index}].stale_trade_days`);
  });
  noBse(value);
}

export function assertNav(value: unknown): asserts value is NavData {
  const root = record(value, "净值");
  status(root.forward_status, "净值 forward_status");
  status(root.freshness_status, "净值 freshness_status");
  integer(root.observation_count, "净值 observation_count");
  integer(root.forward_observation_count, "净值 forward_observation_count");
  if (!Array.isArray(root.series) || root.series.length !== root.observation_count) {
    throw new Error("净值 series 数量与证据不一致");
  }
  root.series.forEach((item, index) => {
    const point = record(item, `净值 point[${index}]`);
    date(point.trade_date, `净值 point[${index}].trade_date`);
    if (point.mode !== "BACKFILL" && point.mode !== "FORWARD") throw new Error("净值 mode 无效");
    status(point.freshness_status, `净值 point[${index}].freshness_status`);
    ["normalized_nav", "benchmark_nav", "net_excess", "drawdown", "turnover", "cash_ratio", "daily_fees"].forEach(
      (name) => numberLike(point[name], `净值 point[${index}].${name}`)
    );
    sha(point.artifact_sha256, `净值 point[${index}].artifact_sha256`);
  });
  noBse(value);
}

export function assertForward(value: unknown): asserts value is ForwardData {
  const root = record(value, "前瞻");
  status(root.status, "前瞻 status");
  status(root.coverage_status, "前瞻 coverage_status");
  status(root.performance_maturity, "前瞻 performance_maturity");
  date(root.forward_anchor_trade_date, "前瞻 anchor date");
  sha(root.forward_anchor_artifact_sha256, "前瞻 anchor hash");
  integer(root.forward_observation_count, "前瞻 observation_count");
  if (!Array.isArray(root.series) || root.series.length !== root.forward_observation_count) {
    throw new Error("前瞻 series 数量与证据不一致");
  }
  root.series.forEach((item, index) => {
    const point = record(item, `前瞻 point[${index}]`);
    date(point.trade_date, `前瞻 point[${index}].trade_date`);
    ["forward_portfolio_nav", "forward_benchmark_nav", "forward_net_excess", "forward_drawdown"].forEach(
      (name) => numberLike(point[name], `前瞻 point[${index}].${name}`)
    );
    sha(point.artifact_sha256, `前瞻 point[${index}].artifact_sha256`);
  });
  noBse(value);
}

export function assertReplay(value: unknown): asserts value is ReplayData {
  const root = record(value, "重放");
  status(root.status, "重放 status");
  if (root.bse_count !== 0) throw new Error("重放北交所计数非零");
  ["run_count", "event_count", "order_count", "fill_count"].forEach((name) =>
    integer(root[name], `重放 ${name}`)
  );
  noBse(value);
}

export function assertSignal(value: unknown): asserts value is SignalData {
  const root = record(value, "信号");
  if (root.bse_count !== 0) throw new Error("信号北交所计数非零");
  date(root.signal_date, "信号 signal_date");
  status(root.execution_evidence_status, "信号 execution_evidence_status");
  status(root.metric_status, "信号 metric_status");
  integer(root.target_count, "信号 target_count");
  integer(root.planned_trade_leg_count, "信号 planned_trade_leg_count");
  [
    "signal_sha256",
    "code_snapshot_sha256",
    "data_snapshot_sha256",
    "model_spec_sha256",
    "model_artifact_sha256",
    "qlib_artifact_sha256",
    "source_file_sha256",
    "actual_weight_artifact_sha256"
  ].forEach((name) => sha(root[name], `信号 ${name}`));
  if (!Array.isArray(root.targets) || root.targets.length !== root.target_count) {
    throw new Error("信号目标数量与证据不一致");
  }
  root.targets.forEach((item, index) => {
    const target = record(item, `信号 target[${index}]`);
    text(target.ts_code, `信号 target[${index}].ts_code`);
    integer(target.rank, `信号 target[${index}].rank`);
    ["actual_weight", "planned_weight_delta", "score", "target_weight"].forEach((name) =>
      numberLike(target[name], `信号 target[${index}].${name}`)
    );
    if (!new Set(["ADDED", "RETAINED", "REMOVED"]).has(String(target.target_change))) {
      throw new Error("信号 target_change 未知");
    }
  });
  noBse(value);
}

function assertOperationsStage(value: unknown, name: string): Record<string, unknown> {
  const stage = record(value, name);
  text(stage.stage, `${name}.stage`);
  status(stage.status, `${name}.status`);
  const attempts = integer(stage.attempt_count, `${name}.attempt_count`);
  const failures = integer(stage.failed_attempt_count, `${name}.failed_attempt_count`);
  if (failures > attempts) throw new Error(`${name} 失败次数超过尝试数`);
  const recovered = booleanValue(stage.recovered, `${name}.recovered`);
  if (stage.status === "PASS" && failures > 0 && !recovered) {
    throw new Error(`${name} 隐藏了失败后恢复`);
  }
  nullableText(stage.first_error_type, `${name}.first_error_type`);
  if (stage.terminal_finished_at !== null) {
    timestamp(stage.terminal_finished_at, `${name}.terminal_finished_at`);
  }
  nullableText(stage.terminal_run_id, `${name}.terminal_run_id`);
  if (stage.evidence_status !== undefined) status(stage.evidence_status, `${name}.evidence_status`);
  if (stage.run_count !== undefined) integer(stage.run_count, `${name}.run_count`);
  if (stage.event_count !== undefined) integer(stage.event_count, `${name}.event_count`);
  return stage;
}

export function assertDataQuality(value: unknown): asserts value is DataQualityData {
  const root = record(value, "数据质量");
  status(root.status, "数据质量 status");
  const evidenceStatus = status(root.evidence_status, "数据质量 evidence_status");
  if (evidenceStatus !== "WARN") throw new Error("数据质量未保留哨兵证据 WARN");
  date(root.as_of, "数据质量 as_of");
  const dataSnapshot = sha(root.data_snapshot_sha256, "数据质量 data_snapshot_sha256");
  sha(root.code_snapshot_sha256, "数据质量 code_snapshot_sha256");
  const reasons = stringArray(root.status_reasons, "数据质量 status_reasons");
  if (!reasons.includes("SENTINEL_REPORT_NOT_HASH_BOUND")) {
    throw new Error("数据质量缺少哨兵未哈希绑定警告");
  }

  const daily = assertOperationsStage(root.daily_increment, "数据质量 daily_increment");
  if (daily.stage !== "daily_increment") throw new Error("数据质量日增量阶段身份错误");
  integer(daily.batch_count, "数据质量 daily_increment.batch_count");
  integer(daily.market_row_count, "数据质量 daily_increment.market_row_count");
  if (sha(daily.data_snapshot_sha256, "数据质量 daily_increment.data_snapshot") !== dataSnapshot) {
    throw new Error("数据质量日增量快照不一致");
  }

  const chain = record(root.batch_chain, "数据质量 batch_chain");
  integer(chain.registered_batch_count, "数据质量 registered_batch_count");
  integer(chain.registered_row_count, "数据质量 registered_row_count");
  const sourceCount = integer(chain.source_api_count, "数据质量 source_api_count");
  const sourceCounts = record(chain.source_api_batch_counts, "数据质量 source_api_batch_counts");
  if (Object.keys(sourceCounts).length !== sourceCount) throw new Error("数据来源数量与明细不一致");
  Object.entries(sourceCounts).forEach(([key, count]) => {
    text(key, "数据来源名称");
    integer(count, `数据来源 ${key}`);
  });
  if (
    sha(chain.reconstructed_data_snapshot_sha256, "数据质量 reconstructed_data_snapshot") !==
    dataSnapshot
  ) {
    throw new Error("数据质量登记身份链快照不一致");
  }
  if (chain.raw_parquet_rehash_status !== "NOT_EVALUATED") {
    throw new Error("数据质量错误声称原始 Parquet 已重验");
  }
  text(chain.raw_parquet_rehash_reason, "数据质量 raw_parquet_rehash_reason");
  const incrementalCount = integer(chain.incremental_batch_count, "数据质量 incremental_batch_count");
  if (!Array.isArray(chain.incremental_batches) || chain.incremental_batches.length !== incrementalCount) {
    throw new Error("数据质量当日批次数与明细不一致");
  }
  const batchIds = new Set<string>();
  chain.incremental_batches.forEach((item, index) => {
    const batch = record(item, `数据质量 batch[${index}]`);
    const batchId = text(batch.batch_id, `数据质量 batch[${index}].batch_id`);
    if (batchIds.has(batchId)) throw new Error("数据质量当日批次身份重复");
    batchIds.add(batchId);
    text(batch.source_api, `数据质量 batch[${index}].source_api`);
    integer(batch.row_count, `数据质量 batch[${index}].row_count`);
    timestamp(batch.ingest_time, `数据质量 batch[${index}].ingest_time`);
    sha(batch.content_sha256, `数据质量 batch[${index}].content_sha256`);
  });

  const sentinel = record(root.sentinel_gate, "数据质量 sentinel_gate");
  status(sentinel.status, "数据质量 sentinel status");
  if (sentinel.evidence_status !== "WARN") throw new Error("哨兵证据 WARN 被覆盖");
  if (sentinel.binding_status !== "IDENTITY_MATCH_UNHASHED") throw new Error("哨兵绑定语义被改变");
  if (sentinel.evidence_warning !== "SENTINEL_REPORT_NOT_HASH_BOUND") {
    throw new Error("哨兵证据警告缺失");
  }
  timestamp(sentinel.report_generated_at, "数据质量 sentinel report_generated_at");
  sha(sentinel.report_sha256, "数据质量 sentinel report_sha256");
  stringArray(sentinel.required_failures, "数据质量 sentinel required_failures");
  if (!Array.isArray(sentinel.sentinels) || sentinel.sentinels.length !== 10) {
    throw new Error("数据质量哨兵必须恰含 S1-S10");
  }
  const expectedSentinels = new Set(Array.from({ length: 10 }, (_, index) => `S${index + 1}`));
  sentinel.sentinels.forEach((item, index) => {
    const result = record(item, `数据质量 sentinel[${index}]`);
    const name = text(result.sentinel, `数据质量 sentinel[${index}].sentinel`);
    if (!expectedSentinels.delete(name)) throw new Error("数据质量哨兵重复或未知");
    const resultStatus = status(result.status, `数据质量 ${name}.status`);
    const accepted = booleanValue(result.accepted_for_signal, `数据质量 ${name}.accepted`);
    integer(result.anomaly_count, `数据质量 ${name}.anomaly_count`);
    record(result.metrics, `数据质量 ${name}.metrics`);
    const allowed = name === "S10" ? new Set(["PASS", "NOT_APPLICABLE"]) : new Set(["PASS"]);
    if (accepted !== allowed.has(resultStatus)) throw new Error(`数据质量 ${name} 接受语义不一致`);
  });
  if (expectedSentinels.size) throw new Error("数据质量哨兵缺项");

  const bse = record(root.bse_gate, "数据质量 bse_gate");
  status(bse.status, "数据质量 bse_gate.status");
  ["validated_market_batch_bse_count", "returned_security_bse_count", "excluded_bse_reference_count"].forEach(
    (name) => {
      if (integer(bse[name], `数据质量 ${name}`) !== 0) throw new Error("数据质量北交所计数非零");
    }
  );
  noBse(value);
}

export function assertSystemRun(value: unknown): asserts value is SystemRunData {
  const root = record(value, "系统运行");
  const overall = status(root.status, "系统运行 status");
  const core = status(root.core_status, "系统运行 core_status");
  status(root.notification_status, "系统运行 notification_status");
  if (overall !== core) throw new Error("系统运行综合状态与核心状态不一致");
  date(root.as_of, "系统运行 as_of");
  const messageCount = integer(root.core_failure_message_count, "系统运行 core_failure_message_count");
  const messageIds = stringArray(root.core_failure_message_ids, "系统运行 core_failure_message_ids");
  if (messageIds.length !== messageCount || !messageIds.every((item) => MESSAGE_ID.test(item))) {
    throw new Error("系统运行核心故障消息身份无效");
  }
  const expectedStages = [
    "daily_increment",
    "sentinels",
    "next_open_reconciliation",
    "shadow_signal",
    "paper_cycle",
    "paper_replay"
  ];
  if (!Array.isArray(root.stages) || root.stages.length !== expectedStages.length) {
    throw new Error("系统运行阶段数量错误");
  }
  root.stages.forEach((item, index) => {
    const stage = assertOperationsStage(item, `系统运行 stage[${index}]`);
    if (stage.stage !== expectedStages[index]) throw new Error("系统运行阶段顺序错误");
  });

  const notifications = record(root.notifications, "系统运行 notifications");
  status(notifications.status, "系统运行 notifications.status");
  [
    "message_count",
    "attempt_count",
    "failed_attempt_count",
    "recovered_message_count",
    "legacy_unaddressable_attempt_count"
  ].forEach((name) => integer(notifications[name], `系统运行 notifications.${name}`));

  const release = record(root.release_identity, "系统运行 release_identity");
  status(release.status, "系统运行 release.status");
  status(release.audit_chain_status, "系统运行 release.audit_chain_status");
  timestamp(release.recorded_at, "系统运行 release.recorded_at");
  if (typeof release.image_id !== "string" || !IMAGE_SHA256.test(release.image_id)) {
    throw new Error("系统运行 release 镜像身份无效");
  }
  sha(release.code_snapshot_sha256, "系统运行 release.code_snapshot_sha256");
  if (typeof release.git_head !== "string" || !/^(?:[0-9a-f]{40}|[0-9a-f]{64})$/.test(release.git_head)) {
    throw new Error("系统运行 release Git 身份无效");
  }
  if (booleanValue(release.read_only_rootfs, "系统运行 release.read_only_rootfs") !== true) {
    throw new Error("系统运行 release 不是只读根");
  }
  stringArray(release.mount_destinations, "系统运行 release.mount_destinations").forEach((item) => {
    if (!item.startsWith("/workspace/")) throw new Error("系统运行 release 挂载目标无效");
  });
  if (release.live_container_identity_status !== "NOT_EVALUATED") {
    throw new Error("系统运行错误声称已读取实时容器身份");
  }
  text(release.live_container_identity_reason, "系统运行 release.live_container_identity_reason");
  sha(release.record_sha256, "系统运行 release.record_sha256");

  const heartbeat = record(root.scheduler_heartbeat, "系统运行 scheduler_heartbeat");
  if (heartbeat.status !== "RECORDED" || heartbeat.scope !== "RECORDED_HEARTBEAT_ONLY") {
    throw new Error("系统运行 scheduler 心跳范围被扩大");
  }
  text(heartbeat.recorded_status, "系统运行 scheduler recorded_status");
  text(heartbeat.detail, "系统运行 scheduler detail");
  timestamp(heartbeat.updated_at, "系统运行 scheduler updated_at");
  if (heartbeat.freshness_status !== "NOT_EVALUATED") {
    throw new Error("系统运行错误推导 scheduler 实时新鲜度");
  }
  noBse(value);
}

export function assertNotification(value: unknown): asserts value is NotificationData {
  const root = record(value, "通知详情");
  const messageId = text(root.message_id, "通知详情 message_id");
  if (!MESSAGE_ID.test(messageId)) throw new Error("通知详情 message_id 无效");
  const event = text(root.event, "通知详情 event");
  status(root.status, "通知详情 status");
  const attemptCount = integer(root.attempt_count, "通知详情 attempt_count");
  const failedCount = integer(root.failed_attempt_count, "通知详情 failed_attempt_count");
  if (failedCount > attemptCount) throw new Error("通知详情失败次数超过尝试数");
  booleanValue(root.recovered, "通知详情 recovered");
  const duplicateRisk = booleanValue(root.duplicate_delivery_risk, "通知详情 duplicate_delivery_risk");
  if (!Array.isArray(root.attempts) || root.attempts.length !== attemptCount) {
    throw new Error("通知详情尝试数与明细不一致");
  }
  if (duplicateRisk !== (attemptCount > 1)) throw new Error("通知详情重复投递风险语义不一致");
  const identities = new Set<string>();
  root.attempts.forEach((item, index) => {
    const attempt = record(item, `通知详情 attempt[${index}]`);
    const number = integer(attempt.attempt, `通知详情 attempt[${index}].attempt`);
    const maximum = integer(attempt.max_attempts, `通知详情 attempt[${index}].max_attempts`);
    if (number < 1 || maximum < number) throw new Error("通知详情尝试序号无效");
    const deliveredAt = timestamp(attempt.delivered_at, `通知详情 attempt[${index}].delivered_at`);
    if (attempt.message_id !== messageId || attempt.event !== event) throw new Error("通知详情尝试身份不一致");
    status(attempt.status, `通知详情 attempt[${index}].status`);
    if (typeof attempt.error_type !== "string") throw new Error("通知详情 error_type 格式错误");
    booleanValue(attempt.recovered, `通知详情 attempt[${index}].recovered`);
    booleanValue(attempt.retryable, `通知详情 attempt[${index}].retryable`);
    safeReference(attempt.source_ref, `通知详情 attempt[${index}].source_ref`);
    const identity = `${number}|${deliveredAt}`;
    if (identities.has(identity)) throw new Error("通知详情尝试身份重复");
    identities.add(identity);
  });
  noBse(value);
}

export function assertFactorCatalog(value: unknown): asserts value is FactorCatalogData {
  const root = record(value, "因子目录");
  if (!Array.isArray(root.items)) throw new Error("因子目录 items 格式错误");
  const identities = new Set<string>();
  root.items.forEach((item, index) => {
    const row = record(item, `因子目录 item[${index}]`);
    const identity = sha(row.factor_id, `因子目录 item[${index}].factor_id`);
    if (identities.has(identity)) throw new Error("因子目录 factor_id 重复");
    identities.add(identity);
    if (row.identity_kind !== "FAMILY_SCOPED_EXACT_FORMULA_SHA256") {
      throw new Error("因子目录 identity_kind 不受支持");
    }
    text(row.research_family, `因子目录 item[${index}].research_family`);
    text(row.data_category, `因子目录 item[${index}].data_category`);
    factorLifecycle(row.lifecycle_status, `因子目录 item[${index}].lifecycle_status`);
    const authority = factorAuthority(
      row.authority_status,
      `因子目录 item[${index}].authority_status`
    );
    const versions = integer(row.version_count, `因子目录 item[${index}].version_count`);
    if (versions < 1) throw new Error("因子目录版本数必须大于 0");
    if (row.current_factor_version !== null) {
      factorVersion(row.current_factor_version, `因子目录 item[${index}].current_factor_version`);
    }
    if (authority === "AUTHORITATIVE_CURRENT" && row.current_factor_version === null) {
      throw new Error("当前权威因子缺少当前版本");
    }
    integer(row.experiment_attempt_n, `因子目录 item[${index}].experiment_attempt_n`);
    recordedDecision(row.latest_recorded_decision, `因子目录 item[${index}].latest_recorded_decision`);
    if (row.evidence_status !== "VERIFIED") throw new Error("因子目录证据未核验");
  });
  const counters = record(root.counters, "因子目录 counters");
  for (const key of [
    "formal_library_count",
    "researched_factor_count",
    "authoritative_rejected_count",
    "historical_only_count"
  ]) {
    integer(counters[key], `因子目录 counters.${key}`);
  }
  if (
    !Array.isArray(root.sort) ||
    root.sort.length !== 2 ||
    root.sort[0] !== "research_family" ||
    root.sort[1] !== "factor_id"
  ) {
    throw new Error("因子目录排序口径发生变化");
  }
  const banner = nullableText(root.historical_response_banner, "因子目录 historical_response_banner");
  if (banner !== null && banner !== "CURRENT_AUTHORITY_APPLIED_TO_HISTORICAL_RECORDS") {
    throw new Error("因子目录历史提示未知");
  }
  noForbiddenResearchPayload(value);
  noBse(value);
}

export function assertFactorDetail(value: unknown): asserts value is FactorDetailData {
  const root = record(value, "因子详情");
  sha(root.factor_id, "因子详情 factor_id");
  factorVersion(root.factor_version, "因子详情 factor_version");
  if (root.identity_kind !== "FAMILY_SCOPED_EXACT_FORMULA_SHA256") {
    throw new Error("因子详情 identity_kind 不受支持");
  }
  factorAuthority(root.authority_status, "因子详情 authority_status");
  factorLifecycle(root.lifecycle_status, "因子详情 lifecycle_status");
  recordedDecision(root.recorded_decision, "因子详情 recorded_decision");
  booleanValue(root.fallback_to_latest_historical, "因子详情 fallback_to_latest_historical");

  const sections = record(root.sections, "因子详情 sections");
  const identity = record(sections.identity, "因子详情 identity");
  factorVersion(identity.candidate_experiment_id, "因子详情 candidate_experiment_id");
  text(identity.research_family, "因子详情 research_family");
  text(identity.data_category, "因子详情 data_category");

  const definition = record(sections.frozen_definition_and_direction, "因子详情 definition");
  text(definition.feature_or_formula, "因子详情 feature_or_formula");
  numberLike(definition.direction, "因子详情 direction");
  text(definition.economic_rationale, "因子详情 economic_rationale");
  if ("normalized_expression" in definition && definition.normalized_expression !== null) {
    text(definition.normalized_expression, "因子详情 normalized_expression");
  }

  const pit = record(sections.pit_shift_and_complexity, "因子详情 PIT/shift");
  booleanValue(pit.pit_sentinel_pass, "因子详情 pit_sentinel_pass");
  booleanValue(pit.shift_sentinel_pass, "因子详情 shift_sentinel_pass");
  integer(pit.ast_nodes, "因子详情 ast_nodes");
  integer(pit.expression_tokens, "因子详情 expression_tokens");
  for (const key of ["max_lookback_days", "required_backtrack_days", "shift_compared_values"]) {
    if (pit[key] !== null) integer(pit[key], `因子详情 ${key}`);
  }

  const g1 = record(sections.g1_statistics_and_all_gates, "因子详情 G1");
  validateStatistics(g1.statistics, "因子详情 G1 statistics");
  const gates = record(g1.gates, "因子详情 G1 gates");
  if (Object.keys(gates).length !== 15) throw new Error("因子详情必须完整包含 15 项门");
  Object.entries(gates).forEach(([name, value]) => {
    const gate = record(value, `因子详情 G1 gate.${name}`);
    jsonMetric(gate.actual, `因子详情 G1 gate.${name}.actual`);
    booleanValue(gate.passed, `因子详情 G1 gate.${name}.passed`);
    text(gate.rule, `因子详情 G1 gate.${name}.rule`);
  });
  validateSixWindows(sections.six_oos_window_rank_ic, "因子详情六窗口");
  if (!Object.keys(finiteRecord(sections.stress_max_drawdown, "因子详情压力期")).length) {
    throw new Error("因子详情压力期缺失");
  }
  validatePortfolio(sections.turnover_and_incremental_portfolio, "因子详情组合");
  validateCosts(sections.cost_and_slippage_stress, "因子详情成本");
  numberLike(sections.library_max_abs_correlation, "因子详情因子库相关");
  for (const key of [
    "coverage_ratio",
    "quantile_returns_and_monotonicity",
    "factor_autocorrelation",
    "candidate_pool_correlation"
  ]) {
    unavailableSection(sections[key], `因子详情 ${key}`);
  }
  stringArray(root.source_refs, "因子详情 source_refs").forEach((item, index) =>
    safeReference(item, `因子详情 source_refs[${index}]`)
  );
  stringArray(root.evidence_hashes, "因子详情 evidence_hashes").forEach((item, index) =>
    sha(item, `因子详情 evidence_hashes[${index}]`)
  );
  const banner = nullableText(root.historical_response_banner, "因子详情 historical_response_banner");
  if (banner !== null && banner !== "CURRENT_AUTHORITY_APPLIED_TO_HISTORICAL_RECORDS") {
    throw new Error("因子详情历史提示未知");
  }
  noForbiddenResearchPayload(value);
  noBse(value);
}

export function assertFactorAdmissionHistory(
  value: unknown
): asserts value is FactorAdmissionHistoryData {
  const root = record(value, "因子准入历史");
  sha(root.factor_id, "因子准入历史 factor_id");
  if (root.append_only !== true) throw new Error("因子准入历史不是追加式");
  if (!Array.isArray(root.items) || root.items.length < 1) {
    throw new Error("因子准入历史 items 缺失");
  }
  let previous = "";
  const decisions = new Set<string>();
  root.items.forEach((item, index) => {
    const row = record(item, `因子准入历史 item[${index}]`);
    const decision = text(row.decision_id, `因子准入历史 item[${index}].decision_id`);
    if (decisions.has(decision)) throw new Error("因子准入历史 decision_id 重复");
    decisions.add(decision);
    const recordedAt = timestamp(row.recorded_at, `因子准入历史 item[${index}].recorded_at`);
    if (recordedAt < previous) throw new Error("因子准入历史未按追加顺序返回");
    previous = recordedAt;
    factorVersion(row.factor_version, `因子准入历史 item[${index}].factor_version`);
    recordedDecision(row.recorded_decision, `因子准入历史 item[${index}].recorded_decision`);
    factorAuthority(row.authority_status, `因子准入历史 item[${index}].authority_status`);
    integer(row.trial_count, `因子准入历史 item[${index}].trial_count`);
    stringArray(row.failed_gates, `因子准入历史 item[${index}].failed_gates`);
    text(row.decision_rule_version, `因子准入历史 item[${index}].decision_rule_version`);
    sha(row.evidence_sha256, `因子准入历史 item[${index}].evidence_sha256`);
    sha(row.report_sha256, `因子准入历史 item[${index}].report_sha256`);
  });
  const banner = nullableText(root.historical_response_banner, "因子准入历史 historical_response_banner");
  if (banner !== null && banner !== "CURRENT_AUTHORITY_APPLIED_TO_HISTORICAL_RECORDS") {
    throw new Error("因子准入历史提示未知");
  }
  noForbiddenResearchPayload(value);
  noBse(value);
}

export function assertFactorCompare(value: unknown): asserts value is FactorCompareData {
  const root = record(value, "因子比较");
  if (
    !Array.isArray(root.factor_versions) ||
    root.factor_versions.length < 2 ||
    root.factor_versions.length > 3
  ) {
    throw new Error("因子比较必须包含 2—3 个版本");
  }
  const versions = root.factor_versions as unknown[];
  versions.forEach((item, index) => factorVersion(item, `因子比较 version[${index}]`));
  if (new Set(versions).size !== versions.length) {
    throw new Error("因子比较版本重复");
  }
  const fingerprint = record(root.fingerprint, "因子比较 fingerprint");
  if (!Object.keys(fingerprint).length) throw new Error("因子比较 fingerprint 缺失");
  Object.entries(fingerprint).forEach(([key, item]) => text(item, `因子比较 fingerprint.${key}`));
  if (!Array.isArray(root.items) || root.items.length !== versions.length) {
    throw new Error("因子比较 items 与版本数不一致");
  }
  let stressKeys: string[] | null = null;
  root.items.forEach((item, index) => {
    const row = record(item, `因子比较 item[${index}]`);
    sha(row.factor_id, `因子比较 item[${index}].factor_id`);
    const version = factorVersion(row.factor_version, `因子比较 item[${index}].factor_version`);
    if (version !== versions[index]) throw new Error("因子比较响应顺序发生变化");
    recordedDecision(row.recorded_decision, `因子比较 item[${index}].recorded_decision`);
    validateStatistics(row.statistics, `因子比较 item[${index}].statistics`);
    validateSixWindows(row.six_oos_window_rank_ic, `因子比较 item[${index}].windows`);
    const stress = finiteRecord(row.stress_max_drawdown, `因子比较 item[${index}].stress`);
    const currentStressKeys = Object.keys(stress).sort();
    if (!currentStressKeys.length) throw new Error("因子比较压力期集合缺失");
    if (stressKeys && JSON.stringify(currentStressKeys) !== JSON.stringify(stressKeys)) {
      throw new Error("因子比较压力期集合不一致");
    }
    stressKeys = currentStressKeys;
    validatePortfolio(row.portfolio, `因子比较 item[${index}].portfolio`);
    validateCosts(row.cost_and_slippage, `因子比较 item[${index}].costs`);
  });
  if (root.sorted_by_performance !== false) throw new Error("因子比较禁止按表现排序");
  noForbiddenResearchPayload(value);
  noBse(value);
}

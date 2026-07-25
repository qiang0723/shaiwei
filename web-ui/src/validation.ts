import type {
  ApiEnvelope,
  DataQualityData,
  DomainStatus,
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

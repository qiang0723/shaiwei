import type {
  ApiEnvelope,
  DomainStatus,
  ForwardData,
  NavData,
  OverviewData,
  PortfolioData,
  ReplayData,
  SignalData
} from "./types";

const SHA256 = /^[0-9a-f]{64}$/;
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
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

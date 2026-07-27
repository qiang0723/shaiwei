import type {
  DomainStatus,
  ForwardData,
  NavData,
  OverviewData,
  PortfolioData,
  ReplayData,
  SignalData
} from "../types";
import {
  booleanValue,
  date,
  hashMap,
  integer,
  noBse,
  nullableText,
  numberLike,
  record,
  safeReference,
  sha,
  status,
  stringArray,
  text,
  timestamp
} from "./core";

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
  if (root.account_id !== "model_baseline" && root.account_id !== "model_top20") {
    throw new Error("组合 account_id 不受支持");
  }
  if (root.bse_count !== 0) throw new Error("组合北交所计数非零");
  date(root.as_of, "组合 as_of");
  status(root.freshness_status, "组合 freshness_status");
  if (root.mode !== "BACKFILL" && root.mode !== "FORWARD") throw new Error("组合 mode 无效");
  ["cash", "market_value", "net_asset", "cash_ratio", "normalized_nav", "benchmark_nav", "drawdown"].forEach(
    (name) => numberLike(root[name], `组合 ${name}`)
  );
  hashMap(root.evidence_hashes, "组合 evidence_hashes");
  if (!Array.isArray(root.positions)) throw new Error("组合 positions 缺失");
  const nameCoverage = record(root.security_name_coverage, "组合 security_name_coverage");
  const coverageStatus = status(nameCoverage.status, "组合 security_name_coverage.status");
  timestamp(nameCoverage.catalog_source_cutoff, "组合 security_name_coverage.catalog_source_cutoff");
  ["position_count", "pit_name_count", "fallback_name_count", "missing_name_count"].forEach(
    (name) => integer(nameCoverage[name], `组合 security_name_coverage.${name}`)
  );
  if (nameCoverage.position_count !== root.positions.length) throw new Error("组合简称覆盖分母不一致");
  if (
    Number(nameCoverage.pit_name_count) + Number(nameCoverage.fallback_name_count) + Number(nameCoverage.missing_name_count)
    !== root.positions.length
  ) throw new Error("组合简称覆盖分层不闭合");
  if (root.position_count !== root.positions.length) throw new Error("组合持仓计数不一致");
  const resolvedStatuses: DomainStatus[] = [];
  root.positions.forEach((item, index) => {
    const position = record(item, `组合 position[${index}]`);
    text(position.ts_code, `组合 position[${index}].ts_code`);
    const nameStatus = status(position.security_name_status, `组合 position[${index}].security_name_status`);
    resolvedStatuses.push(nameStatus);
    if (!["NAMECHANGE_PIT", "STOCK_BASIC_CURRENT_FALLBACK", "UNAVAILABLE"].includes(String(position.security_name_source))) {
      throw new Error(`组合 position[${index}].security_name_source 无效`);
    }
    if (position.security_name === null) {
      if (position.security_name_status !== "NOT_READY" || position.security_name_source !== "UNAVAILABLE") {
        throw new Error(`组合 position[${index}] 缺失简称未显式标记`);
      }
    } else {
      text(position.security_name, `组合 position[${index}].security_name`);
    }
    const validPair =
      (position.security_name_source === "NAMECHANGE_PIT" && nameStatus === "PASS" && position.security_name !== null)
      || (position.security_name_source === "STOCK_BASIC_CURRENT_FALLBACK" && nameStatus === "WARN" && position.security_name !== null)
      || (position.security_name_source === "UNAVAILABLE" && nameStatus === "NOT_READY" && position.security_name === null);
    if (!validPair) throw new Error(`组合 position[${index}] 简称来源与状态不一致`);
    ["actual_weight", "market_value", "cost_basis", "unrealized_pnl", "realized_pnl"].forEach(
      (name) => numberLike(position[name], `组合 position[${index}].${name}`)
    );
    integer(position.stale_trade_days, `组合 position[${index}].stale_trade_days`);
  });
  const expectedCoverageStatus = resolvedStatuses.includes("NOT_READY")
    ? "NOT_READY"
    : resolvedStatuses.includes("WARN")
      ? "WARN"
      : "PASS";
  if (coverageStatus !== expectedCoverageStatus) throw new Error("组合简称覆盖状态不一致");
  noBse(value);
}

export function assertNav(value: unknown): asserts value is NavData {
  const root = record(value, "净值");
  if (root.account_id !== "model_baseline" && root.account_id !== "model_top20") {
    throw new Error("净值 account_id 不受支持");
  }
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
  integer(root.forward_observation_count, "前瞻 observation_count");
  if (!Array.isArray(root.series) || root.series.length !== root.forward_observation_count) {
    throw new Error("前瞻 series 数量与证据不一致");
  }
  text(root.execution_policy_version, "前瞻 execution_policy_version");
  text(root.coverage_reason, "前瞻 coverage_reason");
  stringArray(root.suppressed_metrics, "前瞻 suppressed_metrics");
  if (root.forward_observation_count === 0) {
    if (root.status !== "NOT_READY" || root.performance_maturity !== "NOT_READY") {
      throw new Error("零前瞻观察必须保持 NOT_READY");
    }
    if (
      root.forward_anchor_trade_date !== null ||
      root.forward_anchor_artifact_sha256 !== null ||
      root.forward_anchor_portfolio_nav !== null ||
      root.forward_anchor_benchmark_nav !== null ||
      root.forward_cumulative_fees !== null ||
      root.forward_cumulative_dividends !== null ||
      root.forward_turnover !== null ||
      root.forward_cash_ratio !== null ||
      root.latest !== null
    ) {
      throw new Error("零前瞻观察不得伪造锚点、指标或最新值");
    }
  } else {
    date(root.forward_anchor_trade_date, "前瞻 anchor date");
    sha(root.forward_anchor_artifact_sha256, "前瞻 anchor hash");
    numberLike(root.forward_anchor_portfolio_nav, "前瞻 anchor portfolio nav");
    numberLike(root.forward_anchor_benchmark_nav, "前瞻 anchor benchmark nav");
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
  if (root.account_id !== "model_baseline" && root.account_id !== "model_top20") {
    throw new Error("重放 account_id 不受支持");
  }
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

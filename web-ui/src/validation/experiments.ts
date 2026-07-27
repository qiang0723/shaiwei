import type { ExperimentCatalogData, ExperimentDetailData } from "../types";
import {
  DECISION_KEYS,
  EXPERIMENT_KIND_VALUES,
  TIER_OUTCOMES,
  booleanValue,
  date,
  experimentAuthority,
  experimentEvidence,
  experimentId,
  experimentKind,
  experimentLifecycle,
  experimentOutcome,
  experimentTier,
  finiteRecord,
  hashMap,
  integer,
  jsonMetric,
  noBse,
  noForbiddenResearchPayload,
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

function validateExperimentCatalogItem(value: unknown, name: string): void {
  const row = record(value, name);
  experimentKind(row.experiment_kind, `${name}.experiment_kind`);
  experimentId(row.experiment_id, `${name}.experiment_id`);
  timestamp(row.recorded_at, `${name}.recorded_at`);
  text(row.research_family, `${name}.research_family`);
  const tier = experimentTier(row.evidence_tier, `${name}.evidence_tier`);
  experimentAuthority(row.authority_status, `${name}.authority_status`);
  experimentLifecycle(row.lifecycle_status, `${name}.lifecycle_status`);
  const outcome = experimentOutcome(row.outcome_status, `${name}.outcome_status`);
  if (!TIER_OUTCOMES[tier].has(outcome)) throw new Error(`${name} tier/outcome 组合未冻结`);
  text(row.model_or_engine, `${name}.model_or_engine`);
  text(row.engine_version, `${name}.engine_version`);
  integer(row.failed_reason_count, `${name}.failed_reason_count`);
  experimentEvidence(row.evidence_status, `${name}.evidence_status`);
}

function sortedUniqueStrings(value: unknown, name: string, validate: (item: unknown) => void): void {
  if (!Array.isArray(value)) throw new Error(`${name} 格式错误`);
  value.forEach(validate);
  const strings = value as string[];
  if (new Set(strings).size !== strings.length) throw new Error(`${name} 包含重复值`);
  if (JSON.stringify(strings) !== JSON.stringify([...strings].sort())) {
    throw new Error(`${name} 未按固定顺序返回`);
  }
}

export function assertExperimentCatalog(
  value: unknown
): asserts value is ExperimentCatalogData {
  const root = record(value, "实验目录");
  if (root.catalog_protocol_id !== "p3-experiment-catalog-v1") {
    throw new Error("实验目录协议身份无效");
  }
  if (!Array.isArray(root.items) || root.items.length > 100) {
    throw new Error("实验目录 items 格式或上限无效");
  }
  const identities = new Set<string>();
  root.items.forEach((item, index) => {
    validateExperimentCatalogItem(item, `实验目录 item[${index}]`);
    const row = item as Record<string, unknown>;
    const identity = `${row.experiment_kind}|${row.experiment_id}`;
    if (identities.has(identity)) throw new Error("实验目录身份重复");
    identities.add(identity);
  });

  const counters = record(root.counters, "实验目录 counters");
  const projected = integer(counters.projected_total_count, "实验目录 projected_total_count");
  const asOfCount = integer(counters.as_of_count, "实验目录 as_of_count");
  const filtered = integer(counters.filtered_count, "实验目录 filtered_count");
  const returned = integer(counters.returned_count, "实验目录 returned_count");
  if (projected < asOfCount || asOfCount < filtered || filtered < returned) {
    throw new Error("实验目录计数层级不一致");
  }
  if (returned !== root.items.length) throw new Error("实验目录 returned_count 与 items 不一致");
  const kindCounts = record(counters.kind_counts, "实验目录 kind_counts");
  const kinds = [...EXPERIMENT_KIND_VALUES];
  if (Object.keys(kindCounts).sort().join("|") !== [...kinds].sort().join("|")) {
    throw new Error("实验目录 kind_counts 集合无效");
  }
  if (
    kinds.reduce((sum, kind) => sum + integer(kindCounts[kind], `实验目录 kind_counts.${kind}`), 0)
    !== asOfCount
  ) {
    throw new Error("实验目录 kind_counts 与 as_of_count 不一致");
  }

  const filterKeys = [
    "experiment_kind",
    "research_family",
    "evidence_tier",
    "authority_status",
    "lifecycle_status",
    "outcome_status",
    "evidence_status",
    "as_of"
  ];
  const filters = record(root.filters, "实验目录 filters");
  if (Object.keys(filters).sort().join("|") !== [...filterKeys].sort().join("|")) {
    throw new Error("实验目录 filters 集合无效");
  }
  filterKeys.forEach((key) => {
    if (filters[key] !== null && typeof filters[key] !== "string") {
      throw new Error(`实验目录 filters.${key} 格式错误`);
    }
  });
  if (filters.as_of !== null) date(filters.as_of, "实验目录 filters.as_of");

  const facets = record(root.available_filters, "实验目录 available_filters");
  if (Object.keys(facets).sort().join("|") !== [...filterKeys.slice(0, -1)].sort().join("|")) {
    throw new Error("实验目录 available_filters 集合无效");
  }
  sortedUniqueStrings(facets.experiment_kind, "实验目录 kind facets", (item) => {
    experimentKind(item, "实验目录 kind facet");
  });
  sortedUniqueStrings(facets.research_family, "实验目录 family facets", (item) => {
    text(item, "实验目录 family facet");
  });
  sortedUniqueStrings(facets.evidence_tier, "实验目录 tier facets", (item) => {
    experimentTier(item, "实验目录 tier facet");
  });
  sortedUniqueStrings(facets.authority_status, "实验目录 authority facets", (item) => {
    experimentAuthority(item, "实验目录 authority facet");
  });
  sortedUniqueStrings(facets.lifecycle_status, "实验目录 lifecycle facets", (item) => {
    experimentLifecycle(item, "实验目录 lifecycle facet");
  });
  sortedUniqueStrings(facets.outcome_status, "实验目录 outcome facets", (item) => {
    experimentOutcome(item, "实验目录 outcome facet");
  });
  sortedUniqueStrings(facets.evidence_status, "实验目录 evidence facets", (item) => {
    experimentEvidence(item, "实验目录 evidence facet");
  });

  const page = record(root.page, "实验目录 page");
  const offset = integer(page.offset, "实验目录 page.offset");
  const limit = integer(page.limit, "实验目录 page.limit");
  if (limit < 1 || limit > 100 || root.items.length > limit) {
    throw new Error("实验目录分页上限无效");
  }
  const hasPrevious = booleanValue(page.has_previous, "实验目录 page.has_previous");
  const hasMore = booleanValue(page.has_more, "实验目录 page.has_more");
  if (hasPrevious !== (offset > 0)) throw new Error("实验目录上一页状态无效");
  if (page.previous_offset !== null) {
    const previous = integer(page.previous_offset, "实验目录 page.previous_offset");
    if (!hasPrevious || previous >= offset) throw new Error("实验目录上一页边界无效");
  } else if (hasPrevious) {
    throw new Error("实验目录缺少上一页边界");
  }
  if (page.next_offset !== null) {
    const next = integer(page.next_offset, "实验目录 page.next_offset");
    if (!hasMore || next !== offset + returned) throw new Error("实验目录下一页边界无效");
  } else if (hasMore) {
    throw new Error("实验目录缺少下一页边界");
  }
  if (
    !Array.isArray(root.sort) ||
    root.sort.join("|") !== "recorded_at:desc|experiment_kind:asc|experiment_id:asc"
  ) {
    throw new Error("实验目录固定排序发生变化");
  }
  if (root.sorted_by_performance !== false) throw new Error("实验目录禁止按表现排序");
  const banner = nullableText(root.historical_response_banner, "实验目录历史提示");
  if (banner !== null && banner !== "CURRENT_AUTHORITY_APPLIED_TO_HISTORICAL_RECORDS") {
    throw new Error("实验目录历史提示未知");
  }
  noForbiddenResearchPayload(value);
  noBse(value);
}

function validateP2EffectDecision(decision: Record<string, unknown>, name: string): void {
  if (!Array.isArray(decision.window_metrics) || decision.window_metrics.length !== 3) {
    throw new Error(`${name} 必须包含三个冻结窗口`);
  }
  const windows: string[] = [];
  let totalTradeDays = 0;
  decision.window_metrics.forEach((value, index) => {
    const row = record(value, `${name}.window_metrics[${index}]`);
    const window = text(row.window, `${name}.window_metrics[${index}].window`);
    if (windows.includes(window)) throw new Error(`${name} 窗口重复`);
    windows.push(window);
    totalTradeDays += integer(row.trade_days, `${name}.${window}.trade_days`);
    integer(row.rebalance_count, `${name}.${window}.rebalance_count`);
    for (const key of [
      "base_net_excess",
      "base_maximum_drawdown",
      "cost_1_5x_net_excess",
      "double_cost_net_excess",
      "extra_slippage_net_excess"
    ]) {
      numberLike(row[key], `${name}.${window}.${key}`);
    }
  });
  if (windows.join("|") !== "STAR-W1|STAR-W2|STAR-W3") {
    throw new Error(`${name} 冻结窗口身份或顺序无效`);
  }
  const pooled = record(decision.pooled, `${name}.pooled`);
  if (integer(pooled.trade_days, `${name}.pooled.trade_days`) !== totalTradeDays) {
    throw new Error(`${name} pooled 交易日与窗口合计不一致`);
  }
  for (const key of [
    "base_net_excess",
    "cost_1_5x_net_excess",
    "double_cost_net_excess",
    "extra_slippage_net_excess"
  ]) {
    numberLike(pooled[key], `${name}.pooled.${key}`);
  }
}

function requireDecisionKeys(
  decision: Record<string, unknown>,
  required: string[],
  name: string
): void {
  const missing = required.filter((key) => !(key in decision));
  if (missing.length) throw new Error(`${name} 缺少冻结 decision 键 ${missing.join(",")}`);
}

export function assertExperimentDetail(value: unknown): asserts value is ExperimentDetailData {
  const root = record(value, "实验详情");
  const allowedRoot = new Set([
    "experiment_kind",
    "experiment_id",
    "recorded_at",
    "research_family",
    "evidence_tier",
    "authority_status",
    "lifecycle_status",
    "outcome_status",
    "model_or_engine",
    "engine_version",
    "seed",
    "train_period",
    "valid_period",
    "code_snapshot_sha256",
    "data_snapshot_sha256",
    "decision",
    "failed_reasons",
    "evidence_status",
    "source_refs",
    "evidence_hashes",
    "historical_response_banner"
  ]);
  const unknownRoot = Object.keys(root).filter((key) => !allowedRoot.has(key));
  if (unknownRoot.length) throw new Error(`实验详情包含未知字段 ${unknownRoot.join(",")}`);

  const kind = experimentKind(root.experiment_kind, "实验详情 experiment_kind");
  experimentId(root.experiment_id, "实验详情 experiment_id");
  timestamp(root.recorded_at, "实验详情 recorded_at");
  text(root.research_family, "实验详情 research_family");
  const tier = experimentTier(root.evidence_tier, "实验详情 evidence_tier");
  const authority = experimentAuthority(root.authority_status, "实验详情 authority_status");
  experimentLifecycle(root.lifecycle_status, "实验详情 lifecycle_status");
  const outcome = experimentOutcome(root.outcome_status, "实验详情 outcome_status");
  if (!TIER_OUTCOMES[tier].has(outcome)) throw new Error("实验详情 tier/outcome 组合未冻结");
  text(root.model_or_engine, "实验详情 model_or_engine");
  text(root.engine_version, "实验详情 engine_version");
  for (const key of ["seed", "train_period", "valid_period"]) {
    if (typeof root[key] !== "string") throw new Error(`实验详情 ${key} 格式错误`);
  }
  for (const key of ["code_snapshot_sha256", "data_snapshot_sha256"]) {
    if (root[key] !== "") sha(root[key], `实验详情 ${key}`);
  }

  const decision = record(root.decision, "实验详情 decision");
  const unknownDecision = Object.keys(decision).filter((key) => !DECISION_KEYS[tier].has(key));
  if (unknownDecision.length) {
    throw new Error(`实验详情 ${tier} 包含未冻结 decision 键 ${unknownDecision.join(",")}`);
  }
  Object.entries(decision).forEach(([key, item]) => jsonMetric(item, `实验详情 decision.${key}`));
  if (tier === "BASELINE_BACKTEST") {
    requireDecisionKeys(decision, [outcome === "FAILED" ? "status" : "prediction_rows"], "实验详情基线");
  } else if (tier === "SHADOW_SIGNAL" || tier === "FORWARD_SHADOW_SIGNAL") {
    requireDecisionKeys(decision, ["score_rows", "signal_sha256"], "实验详情信号");
  } else if (tier === "GP_DISCOVERY_ATTEMPT" || tier === "GP_STAGE1_ATTEMPT") {
    requireDecisionKeys(decision, ["rank_ic"], "实验详情 GP");
  } else if (tier === "D1_DISCOVERY_ATTEMPT_WITH_REVIEW_OVERLAY") {
    requireDecisionKeys(
      decision,
      ["discovery_status", "g1_run", "strategy_effective", "review_overlay"],
      "实验详情 D1"
    );
    if (outcome === "REVIEW_STOPPED") {
      requireDecisionKeys(
        decision,
        ["human_gate_ready", "production_authorization", "review_roles"],
        "实验详情 D1 复核停止"
      );
    }
  } else if (tier === "P2_ENGINEERING") {
    requireDecisionKeys(decision, [...DECISION_KEYS.P2_ENGINEERING], "实验详情 P2 工程");
  } else if (tier === "P2_EFFECT_AUTHORITATIVE") {
    requireDecisionKeys(
      decision,
      [...DECISION_KEYS.P2_EFFECT_AUTHORITATIVE],
      "实验详情 P2 权威效果"
    );
  } else if (tier === "P2_EFFECT_INVALIDATED") {
    requireDecisionKeys(
      decision,
      [...DECISION_KEYS.P2_EFFECT_INVALIDATED],
      "实验详情 P2 失效效果"
    );
  } else if (tier === "G1_FACTOR_DECISION") {
    requireDecisionKeys(
      decision,
      outcome === "G1_REJECTED" || outcome === "G1_ADMITTED"
        ? ["recorded_decision", "trial_count", "all_gates"]
        : ["status"],
      "实验详情 G1"
    );
  }
  if ("all_gates" in decision) {
    const gates = record(decision.all_gates, "实验详情 G1 all_gates");
    if (Object.keys(gates).length !== 15) throw new Error("实验详情 G1 必须完整包含 15 项门");
    Object.entries(gates).forEach(([key, value]) => {
      const gate = record(value, `实验详情 G1.${key}`);
      jsonMetric(gate.actual, `实验详情 G1.${key}.actual`);
      booleanValue(gate.passed, `实验详情 G1.${key}.passed`);
      text(gate.rule, `实验详情 G1.${key}.rule`);
    });
  }
  if (tier === "P2_EFFECT_AUTHORITATIVE" || tier === "P2_EFFECT_INVALIDATED") {
    validateP2EffectDecision(decision, "实验详情 P2 effect");
  }
  if (tier === "P2_EFFECT_AUTHORITATIVE") {
    if (
      kind !== "p2_effect_correction" ||
      authority !== "AUTHORITATIVE_CURRENT" ||
      outcome !== "HISTORICAL_EFFECT_REJECTED" ||
      decision.historical_effect_gate !== "NO_GO" ||
      decision.strategy_effective !== "REJECT" ||
      decision.production_authorization !== "none"
    ) {
      throw new Error("实验详情 P2 权威效果边界无效");
    }
  }
  if (tier === "P2_EFFECT_INVALIDATED") {
    if (
      kind !== "p2_effect_original" ||
      authority !== "INVALIDATED_METHOD" ||
      outcome !== "INVALIDATED_METHOD" ||
      decision.historical_effect_gate !== "NO_GO" ||
      decision.strategy_effective !== "REJECT" ||
      decision.production_authorization !== "none" ||
      decision.numeric_results_status !== "REPRODUCIBLE_NOT_AUTHORITATIVE" ||
      decision.authoritative_successor_kind !== "p2_effect_correction"
    ) {
      throw new Error("实验详情失效方法边界无效");
    }
    experimentId(decision.authoritative_successor_id, "实验详情 successor_id");
  }

  stringArray(root.failed_reasons, "实验详情 failed_reasons");
  experimentEvidence(root.evidence_status, "实验详情 evidence_status");
  stringArray(root.source_refs, "实验详情 source_refs").forEach((item, index) =>
    safeReference(item, `实验详情 source_refs[${index}]`)
  );
  stringArray(root.evidence_hashes, "实验详情 evidence_hashes").forEach((item, index) =>
    sha(item, `实验详情 evidence_hashes[${index}]`)
  );
  const banner = nullableText(root.historical_response_banner, "实验详情历史提示");
  if (banner !== null && banner !== "CURRENT_AUTHORITY_APPLIED_TO_HISTORICAL_RECORDS") {
    throw new Error("实验详情历史提示未知");
  }
  noForbiddenResearchPayload(value);
  noBse(value);
}

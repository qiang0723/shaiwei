import type {
  FactorAdmissionHistoryData,
  FactorCatalogData,
  FactorCompareData,
  FactorDetailData
} from "../types";
import {
  booleanValue,
  date,
  factorAuthority,
  factorLifecycle,
  factorVersion,
  finiteRecord,
  hashMap,
  integer,
  jsonMetric,
  noBse,
  noForbiddenResearchPayload,
  nullableText,
  numberLike,
  record,
  recordedDecision,
  safeReference,
  sha,
  status,
  stringArray,
  text,
  timestamp,
  unavailableSection,
  validateCosts,
  validatePortfolio,
  validateSixWindows,
  validateStatistics
} from "./core";

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

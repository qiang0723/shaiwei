import type {
  StrategyFactoryData,
  StrategyFactoryDataStatus,
  StrategyFactoryOutcome
} from "../strategyFactoryTypes";
import {
  booleanValue,
  integer,
  noBse,
  nullableText,
  record,
  stringArray,
  text
} from "./core";

const DATA_STATUSES = new Set<StrategyFactoryDataStatus>([
  "READY",
  "BLOCKED_OFFICIAL_LINEAGE",
  "DATA_GATE_REQUIRED"
]);
const OUTCOMES = new Set<StrategyFactoryOutcome>([
  "PRODUCTION_CURRENT_EXISTING",
  "REJECT_CURRENT_PROGRAMS",
  "NOT_EVALUATED",
  "STOPPED_CONTRACT",
  "REJECT"
]);
const EXPECTED_UNIVERSES = new Set([
  "csi800-pit-v1",
  "star50-official-pit-v2",
  "star100-official-pit-v1",
  "star200-official-pit-v1",
  "star-composite-official-v1",
  "star-board-all-pit-v1",
  "star-board-midcap-pit-v1",
  "star-board-smallcap-pit-v1"
]);

function rows(value: unknown, name: string): Record<string, unknown>[] {
  if (!Array.isArray(value)) throw new Error(`${name} 缺失或格式错误`);
  return value.map((item, index) => record(item, `${name}[${index}]`));
}

function unique(values: string[], name: string): void {
  if (values.length !== new Set(values).size) throw new Error(`${name} 包含重复身份`);
}

function enumValue<T extends string>(value: unknown, allowed: Set<T>, name: string): T {
  const result = text(value, name) as T;
  if (!allowed.has(result)) throw new Error(`${name} 返回未知枚举`);
  return result;
}

function validateSummary(value: unknown): void {
  const summary = record(value, "strategyFactory.summary");
  if (summary.overall_status !== "WARN") throw new Error("策略工厂总状态必须保留WARN");
  text(summary.decision, "strategyFactory.summary.decision");
  const frozen: Record<string, number> = {
    registered_universe_count: 8,
    research_eligible_universe_count: 5,
    blocked_universe_count: 3,
    existing_production_strategy_count: 1,
    admitted_factor_count: 0,
    active_authorized_task_count: 0,
    registered_program_count: 8
  };
  Object.entries(frozen).forEach(([key, expected]) => {
    if (integer(summary[key], `strategyFactory.summary.${key}`) !== expected) {
      throw new Error(`strategyFactory.summary.${key} 与冻结事实不一致`);
    }
  });
  integer(summary.authoritative_reject_program_count, "summary.authoritative_reject_program_count");
  integer(summary.stopped_contract_program_count, "summary.stopped_contract_program_count");
  integer(summary.factor_admission_decision_count, "summary.factor_admission_decision_count");
}

function validateUniverses(value: unknown): Set<string> {
  const items = rows(value, "strategyFactory.universes");
  const ids = items.map((item, index) => text(item.universe_id, `universes[${index}].universe_id`));
  unique(ids, "股票池");
  if (ids.length !== 8 || ids.some((id) => !EXPECTED_UNIVERSES.has(id))) {
    throw new Error("股票池身份集合与冻结注册不一致");
  }
  items.forEach((item, index) => {
    const prefix = `universes[${index}]`;
    text(item.display_name, `${prefix}.display_name`);
    const kind = enumValue(item.identity_kind, new Set(["OFFICIAL_INDEX", "CUSTOM_RULE_BASED"]), `${prefix}.identity_kind`);
    const code = nullableText(item.official_index_code, `${prefix}.official_index_code`);
    if (kind === "OFFICIAL_INDEX" && !/^[0-9]{6}\.SH$/.test(code ?? "")) {
      throw new Error(`${prefix} 官方代码无效`);
    }
    if (kind === "CUSTOM_RULE_BASED" && code !== null) throw new Error(`${prefix} 规则池冒充官方指数`);
    const dataStatus = enumValue(item.data_status, DATA_STATUSES, `${prefix}.data_status`);
    enumValue(item.authoritative_outcome, OUTCOMES, `${prefix}.authoritative_outcome`);
    const eligible = booleanValue(item.research_draft_eligible, `${prefix}.research_draft_eligible`);
    booleanValue(item.existing_production, `${prefix}.existing_production`);
    text(item.evidence_tier, `${prefix}.evidence_tier`);
    text(item.allowed_action, `${prefix}.allowed_action`);
    const blocker = nullableText(item.blocker, `${prefix}.blocker`);
    if (eligible !== (dataStatus === "READY") || eligible !== (blocker === null)) {
      throw new Error(`${prefix} 数据、草案权限和阻断原因冲突`);
    }
    if (!stringArray(item.evidence_ids, `${prefix}.evidence_ids`).length) {
      throw new Error(`${prefix} 缺少证据引用`);
    }
  });
  return new Set(ids);
}

function validateFamilies(value: unknown): Set<string> {
  const items = rows(value, "strategyFactory.research_families");
  const ids = items.map((item, index) => text(item.family_id, `families[${index}].family_id`));
  unique(ids, "研究家族");
  items.forEach((item, index) => {
    text(item.display_name, `families[${index}].display_name`);
    booleanValue(item.draft_eligible, `families[${index}].draft_eligible`);
  });
  return new Set(ids);
}

function validatePrograms(value: unknown, universes: Set<string>, families: Set<string>): Set<string> {
  const items = rows(value, "strategyFactory.programs");
  if (items.length !== 8) throw new Error("策略工厂工作包数量与冻结事实不一致");
  const ids = items.map((item, index) => text(item.program_id, `programs[${index}].program_id`));
  unique(ids, "研究工作包");
  items.forEach((item, index) => {
    const prefix = `programs[${index}]`;
    text(item.display_name, `${prefix}.display_name`);
    const family = text(item.family_id, `${prefix}.family_id`);
    if (!families.has(family)) throw new Error(`${prefix} 引用了未知研究家族`);
    const universeIds = stringArray(item.universe_ids, `${prefix}.universe_ids`);
    if (!universeIds.length || universeIds.some((id) => !universes.has(id))) {
      throw new Error(`${prefix} 引用了未知股票池`);
    }
    const lifecycle = enumValue(item.lifecycle_state, new Set(["CLOSED", "STOPPED_CONTRACT"]), `${prefix}.lifecycle_state`);
    const outcome = enumValue(item.authoritative_outcome, OUTCOMES, `${prefix}.authoritative_outcome`);
    const effective = enumValue(item.strategy_effective, new Set(["EXISTING_PRODUCTION_BASELINE", "REJECT", "NOT_EVALUATED"]), `${prefix}.strategy_effective`);
    if (lifecycle === "STOPPED_CONTRACT" && (outcome !== "STOPPED_CONTRACT" || effective !== "NOT_EVALUATED")) {
      throw new Error(`${prefix} 合同停止却产生了效果裁决`);
    }
    text(item.evidence_tier, `${prefix}.evidence_tier`);
    const evaluations = integer(item.evaluation_unit_count, `${prefix}.evaluation_unit_count`);
    const effects = integer(item.effect_test_count, `${prefix}.effect_test_count`);
    if (effects > evaluations) throw new Error(`${prefix} 效果读取数超过评价单元`);
    integer(item.generation_attempt_count, `${prefix}.generation_attempt_count`);
    integer(item.candidate_count, `${prefix}.candidate_count`);
    const production = enumValue(item.production_authorization, new Set(["none", "production_current"]), `${prefix}.production_authorization`);
    if (production === "production_current" && outcome !== "PRODUCTION_CURRENT_EXISTING") {
      throw new Error(`${prefix} 生产事实与权威裁决冲突`);
    }
    text(item.summary, `${prefix}.summary`);
    text(item.next_action, `${prefix}.next_action`);
    if (!stringArray(item.evidence_ids, `${prefix}.evidence_ids`).length) {
      throw new Error(`${prefix} 缺少证据引用`);
    }
  });
  return new Set(ids);
}

function validateMatrix(
  value: unknown,
  universes: Set<string>,
  families: Set<string>,
  programs: Set<string>
): void {
  const items = rows(value, "strategyFactory.matrix");
  if (items.length !== universes.size * families.size) throw new Error("研究矩阵不完整");
  const identities: string[] = [];
  items.forEach((item, index) => {
    const family = text(item.family_id, `matrix[${index}].family_id`);
    const universe = text(item.universe_id, `matrix[${index}].universe_id`);
    if (!families.has(family) || !universes.has(universe)) throw new Error("研究矩阵引用未知身份");
    identities.push(`${family}\0${universe}`);
    const programIds = stringArray(item.program_ids, `matrix[${index}].program_ids`);
    if (programIds.some((id) => !programs.has(id))) throw new Error("研究矩阵引用未知工作包");
    const outcomes = stringArray(item.authoritative_outcomes, `matrix[${index}].authoritative_outcomes`);
    if (!outcomes.length || outcomes.some((outcome) => !OUTCOMES.has(outcome as StrategyFactoryOutcome))) {
      throw new Error("研究矩阵返回未知裁决");
    }
    if (!stringArray(item.evidence_tiers, `matrix[${index}].evidence_tiers`).length) {
      throw new Error("研究矩阵缺少证据层");
    }
  });
  unique(identities, "研究矩阵单元格");
}

function validateDraft(value: unknown, universes: Set<string>, families: Set<string>): void {
  const draft = record(value, "strategyFactory.draft_template");
  if (draft.template_id !== "bounded-research-draft-v1" || draft.status !== "DRAFT_NOT_SUBMITTED") {
    throw new Error("研究草案模板身份无效");
  }
  const universeIds = stringArray(draft.eligible_universe_ids, "draft.eligible_universe_ids");
  const familyIds = stringArray(draft.eligible_family_ids, "draft.eligible_family_ids");
  if (universeIds.some((id) => !universes.has(id)) || familyIds.some((id) => !families.has(id))) {
    throw new Error("研究草案模板引用未知身份");
  }
  integer(draft.maximum_universe_count, "draft.maximum_universe_count");
  integer(draft.maximum_candidate_count, "draft.maximum_candidate_count");
  if (
    draft.external_call_authorization !== "NOT_GRANTED" ||
    draft.sealed_effect_authorization !== "NOT_GRANTED" ||
    draft.production_authorization !== "none"
  ) throw new Error("研究草案越过授权边界");
  text(draft.disclaimer, "draft.disclaimer");
}

function validateGateDecisions(
  value: unknown,
  universes: Set<string>,
  families: Set<string>
): string {
  const items = rows(value, "strategyFactory.recent_gate_decisions");
  if (items.length !== 1) throw new Error("策略工厂必须投影恰好一条最新权威数据门裁决");
  const decision = items[0]!;
  const decisionId = text(decision.decision_id, "gateDecision.decision_id");
  if (decisionId !== "m5-dynamic-fundamental-lineage-gate-20260806-v1") {
    throw new Error("策略工厂权威数据门身份漂移");
  }
  if (decision.display_name !== "动态基本面跨池研究") throw new Error("策略工厂权威数据门名称漂移");
  const familyId = text(decision.family_id, "gateDecision.family_id");
  if (familyId !== "fundamental_dynamic" || !families.has(familyId)) {
    throw new Error("策略工厂权威数据门研究家族漂移");
  }
  const universeIds = stringArray(decision.universe_ids, "gateDecision.universe_ids");
  const expectedUniverses = [
    "star50-official-pit-v2",
    "star-board-midcap-pit-v1",
    "star-board-smallcap-pit-v1"
  ];
  if (universeIds.join("|") !== expectedUniverses.join("|") || universeIds.some((id) => !universes.has(id))) {
    throw new Error("策略工厂权威数据门股票池漂移");
  }
  const exact: Record<string, unknown> = {
    gate_stage: "SOURCE_LINEAGE_FEASIBILITY",
    terminal_state: "BLOCKED_DATA",
    evidence_tier: "LINEAGE_NO_GO_ONLY",
    verdict: "NO_GO_M5_2_SOURCE_LINEAGE_PREEXECUTION",
    strategy_effective: "NOT_EVALUATED",
    effect_read: false,
    real_gate_run_count: 1,
    conflict_group_count: 23,
    forward_only_group_count: 23,
    pit_resolved_group_count: 0,
    route_status: "PAUSE",
    production_authorization: "none",
    release_consumed: true,
    active_task: false
  };
  Object.entries(exact).forEach(([key, expected]) => {
    if (decision[key] !== expected) throw new Error(`策略工厂权威数据门 ${key} 漂移`);
  });
  text(decision.blocked_reason, "gateDecision.blocked_reason");
  text(decision.next_action, "gateDecision.next_action");
  [
    "release_scope_sha256",
    "run_id",
    "independent_audit_sha256",
    "registry_event_sha256"
  ].forEach((key) => {
    if (!/^[0-9a-f]{64}$/.test(text(decision[key], `gateDecision.${key}`))) {
      throw new Error(`策略工厂权威数据门 ${key} 无效`);
    }
  });
  ["evidence_commit", "route_review_commit"].forEach((key) => {
    if (!/^[0-9a-f]{40}$/.test(text(decision[key], `gateDecision.${key}`))) {
      throw new Error(`策略工厂权威数据门 ${key} 无效`);
    }
  });
  const evidenceIds = stringArray(decision.evidence_ids, "gateDecision.evidence_ids");
  if (evidenceIds.join("|") !== "lineage_release_scope|lineage_real_run_acceptance|platform_route_review") {
    throw new Error("策略工厂权威数据门证据集合漂移");
  }
  return decisionId;
}

function validateCurrentRoute(value: unknown): void {
  const route = record(value, "strategyFactory.route_decision");
  if (
    route.route_id !== "platform-route-review-20260809"
    || route.status !== "COURSE_CORRECTION_AND_OBSERVE"
    || route.active_authorized_task_count !== 0
    || route.production_authorization !== "none"
  ) throw new Error("策略工厂当前路线漂移");
  text(route.headline, "strategyFactory.route.headline");
  text(route.summary, "strategyFactory.route.summary");
  const primary = record(route.primary_goal, "strategyFactory.route.primary_goal");
  const primaryExact: Record<string, unknown> = {
    goal_id: "R2-1_FORWARD_EVIDENCE_CHECKPOINT",
    state: "NOT_DUE",
    live_dual_days_at_freeze: 5,
    minimum_live_dual_days: 20,
    live_dual_rebalances_at_freeze: 0,
    minimum_live_dual_rebalances: 2,
    expected_first_live_rebalance_execution_date: "20260814",
    expected_first_due_execution_date: "20260828",
    dates_are_planning_only: true
  };
  Object.entries(primaryExact).forEach(([key, expected]) => {
    if (primary[key] !== expected) throw new Error(`策略工厂当前目标 ${key} 漂移`);
  });
  const m7 = record(route.m7, "strategyFactory.route.m7");
  const m7Exact: Record<string, unknown> = {
    verdict: "NO_GO_M7_EVIDENCE_RECOVERY_INCOMPLETE",
    strategy_effective: "NOT_EVALUATED",
    candidate_count: 0,
    effect_read_count: 0,
    production_authorization: "none"
  };
  Object.entries(m7Exact).forEach(([key, expected]) => {
    if (m7[key] !== expected) throw new Error(`策略工厂M7当前事实 ${key} 漂移`);
  });
  text(m7.next_action, "strategyFactory.route.m7.next_action");
  if (stringArray(route.paused_work, "strategyFactory.route.paused_work").length !== 5) {
    throw new Error("策略工厂暂停工作集合漂移");
  }
  text(route.capability_note, "strategyFactory.route.capability_note");
}

export function assertStrategyFactory(value: unknown): asserts value is StrategyFactoryData {
  noBse(value);
  const root = record(value, "strategyFactory");
  validateSummary(root.summary);
  const universes = validateUniverses(root.universes);
  const families = validateFamilies(root.research_families);
  const programs = validatePrograms(root.programs, universes, families);
  validateMatrix(root.matrix, universes, families, programs);
  if (root.authority_projection_version !== "m5-strategy-factory-authority-projection-v1") {
    throw new Error("策略工厂权威投影版本无效");
  }
  const gateDecisionId = validateGateDecisions(root.recent_gate_decisions, universes, families);
  validateCurrentRoute(root.route_decision);
  const attention = record(root.attention, "strategyFactory.attention");
  stringArray(attention.blocked_universe_ids, "attention.blocked_universe_ids");
  stringArray(attention.rejected_program_ids, "attention.rejected_program_ids");
  stringArray(attention.stopped_program_ids, "attention.stopped_program_ids");
  const blockedGateIds = stringArray(
    attention.blocked_gate_decision_ids,
    "attention.blocked_gate_decision_ids"
  );
  if (blockedGateIds.length !== 1 || blockedGateIds[0] !== gateDecisionId) {
    throw new Error("策略工厂关注项未绑定最新权威数据门");
  }
  booleanValue(attention.formal_library_empty, "attention.formal_library_empty");
  if (!Array.isArray(root.active_tasks) || root.active_tasks.length !== 0) {
    throw new Error("M5-0 不允许活跃执行任务");
  }
  validateDraft(root.draft_template, universes, families);
  const invariants = record(root.invariants, "strategyFactory.invariants");
  if (
    invariants.source_backed !== true ||
    invariants.web_read_only !== true ||
    invariants.browser_draft_only !== true ||
    invariants.performance_sorting !== false ||
    invariants.external_calls_made !== 0 ||
    invariants.real_research_runs !== 0 ||
    invariants.bse_count !== 0 ||
    invariants.production_authorization !== "none"
  ) throw new Error("策略工厂只读不变量失效");
}

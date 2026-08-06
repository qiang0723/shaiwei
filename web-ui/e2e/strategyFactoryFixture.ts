import type { StrategyFactoryData } from "../src/strategyFactoryTypes";

const universeRows = [
  ["csi800-pit-v1", "中证800", "OFFICIAL_INDEX", "000906.SH", "READY", "PRODUCTION_CURRENT", "PRODUCTION_CURRENT_EXISTING", true, true, null],
  ["star50-official-pit-v2", "科创50", "OFFICIAL_INDEX", "000688.SH", "READY", "HISTORICAL_EFFECT_AUDITED", "REJECT_CURRENT_PROGRAMS", true, false, null],
  ["star100-official-pit-v1", "科创100", "OFFICIAL_INDEX", "000698.SH", "BLOCKED_OFFICIAL_LINEAGE", "SOURCE_GO_ONLY", "NOT_EVALUATED", false, false, "缺少官方历史成员谱系"],
  ["star200-official-pit-v1", "科创200", "OFFICIAL_INDEX", "000699.SH", "BLOCKED_OFFICIAL_LINEAGE", "SECONDARY_SOURCE_GO_ONLY", "NOT_EVALUATED", false, false, "二级集合不能替代官方PIT"],
  ["star-composite-official-v1", "科创综指", "OFFICIAL_INDEX", "000680.SH", "DATA_GATE_REQUIRED", "PROTOCOL_ONLY", "NOT_EVALUATED", false, false, "尚未完成数据门"],
  ["star-board-all-pit-v1", "科创板全市场PIT研究池", "CUSTOM_RULE_BASED", null, "READY", "DISCOVERY_ONLY", "STOPPED_CONTRACT", true, false, null],
  ["star-board-midcap-pit-v1", "科创板中盘PIT研究池", "CUSTOM_RULE_BASED", null, "READY", "DISCOVERY_ONLY", "STOPPED_CONTRACT", true, false, null],
  ["star-board-smallcap-pit-v1", "科创板小盘PIT研究池", "CUSTOM_RULE_BASED", null, "READY", "DISCOVERY_ONLY", "STOPPED_CONTRACT", true, false, null]
] as const;

export const strategyFactoryUniverses = universeRows.map((row) => ({
  universe_id: row[0],
  display_name: row[1],
  identity_kind: row[2],
  official_index_code: row[3],
  data_status: row[4],
  evidence_tier: row[5],
  authoritative_outcome: row[6],
  research_draft_eligible: row[7],
  existing_production: row[8],
  allowed_action: row[7] ? "CREATE_RESEARCH_DRAFT" : "FREEZE_DATA_RECOVERY_PROTOCOL",
  blocker: row[9],
  evidence_ids: ["fixture"]
}));

export const strategyFactoryFamilies = [
  { family_id: "baseline_model", display_name: "基线模型", draft_eligible: false },
  { family_id: "moneyflow", display_name: "资金流", draft_eligible: true },
  { family_id: "fundamental_static", display_name: "静态基本面", draft_eligible: true },
  { family_id: "fundamental_dynamic", display_name: "动态基本面", draft_eligible: true },
  { family_id: "price_volume", display_name: "量价机制", draft_eligible: true },
  { family_id: "residual_risk", display_name: "残差与特异风险", draft_eligible: true }
];

function program(
  programId: string,
  displayName: string,
  familyId: string,
  universeIds: string[],
  outcome: "PRODUCTION_CURRENT_EXISTING" | "REJECT" | "STOPPED_CONTRACT",
  attempts: number,
  evaluations: number,
  effects: number
) {
  return {
    program_id: programId,
    display_name: displayName,
    family_id: familyId,
    universe_ids: universeIds,
    lifecycle_state: outcome === "STOPPED_CONTRACT" ? "STOPPED_CONTRACT" as const : "CLOSED" as const,
    evidence_tier: outcome === "PRODUCTION_CURRENT_EXISTING" ? "PRODUCTION_CURRENT" as const : outcome === "STOPPED_CONTRACT" ? "DISCOVERY_ONLY" as const : "HISTORICAL_EFFECT_AUDITED" as const,
    authoritative_outcome: outcome,
    strategy_effective: outcome === "PRODUCTION_CURRENT_EXISTING" ? "EXISTING_PRODUCTION_BASELINE" as const : outcome === "STOPPED_CONTRACT" ? "NOT_EVALUATED" as const : "REJECT" as const,
    generation_attempt_count: attempts,
    evaluation_unit_count: evaluations,
    effect_test_count: effects,
    candidate_count: attempts,
    production_authorization: outcome === "PRODUCTION_CURRENT_EXISTING" ? "production_current" as const : "none" as const,
    summary: outcome === "REJECT" ? "按冻结效果门完成并权威拒绝。" : outcome === "STOPPED_CONTRACT" ? "发现期完成，审查合同停止，效果未评价。" : "当前唯一生产主策略。",
    next_action: outcome === "PRODUCTION_CURRENT_EXISTING" ? "持续前瞻观察" : "独立新机制须另立协议",
    evidence_ids: ["fixture"]
  };
}

export const strategyFactoryPrograms = [
  program("csi800-production-baseline-v1", "中证800 Alpha158生产基线", "baseline_model", ["csi800-pit-v1"], "PRODUCTION_CURRENT_EXISTING", 0, 0, 0),
  program("p1-csi800-moneyflow-v1", "中证800资金流候选", "moneyflow", ["csi800-pit-v1"], "REJECT", 18, 6, 6),
  program("f1-csi800-static-fundamental-v1", "中证800静态基本面候选", "fundamental_static", ["csi800-pit-v1"], "REJECT", 6, 6, 6),
  program("f2-csi800-dynamic-fundamental-v1", "中证800动态基本面候选", "fundamental_dynamic", ["csi800-pit-v1"], "REJECT", 6, 6, 5),
  program("p2-star50-baseline-v1", "科创50独立基线", "baseline_model", ["star50-official-pit-v2"], "REJECT", 1, 1, 1),
  program("m1-star50-price-volume-v1", "科创50价量发现批", "price_volume", ["star50-official-pit-v2"], "STOPPED_CONTRACT", 40, 14, 0),
  program("m3-custom-pools-price-volume-v1", "三自建科创池价量发现批", "price_volume", ["star-board-all-pit-v1", "star-board-midcap-pit-v1", "star-board-smallcap-pit-v1"], "STOPPED_CONTRACT", 24, 24, 0),
  program("m4-star50-residual-v1", "科创50残差因子候选", "residual_risk", ["star50-official-pit-v2"], "REJECT", 3, 3, 2)
];

const matrix = strategyFactoryFamilies.flatMap((family) => strategyFactoryUniverses.map((universe) => {
  const matches = strategyFactoryPrograms.filter((item) => item.family_id === family.family_id && item.universe_ids.includes(universe.universe_id));
  return {
    family_id: family.family_id,
    universe_id: universe.universe_id,
    program_ids: matches.map((item) => item.program_id),
    authoritative_outcomes: matches.length ? matches.map((item) => item.authoritative_outcome) : ["NOT_EVALUATED"],
    evidence_tiers: matches.length ? matches.map((item) => item.evidence_tier) : ["NOT_EVALUATED"]
  };
}));

export const strategyFactoryData: StrategyFactoryData = {
  summary: {
    overall_status: "WARN",
    decision: "5个股票池具备研究草案条件；最新M5动态基本面批次因历史来源谱系不足被阻断，未进入效果评价。",
    registered_universe_count: 8,
    research_eligible_universe_count: 5,
    blocked_universe_count: 3,
    existing_production_strategy_count: 1,
    admitted_factor_count: 0,
    active_authorized_task_count: 0,
    registered_program_count: 8,
    authoritative_reject_program_count: 5,
    stopped_contract_program_count: 2,
    factor_admission_decision_count: 29
  },
  attention: {
    blocked_universe_ids: ["star100-official-pit-v1", "star200-official-pit-v1", "star-composite-official-v1"],
    rejected_program_ids: strategyFactoryPrograms.filter((item) => item.authoritative_outcome === "REJECT").map((item) => item.program_id),
    stopped_program_ids: strategyFactoryPrograms.filter((item) => item.authoritative_outcome === "STOPPED_CONTRACT").map((item) => item.program_id),
    blocked_gate_decision_ids: ["m5-dynamic-fundamental-lineage-gate-20260806-v1"],
    formal_library_empty: true
  },
  universes: strategyFactoryUniverses,
  research_families: strategyFactoryFamilies,
  programs: strategyFactoryPrograms,
  matrix,
  active_tasks: [],
  authority_projection_version: "m5-strategy-factory-authority-projection-v1",
  recent_gate_decisions: [{
    decision_id: "m5-dynamic-fundamental-lineage-gate-20260806-v1",
    display_name: "动态基本面跨池研究",
    family_id: "fundamental_dynamic",
    universe_ids: ["star50-official-pit-v2", "star-board-midcap-pit-v1", "star-board-smallcap-pit-v1"],
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
    blocked_reason: "现有本地批次只能证明当前观察版本，无法证明历史修订何时生效。",
    next_action: "本支线暂停；只有补齐权威历史版本与生效链后，才可另立结果前协议。",
    release_scope_sha256: "f7904929991e90a3d4c220cbdaf88818953694803625c41eb3634731e376e2d5",
    run_id: "8ffe2570e740dd84ce8d3ccfc0f75f429488d201cf0088ef54ba715cc9dd1fab",
    independent_audit_sha256: "e056e41a3473206ebd806e8b917b33e953210ede4b71e15c3ebdfc009ba2ba45",
    registry_event_sha256: "9cfc67deb0d199d969a09f08494644b18c0aed72c0ab68ade4c834f19cba38d8",
    evidence_commit: "fb134b91433003774945ab91f1dba02cf6daad5e",
    route_review_commit: "e8dab33217fcce7b9a89bd1d1c78727c91051f52",
    production_authorization: "none",
    release_consumed: true,
    active_task: false,
    evidence_ids: ["lineage_release_scope", "lineage_real_run_acceptance", "platform_route_review"]
  }],
  draft_template: {
    template_id: "bounded-research-draft-v1",
    display_name: "有界多股票池研究草案",
    status: "DRAFT_NOT_SUBMITTED",
    eligible_universe_ids: strategyFactoryUniverses.filter((item) => item.research_draft_eligible).map((item) => item.universe_id),
    eligible_family_ids: strategyFactoryFamilies.filter((item) => item.draft_eligible).map((item) => item.family_id),
    maximum_universe_count: 3,
    maximum_candidate_count: 24,
    external_call_authorization: "NOT_GRANTED",
    sealed_effect_authorization: "NOT_GRANTED",
    production_authorization: "none",
    disclaimer: "仅生成本浏览器临时预览，不保存、不提交、不冻结、不运行。"
  },
  invariants: {
    source_backed: true,
    web_read_only: true,
    browser_draft_only: true,
    performance_sorting: false,
    external_calls_made: 0,
    real_research_runs: 0,
    bse_count: 0,
    production_authorization: "none"
  }
};

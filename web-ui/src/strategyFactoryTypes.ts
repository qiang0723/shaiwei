export type StrategyFactoryDataStatus =
  | "READY"
  | "BLOCKED_OFFICIAL_LINEAGE"
  | "DATA_GATE_REQUIRED";

export type StrategyFactoryOutcome =
  | "PRODUCTION_CURRENT_EXISTING"
  | "REJECT_CURRENT_PROGRAMS"
  | "NOT_EVALUATED"
  | "STOPPED_CONTRACT"
  | "REJECT";

export interface StrategyFactorySummary {
  overall_status: "WARN";
  decision: string;
  registered_universe_count: number;
  research_eligible_universe_count: number;
  blocked_universe_count: number;
  existing_production_strategy_count: number;
  admitted_factor_count: number;
  active_authorized_task_count: number;
  registered_program_count: number;
  authoritative_reject_program_count: number;
  stopped_contract_program_count: number;
  factor_admission_decision_count: number;
}

export interface StrategyFactoryUniverse {
  universe_id: string;
  display_name: string;
  identity_kind: "OFFICIAL_INDEX" | "CUSTOM_RULE_BASED";
  official_index_code: string | null;
  data_status: StrategyFactoryDataStatus;
  evidence_tier: string;
  authoritative_outcome: Exclude<StrategyFactoryOutcome, "REJECT">;
  research_draft_eligible: boolean;
  existing_production: boolean;
  allowed_action: string;
  blocker: string | null;
  evidence_ids: string[];
}

export interface StrategyFactoryFamily {
  family_id: string;
  display_name: string;
  draft_eligible: boolean;
}

export interface StrategyFactoryProgram {
  program_id: string;
  display_name: string;
  family_id: string;
  universe_ids: string[];
  lifecycle_state: "CLOSED" | "STOPPED_CONTRACT";
  evidence_tier: "PRODUCTION_CURRENT" | "HISTORICAL_EFFECT_AUDITED" | "DISCOVERY_ONLY";
  authoritative_outcome: "PRODUCTION_CURRENT_EXISTING" | "REJECT" | "STOPPED_CONTRACT";
  strategy_effective: "EXISTING_PRODUCTION_BASELINE" | "REJECT" | "NOT_EVALUATED";
  generation_attempt_count: number;
  evaluation_unit_count: number;
  effect_test_count: number;
  candidate_count: number;
  production_authorization: "none" | "production_current";
  summary: string;
  next_action: string;
  evidence_ids: string[];
}

export interface StrategyFactoryMatrixCell {
  family_id: string;
  universe_id: string;
  program_ids: string[];
  authoritative_outcomes: string[];
  evidence_tiers: string[];
}

export interface StrategyFactoryDraftTemplate {
  template_id: "bounded-research-draft-v1";
  display_name: string;
  status: "DRAFT_NOT_SUBMITTED";
  eligible_universe_ids: string[];
  eligible_family_ids: string[];
  maximum_universe_count: number;
  maximum_candidate_count: number;
  external_call_authorization: "NOT_GRANTED";
  sealed_effect_authorization: "NOT_GRANTED";
  production_authorization: "none";
  disclaimer: string;
}

export interface StrategyFactoryGateDecision {
  decision_id: "m5-dynamic-fundamental-lineage-gate-20260806-v1";
  display_name: "动态基本面跨池研究";
  family_id: "fundamental_dynamic";
  universe_ids: string[];
  gate_stage: "SOURCE_LINEAGE_FEASIBILITY";
  terminal_state: "BLOCKED_DATA";
  evidence_tier: "LINEAGE_NO_GO_ONLY";
  verdict: "NO_GO_M5_2_SOURCE_LINEAGE_PREEXECUTION";
  strategy_effective: "NOT_EVALUATED";
  effect_read: false;
  real_gate_run_count: 1;
  conflict_group_count: 23;
  forward_only_group_count: 23;
  pit_resolved_group_count: 0;
  route_status: "PAUSE";
  blocked_reason: string;
  next_action: string;
  release_scope_sha256: string;
  run_id: string;
  independent_audit_sha256: string;
  registry_event_sha256: string;
  evidence_commit: string;
  route_review_commit: string;
  production_authorization: "none";
  release_consumed: true;
  active_task: false;
  evidence_ids: string[];
}

export interface StrategyFactoryRouteDecision {
  route_id: "platform-route-review-20260809";
  published_at: string;
  status: "COURSE_CORRECTION_AND_OBSERVE";
  headline: string;
  summary: string;
  primary_goal: {
    goal_id: "R2-1_FORWARD_EVIDENCE_CHECKPOINT";
    state: "NOT_DUE";
    live_dual_days_at_freeze: 5;
    minimum_live_dual_days: 20;
    live_dual_rebalances_at_freeze: 0;
    minimum_live_dual_rebalances: 2;
    expected_first_live_rebalance_execution_date: "20260814";
    expected_first_due_execution_date: "20260828";
    dates_are_planning_only: true;
  };
  m7: {
    verdict: "NO_GO_M7_EVIDENCE_RECOVERY_INCOMPLETE";
    strategy_effective: "NOT_EVALUATED";
    candidate_count: 0;
    effect_read_count: 0;
    production_authorization: "none";
    next_action: string;
  };
  paused_work: string[];
  capability_note: string;
  active_authorized_task_count: 0;
  production_authorization: "none";
}

export interface StrategyFactoryData {
  summary: StrategyFactorySummary;
  attention: {
    blocked_universe_ids: string[];
    rejected_program_ids: string[];
    stopped_program_ids: string[];
    blocked_gate_decision_ids: string[];
    formal_library_empty: boolean;
  };
  universes: StrategyFactoryUniverse[];
  research_families: StrategyFactoryFamily[];
  programs: StrategyFactoryProgram[];
  matrix: StrategyFactoryMatrixCell[];
  active_tasks: never[];
  authority_projection_version: "m5-strategy-factory-authority-projection-v1";
  recent_gate_decisions: StrategyFactoryGateDecision[];
  route_decision: StrategyFactoryRouteDecision;
  draft_template: StrategyFactoryDraftTemplate;
  invariants: {
    source_backed: true;
    web_read_only: true;
    browser_draft_only: true;
    performance_sorting: false;
    external_calls_made: 0;
    real_research_runs: 0;
    bse_count: 0;
    production_authorization: "none";
  };
}

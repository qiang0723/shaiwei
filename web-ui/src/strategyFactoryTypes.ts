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

export interface StrategyFactoryData {
  summary: StrategyFactorySummary;
  attention: {
    blocked_universe_ids: string[];
    rejected_program_ids: string[];
    stopped_program_ids: string[];
    formal_library_empty: boolean;
  };
  universes: StrategyFactoryUniverse[];
  research_families: StrategyFactoryFamily[];
  programs: StrategyFactoryProgram[];
  matrix: StrategyFactoryMatrixCell[];
  active_tasks: never[];
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

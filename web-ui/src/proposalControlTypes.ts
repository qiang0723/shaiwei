export type ProposalState = "DRAFT" | "REVIEW_REQUIRED" | "CANCELLED";
export type ProposalAction = "SUBMIT_FOR_REVIEW" | "CANCEL";

export interface ProposalEvent {
  event_id?: string;
  event_seq: number;
  event_type: "PROPOSAL_CREATED" | "SUBMITTED_FOR_REVIEW" | "CANCELLED_BY_PROPOSER";
  from_state: "NONE" | "DRAFT" | "REVIEW_REQUIRED";
  to_state: ProposalState;
  recorded_at: string;
  event_sha256?: string;
}

export interface CanonicalProposal {
  schema_version: "m5-research-proposal-v1";
  proposal_id: string;
  created_at: string;
  expires_at: string;
  request: ProposalCreateInput;
  derived: {
    home_universe_id: string;
    transfer_universe_ids: string[];
    universe_count: number;
    evaluation_unit_cap: number;
    planned_generation_attempt_count: number;
    multiplicity_context: MultiplicityContext;
    actual_research_attempt_increment?: number;
  };
  authority: FixedProposalAuthority;
}

export interface ProposalCreateInput {
  template_id: "bounded-research-proposal-v1";
  template_version: 2;
  universe_ids: string[];
  home_universe_id: string;
  family_id: string;
  hypothesis_id: string;
  falsification_rule_id: "frozen-gates-reject-v1";
  generation_mode: "DETERMINISTIC_CODE" | "LLM_BOUNDED_DSL";
  generation_attempt_cap: 8 | 12 | 24;
  candidate_cap: number;
  provider_identity: "NONE_NOT_APPLICABLE" | "TO_BE_REVIEWED_NOT_AUTHORIZED";
  provider_call_intent_count: number;
  completed_response_target: number;
  provider_budget_usd: string;
  valid_days: number;
  authority: FixedProposalAuthority;
}

export interface MultiplicityScope {
  scope_id: string;
  prior_attempt_count: number;
  primary_planned_after?: number;
  sensitivity_planned_after?: number;
}

export interface MultiplicityContext {
  primary: MultiplicityScope;
  sensitivity: MultiplicityScope | null;
  planned_increment_policy: "GENERATION_ATTEMPT_CAP_COUNTS_ONCE";
  actual_research_attempt_increment: 0;
}

export interface FixedProposalAuthority {
  evidence_tier: "PROPOSAL_ONLY";
  authority_status: "NON_AUTHORITATIVE_PROPOSAL";
  authoritative_outcome: "NOT_EVALUATED";
  production_authorization: "none";
  approval_authorized: false;
  protocol_freeze_authorized: false;
  execution_release_authorized: false;
  worker_dispatch_authorized: false;
  provider_spend_authorized: false;
  external_call_authorized: false;
  deepseek_authorized: false;
  data_collection_authorized: false;
  real_data_read_authorized: false;
  label_read_authorized: false;
  sealed_effect_read_authorized: false;
  model_training_authorized: false;
  backtest_authorized: false;
  paper_authorized: false;
  forward_authorized: false;
  production_authorized: false;
  scheduler_mutation_authorized: false;
  docker_write_authorized: false;
  git_write_authorized: false;
}

export interface ProposalView {
  proposal_id: string;
  current_state: ProposalState;
  current_event_seq: number;
  available_actions: ProposalAction[];
  proposal_request_sha256: string;
  canonical_proposal: CanonicalProposal;
  events: ProposalEvent[];
}

export interface ProposalList {
  items: ProposalView[];
}

export interface FamilyControl {
  familyId: string;
  hypothesisId: string;
  generationModes: ProposalCreateInput["generation_mode"][];
}

export const FAMILY_CONTROLS: FamilyControl[] = [
  { familyId: "moneyflow", hypothesisId: "incremental-flow-information-v1", generationModes: ["DETERMINISTIC_CODE", "LLM_BOUNDED_DSL"] },
  { familyId: "fundamental_static", hypothesisId: "pit-level-quality-value-v1", generationModes: ["DETERMINISTIC_CODE"] },
  { familyId: "fundamental_dynamic", hypothesisId: "pit-fundamental-change-v1", generationModes: ["DETERMINISTIC_CODE"] },
  { familyId: "price_volume", hypothesisId: "bounded-price-volume-mechanism-v1", generationModes: ["DETERMINISTIC_CODE", "LLM_BOUNDED_DSL"] },
  { familyId: "residual_risk", hypothesisId: "benchmark-residual-structure-v1", generationModes: ["DETERMINISTIC_CODE"] }
];

export const FIXED_PROPOSAL_AUTHORITY: FixedProposalAuthority = {
  evidence_tier: "PROPOSAL_ONLY",
  authority_status: "NON_AUTHORITATIVE_PROPOSAL",
  authoritative_outcome: "NOT_EVALUATED",
  production_authorization: "none",
  approval_authorized: false,
  protocol_freeze_authorized: false,
  execution_release_authorized: false,
  worker_dispatch_authorized: false,
  provider_spend_authorized: false,
  external_call_authorized: false,
  deepseek_authorized: false,
  data_collection_authorized: false,
  real_data_read_authorized: false,
  label_read_authorized: false,
  sealed_effect_read_authorized: false,
  model_training_authorized: false,
  backtest_authorized: false,
  paper_authorized: false,
  forward_authorized: false,
  production_authorized: false,
  scheduler_mutation_authorized: false,
  docker_write_authorized: false,
  git_write_authorized: false
};

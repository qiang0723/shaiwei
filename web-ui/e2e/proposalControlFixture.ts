import {
  FIXED_PROPOSAL_AUTHORITY,
  type ProposalView
} from "../src/proposalControlTypes";

export const proposalDraft: ProposalView = {
  proposal_id: "a".repeat(64),
  current_state: "DRAFT",
  current_event_seq: 1,
  available_actions: ["SUBMIT_FOR_REVIEW", "CANCEL"],
  proposal_request_sha256: "b".repeat(64),
  canonical_proposal: {
    schema_version: "m5-research-proposal-v1",
    proposal_id: "a".repeat(64),
    created_at: "2026-08-05T10:00:00+00:00",
    expires_at: "2026-08-12T10:00:00+00:00",
    request: {
      template_id: "bounded-research-proposal-v1",
      template_version: 2,
      universe_ids: ["csi800-pit-v1"],
      home_universe_id: "csi800-pit-v1",
      family_id: "price_volume",
      hypothesis_id: "bounded-price-volume-mechanism-v1",
      falsification_rule_id: "frozen-gates-reject-v1",
      generation_mode: "DETERMINISTIC_CODE",
      generation_attempt_cap: 8,
      candidate_cap: 8,
      provider_identity: "NONE_NOT_APPLICABLE",
      provider_call_intent_count: 0,
      completed_response_target: 0,
      provider_budget_usd: "0.00",
      valid_days: 7,
      authority: FIXED_PROPOSAL_AUTHORITY
    },
    derived: {
      home_universe_id: "csi800-pit-v1",
      transfer_universe_ids: [],
      universe_count: 1,
      evaluation_unit_cap: 8,
      planned_generation_attempt_count: 8,
      actual_research_attempt_increment: 0,
      multiplicity_context: {
        primary: {
          scope_id: "related_price_volume_domain",
          prior_attempt_count: 273,
          primary_planned_after: 281
        },
        sensitivity: null,
        planned_increment_policy: "GENERATION_ATTEMPT_CAP_COUNTS_ONCE",
        actual_research_attempt_increment: 0
      }
    },
    authority: FIXED_PROPOSAL_AUTHORITY
  },
  events: [
    {
      event_seq: 1,
      event_type: "PROPOSAL_CREATED",
      from_state: "NONE",
      to_state: "DRAFT",
      recorded_at: "2026-08-05T10:00:00+00:00"
    }
  ]
};

export function submittedProposal(): ProposalView {
  return {
    ...structuredClone(proposalDraft),
    current_state: "REVIEW_REQUIRED",
    current_event_seq: 2,
    available_actions: ["CANCEL"],
    events: [
      ...proposalDraft.events,
      {
        event_seq: 2,
        event_type: "SUBMITTED_FOR_REVIEW",
        from_state: "DRAFT",
        to_state: "REVIEW_REQUIRED",
        recorded_at: "2026-08-05T10:05:00+00:00"
      }
    ]
  };
}

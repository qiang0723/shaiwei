import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  createProposal,
  resetProposalSessionForTest,
  submitProposal
} from "../proposalControlApi";
import {
  FIXED_PROPOSAL_AUTHORITY,
  type ProposalCreateInput,
  type ProposalView
} from "../proposalControlTypes";

const input: ProposalCreateInput = {
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
};

const draft: ProposalView = {
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
    request: input,
    derived: {
      home_universe_id: "csi800-pit-v1",
      transfer_universe_ids: [],
      universe_count: 1,
      evaluation_unit_cap: 8,
      planned_generation_attempt_count: 8,
      multiplicity_context: {
        primary: { scope_id: "related_price_volume_domain", prior_attempt_count: 273, primary_planned_after: 281 },
        sensitivity: null,
        planned_increment_policy: "GENERATION_ATTEMPT_CAP_COUNTS_ONCE",
        actual_research_attempt_increment: 0
      }
    },
    authority: FIXED_PROPOSAL_AUTHORITY
  },
  events: []
};

function jsonResponse(body: unknown, status = 200, csrf = false): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
      ...(csrf ? { "X-CSRF-Token": "fixture-csrf" } : {})
    }
  });
}

describe("proposal control idempotency recovery", () => {
  beforeEach(() => {
    resetProposalSessionForTest();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("reuses the create idempotency key and identical body after a lost response", async () => {
    const writes: Array<{ key: string; body: string }> = [];
    let writeCount = 0;
    vi.stubGlobal("fetch", vi.fn(async (_path: string, init?: RequestInit) => {
      if (init?.method === "GET") return jsonResponse({ count: 0, items: [] }, 200, true);
      writes.push({
        key: new Headers(init?.headers).get("Idempotency-Key") ?? "",
        body: String(init?.body)
      });
      writeCount += 1;
      if (writeCount === 1) throw new TypeError("response lost");
      return jsonResponse(draft, 201);
    }));

    await expect(createProposal(input)).rejects.toMatchObject({ code: "CONTROL_NOT_READY" });
    await expect(createProposal(input)).resolves.toMatchObject({ current_state: "DRAFT" });
    expect(writes).toHaveLength(2);
    expect(writes[1]).toEqual(writes[0]);
  });

  it("reuses both command_id and idempotency key after a lost submit response", async () => {
    const writes: Array<{ key: string; body: string }> = [];
    let writeCount = 0;
    vi.stubGlobal("fetch", vi.fn(async (_path: string, init?: RequestInit) => {
      if (init?.method === "GET") return jsonResponse({ count: 1, items: [draft] }, 200, true);
      writes.push({
        key: new Headers(init?.headers).get("Idempotency-Key") ?? "",
        body: String(init?.body)
      });
      writeCount += 1;
      if (writeCount === 1) throw new TypeError("response lost");
      if (writeCount === 2) return jsonResponse({ error: { code: "RATE_LIMITED" } }, 429);
      if (writeCount === 3) return jsonResponse({ error: { code: "CSRF_REJECTED" } }, 403);
      return jsonResponse({ ...draft, current_state: "REVIEW_REQUIRED", current_event_seq: 2, available_actions: ["CANCEL"] });
    }));

    await expect(submitProposal(draft)).rejects.toMatchObject({ code: "CONTROL_NOT_READY" });
    await expect(submitProposal(draft)).rejects.toMatchObject({ code: "RATE_LIMITED" });
    await expect(submitProposal(draft)).rejects.toMatchObject({ code: "CSRF_REJECTED" });
    await expect(submitProposal(draft)).resolves.toMatchObject({ current_state: "REVIEW_REQUIRED" });
    expect(writes).toHaveLength(4);
    expect(writes.slice(1)).toEqual([writes[0], writes[0], writes[0]]);
    const keyDigest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(writes[0]!.key));
    const keyHex = Array.from(new Uint8Array(keyDigest), (byte) => byte.toString(16).padStart(2, "0")).join("");
    expect(JSON.parse(writes[0]!.body).command_id).toBe(`m5cmd-${keyHex}`);
  });

  it("fails closed before sending a command when Web Crypto digest is unavailable", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("crypto", { randomUUID: () => "fixed-idempotency-key" });

    await expect(submitProposal(draft)).rejects.toMatchObject({ code: "CONTROL_NOT_READY" });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("fails closed before creating an intent when secure randomness is unavailable", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("crypto", {});

    await expect(createProposal(input)).rejects.toMatchObject({ code: "CONTROL_NOT_READY" });
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

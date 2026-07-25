import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchPaperBundle } from "../api";
import { formatMoney, formatPercentagePoints, formatPercent } from "../format";
import { assertReplay, assertSignal } from "../validation";

const HASH = "a".repeat(64);

function meta(snapshot = HASH) {
  return {
    as_of: "2026-07-24",
    generated_at: "2026-07-24T12:33:54+00:00",
    timezone: "Asia/Shanghai",
    freshness_status: "PASS",
    snapshot_id: snapshot,
    source_refs: [],
    evidence_hashes: {}
  };
}

function envelope(data: unknown, snapshot = HASH) {
  return {
    schema_version: "web-v1",
    request_id: "request-1",
    data,
    meta: meta(snapshot)
  };
}

const portfolio = {
  account_id: "model_baseline",
  as_of: "2026-07-24",
  benchmark_nav: "1",
  bse_count: 0,
  cash: "100",
  cash_ratio: "0.1",
  cumulative_dividends: "0",
  cumulative_fees: "1",
  drawdown: "-0.02",
  evidence_hashes: {},
  execution_policy_version: "paper-v1",
  freshness_status: "PASS",
  generated_at: "2026-07-24T12:00:00+00:00",
  market_value: "900",
  mode: "FORWARD",
  net_asset: "1000",
  net_excess: "0",
  normalized_nav: "1",
  position_count: 0,
  positions: [],
  source_ref: "data/paper/fixture.json",
  turnover: "0"
};

const nav = {
  account_id: "model_baseline",
  as_of: "2026-07-24",
  execution_policy_version: "paper-v1",
  forward_observation_count: 1,
  forward_status: "PASS",
  freshness_status: "PASS",
  observation_count: 1,
  series: [
    {
      artifact_sha256: HASH,
      benchmark_nav: "1",
      cash_ratio: "0.1",
      daily_fees: "0",
      drawdown: "0",
      freshness_status: "PASS",
      mode: "FORWARD",
      net_excess: "0",
      normalized_nav: "1",
      trade_date: "2026-07-24",
      turnover: "0"
    }
  ]
};

const forward = {
  coverage_ratio: null,
  coverage_reason: "未挂载官方日历",
  coverage_status: "NOT_EVALUATED",
  execution_policy_version: "paper-v1",
  forward_anchor_artifact_sha256: HASH,
  forward_anchor_benchmark_nav: "1",
  forward_anchor_portfolio_nav: "1",
  forward_anchor_trade_date: "2026-07-23",
  forward_cash_ratio: "0.1",
  forward_cumulative_dividends: "0",
  forward_cumulative_fees: "0",
  forward_observation_count: 1,
  forward_rebalance_count: 0,
  forward_turnover: "0",
  latest: null,
  performance_maturity: "OBSERVING",
  series: [
    {
      artifact_sha256: HASH,
      cash_ratio: "0.1",
      daily_fees: "0",
      forward_benchmark_nav: "1",
      forward_drawdown: "0",
      forward_net_excess: "0",
      forward_portfolio_nav: "1",
      trade_date: "2026-07-24",
      turnover: "0"
    }
  ],
  status: "PASS",
  suppressed_metrics: ["forward_sharpe"]
};

const replay = {
  account_id: "model_baseline",
  as_of: "2026-07-24",
  bse_count: 0,
  event_count: 3,
  fill_count: 0,
  mode_counts: { FORWARD: 1 },
  order_count: 0,
  run_count: 1,
  status: "PASS"
};

afterEach(() => vi.unstubAllGlobals());

describe("P3-1 fail-closed contract", () => {
  it("accepts a paper bundle only when every response shares one snapshot", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input);
        const data = path.includes("portfolio")
          ? portfolio
          : path.includes("forward")
            ? forward
            : path.includes("replay")
              ? replay
              : nav;
        return new Response(JSON.stringify(envelope(data)), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      })
    );
    const result = await fetchPaperBundle("2026-07-24", new AbortController().signal);
    expect(result.snapshotId).toBe(HASH);
    expect(result.nav.observation_count).toBe(1);
    expect(fetch).toHaveBeenCalledTimes(4);
    expect(String(vi.mocked(fetch).mock.calls[0]?.[0])).toContain("as_of=2026-07-24");
  });

  it("rejects a cross-snapshot paper response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input);
        const data = path.includes("portfolio")
          ? portfolio
          : path.includes("forward")
            ? forward
            : path.includes("replay")
              ? replay
              : nav;
        const snapshot = path.includes("replay") ? "b".repeat(64) : HASH;
        return new Response(JSON.stringify(envelope(data, snapshot)), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      })
    );
    await expect(
      fetchPaperBundle(undefined, new AbortController().signal)
    ).rejects.toMatchObject({ code: "CONFLICT" });
  });

  it("rejects unknown domain status", () => {
    expect(() => assertReplay({ ...replay, status: "MAYBE" })).toThrow("未知状态");
  });

  it("rejects any .BJ security instead of filtering it", () => {
    const invalidSignal = {
      actual_weight_artifact_sha256: HASH,
      actual_weight_as_of: "2026-07-23",
      bse_count: 0,
      code_snapshot_sha256: HASH,
      data_complete_at: "2026-07-24T12:00:00+00:00",
      data_snapshot_sha256: HASH,
      estimated_cost: null,
      executed_trade_leg_count: null,
      execution_evidence_status: "NOT_DUE",
      generated_at: "2026-07-24T12:00:00+00:00",
      metric_status: "NOT_DUE",
      model_artifact_sha256: HASH,
      model_spec_sha256: HASH,
      next_execution_date: null,
      open_gap: null,
      planned_trade_leg_count: 0,
      previous_signal_sha256: HASH,
      qlib_artifact_sha256: HASH,
      rebalance_days: 10,
      rebalance_due: false,
      removed_targets: [],
      signal_date: "2026-07-24",
      signal_sha256: HASH,
      source_file_sha256: HASH,
      source_ref: "data/shadow/signal.json",
      target_count: 1,
      targets: [
        {
          actual_weight: "0",
          planned_weight_delta: "0.1",
          rank: 1,
          score: 1,
          target_change: "RETAINED",
          target_weight: "0.1",
          ts_code: "920001.BJ"
        }
      ],
      tradable_denominator: null,
      tradable_numerator: null,
      turnover: null
    };
    expect(() => assertSignal(invalidSignal)).toThrow("北交所");
  });
});

describe("financial display formatting", () => {
  it("keeps units and signs explicit", () => {
    expect(formatMoney("471824.9")).toContain("471,824.90");
    expect(formatPercent("-0.0235929")).toBe("-2.36%");
    expect(formatPercentagePoints("0.005")).toBe("+0.50 个百分点");
  });

  it("does not round a tiny non-zero ratio to a false zero", () => {
    expect(formatPercent("0.00001")).toContain("<0.01%");
  });
});

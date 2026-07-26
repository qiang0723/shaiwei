import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchExperimentCatalog, fetchFactorCompare, fetchPaperBundle } from "../api";
import { formatMoney, formatPercentagePoints, formatPercent } from "../format";
import { dataVerdictCopy, notificationCopy, systemCoreCopy } from "../operationsPresentation";
import {
  assertDataQuality,
  assertFactorAdmissionHistory,
  assertFactorCatalog,
  assertFactorCompare,
  assertFactorDetail,
  assertExperimentCatalog,
  assertExperimentDetail,
  assertNotification,
  assertReplay,
  assertSignal,
  assertSystemRun
} from "../validation";
import {
  dataQuality,
  experimentCatalog,
  experimentCorrection,
  experimentG1,
  experimentOriginal,
  factorCatalog,
  factorCompare,
  factorDetail,
  factorHistory,
  notification,
  systemRuns,
  VERSION_A,
  VERSION_B
} from "../../e2e/fixtures";

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

describe("P3-2B operational evidence contract", () => {
  it("accepts the frozen data, system and notification shapes", () => {
    expect(() => assertDataQuality(structuredClone(dataQuality))).not.toThrow();
    expect(() => assertSystemRun(structuredClone(systemRuns))).not.toThrow();
    expect(() => assertNotification(structuredClone(notification))).not.toThrow();
  });

  it("does not allow data PASS to hide evidence WARN or raw-data scope", () => {
    const hiddenWarning = structuredClone(dataQuality);
    hiddenWarning.evidence_status = "PASS";
    expect(() => assertDataQuality(hiddenWarning)).toThrow("证据 WARN");

    const overclaim = structuredClone(dataQuality);
    overclaim.batch_chain.raw_parquet_rehash_status = "PASS";
    expect(() => assertDataQuality(overclaim)).toThrow("原始 Parquet");
  });

  it("preserves a recovered failure and fail-closes on BSE content", () => {
    const hiddenRecovery = structuredClone(systemRuns);
    hiddenRecovery.stages[3]!.recovered = false;
    expect(() => assertSystemRun(hiddenRecovery)).toThrow("隐藏了失败后恢复");

    const bse = structuredClone(dataQuality);
    (bse.sentinel_gate.sentinels[0]!.metrics as Record<string, unknown>).sample = "920001.BJ";
    expect(() => assertDataQuality(bse)).toThrow("北交所");
  });

  it("requires notification attempts to retain the requested message identity", () => {
    const mismatch = structuredClone(notification);
    mismatch.attempts[1]!.message_id = "aaaaaaaaaaaaaaaa";
    expect(() => assertNotification(mismatch)).toThrow("身份不一致");
  });

  it("never labels a failed or incomplete data gate as passed", () => {
    expect(dataVerdictCopy("PASS").title).toContain("通过");
    expect(dataVerdictCopy("FAIL").title).toContain("失败");
    expect(dataVerdictCopy("NOT_READY").title).toContain("尚未");
    expect(dataVerdictCopy("FAIL").tone).toBe("negative");
  });

  it("keeps system and notification copy aligned with their independent states", () => {
    expect(systemCoreCopy("WARN").title).toContain("失败恢复");
    expect(systemCoreCopy("FAIL").title).toContain("仍处于失败");
    expect(notificationCopy("PASS").title).toContain("已完成");
    expect(notificationCopy("NOT_READY").title).toContain("尚未就绪");
  });
});

describe("P3-3C factor factory evidence contract", () => {
  it("accepts the four frozen factor query shapes", () => {
    expect(() => assertFactorCatalog(structuredClone(factorCatalog))).not.toThrow();
    expect(() => assertFactorDetail(structuredClone(factorDetail))).not.toThrow();
    expect(() => assertFactorAdmissionHistory(structuredClone(factorHistory))).not.toThrow();
    expect(() => assertFactorCompare(structuredClone(factorCompare))).not.toThrow();
  });

  it("requires all fifteen gates and preserves explicit unavailable evidence", () => {
    const missingGate = structuredClone(factorDetail);
    delete (missingGate.sections.g1_statistics_and_all_gates.gates as Record<string, unknown>).hac_t;
    expect(() => assertFactorDetail(missingGate)).toThrow("15 项门");

    const recomputed = structuredClone(factorDetail);
    recomputed.sections.coverage_ratio.recomputed = true;
    expect(() => assertFactorDetail(recomputed)).toThrow("不得补算");
  });

  it("rejects performance reordering, raw payloads and BSE content", () => {
    const ranked = structuredClone(factorCompare);
    ranked.sorted_by_performance = true;
    expect(() => assertFactorCompare(ranked)).toThrow("禁止按表现排序");

    const raw = structuredClone(factorDetail) as typeof factorDetail & { params_json?: object };
    raw.params_json = { hidden: true };
    expect(() => assertFactorDetail(raw)).toThrow("禁止字段");

    const bse = structuredClone(factorDetail);
    bse.sections.frozen_definition_and_direction.economic_rationale = "920001.BJ";
    expect(() => assertFactorDetail(bse)).toThrow("北交所");
  });

  it("rejects mismatched stress-period sets instead of filling missing evidence with zero", () => {
    const mismatch = structuredClone(factorCompare);
    delete (mismatch.items[1]!.stress_max_drawdown as Record<string, number>).style_shift_2017;
    expect(() => assertFactorCompare(mismatch)).toThrow("压力期集合不一致");
  });

  it("sends repeated versions in user order and validates the response order", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = new URL(String(input), "http://localhost");
        expect(url.searchParams.getAll("version")).toEqual([VERSION_A, VERSION_B]);
        return new Response(JSON.stringify(envelope(factorCompare)), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      })
    );
    const result = await fetchFactorCompare(
      [VERSION_A, VERSION_B],
      new AbortController().signal
    );
    expect(result.data.sorted_by_performance).toBe(false);
  });
});

describe("P3-4B model and backtest evidence contract", () => {
  it("accepts the catalog, authoritative effect, invalidated method and G1 shapes", () => {
    expect(() => assertExperimentCatalog(structuredClone(experimentCatalog))).not.toThrow();
    expect(() => assertExperimentDetail(structuredClone(experimentCorrection))).not.toThrow();
    expect(() => assertExperimentDetail(structuredClone(experimentOriginal))).not.toThrow();
    expect(() => assertExperimentDetail(structuredClone(experimentG1))).not.toThrow();
  });

  it("rejects performance ranking, generic payloads and unknown decision keys", () => {
    const ranked = structuredClone(experimentCatalog);
    ranked.sorted_by_performance = true;
    expect(() => assertExperimentCatalog(ranked)).toThrow("禁止按表现排序");

    const raw = structuredClone(experimentCorrection) as typeof experimentCorrection & {
      result_json?: object;
    };
    raw.result_json = { hidden: true };
    expect(() => assertExperimentDetail(raw)).toThrow("未知字段");

    const unknown = structuredClone(experimentCorrection) as typeof experimentCorrection;
    (unknown.decision as Record<string, unknown>).sharpe = 3.2;
    expect(() => assertExperimentDetail(unknown)).toThrow("未冻结 decision 键");
  });

  it("requires all G1 gates and a typed authoritative successor for invalidated evidence", () => {
    const missingGate = structuredClone(experimentG1);
    delete (missingGate.decision.all_gates as Record<string, unknown>).hac_t;
    expect(() => assertExperimentDetail(missingGate)).toThrow("15 项门");

    const missingSuccessor = structuredClone(experimentOriginal);
    delete (missingSuccessor.decision as Record<string, unknown>).authoritative_successor_id;
    expect(() => assertExperimentDetail(missingSuccessor)).toThrow("successor_id");
  });

  it("binds the catalog response to the exact requested filter and fixed pagination", async () => {
    const mismatch = structuredClone(experimentCatalog);
    mismatch.filters.outcome_status = null;
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify(envelope(mismatch)), {
        status: 200,
        headers: { "Content-Type": "application/json" }
      }))
    );
    await expect(fetchExperimentCatalog({
      outcomeStatus: "INVALIDATED_METHOD",
      offset: 0
    }, new AbortController().signal)).rejects.toMatchObject({ code: "EVIDENCE_MISMATCH" });
  });
});

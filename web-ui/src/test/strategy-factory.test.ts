import { describe, expect, it } from "vitest";
import { strategyFactoryData } from "../../e2e/strategyFactoryFixture";
import { assertStrategyFactory } from "../validation/strategyFactory";

function clone(): typeof strategyFactoryData {
  return structuredClone(strategyFactoryData);
}

describe("strategy factory evidence contract", () => {
  it("accepts the frozen source-backed read-only fixture", () => {
    expect(() => assertStrategyFactory(clone())).not.toThrow();
  });

  it("rejects unknown outcomes and North Exchange identities", () => {
    const unknown = clone();
    unknown.programs[0]!.authoritative_outcome = "REJECT";
    unknown.programs[0]!.strategy_effective = "NOT_EVALUATED";
    expect(() => assertStrategyFactory(unknown)).toThrow();

    const bse = clone();
    bse.universes[0]!.official_index_code = "430047.BJ";
    expect(() => assertStrategyFactory(bse)).toThrow(/北交所/);
  });

  it("rejects an execution task or changed frozen counts", () => {
    const task = clone() as unknown as Record<string, unknown>;
    task.active_tasks = [{ task_id: "unexpected" }];
    expect(() => assertStrategyFactory(task)).toThrow(/活跃执行任务/);

    const count = clone();
    count.summary.admitted_factor_count = 1;
    expect(() => assertStrategyFactory(count)).toThrow(/冻结事实/);
  });
});

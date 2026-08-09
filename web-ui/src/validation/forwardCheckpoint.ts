import type { ForwardCheckpointData } from "../forwardCheckpointTypes";
import {
  booleanValue,
  date,
  hashMap,
  integer,
  numberLike,
  record,
  safeReference,
  stringArray
} from "./core";

export function assertForwardCheckpoint(value: unknown): asserts value is ForwardCheckpointData {
  const root = record(value, "双账户前瞻检查点");
  if (root.schema_version !== "web-forward-checkpoint-v1") throw new Error("双账户检查点版本无效");
  if (!["NOT_DUE", "CHECKPOINT_OBSERVED", "BLOCKED_EVIDENCE"].includes(String(root.status))) {
    throw new Error("双账户检查点状态无效");
  }
  if (!["PASS", "BLOCKED_EVIDENCE"].includes(String(root.coverage_status))) {
    throw new Error("双账户检查点覆盖状态无效");
  }
  date(root.as_of, "双账户检查点 as_of");
  [
    "protocol_forward_count",
    "protocol_forward_rebalance_count",
    "controlled_catchup_count",
    "controlled_catchup_rebalance_count",
    "live_dual_count",
    "live_dual_rebalance_count",
    "expected_open_day_count"
  ].forEach((name) => integer(root[name], `双账户检查点 ${name}`));
  if (root.minimum_live_dual_days !== 20 || root.minimum_live_dual_rebalances !== 2) {
    throw new Error("双账户检查点门槛漂移");
  }
  if (
    Number(root.protocol_forward_count) !== Number(root.controlled_catchup_count) + Number(root.live_dual_count)
    || Number(root.protocol_forward_rebalance_count)
      !== Number(root.controlled_catchup_rebalance_count) + Number(root.live_dual_rebalance_count)
  ) throw new Error("双账户检查点分层不闭合");
  if (root.coverage_ratio !== null) numberLike(root.coverage_ratio, "双账户检查点 coverage_ratio");
  ["missing_open_dates", "unexpected_live_dates"].forEach((name) => {
    stringArray(root[name], `双账户检查点 ${name}`).forEach((value) => date(value, name));
  });
  stringArray(root.blocked_reasons, "双账户检查点 blocked_reasons");
  date(root.anchor_trade_date, "双账户检查点 anchor");
  date(root.live_dual_start_trade_date, "双账户检查点 live start");
  date(root.expected_first_live_rebalance_execution_date, "双账户检查点 first rebalance");
  date(root.expected_first_due_execution_date, "双账户检查点 first due");
  if (root.next_official_open_date !== null) date(root.next_official_open_date, "双账户检查点 next open");
  if (root.comparison_anchor_source !== "CONTROLLED_CATCHUP_FORWARD" || root.dates_are_planning_only !== true) {
    throw new Error("双账户检查点锚点或计划边界无效");
  }
  if (!Array.isArray(root.series) || root.series.length !== root.live_dual_count) {
    throw new Error("双账户检查点序列数量不一致");
  }
  root.series.forEach((item, index) => {
    const point = record(item, `双账户检查点 series[${index}]`);
    date(point.trade_date, `双账户检查点 series[${index}].trade_date`);
    booleanValue(point.rebalance_due, `双账户检查点 series[${index}].rebalance_due`);
    ["top30", "top20"].forEach((role) => {
      const account = record(point[role], `双账户检查点 ${role}`);
      ["portfolio_nav", "benchmark_nav", "net_excess", "daily_fees", "cash_ratio", "turnover"].forEach(
        (name) => numberLike(account[name], `双账户检查点 ${role}.${name}`)
      );
      ["position_count", "order_count", "fill_count"].forEach(
        (name) => integer(account[name], `双账户检查点 ${role}.${name}`)
      );
    });
    numberLike(point.top20_minus_top30_portfolio_nav, "双账户检查点组合差");
    numberLike(point.top20_minus_top30_net_excess, "双账户检查点净值差之差");
  });
  stringArray(root.source_refs, "双账户检查点 source_refs").forEach((value, index) =>
    safeReference(value, `双账户检查点 source_refs[${index}]`)
  );
  hashMap(root.evidence_hashes, "双账户检查点 evidence_hashes");
  stringArray(root.prohibited_outputs, "双账户检查点 prohibited_outputs");
}

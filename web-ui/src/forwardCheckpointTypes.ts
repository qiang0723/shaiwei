export type EvidenceStratum =
  | "BACKFILL"
  | "SAME_DAY_FORWARD"
  | "CONTROLLED_CATCHUP_FORWARD";

export interface ForwardCheckpointAccountPoint {
  portfolio_nav: string;
  benchmark_nav: string;
  net_excess: string;
  daily_fees: string;
  cash_ratio: string;
  turnover: string;
  position_count: number;
  order_count: number;
  fill_count: number;
}

export interface ForwardCheckpointPoint {
  trade_date: string;
  rebalance_due: boolean;
  top30: ForwardCheckpointAccountPoint;
  top20: ForwardCheckpointAccountPoint;
  top20_minus_top30_portfolio_nav: string;
  top20_minus_top30_net_excess: string;
}

export interface ForwardCheckpointData {
  schema_version: "web-forward-checkpoint-v1";
  status: "NOT_DUE" | "CHECKPOINT_OBSERVED" | "BLOCKED_EVIDENCE";
  as_of: string;
  protocol_forward_count: number;
  protocol_forward_rebalance_count: number;
  controlled_catchup_count: number;
  controlled_catchup_rebalance_count: number;
  live_dual_count: number;
  live_dual_rebalance_count: number;
  minimum_live_dual_days: 20;
  minimum_live_dual_rebalances: 2;
  coverage_status: "PASS" | "BLOCKED_EVIDENCE";
  coverage_ratio: string | null;
  expected_open_day_count: number;
  missing_open_dates: string[];
  unexpected_live_dates: string[];
  blocked_reasons: string[];
  anchor_trade_date: string;
  live_dual_start_trade_date: string;
  comparison_anchor_source: "CONTROLLED_CATCHUP_FORWARD";
  next_official_open_date: string | null;
  expected_first_live_rebalance_execution_date: string;
  expected_first_due_execution_date: string;
  dates_are_planning_only: true;
  series: ForwardCheckpointPoint[];
  source_refs: string[];
  evidence_hashes: Record<string, string>;
  prohibited_outputs: string[];
}

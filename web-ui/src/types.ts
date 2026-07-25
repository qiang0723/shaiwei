export type DomainStatus =
  | "PASS"
  | "WARN"
  | "FAIL"
  | "STALE"
  | "NOT_READY"
  | "NOT_APPLICABLE"
  | "NO_DATA"
  | "OBSERVING"
  | "NOT_DUE"
  | "NOT_EVALUATED";

export interface ApiMeta {
  as_of: string;
  generated_at: string;
  timezone: "Asia/Shanghai";
  freshness_status: DomainStatus;
  snapshot_id: string;
  source_refs: string[];
  evidence_hashes: Record<string, string>;
}

export interface ApiEnvelope<T> {
  schema_version: "web-v1";
  request_id: string;
  data: T;
  meta: ApiMeta;
}

export interface ApiErrorEnvelope {
  schema_version?: string;
  request_id?: string;
  error?: {
    code?: string;
    message?: string;
    retryable?: boolean;
  };
}

export interface OverviewData {
  schema_version: "web-v1";
  snapshot_id: string;
  as_of: string;
  generated_at: string;
  timezone: "Asia/Shanghai";
  overall_status: DomainStatus;
  status_reason: string[];
  required_evidence_complete: boolean;
  latest_complete_trade_date: string;
  operational_status: DomainStatus;
  evidence_status: DomainStatus;
  performance_observation_status: DomainStatus;
  notification_status: DomainStatus;
  action: {
    execution_evidence_status: DomainStatus;
    next_execution_date: string | null;
    planned_trade_leg_count: number;
    rebalance_due: boolean;
    signal_date: string;
    signal_sha256: string;
    target_count: number;
  };
  paper: {
    account_day: string;
    account_id: string;
    cash: string;
    freshness_status: DomainStatus;
    market_value: string;
    net_asset: string;
    position_count: number;
    replay_status: DomainStatus;
  };
  forward: {
    coverage_ratio: string | null;
    coverage_status: DomainStatus;
    forward_anchor_trade_date: string;
    forward_cash_ratio: string;
    forward_cumulative_fees: string;
    forward_observation_count: number;
    forward_rebalance_count: number;
    forward_turnover: string;
    performance_maturity: DomainStatus;
    status: DomainStatus;
    suppressed_metrics: string[];
    latest: ForwardPoint | null;
  };
  runtime: {
    attempt_count: number;
    failed_attempt_count: number;
    first_failed_step: string | null;
    on_time: boolean;
    recovered: boolean;
    task_status: DomainStatus;
    notification: {
      status: DomainStatus;
      failed_attempt_count: number;
      recovered_message_count: number;
      duplicate_delivery_risk: boolean;
      missing_events: string[];
      required_events: string[];
      final_delivery_status: Record<string, DomainStatus>;
      max_attempt_by_event: Record<string, number>;
      source_ref: string | null;
    };
  };
  evidence: {
    acceptance_scope: string;
    bse_count: number;
    controlled_code_snapshot: string;
    data_snapshot_sha256: string;
    model_artifact_sha256: string;
    replay_status: DomainStatus;
    signal_sha256: string;
    source_refs: string[];
    evidence_hashes: Record<string, string>;
  };
}

export interface Position {
  actual_weight: string;
  close: string;
  cost_basis: string;
  market_value: string;
  price_date: string;
  quantity: number;
  realized_pnl: string;
  stale_trade_days: number;
  ts_code: string;
  unrealized_pnl: string;
}

export interface PortfolioData {
  account_id: string;
  as_of: string;
  benchmark_nav: string;
  bse_count: number;
  cash: string;
  cash_ratio: string;
  cumulative_dividends: string;
  cumulative_fees: string;
  drawdown: string;
  evidence_hashes: Record<string, string>;
  execution_policy_version: string;
  freshness_status: DomainStatus;
  generated_at: string;
  market_value: string;
  mode: "BACKFILL" | "FORWARD";
  net_asset: string;
  net_excess: string;
  normalized_nav: string;
  position_count: number;
  positions: Position[];
  source_ref: string;
  turnover: string;
}

export interface NavPoint {
  artifact_sha256: string;
  benchmark_nav: string;
  cash_ratio: string;
  daily_fees: string;
  drawdown: string;
  freshness_status: DomainStatus;
  mode: "BACKFILL" | "FORWARD";
  net_excess: string;
  normalized_nav: string;
  trade_date: string;
  turnover: string;
}

export interface NavData {
  account_id: string;
  as_of: string;
  execution_policy_version: string;
  forward_observation_count: number;
  forward_status: DomainStatus;
  freshness_status: DomainStatus;
  observation_count: number;
  series: NavPoint[];
}

export interface ForwardPoint {
  artifact_sha256: string;
  cash_ratio: string;
  daily_fees: string;
  forward_benchmark_nav: string;
  forward_drawdown: string;
  forward_net_excess: string;
  forward_portfolio_nav: string;
  trade_date: string;
  turnover: string;
}

export interface ForwardData {
  coverage_ratio: string | null;
  coverage_reason: string;
  coverage_status: DomainStatus;
  execution_policy_version: string;
  forward_anchor_artifact_sha256: string;
  forward_anchor_benchmark_nav: string;
  forward_anchor_portfolio_nav: string;
  forward_anchor_trade_date: string;
  forward_cash_ratio: string;
  forward_cumulative_dividends: string;
  forward_cumulative_fees: string;
  forward_observation_count: number;
  forward_rebalance_count: number;
  forward_turnover: string;
  latest: ForwardPoint | null;
  performance_maturity: DomainStatus;
  series: ForwardPoint[];
  status: DomainStatus;
  suppressed_metrics: string[];
}

export interface ReplayData {
  account_id: string;
  as_of: string;
  bse_count: number;
  event_count: number;
  fill_count: number;
  mode_counts: Record<string, number>;
  order_count: number;
  run_count: number;
  status: DomainStatus;
}

export interface SignalTarget {
  actual_weight: string;
  planned_weight_delta: string;
  rank: number;
  score: number;
  target_change: "ADDED" | "RETAINED" | "REMOVED";
  target_weight: string;
  ts_code: string;
}

export interface SignalData {
  actual_weight_artifact_sha256: string;
  actual_weight_as_of: string;
  bse_count: number;
  code_snapshot_sha256: string;
  data_complete_at: string;
  data_snapshot_sha256: string;
  estimated_cost: string | null;
  executed_trade_leg_count: number | null;
  execution_evidence_status: DomainStatus;
  generated_at: string;
  metric_status: DomainStatus;
  model_artifact_sha256: string;
  model_spec_sha256: string;
  next_execution_date: string | null;
  open_gap: string | null;
  planned_trade_leg_count: number;
  previous_signal_sha256: string;
  qlib_artifact_sha256: string;
  rebalance_days: number;
  rebalance_due: boolean;
  removed_targets: string[];
  signal_date: string;
  signal_sha256: string;
  source_file_sha256: string;
  source_ref: string;
  target_count: number;
  targets: SignalTarget[];
  tradable_denominator: number | null;
  tradable_numerator: number | null;
  turnover: string | null;
}

export interface PaperBundle {
  snapshotId: string;
  asOf: string;
  generatedAt: string;
  meta: ApiMeta;
  portfolio: PortfolioData;
  nav: NavData;
  forward: ForwardData;
  replay: ReplayData;
}

export interface EvidencePayload {
  title: string;
  snapshotId?: string;
  asOf?: string;
  generatedAt?: string;
  hashes: Record<string, string>;
  sources: string[];
  facts?: Array<{ label: string; value: string }>;
}

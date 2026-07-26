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

export type JsonMetric =
  | null
  | boolean
  | number
  | string
  | JsonMetric[]
  | { [key: string]: JsonMetric };

export interface OperationsStage {
  stage: string;
  status: DomainStatus;
  attempt_count: number;
  failed_attempt_count: number;
  recovered: boolean;
  first_error_type: string | null;
  terminal_finished_at: string | null;
  terminal_run_id: string | null;
  operator?: string | null;
  evidence_status?: DomainStatus;
  run_count?: number;
  event_count?: number;
}

export interface IncrementalBatch {
  batch_id: string;
  source_api: string;
  row_count: number;
  ingest_time: string;
  content_sha256: string;
}

export interface SentinelResult {
  sentinel: string;
  status: DomainStatus;
  accepted_for_signal: boolean;
  anomaly_count: number;
  metrics: Record<string, JsonMetric>;
}

export interface DataQualityData {
  status: DomainStatus;
  evidence_status: DomainStatus;
  status_reasons: string[];
  as_of: string;
  data_snapshot_sha256: string;
  code_snapshot_sha256: string;
  daily_increment: OperationsStage & {
    batch_count: number;
    market_row_count: number;
    data_snapshot_sha256: string;
  };
  batch_chain: {
    registered_batch_count: number;
    registered_row_count: number;
    source_api_count: number;
    source_api_batch_counts: Record<string, number>;
    reconstructed_data_snapshot_sha256: string;
    incremental_batch_count: number;
    incremental_batches: IncrementalBatch[];
    raw_parquet_rehash_status: DomainStatus;
    raw_parquet_rehash_reason: string;
  };
  sentinel_gate: {
    status: DomainStatus;
    evidence_status: DomainStatus;
    binding_status: "IDENTITY_MATCH_UNHASHED";
    evidence_warning: "SENTINEL_REPORT_NOT_HASH_BOUND";
    report_generated_at: string;
    report_sha256: string;
    required_failures: string[];
    sentinels: SentinelResult[];
  };
  bse_gate: {
    status: DomainStatus;
    validated_market_batch_bse_count: number;
    returned_security_bse_count: number;
    excluded_bse_reference_count: number;
  };
}

export interface SystemRunData {
  status: DomainStatus;
  as_of: string;
  core_status: DomainStatus;
  notification_status: DomainStatus;
  core_failure_message_count: number;
  core_failure_message_ids: string[];
  stages: OperationsStage[];
  notifications: {
    status: DomainStatus;
    message_count: number;
    attempt_count: number;
    failed_attempt_count: number;
    recovered_message_count: number;
    legacy_unaddressable_attempt_count: number;
  };
  release_identity: {
    status: DomainStatus;
    audit_chain_status: DomainStatus;
    recorded_at: string;
    image_id: string;
    code_snapshot_sha256: string;
    git_head: string;
    read_only_rootfs: boolean;
    mount_destinations: string[];
    live_container_identity_status: DomainStatus;
    live_container_identity_reason: string;
    record_sha256: string;
  };
  scheduler_heartbeat: {
    status: "RECORDED";
    scope: "RECORDED_HEARTBEAT_ONLY";
    recorded_status: string;
    detail: string;
    updated_at: string;
    freshness_status: DomainStatus;
  };
}

export interface NotificationAttempt {
  attempt: number;
  delivered_at: string;
  error_type: string;
  event: string;
  max_attempts: number;
  message_id: string;
  recovered: boolean;
  retryable: boolean;
  source_ref: string;
  status: DomainStatus;
}

export interface NotificationData {
  message_id: string;
  event: string;
  status: DomainStatus;
  attempt_count: number;
  failed_attempt_count: number;
  recovered: boolean;
  duplicate_delivery_risk: boolean;
  attempts: NotificationAttempt[];
}

export type FactorLifecycleStatus =
  | "CANDIDATE"
  | "TESTING"
  | "REJECTED"
  | "ADMITTED"
  | "RETIRED";

export type FactorAuthorityStatus =
  | "AUTHORITATIVE_CURRENT"
  | "HISTORICAL_NON_AUTHORITATIVE"
  | "SUPERSEDED_ENGINEERING_GENERATION"
  | "INVALIDATED";

export interface FactorCatalogItem {
  factor_id: string;
  identity_kind: "FAMILY_SCOPED_EXACT_FORMULA_SHA256";
  research_family: string;
  data_category: string;
  lifecycle_status: FactorLifecycleStatus;
  authority_status: FactorAuthorityStatus;
  version_count: number;
  current_factor_version: string | null;
  experiment_attempt_n: number;
  latest_recorded_decision: "ADMITTED" | "REJECTED";
  evidence_status: "VERIFIED";
}

export interface FactorCatalogData {
  items: FactorCatalogItem[];
  counters: {
    formal_library_count: number;
    researched_factor_count: number;
    authoritative_rejected_count: number;
    historical_only_count: number;
  };
  sort: ["research_family", "factor_id"];
  historical_response_banner: string | null;
}

export interface G1GateEvidence {
  actual: JsonMetric;
  passed: boolean;
  rule: string;
}

export interface FactorDetailSections {
  identity: {
    candidate_experiment_id: string;
    research_family: string;
    data_category: string;
  };
  frozen_definition_and_direction: {
    feature_or_formula: string;
    direction: number;
    economic_rationale: string;
    normalized_expression?: string | null;
  };
  pit_shift_and_complexity: {
    pit_sentinel_pass: boolean;
    shift_sentinel_pass: boolean;
    ast_nodes: number;
    expression_tokens: number;
    max_lookback_days: number | null;
    required_backtrack_days: number | null;
    shift_compared_values: number | null;
  };
  g1_statistics_and_all_gates: {
    statistics: Record<string, number>;
    gates: Record<string, G1GateEvidence>;
  };
  six_oos_window_rank_ic: Record<"W1" | "W2" | "W3" | "W4" | "W5" | "W6", number>;
  stress_max_drawdown: Record<string, number>;
  turnover_and_incremental_portfolio: {
    baseline_net_excess: number;
    baseline_net_icir: number;
    baseline_turnover: number;
    candidate_net_excess: number;
    candidate_net_icir: number;
    candidate_turnover: number;
  };
  cost_and_slippage_stress: {
    cost_2x_net_excess: number;
    slippage_2x_net_excess: number;
  };
  library_max_abs_correlation: number;
  coverage_ratio: UnavailableResearchSection;
  quantile_returns_and_monotonicity: UnavailableResearchSection;
  factor_autocorrelation: UnavailableResearchSection;
  candidate_pool_correlation: UnavailableResearchSection;
}

export interface UnavailableResearchSection {
  status: "NOT_EVALUATED";
  recomputed: false;
}

export interface FactorDetailData {
  factor_id: string;
  identity_kind: "FAMILY_SCOPED_EXACT_FORMULA_SHA256";
  factor_version: string;
  authority_status: FactorAuthorityStatus;
  lifecycle_status: FactorLifecycleStatus;
  recorded_decision: "ADMITTED" | "REJECTED";
  fallback_to_latest_historical: boolean;
  sections: FactorDetailSections;
  source_refs: string[];
  evidence_hashes: string[];
  historical_response_banner: string | null;
}

export interface FactorAdmissionItem {
  decision_id: string;
  recorded_at: string;
  factor_version: string;
  recorded_decision: "ADMITTED" | "REJECTED";
  authority_status: FactorAuthorityStatus;
  trial_count: number;
  failed_gates: string[];
  decision_rule_version: string;
  evidence_sha256: string;
  report_sha256: string;
}

export interface FactorAdmissionHistoryData {
  factor_id: string;
  items: FactorAdmissionItem[];
  append_only: true;
  historical_response_banner: string | null;
}

export interface FactorCompareItem {
  factor_id: string;
  factor_version: string;
  recorded_decision: "ADMITTED" | "REJECTED";
  statistics: Record<string, number>;
  six_oos_window_rank_ic: Record<"W1" | "W2" | "W3" | "W4" | "W5" | "W6", number>;
  stress_max_drawdown: Record<string, number>;
  portfolio: FactorDetailSections["turnover_and_incremental_portfolio"];
  cost_and_slippage: FactorDetailSections["cost_and_slippage_stress"];
}

export interface FactorCompareData {
  factor_versions: string[];
  fingerprint: Record<string, string>;
  items: FactorCompareItem[];
  sorted_by_performance: false;
}

export type ExperimentKind =
  | "research_experiment"
  | "p2_engineering_run"
  | "p2_effect_original"
  | "p2_effect_correction";

export type ExperimentOutcome =
  | "RECORDED"
  | "FAILED"
  | "DISCOVERY_ONLY"
  | "DISCOVERY_REJECTED"
  | "G1_REJECTED"
  | "G1_ADMITTED"
  | "REVIEW_STOPPED"
  | "ENGINEERING_GO_ONLY"
  | "HISTORICAL_EFFECT_REJECTED"
  | "INVALIDATED_METHOD";

export type ExperimentEvidenceTier =
  | "BASELINE_BACKTEST"
  | "SHADOW_SIGNAL"
  | "FORWARD_SHADOW_SIGNAL"
  | "G1_FACTOR_DECISION"
  | "GP_DISCOVERY_ATTEMPT"
  | "GP_STAGE1_ATTEMPT"
  | "D1_DISCOVERY_ATTEMPT_WITH_REVIEW_OVERLAY"
  | "P2_ENGINEERING"
  | "P2_EFFECT_AUTHORITATIVE"
  | "P2_EFFECT_INVALIDATED";

export type ExperimentAuthorityStatus =
  | "AUTHORITATIVE_CURRENT"
  | "AUTHORITATIVE_STOP"
  | "DISCOVERY_ONLY"
  | "HISTORICAL_NON_AUTHORITATIVE"
  | "INVALIDATED_METHOD"
  | "PROVISIONAL_HISTORICAL"
  | "RECORDED_EXPERIMENT"
  | "SUPERSEDED_ENGINEERING_GENERATION";

export type ExperimentLifecycleStatus =
  | "COMPLETED"
  | "DISCOVERY_ATTEMPT"
  | "DISCOVERY_EVALUATED"
  | "ENGINEERING_GO_ONLY"
  | "FAILED"
  | "REJECT"
  | "REJECTED"
  | "REVIEW_STOPPED";

export type ExperimentEvidenceStatus = "VERIFIED" | "LEDGER_RECORDED_PROVISIONAL";

export interface ExperimentCatalogItem {
  experiment_kind: ExperimentKind;
  experiment_id: string;
  recorded_at: string;
  research_family: string;
  evidence_tier: ExperimentEvidenceTier;
  authority_status: ExperimentAuthorityStatus;
  lifecycle_status: ExperimentLifecycleStatus;
  outcome_status: ExperimentOutcome;
  model_or_engine: string;
  engine_version: string;
  failed_reason_count: number;
  evidence_status: ExperimentEvidenceStatus;
}

export interface ExperimentCatalogData {
  catalog_protocol_id: "p3-experiment-catalog-v1";
  items: ExperimentCatalogItem[];
  counters: {
    projected_total_count: number;
    as_of_count: number;
    filtered_count: number;
    returned_count: number;
    kind_counts: Record<ExperimentKind, number>;
  };
  filters: Record<string, string | null> & { as_of: string | null };
  available_filters: {
    experiment_kind: ExperimentKind[];
    research_family: string[];
    evidence_tier: ExperimentEvidenceTier[];
    authority_status: ExperimentAuthorityStatus[];
    lifecycle_status: ExperimentLifecycleStatus[];
    outcome_status: ExperimentOutcome[];
    evidence_status: ExperimentEvidenceStatus[];
  };
  page: {
    offset: number;
    limit: number;
    has_previous: boolean;
    has_more: boolean;
    previous_offset: number | null;
    next_offset: number | null;
  };
  sort: ["recorded_at:desc", "experiment_kind:asc", "experiment_id:asc"];
  sorted_by_performance: false;
  historical_response_banner: string | null;
}

export interface ExperimentDetailData {
  experiment_kind: ExperimentKind;
  experiment_id: string;
  recorded_at: string;
  research_family: string;
  evidence_tier: ExperimentEvidenceTier;
  authority_status: ExperimentAuthorityStatus;
  lifecycle_status: ExperimentLifecycleStatus;
  outcome_status: ExperimentOutcome;
  model_or_engine: string;
  engine_version: string;
  seed: string;
  train_period: string;
  valid_period: string;
  code_snapshot_sha256: string;
  data_snapshot_sha256: string;
  decision: Record<string, JsonMetric>;
  failed_reasons: string[];
  evidence_status: ExperimentEvidenceStatus;
  source_refs: string[];
  evidence_hashes: string[];
  historical_response_banner: string | null;
}

export interface EvidencePayload {
  title: string;
  snapshotId?: string;
  asOf?: string;
  generatedAt?: string;
  hashes: Record<string, string>;
  sources: string[];
  facts?: Array<{ label: string; value: string }>;
  technicalFacts?: Array<{ label: string; value: string }>;
}

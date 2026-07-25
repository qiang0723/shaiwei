const A = "a".repeat(64);
const B = "b".repeat(64);
const C = "c".repeat(64);

const meta = {
  as_of: "2026-07-24",
  generated_at: "2026-07-24T12:33:54+00:00",
  timezone: "Asia/Shanghai",
  freshness_status: "PASS",
  snapshot_id: A,
  source_refs: ["ledger/paper_runs.csv", "data/paper/example.json"],
  evidence_hashes: { paper_run_rows_sha256: B }
};

export const overview = {
  schema_version: "web-v1",
  snapshot_id: A,
  as_of: "2026-07-24",
  generated_at: "2026-07-24T12:33:54+00:00",
  timezone: "Asia/Shanghai",
  overall_status: "WARN",
  status_reason: ["OPERATIONAL_WARN", "NOTIFICATION_WARN"],
  required_evidence_complete: true,
  latest_complete_trade_date: "2026-07-24",
  operational_status: "WARN",
  evidence_status: "PASS",
  performance_observation_status: "OBSERVING",
  notification_status: "WARN",
  action: {
    execution_evidence_status: "NOT_DUE",
    next_execution_date: null,
    planned_trade_leg_count: 0,
    rebalance_due: false,
    signal_date: "2026-07-24",
    signal_sha256: A,
    target_count: 30
  },
  paper: {
    account_day: "2026-07-24",
    account_id: "model_baseline",
    cash: "180557.98",
    freshness_status: "PASS",
    market_value: "291266.92",
    net_asset: "471824.90",
    position_count: 22,
    replay_status: "PASS"
  },
  forward: {
    coverage_ratio: null,
    coverage_status: "NOT_EVALUATED",
    forward_anchor_trade_date: "2026-07-22",
    forward_cash_ratio: "0.3826800578",
    forward_cumulative_fees: "0",
    forward_observation_count: 2,
    forward_rebalance_count: 0,
    forward_turnover: "0",
    performance_maturity: "OBSERVING",
    status: "PASS",
    suppressed_metrics: ["forward_sharpe"],
    latest: {
      artifact_sha256: C,
      cash_ratio: "0.3826800578",
      daily_fees: "0",
      forward_benchmark_nav: "0.9818987628",
      forward_drawdown: "-0.0235929342",
      forward_net_excess: "-0.0054916969",
      forward_portfolio_nav: "0.9764070658",
      trade_date: "2026-07-24",
      turnover: "0"
    }
  },
  runtime: {
    attempt_count: 2,
    failed_attempt_count: 1,
    first_failed_step: "ForwardQlibError",
    on_time: true,
    recovered: true,
    task_status: "PASS",
    notification: {
      status: "WARN",
      failed_attempt_count: 1,
      recovered_message_count: 1,
      duplicate_delivery_risk: true,
      missing_events: [],
      required_events: ["paper_cycle_started", "paper_cycle_completed"],
      final_delivery_status: { paper_cycle_started: "PASS", paper_cycle_completed: "PASS" },
      max_attempt_by_event: { paper_cycle_started: 1, paper_cycle_completed: 2 },
      source_ref: "logs/notifications/example.jsonl"
    }
  },
  evidence: {
    acceptance_scope: "P3-0_READ_ONLY_QUERY_ONLY",
    bse_count: 0,
    controlled_code_snapshot: A,
    data_snapshot_sha256: B,
    model_artifact_sha256: C,
    replay_status: "PASS",
    signal_sha256: A,
    source_refs: meta.source_refs,
    evidence_hashes: { latest_paper_artifact_sha256: C }
  }
};

export const portfolio = {
  account_id: "model_baseline",
  as_of: "2026-07-24",
  benchmark_nav: "0.9854111248",
  bse_count: 0,
  cash: "180557.98",
  cash_ratio: "0.3826800578",
  cumulative_dividends: "32.00",
  cumulative_fees: "113.22",
  drawdown: "-0.0563502",
  evidence_hashes: { artifact_sha256: C, code_snapshot_sha256: A },
  execution_policy_version: "paper-v1",
  freshness_status: "PASS",
  generated_at: "2026-07-24T12:33:43+00:00",
  market_value: "291266.92",
  mode: "FORWARD",
  net_asset: "471824.90",
  net_excess: "-0.0417613248",
  normalized_nav: "0.9436498",
  position_count: 2,
  positions: [
    { actual_weight: "0.02699", close: "14.15", cost_basis: "15548.16", market_value: "12735", price_date: "20260724", quantity: 900, realized_pnl: "0", stale_trade_days: 0, ts_code: "000032.SZ", unrealized_pnl: "-2813.16" },
    { actual_weight: "0.03545", close: "41.81", cost_basis: "16505.17", market_value: "16724", price_date: "20260724", quantity: 400, realized_pnl: "0", stale_trade_days: 0, ts_code: "603699.SH", unrealized_pnl: "218.83" }
  ],
  source_ref: "data/paper/example.json",
  turnover: "0"
};

export const nav = {
  account_id: "model_baseline",
  as_of: "2026-07-24",
  execution_policy_version: "paper-v1",
  forward_observation_count: 2,
  forward_status: "PASS",
  freshness_status: "PASS",
  observation_count: 3,
  series: [
    { artifact_sha256: A, benchmark_nav: "1.0035", cash_ratio: "0.3736", daily_fees: "113.22", drawdown: "-0.0335", freshness_status: "PASS", mode: "BACKFILL", net_excess: "-0.0371", normalized_nav: "0.9664", trade_date: "2026-07-22", turnover: "0.63" },
    { artifact_sha256: B, benchmark_nav: "1.0046", cash_ratio: "0.3771", daily_fees: "0", drawdown: "-0.0424", freshness_status: "PASS", mode: "FORWARD", net_excess: "-0.0471", normalized_nav: "0.9575", trade_date: "2026-07-23", turnover: "0" },
    { artifact_sha256: C, benchmark_nav: "0.9854", cash_ratio: "0.3827", daily_fees: "0", drawdown: "-0.0564", freshness_status: "PASS", mode: "FORWARD", net_excess: "-0.0418", normalized_nav: "0.9436", trade_date: "2026-07-24", turnover: "0" }
  ]
};

export const forward = {
  coverage_ratio: null,
  coverage_reason: "P3-0 未挂载官方交易日历，成熟度保持 OBSERVING",
  coverage_status: "NOT_EVALUATED",
  execution_policy_version: "paper-v1",
  forward_anchor_artifact_sha256: A,
  forward_anchor_benchmark_nav: "1.0035",
  forward_anchor_portfolio_nav: "0.9664",
  forward_anchor_trade_date: "2026-07-22",
  forward_cash_ratio: "0.3827",
  forward_cumulative_dividends: "0",
  forward_cumulative_fees: "0",
  forward_observation_count: 2,
  forward_rebalance_count: 0,
  forward_turnover: "0",
  latest: overview.forward.latest,
  performance_maturity: "OBSERVING",
  series: [
    { artifact_sha256: B, cash_ratio: "0.3771", daily_fees: "0", forward_benchmark_nav: "1.0011", forward_drawdown: "-0.0092", forward_net_excess: "-0.0103", forward_portfolio_nav: "0.9908", trade_date: "2026-07-23", turnover: "0" },
    overview.forward.latest
  ],
  status: "PASS",
  suppressed_metrics: ["forward_annualized_return", "forward_sharpe"]
};

export const replay = {
  account_id: "model_baseline",
  as_of: "2026-07-24",
  bse_count: 0,
  event_count: 198,
  fill_count: 22,
  mode_counts: { BACKFILL: 1, FORWARD: 2 },
  order_count: 30,
  run_count: 3,
  status: "PASS"
};

export const signal = {
  actual_weight_artifact_sha256: B,
  actual_weight_as_of: "2026-07-23",
  bse_count: 0,
  code_snapshot_sha256: A,
  data_complete_at: "2026-07-24T12:06:18+00:00",
  data_snapshot_sha256: B,
  estimated_cost: null,
  executed_trade_leg_count: null,
  execution_evidence_status: "NOT_DUE",
  generated_at: "2026-07-24T12:33:28+00:00",
  metric_status: "NOT_DUE",
  model_artifact_sha256: C,
  model_spec_sha256: A,
  next_execution_date: null,
  open_gap: null,
  planned_trade_leg_count: 0,
  previous_signal_sha256: C,
  qlib_artifact_sha256: A,
  rebalance_days: 10,
  rebalance_due: false,
  removed_targets: [],
  signal_date: "2026-07-24",
  signal_sha256: A,
  source_file_sha256: B,
  source_ref: "data/shadow/signals/example.json",
  target_count: 3,
  targets: [
    { actual_weight: "0", planned_weight_delta: "0.0333", rank: 1, score: 0.0921, target_change: "RETAINED", target_weight: "0.0333", ts_code: "688008.SH" },
    { actual_weight: "0.0284", planned_weight_delta: "0.0049", rank: 2, score: 0.0501, target_change: "RETAINED", target_weight: "0.0333", ts_code: "603308.SH" },
    { actual_weight: "0", planned_weight_delta: "0.0333", rank: 3, score: 0.0792, target_change: "ADDED", target_weight: "0.0333", ts_code: "300475.SZ" }
  ],
  tradable_denominator: null,
  tradable_numerator: null,
  turnover: null
};

export const dataQuality = {
  status: "PASS",
  evidence_status: "WARN",
  status_reasons: ["SENTINEL_REPORT_NOT_HASH_BOUND"],
  as_of: "2026-07-24",
  data_snapshot_sha256: B,
  code_snapshot_sha256: A,
  daily_increment: {
    stage: "daily_increment",
    status: "PASS",
    attempt_count: 1,
    failed_attempt_count: 0,
    recovered: false,
    first_error_type: null,
    terminal_finished_at: "2026-07-24T12:06:18+00:00",
    terminal_run_id: "daily-run-1",
    operator: "docker-scheduler",
    batch_count: 1,
    market_row_count: 5197,
    data_snapshot_sha256: B
  },
  batch_chain: {
    registered_batch_count: 69020,
    registered_row_count: 45160002,
    source_api_count: 2,
    source_api_batch_counts: { "tushare.daily": 8272, "tushare.adj_factor": 8271 },
    reconstructed_data_snapshot_sha256: B,
    incremental_batch_count: 1,
    incremental_batches: [
      {
        batch_id: "batch-001",
        source_api: "tushare.daily",
        row_count: 5197,
        ingest_time: "2026-07-24T12:06:15+00:00",
        content_sha256: C
      }
    ],
    raw_parquet_rehash_status: "NOT_EVALUATED",
    raw_parquet_rehash_reason: "P3-2A 不挂载 data/raw"
  },
  sentinel_gate: {
    status: "PASS",
    evidence_status: "WARN",
    binding_status: "IDENTITY_MATCH_UNHASHED",
    evidence_warning: "SENTINEL_REPORT_NOT_HASH_BOUND",
    report_generated_at: "2026-07-24T12:29:27+00:00",
    report_sha256: C,
    required_failures: [],
    sentinels: Array.from({ length: 10 }, (_, index) => ({
      sentinel: `S${index + 1}`,
      status: index === 9 ? "NOT_APPLICABLE" : "PASS",
      accepted_for_signal: true,
      anomaly_count: 0,
      metrics: index === 0 ? { security_count: 5535, excluded_bse_count: 0 } : { checked_rows: 100 + index }
    }))
  },
  bse_gate: {
    status: "PASS",
    validated_market_batch_bse_count: 0,
    returned_security_bse_count: 0,
    excluded_bse_reference_count: 0
  }
};

const stages = [
  ["daily_increment", 1, 0, false, null],
  ["sentinels", 1, 0, false, null],
  ["next_open_reconciliation", 1, 0, false, null],
  ["shadow_signal", 2, 1, true, "ForwardQlibError"],
  ["paper_cycle", 1, 0, false, null],
  ["paper_replay", 1, 0, false, null]
] as const;

export const systemRuns = {
  status: "WARN",
  as_of: "2026-07-24",
  core_status: "WARN",
  notification_status: "WARN",
  core_failure_message_count: 1,
  core_failure_message_ids: ["ce3bfbf96e9ec474"],
  stages: stages.map(([stage, attempts, failures, recovered, error], index) => ({
    stage,
    status: "PASS",
    attempt_count: attempts,
    failed_attempt_count: failures,
    recovered,
    first_error_type: error,
    terminal_finished_at: index === 5 ? null : `2026-07-24T12:${String(10 + index).padStart(2, "0")}:00+00:00`,
    terminal_run_id: index === 1 || index === 5 ? null : `run-${index}`,
    ...(index === 1 ? { evidence_status: "WARN" } : {}),
    ...(index === 5 ? { run_count: 6, event_count: 198 } : {})
  })),
  notifications: {
    status: "WARN",
    message_count: 9,
    attempt_count: 11,
    failed_attempt_count: 1,
    recovered_message_count: 1,
    legacy_unaddressable_attempt_count: 40
  },
  release_identity: {
    status: "PASS",
    audit_chain_status: "PASS",
    recorded_at: "2026-07-24T12:25:29+00:00",
    image_id: `sha256:${A}`,
    code_snapshot_sha256: A,
    git_head: "e".repeat(40),
    read_only_rootfs: true,
    mount_destinations: ["/workspace/data", "/workspace/ledger", "/workspace/logs"],
    live_container_identity_status: "NOT_EVALUATED",
    live_container_identity_reason: "Web 查询不挂 Docker socket",
    record_sha256: B
  },
  scheduler_heartbeat: {
    status: "RECORDED",
    scope: "RECORDED_HEARTBEAT_ONLY",
    recorded_status: "noop",
    detail: "20260725",
    updated_at: "2026-07-25T13:14:23+00:00",
    freshness_status: "NOT_EVALUATED"
  }
};

export const notification = {
  message_id: "ce3bfbf96e9ec474",
  event: "daily_scheduler_cycle_failed",
  status: "PASS",
  attempt_count: 2,
  failed_attempt_count: 1,
  recovered: true,
  duplicate_delivery_risk: true,
  attempts: [
    {
      attempt: 1,
      delivered_at: "2026-07-23T14:42:05+00:00",
      error_type: "NetworkError",
      event: "daily_scheduler_cycle_failed",
      max_attempts: 3,
      message_id: "ce3bfbf96e9ec474",
      recovered: false,
      retryable: true,
      source_ref: "logs/notifications/feishu_20260723.jsonl",
      status: "FAIL"
    },
    {
      attempt: 2,
      delivered_at: "2026-07-23T14:42:08+00:00",
      error_type: "",
      event: "daily_scheduler_cycle_failed",
      max_attempts: 3,
      message_id: "ce3bfbf96e9ec474",
      recovered: true,
      retryable: false,
      source_ref: "logs/notifications/feishu_20260723.jsonl",
      status: "PASS"
    }
  ]
};

export const FACTOR_A = "1".repeat(64);
export const FACTOR_B = "2".repeat(64);
export const FACTOR_HISTORICAL = "3".repeat(64);
export const VERSION_A = "a1".repeat(6);
export const VERSION_B = "b2".repeat(6);
export const VERSION_OLD = "c3".repeat(6);

export const factorCatalog = {
  items: [
    {
      factor_id: FACTOR_A,
      identity_kind: "FAMILY_SCOPED_EXACT_FORMULA_SHA256",
      research_family: "p1-moneyflow-v1",
      data_category: "moneyflow",
      lifecycle_status: "REJECTED",
      authority_status: "AUTHORITATIVE_CURRENT",
      version_count: 2,
      current_factor_version: VERSION_A,
      experiment_attempt_n: 18,
      latest_recorded_decision: "REJECTED",
      evidence_status: "VERIFIED"
    },
    {
      factor_id: FACTOR_B,
      identity_kind: "FAMILY_SCOPED_EXACT_FORMULA_SHA256",
      research_family: "p1-moneyflow-v1",
      data_category: "moneyflow",
      lifecycle_status: "REJECTED",
      authority_status: "AUTHORITATIVE_CURRENT",
      version_count: 2,
      current_factor_version: VERSION_B,
      experiment_attempt_n: 18,
      latest_recorded_decision: "REJECTED",
      evidence_status: "VERIFIED"
    },
    {
      factor_id: FACTOR_HISTORICAL,
      identity_kind: "FAMILY_SCOPED_EXACT_FORMULA_SHA256",
      research_family: "stage1-gp-preflight-v1",
      data_category: "price_volume",
      lifecycle_status: "REJECTED",
      authority_status: "HISTORICAL_NON_AUTHORITATIVE",
      version_count: 1,
      current_factor_version: null,
      experiment_attempt_n: 82,
      latest_recorded_decision: "REJECTED",
      evidence_status: "VERIFIED"
    }
  ],
  counters: {
    formal_library_count: 0,
    researched_factor_count: 10,
    authoritative_rejected_count: 8,
    historical_only_count: 2
  },
  sort: ["research_family", "factor_id"],
  historical_response_banner: null
};

const factorStatistics = {
  direction: 1,
  dsr_probability: 0.63,
  expected_maximum_periodic_sharpe: 0.014,
  hac_t: 0.59,
  kurtosis: 5.24,
  mean_oriented_oos_rank_ic: 0.0047,
  observed_periodic_sharpe: 0.022,
  positive_oos_windows: 4,
  rank_ic_retention: 0.356,
  skewness: -0.028,
  trial_count: 18,
  turnover_ratio: 0.865,
  valid_trial_sharpes: 18,
  z_score: 0.332
};

const factorGates = Object.fromEntries([
  ["complexity", { actual: { ast_nodes: 11, expression_tokens: 9 }, passed: true, rule: "tokens<=20; ast_nodes<=80" }],
  ["cost_2x", { actual: 0.1663, passed: true, rule: "net excess at cost +100% >= 0" }],
  ["deflated_sharpe", { actual: 0.63, passed: false, rule: "DSR probability>=0.95" }],
  ["economic_rationale", { actual: 36, passed: true, rule: "human rationale length>=20" }],
  ["hac_t", { actual: 0.59, passed: false, rule: "Newey-West(10) t>=3.0" }],
  ["incremental_net_excess", { actual: -0.317, passed: false, rule: "incremental net excess > 0" }],
  ["incremental_net_icir", { actual: -0.011, passed: false, rule: "incremental net ICIR > 0" }],
  ["library_correlation", { actual: 0, passed: true, rule: "max |rho|<0.5" }],
  ["pit_and_shift", { actual: { pit: true, shift: true }, passed: true, rule: "PIT and shift PASS" }],
  ["rank_ic_retention", { actual: 0.356, passed: false, rule: "retention>=0.5" }],
  ["rolling_window_sign", { actual: 4, passed: true, rule: "positive windows>=4/6" }],
  ["slippage_2x", { actual: 0.1661, passed: true, rule: "doubled slippage >= 0" }],
  ["stress_drawdown", { actual: 0.1138, passed: true, rule: "every stress drawdown<=0.2" }],
  ["turnover", { actual: 0.865, passed: true, rule: "candidate/base turnover<=1.1" }],
  ["valid_trial_sharpes", { actual: 18, passed: true, rule: "valid trial Sharpes>=2" }]
]);

const factorWindows = { W1: -0.0124, W2: 0.0342, W3: -0.0098, W4: 0.0043, W5: 0.0061, W6: 0.0061 };
const factorStress = { style_shift_2017: 0.0219, microcap_crash_2024: 0.0635, volume_price_drawdown_2026h1: 0.1138 };
const factorPortfolio = {
  baseline_net_excess: 0.5182,
  baseline_net_icir: 0.389,
  baseline_turnover: 34.049,
  candidate_net_excess: 0.2012,
  candidate_net_icir: 0.378,
  candidate_turnover: 29.469
};
const factorCosts = { cost_2x_net_excess: 0.1664, slippage_2x_net_excess: 0.1661 };

export const factorDetail = {
  factor_id: FACTOR_A,
  identity_kind: "FAMILY_SCOPED_EXACT_FORMULA_SHA256",
  factor_version: VERSION_A,
  authority_status: "AUTHORITATIVE_CURRENT",
  lifecycle_status: "REJECTED",
  recorded_decision: "REJECTED",
  fallback_to_latest_historical: false,
  sections: {
    identity: { candidate_experiment_id: VERSION_A, research_family: "p1-moneyflow-v1", data_category: "moneyflow" },
    frozen_definition_and_direction: {
      feature_or_formula: "sum(net_mf_amount, 20) / sum(daily.amount / 10, 20)",
      direction: 1,
      economic_rationale: "二十个连续交易日累计净流入强度检验月度资金压力是否稳定并能覆盖交易成本。"
    },
    pit_shift_and_complexity: {
      pit_sentinel_pass: true,
      shift_sentinel_pass: true,
      ast_nodes: 11,
      expression_tokens: 9,
      max_lookback_days: null,
      required_backtrack_days: null,
      shift_compared_values: null
    },
    g1_statistics_and_all_gates: { statistics: factorStatistics, gates: factorGates },
    six_oos_window_rank_ic: factorWindows,
    stress_max_drawdown: factorStress,
    turnover_and_incremental_portfolio: factorPortfolio,
    cost_and_slippage_stress: factorCosts,
    library_max_abs_correlation: 0,
    coverage_ratio: { status: "NOT_EVALUATED", recomputed: false },
    quantile_returns_and_monotonicity: { status: "NOT_EVALUATED", recomputed: false },
    factor_autocorrelation: { status: "NOT_EVALUATED", recomputed: false },
    candidate_pool_correlation: { status: "NOT_EVALUATED", recomputed: false }
  },
  source_refs: [`experiment:${VERSION_A}`, "factor_admission:1853210f3504"],
  evidence_hashes: [A, B, C],
  historical_response_banner: null
};

export const factorHistory = {
  factor_id: FACTOR_A,
  items: [
    {
      decision_id: "111111111111",
      recorded_at: "2026-07-22T12:00:00+00:00",
      factor_version: VERSION_OLD,
      recorded_decision: "REJECTED",
      authority_status: "SUPERSEDED_ENGINEERING_GENERATION",
      trial_count: 18,
      failed_gates: ["hac_t", "incremental_net_excess"],
      decision_rule_version: "g1-v1",
      evidence_sha256: B,
      report_sha256: C
    },
    {
      decision_id: "222222222222",
      recorded_at: "2026-07-24T12:00:00+00:00",
      factor_version: VERSION_A,
      recorded_decision: "REJECTED",
      authority_status: "AUTHORITATIVE_CURRENT",
      trial_count: 18,
      failed_gates: ["deflated_sharpe", "hac_t", "incremental_net_excess", "incremental_net_icir", "rank_ic_retention"],
      decision_rule_version: "g1-v1",
      evidence_sha256: A,
      report_sha256: B
    }
  ],
  append_only: true,
  historical_response_banner: null
};

export const factorCompare = {
  factor_versions: [VERSION_A, VERSION_B],
  fingerprint: {
    universe_id: "csi800-pit-v1",
    benchmark_id: "000906.SH",
    label_id: "t11-vwap",
    horizon_id: "10d",
    neutralization_id: "industry-size-v1",
    window_set_id: "w1-w6-v1",
    stress_set_id: "stress-v1",
    portfolio_policy_id: "top30-equal-v1",
    cost_policy_id: "cost-v1",
    decision_rule_version: "g1-v1",
    candidate_code_sha256: A,
    data_snapshot_sha256: B,
    comparison_policy_id: C
  },
  items: [
    {
      factor_id: FACTOR_A,
      factor_version: VERSION_A,
      recorded_decision: "REJECTED",
      statistics: factorStatistics,
      six_oos_window_rank_ic: factorWindows,
      stress_max_drawdown: factorStress,
      portfolio: factorPortfolio,
      cost_and_slippage: factorCosts
    },
    {
      factor_id: FACTOR_B,
      factor_version: VERSION_B,
      recorded_decision: "REJECTED",
      statistics: { ...factorStatistics, dsr_probability: 0.51, hac_t: 0.41 },
      six_oos_window_rank_ic: { W1: 0.004, W2: 0.009, W3: -0.006, W4: 0.002, W5: 0.001, W6: 0.003 },
      stress_max_drawdown: { style_shift_2017: 0.041, microcap_crash_2024: 0.091, volume_price_drawdown_2026h1: 0.142 },
      portfolio: { ...factorPortfolio, candidate_net_excess: 0.131, candidate_net_icir: 0.301 },
      cost_and_slippage: { cost_2x_net_excess: 0.102, slippage_2x_net_excess: 0.099 }
    }
  ],
  sorted_by_performance: false
};

export function response(data: unknown, asOf?: string | null) {
  return {
    schema_version: "web-v1",
    request_id: "e2e-request",
    data,
    meta: { ...meta, as_of: asOf ?? meta.as_of }
  };
}

import {
  ArrowLeftOutlined,
  CheckCircleFilled,
  CloseCircleFilled,
  HistoryOutlined,
  InfoCircleFilled,
  SafetyCertificateFilled,
  WarningFilled
} from "@ant-design/icons";
import { Column } from "@ant-design/charts";
import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Empty, Select, Tag } from "antd";
import { useMemo } from "react";
import { fetchExperimentCatalog, fetchExperimentDetail, UiQueryError } from "../api";
import { DataTable, type DataColumn } from "../components/DataTable";
import { useAsOf } from "../components/AppShell";
import { MetricCard } from "../components/MetricCard";
import { PageHeader } from "../components/PageHeader";
import { PageError, PageLoading, RefreshNotice } from "../components/RequestState";
import { formatDateTime, formatNumber, formatPercent, shortHash } from "../format";
import { RouterLink, useRouter } from "../routing";
import type {
  ApiMeta,
  EvidencePayload,
  ExperimentAuthorityStatus,
  ExperimentCatalogItem,
  ExperimentDetailData,
  ExperimentEvidenceTier,
  ExperimentKind,
  ExperimentLifecycleStatus,
  ExperimentOutcome,
  JsonMetric
} from "../types";

const KIND_LABELS: Record<ExperimentKind, string> = {
  research_experiment: "研究实验",
  p2_engineering_run: "P2 工程运行",
  p2_effect_original: "P2 原效果（失效）",
  p2_effect_correction: "P2 权威纠错"
};

const TIER_LABELS: Record<ExperimentEvidenceTier, string> = {
  BASELINE_BACKTEST: "基线回测记录",
  SHADOW_SIGNAL: "影子信号",
  FORWARD_SHADOW_SIGNAL: "前瞻影子信号",
  G1_FACTOR_DECISION: "G1 因子判决",
  GP_DISCOVERY_ATTEMPT: "GP 发现尝试",
  GP_STAGE1_ATTEMPT: "GP Stage-1 尝试",
  D1_DISCOVERY_ATTEMPT_WITH_REVIEW_OVERLAY: "LLM 发现与复核",
  P2_ENGINEERING: "P2 工程门",
  P2_EFFECT_AUTHORITATIVE: "P2 权威历史效果",
  P2_EFFECT_INVALIDATED: "P2 失效方法效果"
};

const AUTHORITY_LABELS: Record<ExperimentAuthorityStatus, string> = {
  AUTHORITATIVE_CURRENT: "当前权威",
  AUTHORITATIVE_STOP: "权威停止",
  DISCOVERY_ONLY: "仅发现层",
  HISTORICAL_NON_AUTHORITATIVE: "历史非权威",
  INVALIDATED_METHOD: "方法已失效",
  PROVISIONAL_HISTORICAL: "历史 provisional",
  RECORDED_EXPERIMENT: "仅登记实验",
  SUPERSEDED_ENGINEERING_GENERATION: "被替代工程代"
};

const LIFECYCLE_LABELS: Record<ExperimentLifecycleStatus, string> = {
  COMPLETED: "已完成记录",
  DISCOVERY_ATTEMPT: "发现尝试",
  DISCOVERY_EVALUATED: "发现期已评估",
  ENGINEERING_GO_ONLY: "仅工程 GO",
  FAILED: "执行失败",
  REJECT: "发现层拒绝",
  REJECTED: "研究拒绝",
  REVIEW_STOPPED: "复核停止"
};

const OUTCOME_COPY: Record<ExperimentOutcome, {
  label: string;
  description: string;
  tone: "neutral" | "positive" | "warning" | "negative";
}> = {
  RECORDED: {
    label: "已登记",
    description: "只说明运行或信号已有记录，不推断策略有效。",
    tone: "neutral"
  },
  FAILED: {
    label: "执行失败",
    description: "这是登记的执行失败，不提供成功结果。",
    tone: "negative"
  },
  DISCOVERY_ONLY: {
    label: "仅发现层",
    description: "仍是 GP/LLM 发现证据，尚未形成 G1 判决。",
    tone: "neutral"
  },
  DISCOVERY_REJECTED: {
    label: "发现层拒绝",
    description: "拒绝发生在发现层，不得表述为 G1 或策略拒绝。",
    tone: "warning"
  },
  G1_REJECTED: {
    label: "G1 未准入",
    description: "已有 G1 拒绝结论；REJECT 是研究结果，不是系统故障。",
    tone: "warning"
  },
  G1_ADMITTED: {
    label: "G1 已准入",
    description: "已有 G1 准入记录，但仍不自动授权生产。",
    tone: "positive"
  },
  REVIEW_STOPPED: {
    label: "复核停止",
    description: "权威复核已停止后续流程，没有进入效果评价或 G1。",
    tone: "warning"
  },
  ENGINEERING_GO_ONLY: {
    label: "仅工程 GO",
    description: "只证明数据与工程通路，不代表策略有效。",
    tone: "neutral"
  },
  HISTORICAL_EFFECT_REJECTED: {
    label: "历史效果拒绝",
    description: "当前权威历史效果结论为 REJECT，且没有生产授权。",
    tone: "warning"
  },
  INVALIDATED_METHOD: {
    label: "方法已失效",
    description: "旧数值可复算但不再权威，禁止据此作效果判断。",
    tone: "negative"
  }
};

const DECISION_LABELS: Record<string, string> = {
  all_gates: "全部 G1 门",
  artifact_file_count: "产物文件数",
  authoritative_successor_id: "权威后继实验",
  authoritative_successor_kind: "权威后继类型",
  base_maximum_drawdown: "基础最大回撤",
  base_net_excess: "基础净超额",
  cost_1_5x_net_excess: "成本 1.5× 净超额",
  cost_gate_pass: "成本门",
  decision: "发现层决定",
  determinism_pass: "确定性",
  discovery_status: "发现状态",
  diversification_gate_status: "分散化门",
  double_cost_net_excess: "成本 2× 净超额",
  drawdown_gate_pass: "回撤门",
  engineering_complete: "工程完成",
  extra_slippage_net_excess: "额外双边 10bp",
  g1_run: "是否运行 G1",
  historical_effect_gate: "历史效果门",
  human_gate_ready: "人工闸就绪",
  idempotency_pass: "幂等复跑",
  numeric_results_status: "旧数值权威状态",
  original_p2_2_execution_valid: "原执行方法有效",
  original_p2_2_model_valid: "原模型方法有效",
  pipeline_fixture_pass: "合成通路",
  pooled: "合并窗口",
  prediction_rows: "预测行数",
  production_authorization: "生产授权",
  rank_ic: "RankIC 聚合",
  rebalance_count: "调仓次数",
  rebalance_due: "是否调仓",
  recorded_decision: "记录判决",
  results_known_before_correction: "纠错前结果已知",
  review_overlay: "复核覆盖",
  review_roles: "复核角色",
  score_rows: "分数行数",
  signal_sha256: "信号哈希",
  status: "记录状态",
  strategy_effective: "策略有效性",
  strategy_results_inspected: "已查看策略效果",
  trade_days: "交易日",
  trial_count: "研究尝试 N",
  valid_period: "验证区间",
  verdict: "机器裁决",
  window_gate_pass: "窗口门",
  window_metrics: "冻结窗口"
};

function decisionLabel(key: string) {
  return DECISION_LABELS[key] ?? key.replaceAll("_", " ");
}

function outcomeIcon(outcome: ExperimentOutcome) {
  const tone = OUTCOME_COPY[outcome].tone;
  if (tone === "positive") return <CheckCircleFilled />;
  if (tone === "negative") return <CloseCircleFilled />;
  if (tone === "warning") return <WarningFilled />;
  return <InfoCircleFilled />;
}

function OutcomeBadge({ outcome }: { outcome: ExperimentOutcome }) {
  const copy = OUTCOME_COPY[outcome];
  return (
    <Tag className={`experiment-outcome experiment-outcome-${copy.tone}`} icon={outcomeIcon(outcome)}>
      {copy.label} · {outcome}
    </Tag>
  );
}

function AuthorityBadge({ authority }: { authority: ExperimentAuthorityStatus }) {
  const current = authority === "AUTHORITATIVE_CURRENT" || authority === "AUTHORITATIVE_STOP";
  return (
    <Tag
      className={`experiment-authority experiment-authority-${current ? "current" : "historical"}`}
      icon={current ? <SafetyCertificateFilled /> : <HistoryOutlined />}
    >
      {AUTHORITY_LABELS[authority]} · {authority}
    </Tag>
  );
}

function HistoricalBanner({ visible }: { visible: boolean }) {
  if (!visible) return null;
  return (
    <Alert
      className="experiment-history-banner"
      type="warning"
      showIcon
      message="历史记录已应用当前权威覆盖"
      description="记录按查询截止日期裁剪，但 authority 使用当前已知纠错；这是按当前知识回看，不是重演当时状态。"
    />
  );
}

function experimentEvidence(
  title: string,
  meta: ApiMeta,
  options: {
    hashes?: Record<string, string>;
    sources?: string[];
    facts?: Array<{ label: string; value: string }>;
  } = {}
): EvidencePayload {
  return {
    title,
    snapshotId: meta.snapshot_id,
    asOf: meta.as_of,
    generatedAt: meta.generated_at,
    hashes: { ...meta.evidence_hashes, ...options.hashes },
    sources: options.sources ?? meta.source_refs,
    facts: options.facts
  };
}

function experimentHeaderProps(meta: ApiMeta) {
  return {
    asOf: meta.as_of,
    generatedAt: meta.generated_at,
    asOfLabel: "查询截止",
    generatedAtLabel: "研究投影生成"
  };
}

function experimentPath(
  kind: ExperimentKind,
  experimentId: string,
  search = ""
) {
  return `/experiments/${kind}/${encodeURIComponent(experimentId)}${search}`;
}

function shortIdentity(value: string) {
  return value.length > 20 ? `${value.slice(0, 17)}…` : value;
}

function formatDecisionNumber(value: number, key: string) {
  if (/net_excess|drawdown/.test(key)) return formatPercent(value, { signed: /net_excess/.test(key) });
  if (/rank_ic/.test(key)) return formatNumber(value, 4);
  return formatNumber(value, Number.isInteger(value) ? 0 : 3);
}

function DecisionValue({ value, metric }: { value: JsonMetric; metric: string }) {
  if (value === null) return <span className="muted">未登记</span>;
  if (typeof value === "boolean") return <span>{value ? "是" : "否"}</span>;
  if (typeof value === "number") return <span>{formatDecisionNumber(value, metric)}</span>;
  if (typeof value === "string") {
    return value.length >= 32 && /^[0-9a-f]+$/.test(value)
      ? <code title={value}>{shortHash(value)}</code>
      : <span>{value}</span>;
  }
  if (Array.isArray(value)) {
    return (
      <span className="experiment-value-array">
        {value.map((item, index) => (
          <DecisionValue key={`${metric}-${index}`} value={item} metric={metric} />
        ))}
      </span>
    );
  }
  return (
    <dl className="experiment-nested-facts">
      {Object.entries(value).map(([key, item]) => (
        <div key={key}>
          <dt>{decisionLabel(key)}</dt>
          <dd><DecisionValue value={item} metric={key} /></dd>
        </div>
      ))}
    </dl>
  );
}

const FILTER_KEYS = [
  "experiment_kind",
  "research_family",
  "evidence_tier",
  "authority_status",
  "lifecycle_status",
  "outcome_status",
  "evidence_status"
] as const;

function CatalogPage() {
  const { asOf } = useAsOf();
  const { location, navigate } = useRouter();
  const parameters = useMemo(() => new URLSearchParams(location.search), [location.search]);
  const rawOffset = parameters.get("offset") ?? "0";
  const offset = /^\d+$/.test(rawOffset) ? Number(rawOffset) : Number.NaN;
  const filters = Object.fromEntries(
    FILTER_KEYS.map((key) => [key, parameters.get(key) || undefined])
  ) as Record<(typeof FILTER_KEYS)[number], string | undefined>;

  const query = useQuery({
    queryKey: ["experiment-catalog", asOf || "latest", ...FILTER_KEYS.map((key) => filters[key] ?? "ALL"), rawOffset],
    queryFn: ({ signal }) => fetchExperimentCatalog({
      experimentKind: filters.experiment_kind,
      researchFamily: filters.research_family,
      evidenceTier: filters.evidence_tier,
      authorityStatus: filters.authority_status,
      lifecycleStatus: filters.lifecycle_status,
      outcomeStatus: filters.outcome_status,
      evidenceStatus: filters.evidence_status,
      asOf,
      offset
    }, signal)
  });

  if (query.isPending) return <PageLoading label="正在核对实验目录、权威覆盖与分页身份…" />;
  if (query.isError) return <PageError error={query.error} retry={() => query.refetch()} />;

  const { data, meta } = query.data;
  const setFilter = (key: (typeof FILTER_KEYS)[number], value: string) => {
    const next = new URLSearchParams(location.search);
    if (value === "ALL") next.delete(key);
    else next.set(key, value);
    next.delete("offset");
    navigate(`/experiments${next.size ? `?${next.toString()}` : ""}`);
  };
  const setOffset = (value: number | null) => {
    if (value === null) return;
    const next = new URLSearchParams(location.search);
    if (value === 0) next.delete("offset");
    else next.set("offset", String(value));
    navigate(`/experiments${next.size ? `?${next.toString()}` : ""}`);
  };
  const search = location.search;
  const columns: DataColumn<ExperimentCatalogItem>[] = [
    {
      title: "实验 ID",
      dataIndex: "experiment_id",
      key: "experiment_id",
      fixed: "left",
      width: 190,
      render: (value: string, item) => (
        <RouterLink
          className="table-factor-link"
          title={value}
          to={experimentPath(item.experiment_kind, value, search)}
        >
          <code>{shortIdentity(value)}</code>
        </RouterLink>
      )
    },
    {
      title: "结论语义",
      dataIndex: "outcome_status",
      key: "outcome",
      width: 250,
      render: (value: ExperimentOutcome) => <OutcomeBadge outcome={value} />
    },
    {
      title: "权威状态",
      dataIndex: "authority_status",
      key: "authority",
      width: 270,
      render: (value: ExperimentAuthorityStatus) => <AuthorityBadge authority={value} />
    },
    { title: "证据层级", dataIndex: "evidence_tier", key: "tier", width: 230, render: (value: ExperimentEvidenceTier) => TIER_LABELS[value] },
    { title: "研究家族", dataIndex: "research_family", key: "family", width: 230 },
    { title: "模型 / 引擎", dataIndex: "model_or_engine", key: "engine", width: 210 },
    { title: "失败项", dataIndex: "failed_reason_count", key: "failures", align: "right", width: 80 },
    { title: "记录时间", dataIndex: "recorded_at", key: "recorded", width: 190, render: formatDateTime },
    { title: "证据", dataIndex: "evidence_status", key: "evidence", width: 190 }
  ];
  const pageNumber = Math.floor(data.page.offset / data.page.limit) + 1;
  const pageCount = Math.max(1, Math.ceil(data.counters.filtered_count / data.page.limit));
  const evidence = experimentEvidence("实验目录证据", meta, {
    facts: [
      { label: "投影记录", value: String(data.counters.projected_total_count) },
      { label: "历史切片", value: String(data.counters.as_of_count) },
      { label: "筛选后", value: String(data.counters.filtered_count) },
      { label: "固定排序", value: data.sort.join(" → ") },
      { label: "按表现排序", value: String(data.sorted_by_performance) }
    ]
  });

  const filterSpecs: Array<{
    key: (typeof FILTER_KEYS)[number];
    label: string;
    values: string[];
    valueLabel?: (value: string) => string;
  }> = [
    { key: "outcome_status", label: "结论语义筛选", values: data.available_filters.outcome_status, valueLabel: (value) => OUTCOME_COPY[value as ExperimentOutcome].label },
    { key: "authority_status", label: "权威状态筛选", values: data.available_filters.authority_status, valueLabel: (value) => AUTHORITY_LABELS[value as ExperimentAuthorityStatus] },
    { key: "evidence_tier", label: "证据层级筛选", values: data.available_filters.evidence_tier, valueLabel: (value) => TIER_LABELS[value as ExperimentEvidenceTier] },
    { key: "research_family", label: "研究家族筛选", values: data.available_filters.research_family },
    { key: "experiment_kind", label: "实验类型筛选", values: data.available_filters.experiment_kind, valueLabel: (value) => KIND_LABELS[value as ExperimentKind] },
    { key: "lifecycle_status", label: "生命周期筛选", values: data.available_filters.lifecycle_status, valueLabel: (value) => LIFECYCLE_LABELS[value as ExperimentLifecycleStatus] },
    { key: "evidence_status", label: "证据状态筛选", values: data.available_filters.evidence_status }
  ];

  return (
    <div className="page-stack experiment-page">
      <PageHeader
        eyebrow="MODEL / BACKTEST EVIDENCE"
        title="研究证据"
        description="运行、发现、判决、工程与历史效果分层；一条记录不等于一个有效模型。"
        status={meta.freshness_status}
        evidence={evidence}
        {...experimentHeaderProps(meta)}
      />
      {query.isFetching ? <RefreshNotice asOf={meta.as_of} generatedAt={meta.generated_at} /> : null}
      <HistoricalBanner visible={Boolean(data.historical_response_banner)} />

      <section className="experiment-scope-hero" aria-labelledby="experiment-scope-heading">
        <div>
          <span className="section-kicker">EVIDENCE SCOPE</span>
          <h2 id="experiment-scope-heading">
            {data.counters.projected_total_count} 条实验记录，不是 {data.counters.projected_total_count} 个有效模型
          </h2>
          <p>先看证据层级与权威状态，再看已登记结果；页面不提供成功率、收益排名或“最佳策略”。</p>
        </div>
        <Tag icon={<SafetyCertificateFilled />}>READ ONLY · NO RANKING</Tag>
      </section>

      <section className="metric-grid experiment-kind-grid" aria-label="实验记录类型计数">
        <MetricCard label="通用研究实验" value={data.counters.kind_counts.research_experiment} detail="含基线、影子、GP、G1 与 D1" />
        <MetricCard label="P2 工程运行" value={data.counters.kind_counts.p2_engineering_run} detail="只证明工程通路" />
        <MetricCard label="P2 失效方法" value={data.counters.kind_counts.p2_effect_original} detail="旧数值非权威" tone="warning" />
        <MetricCard label="P2 权威纠错" value={data.counters.kind_counts.p2_effect_correction} detail="当前历史效果裁决" tone="warning" />
      </section>

      <section className="table-surface" aria-labelledby="experiment-catalog-heading">
        <div className="section-heading experiment-catalog-heading">
          <div>
            <span className="section-kicker">CATALOG · BACKEND PAGINATED</span>
            <h2 id="experiment-catalog-heading">实验目录</h2>
            <p>历史切片 {data.counters.as_of_count} 条 · 筛选后 {data.counters.filtered_count} 条 · 当前第 {pageNumber}/{pageCount} 页</p>
          </div>
        </div>
        <details className="filter-disclosure">
          <summary>精确筛选 · 7 项</summary>
          <div className="experiment-filters" aria-label="实验目录筛选">
            {filterSpecs.map((spec) => (
              <Select
                key={spec.key}
                aria-label={spec.label}
                value={filters[spec.key] ?? "ALL"}
                onChange={(value) => setFilter(spec.key, value)}
                options={[
                  { value: "ALL", label: spec.label.replace("筛选", "：全部") },
                  ...spec.values.map((value) => ({ value, label: spec.valueLabel ? `${spec.valueLabel(value)} · ${value}` : value }))
                ]}
              />
            ))}
          </div>
        </details>

        <div className="experiment-desktop-catalog">
          <DataTable
            label="实验目录"
            columns={columns}
            data={data.items}
            rowKey={(item) => `${item.experiment_kind}|${item.experiment_id}`}
            minimumWidth="wide"
            emptyText="当前精确筛选没有实验记录"
          />
        </div>
        <div className="experiment-mobile-cards" aria-label="移动端实验目录">
          {data.items.map((item) => (
            <article key={`${item.experiment_kind}|${item.experiment_id}`} className="experiment-catalog-card">
              <div className="experiment-card-heading">
                <RouterLink to={experimentPath(item.experiment_kind, item.experiment_id, search)}>
                  <code title={item.experiment_id}>{shortIdentity(item.experiment_id)}</code>
                </RouterLink>
                <OutcomeBadge outcome={item.outcome_status} />
              </div>
              <p>{item.research_family}</p>
              <AuthorityBadge authority={item.authority_status} />
              <dl>
                <div><dt>证据层级</dt><dd>{TIER_LABELS[item.evidence_tier]}</dd></div>
                <div><dt>生命周期</dt><dd>{LIFECYCLE_LABELS[item.lifecycle_status]}</dd></div>
                <div><dt>记录时间</dt><dd>{formatDateTime(item.recorded_at)}</dd></div>
                <div><dt>失败项</dt><dd>{item.failed_reason_count}</dd></div>
              </dl>
              <RouterLink to={experimentPath(item.experiment_kind, item.experiment_id, search)}>查看类型化证据</RouterLink>
            </article>
          ))}
          {!data.items.length ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前精确筛选没有实验记录" /> : null}
        </div>
        <div className="experiment-pagination" aria-label="实验目录分页">
          <Button disabled={!data.page.has_previous} onClick={() => setOffset(data.page.previous_offset)}>上一页</Button>
          <span>第 {pageNumber} / {pageCount} 页 · 每页 {data.page.limit} 条</span>
          <Button disabled={!data.page.has_more} onClick={() => setOffset(data.page.next_offset)}>下一页</Button>
        </div>
      </section>
      <p className="page-evidence-footer">目录每次只读取一个后台分页响应；不批量拉取详情，不按结果重排，不跨快照拼页。</p>
    </div>
  );
}

function metricObject(value: JsonMetric | undefined): Record<string, JsonMetric> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return {};
  return value;
}

interface P2WindowRow {
  window: string;
  trade_days: number;
  rebalance_count: number;
  base_net_excess: number;
  base_maximum_drawdown: number;
  cost_1_5x_net_excess: number;
  double_cost_net_excess: number;
  extra_slippage_net_excess: number;
}

function p2WindowRows(decision: Record<string, JsonMetric>): P2WindowRow[] {
  const rows = decision.window_metrics;
  if (!Array.isArray(rows)) return [];
  return rows.map((value) => {
    const row = metricObject(value);
    return {
      window: String(row.window),
      trade_days: Number(row.trade_days),
      rebalance_count: Number(row.rebalance_count),
      base_net_excess: Number(row.base_net_excess),
      base_maximum_drawdown: Number(row.base_maximum_drawdown),
      cost_1_5x_net_excess: Number(row.cost_1_5x_net_excess),
      double_cost_net_excess: Number(row.double_cost_net_excess),
      extra_slippage_net_excess: Number(row.extra_slippage_net_excess)
    };
  });
}

function DetailBoundary({ data, search }: { data: ExperimentDetailData; search: string }) {
  const copy = OUTCOME_COPY[data.outcome_status];
  const successorKind = data.decision.authoritative_successor_kind;
  const successorId = data.decision.authoritative_successor_id;
  if (data.outcome_status === "INVALIDATED_METHOD") {
    const successor = successorKind === "p2_effect_correction" && typeof successorId === "string"
      ? experimentPath(successorKind, successorId, search)
      : null;
    return (
      <Alert
        className="experiment-boundary-alert"
        type="error"
        showIcon
        message="方法已失效：以下旧数值可复算，但不能用于权威效果判断"
        description="标签成熟、执行时钟或容量约束违反冻结方法；旧证据保留，不覆盖、不删除。"
        action={successor ? <RouterLink to={successor}>查看权威纠错实验</RouterLink> : undefined}
      />
    );
  }
  const type = copy.tone === "negative" ? "error" : copy.tone === "warning" ? "warning" : "info";
  return (
    <Alert
      className="experiment-boundary-alert"
      type={type}
      showIcon
      message={`${copy.label}：${copy.description}`}
      description={`证据层级 ${TIER_LABELS[data.evidence_tier]}；权威状态 ${AUTHORITY_LABELS[data.authority_status]}。`}
    />
  );
}

function G1GateTable({ gates }: { gates: Record<string, JsonMetric> }) {
  return (
    <div className="experiment-gate-table-wrap" role="region" aria-label="实验 G1 十五门" tabIndex={0}>
      <table className="experiment-detail-table">
        <thead><tr><th>门</th><th>结论</th><th>实际</th><th>规则</th></tr></thead>
        <tbody>
          {Object.entries(gates).map(([name, value]) => {
            const gate = metricObject(value);
            const passed = gate.passed === true;
            return (
              <tr key={name}>
                <th>{decisionLabel(name)}</th>
                <td><Tag color={passed ? "success" : "warning"}>{passed ? "PASS" : "REJECT"}</Tag></td>
                <td><DecisionValue value={gate.actual ?? null} metric={name} /></td>
                <td>{String(gate.rule ?? "")}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function P2EffectSection({ data }: { data: ExperimentDetailData }) {
  const rows = p2WindowRows(data.decision);
  if (!rows.length) return null;
  const scenarios = [
    ["基础", "base_net_excess"],
    ["成本 1.5×", "cost_1_5x_net_excess"],
    ["成本 2×", "double_cost_net_excess"],
    ["额外双边 10bp", "extra_slippage_net_excess"]
  ] as const;
  const chart = rows.flatMap((row) => scenarios.map(([scenario, key]) => ({
    window: row.window,
    scenario,
    value: row[key]
  })));
  const invalidated = data.outcome_status === "INVALIDATED_METHOD";
  const pooled = metricObject(data.decision.pooled);
  return (
    <>
      <section className={`chart-surface experiment-effect-section ${invalidated ? "invalidated-result" : ""}`} aria-labelledby="experiment-window-heading">
        <div className="section-heading">
          <div>
            <span className="section-kicker">REGISTERED WINDOW EVIDENCE</span>
            <h2 id="experiment-window-heading">冻结窗口与成本场景</h2>
          </div>
          {invalidated ? <Tag color="error">可复算 · 非权威</Tag> : <Tag color="warning">权威历史 REJECT</Tag>}
        </div>
        <div className="chart-canvas" role="img" aria-label="三个冻结窗口在四种成本场景下的净超额分组柱状图">
          <Column
            data={chart}
            xField="window"
            yField="value"
            colorField="scenario"
            group
            height={330}
            axis={{ y: { labelFormatter: (value: number) => `${(Number(value) * 100).toFixed(0)}%` } }}
            legend={{ color: { position: "top" } }}
            animate={false}
          />
        </div>
        <div className="experiment-effect-table-wrap" role="region" aria-label="P2 窗口与成本精确数据" tabIndex={0}>
          <table className="experiment-detail-table">
            <thead><tr><th>窗口</th><th>交易日</th><th>调仓</th><th>基础净超额</th><th>成本 1.5×</th><th>成本 2×</th><th>额外 10bp</th><th>基础最大回撤</th></tr></thead>
            <tbody>{rows.map((row) => <tr key={row.window}><th>{row.window}</th><td>{row.trade_days}</td><td>{row.rebalance_count}</td><td>{formatPercent(row.base_net_excess, { signed: true })}</td><td>{formatPercent(row.cost_1_5x_net_excess, { signed: true })}</td><td>{formatPercent(row.double_cost_net_excess, { signed: true })}</td><td>{formatPercent(row.extra_slippage_net_excess, { signed: true })}</td><td>{formatPercent(row.base_maximum_drawdown)}</td></tr>)}</tbody>
          </table>
        </div>
      </section>
      <section className={`surface-panel ${invalidated ? "invalidated-result" : ""}`} aria-labelledby="experiment-pooled-heading">
        <div className="section-heading"><div><span className="section-kicker">POOLED</span><h2 id="experiment-pooled-heading">合并窗口精确结果</h2></div></div>
        <dl className="experiment-decision-grid">
          {Object.entries(pooled).map(([key, value]) => <div key={key}><dt>{decisionLabel(key)}</dt><dd><DecisionValue value={value} metric={key} /></dd></div>)}
        </dl>
      </section>
    </>
  );
}

function DetailPage({ kind, experimentId }: { kind: ExperimentKind; experimentId: string }) {
  const { asOf } = useAsOf();
  const { location } = useRouter();
  const query = useQuery({
    queryKey: ["experiment-detail", kind, experimentId, asOf || "latest"],
    queryFn: ({ signal }) => fetchExperimentDetail(kind, experimentId, asOf, signal)
  });

  if (query.isPending) return <PageLoading label="正在核对实验身份、权威覆盖与类型化证据…" />;
  if (query.isError) return <PageError error={query.error} retry={() => query.refetch()} />;

  const { data, meta } = query.data;
  const evidenceHashes = Object.fromEntries(
    data.evidence_hashes.map((hash, index) => [`experiment_evidence_${index + 1}`, hash])
  );
  const evidence = experimentEvidence("实验详情证据", meta, {
    hashes: {
      ...(data.code_snapshot_sha256 ? { code_snapshot_sha256: data.code_snapshot_sha256 } : {}),
      ...(data.data_snapshot_sha256 ? { data_snapshot_sha256: data.data_snapshot_sha256 } : {}),
      ...evidenceHashes
    },
    sources: data.source_refs,
    facts: [
      { label: "实验类型", value: KIND_LABELS[data.experiment_kind] },
      { label: "结论语义", value: data.outcome_status },
      { label: "权威状态", value: data.authority_status },
      { label: "证据层级", value: data.evidence_tier }
    ]
  });
  const generalDecision = Object.entries(data.decision).filter(
    ([key]) => !["all_gates", "window_metrics", "pooled"].includes(key)
  );
  const gates = "all_gates" in data.decision ? metricObject(data.decision.all_gates) : null;
  const backSearch = location.search;

  return (
    <div className="page-stack experiment-page">
      <PageHeader
        eyebrow="EXPERIMENT EVIDENCE"
        title="实验结论与证据"
        description="先确认 evidence tier、authority 与 outcome，再阅读已登记数值；页面不重算任何效果。"
        status={meta.freshness_status}
        evidence={evidence}
        {...experimentHeaderProps(meta)}
      />
      {query.isFetching ? <RefreshNotice asOf={meta.as_of} generatedAt={meta.generated_at} /> : null}
      <HistoricalBanner visible={Boolean(data.historical_response_banner)} />
      <RouterLink className="factor-back-link" to={`/experiments${backSearch}`}>
        <ArrowLeftOutlined /> 返回实验目录
      </RouterLink>
      <DetailBoundary data={data} search={location.search} />

      <section className="surface-panel experiment-identity-panel" aria-labelledby="experiment-identity-heading">
        <div className="section-heading">
          <div><span className="section-kicker">IDENTITY / AUTHORITY</span><h2 id="experiment-identity-heading">实验身份与结论边界</h2></div>
          <div className="experiment-badge-stack"><OutcomeBadge outcome={data.outcome_status} /><AuthorityBadge authority={data.authority_status} /></div>
        </div>
        <dl className="experiment-identity-grid">
          <div><dt>实验 ID</dt><dd><code title={data.experiment_id}>{data.experiment_id}</code></dd></div>
          <div><dt>实验类型</dt><dd>{KIND_LABELS[data.experiment_kind]}</dd></div>
          <div><dt>证据层级</dt><dd>{TIER_LABELS[data.evidence_tier]} · <code>{data.evidence_tier}</code></dd></div>
          <div><dt>生命周期</dt><dd>{LIFECYCLE_LABELS[data.lifecycle_status]} · <code>{data.lifecycle_status}</code></dd></div>
          <div><dt>研究家族</dt><dd>{data.research_family}</dd></div>
          <div><dt>模型 / 引擎</dt><dd>{data.model_or_engine}</dd></div>
          <div><dt>引擎版本</dt><dd><code title={data.engine_version}>{shortIdentity(data.engine_version)}</code></dd></div>
          <div><dt>记录时间</dt><dd>{formatDateTime(data.recorded_at)}</dd></div>
          <div><dt>训练区间</dt><dd>{data.train_period || "未登记"}</dd></div>
          <div><dt>验证区间</dt><dd>{data.valid_period || "未登记"}</dd></div>
          <div><dt>seed</dt><dd>{data.seed || "未登记"}</dd></div>
          <div><dt>证据状态</dt><dd>{data.evidence_status}</dd></div>
        </dl>
      </section>

      {generalDecision.length ? (
        <section className="surface-panel" aria-labelledby="experiment-decision-heading">
          <div className="section-heading"><div><span className="section-kicker">REGISTERED DECISION</span><h2 id="experiment-decision-heading">已登记的类型化结论</h2></div></div>
          <dl className="experiment-decision-grid">
            {generalDecision.map(([key, value]) => <div key={key}><dt>{decisionLabel(key)}</dt><dd><DecisionValue value={value} metric={key} /></dd></div>)}
          </dl>
        </section>
      ) : null}

      {gates ? (
        <section className="table-surface" aria-labelledby="experiment-gates-heading">
          <div className="section-heading"><div><span className="section-kicker">G1 · ALL GATES</span><h2 id="experiment-gates-heading">全部 G1 门</h2></div><Tag color="warning">记录判决，不是系统故障</Tag></div>
          <G1GateTable gates={gates} />
        </section>
      ) : null}

      <P2EffectSection data={data} />

      <section className="surface-panel" aria-labelledby="experiment-failures-heading">
        <div className="section-heading"><div><span className="section-kicker">FAILURES / LIMITS</span><h2 id="experiment-failures-heading">失败原因与证据缺口</h2></div></div>
        {data.failed_reasons.length ? (
          <ul className="experiment-failure-list">{data.failed_reasons.map((reason) => <li key={reason}><WarningFilled /><code>{reason}</code></li>)}</ul>
        ) : <p className="muted">没有登记失败原因；这不等于策略有效，只表示本记录未附失败项。</p>}
        <Alert
          type="info"
          showIcon
          message="没有逐日 NAV，页面不绘制净值、日回撤或交易时序"
          description="experiment_summary 只登记聚合证据；浏览器不会从其他文件、账本或端点补算。"
        />
      </section>
      <p className="page-evidence-footer">详情只消费一个类型化响应；decision 按证据层级白名单渲染，未知键会阻断页面而不是通用 JSON 展示。</p>
    </div>
  );
}

export default function ExperimentsPage() {
  const { location } = useRouter();
  if (location.pathname === "/experiments") return <CatalogPage />;
  const detail = location.pathname.match(
    /^\/experiments\/(research_experiment|p2_engineering_run|p2_effect_original|p2_effect_correction)\/([A-Za-z0-9][A-Za-z0-9._-]{0,127})$/
  );
  if (detail) return <DetailPage kind={detail[1] as ExperimentKind} experimentId={detail[2]!} />;
  return (
    <PageError
      error={new UiQueryError("INVALID_ARGUMENT", "模型/回测页面路径无效")}
      retry={() => window.location.assign("/experiments")}
    />
  );
}

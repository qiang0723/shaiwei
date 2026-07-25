import {
  ArrowLeftOutlined,
  CheckCircleFilled,
  CloseCircleFilled,
  ExperimentOutlined,
  FileSearchOutlined,
  HistoryOutlined,
  InfoCircleOutlined,
  MinusCircleFilled,
  SafetyCertificateFilled,
  SwapOutlined
} from "@ant-design/icons";
import { Column, Line } from "@ant-design/charts";
import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Checkbox, Empty, Select, Tag } from "antd";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  fetchFactorAdmissionHistory,
  fetchFactorCatalog,
  fetchFactorCompare,
  fetchFactorDetail,
  UiQueryError
} from "../api";
import { DataTable, type DataColumn } from "../components/DataTable";
import { useAsOf } from "../components/AppShell";
import { MetricCard } from "../components/MetricCard";
import { PageHeader } from "../components/PageHeader";
import { PageError, PageLoading, RefreshNotice } from "../components/RequestState";
import { StatusBadge } from "../components/StatusBadge";
import { displayDate, formatDateTime, formatNumber, formatPercent, shortHash } from "../format";
import { RouterLink, useRouter } from "../routing";
import type {
  ApiMeta,
  EvidencePayload,
  FactorAdmissionItem,
  FactorAuthorityStatus,
  FactorCatalogItem,
  FactorCompareItem,
  FactorDetailSections,
  FactorLifecycleStatus,
  G1GateEvidence,
  JsonMetric
} from "../types";

const VERSION = /^[0-9a-f]{12}$/;
const WINDOWS = ["W1", "W2", "W3", "W4", "W5", "W6"] as const;

const AUTHORITY_LABELS: Record<FactorAuthorityStatus, string> = {
  AUTHORITATIVE_CURRENT: "当前权威",
  HISTORICAL_NON_AUTHORITATIVE: "历史非权威",
  SUPERSEDED_ENGINEERING_GENERATION: "被替代工程版本",
  INVALIDATED: "已失效"
};

const LIFECYCLE_LABELS: Record<FactorLifecycleStatus, string> = {
  CANDIDATE: "候选",
  TESTING: "测试中",
  REJECTED: "未准入",
  ADMITTED: "已准入",
  RETIRED: "已退役"
};

const METRIC_LABELS: Record<string, string> = {
  ast_nodes: "AST 节点",
  candidate_net_excess: "候选净超额",
  candidate_net_icir: "候选净 ICIR",
  candidate_turnover: "候选换手",
  cost_2x_net_excess: "成本 2× 净超额",
  direction: "冻结方向",
  dsr_probability: "DSR 概率",
  expression_tokens: "表达式 token",
  hac_t: "Newey-West(10) t",
  incremental_net_excess: "增量净超额",
  incremental_net_icir: "增量净 ICIR",
  max_library_abs_spearman: "因子库最大 |ρ|",
  mean_oriented_oos_rank_ic: "平均方向化 OOS RankIC",
  pit: "PIT 哨兵",
  positive_oos_windows: "正向 OOS 窗口",
  rank_ic_retention: "RankIC 保留率",
  shift: "shift 哨兵",
  slippage_2x_net_excess: "滑点 2× 净超额",
  stress_drawdown: "压力期最大回撤",
  trial_count: "研究尝试 N",
  turnover_ratio: "换手比",
  valid_trial_sharpes: "有效试验 Sharpe 数"
};

function AuthorityBadge({ authority }: { authority: FactorAuthorityStatus }) {
  const current = authority === "AUTHORITATIVE_CURRENT";
  return (
    <Tag
      className={`factor-authority factor-authority-${current ? "current" : "historical"}`}
      icon={current ? <SafetyCertificateFilled /> : <HistoryOutlined />}
    >
      {AUTHORITY_LABELS[authority]} · {authority}
    </Tag>
  );
}

function DecisionBadge({ decision }: { decision: "ADMITTED" | "REJECTED" }) {
  return (
    <Tag
      className={`factor-decision factor-decision-${decision.toLowerCase()}`}
      icon={decision === "ADMITTED" ? <CheckCircleFilled /> : <CloseCircleFilled />}
    >
      {decision === "ADMITTED" ? "已准入" : "未准入"} · {decision}
    </Tag>
  );
}

function HistoricalBanner({ visible }: { visible: boolean }) {
  if (!visible) return null;
  return (
    <Alert
      className="factor-history-banner"
      type="warning"
      showIcon
      message="历史记录已应用当前权威覆盖"
      description="事件按查询截止日期裁剪，但 authority 使用当前已知纠错；这是按当前知识回看，不是重演当时的权威状态。"
    />
  );
}

function researchEvidence(
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

function researchHeaderProps(meta: ApiMeta) {
  return {
    asOf: meta.as_of,
    generatedAt: meta.generated_at,
    asOfLabel: "查询截止",
    generatedAtLabel: "研究投影生成"
  };
}

function factorPath(factorId: string, options: { version?: string; asOf?: string } = {}) {
  const search = new URLSearchParams();
  if (options.version) search.set("version", options.version);
  if (options.asOf) search.set("as_of", options.asOf);
  return `/factors/${factorId}${search.size ? `?${search.toString()}` : ""}`;
}

function admissionsPath(factorId: string, asOf?: string) {
  return `/factors/${factorId}/admissions${asOf ? `?as_of=${encodeURIComponent(asOf)}` : ""}`;
}

function comparePath(versions: string[]) {
  const search = new URLSearchParams();
  versions.forEach((version) => search.append("version", version));
  return `/factors/compare?${search.toString()}`;
}

function metricLabel(key: string) {
  return METRIC_LABELS[key] ?? key.replaceAll("_", " ");
}

function formatResearchNumber(value: number, key: string) {
  if (/net_excess|drawdown|probability|retention/.test(key)) {
    return formatPercent(value, { signed: /net_excess/.test(key), digits: 2 });
  }
  if (/rank_ic/.test(key)) return formatNumber(value, 4);
  if (/hac_t/.test(key)) return formatNumber(value, 2);
  if (/icir|correlation|spearman|ratio/.test(key)) return formatNumber(value, 3);
  return formatNumber(value, Number.isInteger(value) ? 0 : 3);
}

function MetricActual({ value, metric }: { value: JsonMetric; metric: string }) {
  if (value === null) return <span className="muted">未登记</span>;
  if (typeof value === "boolean") return <span>{value ? "是" : "否"}</span>;
  if (typeof value === "number") return <span>{formatResearchNumber(value, metric)}</span>;
  if (typeof value === "string") return <span>{value}</span>;
  if (Array.isArray(value)) {
    return (
      <span className="factor-actual-array">
        {value.map((item, index) => (
          <MetricActual key={`${metric}-${index}`} value={item} metric={metric} />
        ))}
      </span>
    );
  }
  return (
    <dl className="factor-actual-list">
      {Object.entries(value).map(([key, item]) => (
        <div key={key}>
          <dt>{metricLabel(key)}</dt>
          <dd><MetricActual value={item} metric={key} /></dd>
        </div>
      ))}
    </dl>
  );
}

function FactorTabs({
  factorId,
  active,
  version,
  asOf
}: {
  factorId: string;
  active: "detail" | "admissions";
  version?: string;
  asOf?: string;
}) {
  return (
    <nav className="factor-tabs" aria-label="因子证据层级">
      <RouterLink
        to={factorPath(factorId, { version, asOf })}
        className={active === "detail" ? "active" : ""}
        aria-current={active === "detail" ? "page" : undefined}
      >
        <FileSearchOutlined /> 单因子证据
      </RouterLink>
      <RouterLink
        to={admissionsPath(factorId, asOf)}
        className={active === "admissions" ? "active" : ""}
        aria-current={active === "admissions" ? "page" : undefined}
      >
        <HistoryOutlined /> 准入历史
      </RouterLink>
    </nav>
  );
}

function CatalogPage() {
  const { asOf } = useAsOf();
  const { location, navigate } = useRouter();
  const parameters = useMemo(() => new URLSearchParams(location.search), [location.search]);
  const requestedStatus = parameters.get("status") ?? "ALL";
  const status = (["ALL", "ADMITTED", "REJECTED", "HISTORICAL_ONLY"] as const).includes(
    requestedStatus as "ALL"
  ) ? requestedStatus as "ALL" | "ADMITTED" | "REJECTED" | "HISTORICAL_ONLY" : "ALL";
  const family = parameters.get("family") ?? "ALL";
  const dataCategory = parameters.get("data_category") ?? "ALL";
  const [selected, setSelected] = useState<string[]>([]);
  useEffect(() => setSelected([]), [asOf]);

  const query = useQuery({
    queryKey: ["factor-catalog", asOf || "latest"],
    queryFn: ({ signal }) => fetchFactorCatalog({ status: "ALL", asOf }, signal),
    placeholderData: (previous) => previous
  });

  if (query.isPending) return <PageLoading label="正在核对因子目录与当前权威覆盖…" />;
  if (query.isError) return <PageError error={query.error} retry={() => query.refetch()} />;

  const { data, meta } = query.data;
  const families = [...new Set(data.items.map((item) => item.research_family))].sort();
  const categories = [...new Set(data.items.map((item) => item.data_category))].sort();
  const filtered = data.items.filter((item) => {
    if (status === "ADMITTED" && item.lifecycle_status !== "ADMITTED") return false;
    if (status === "REJECTED" && item.lifecycle_status !== "REJECTED") return false;
    if (status === "HISTORICAL_ONLY" && item.authority_status === "AUTHORITATIVE_CURRENT") return false;
    if (family !== "ALL" && item.research_family !== family) return false;
    if (dataCategory !== "ALL" && item.data_category !== dataCategory) return false;
    return true;
  });
  const selectedItems = data.items.filter((item) =>
    item.current_factor_version ? selected.includes(item.current_factor_version) : false
  );
  const selectedFamily = selectedItems[0]?.research_family;

  const setFilter = (key: "status" | "family" | "data_category", value: string) => {
    const next = new URLSearchParams(location.search);
    if (value === "ALL") next.delete(key);
    else next.set(key, value);
    navigate(`/factors${next.size ? `?${next.toString()}` : ""}`);
  };

  const toggleCompare = (item: FactorCatalogItem, checked: boolean) => {
    const version = item.current_factor_version;
    if (!version || asOf) return;
    setSelected((current) => checked ? [...current, version] : current.filter((value) => value !== version));
  };

  const columns: DataColumn<FactorCatalogItem>[] = [
    {
      title: "比较",
      key: "compare",
      width: 68,
      render: (_value, item) => {
        const version = item.current_factor_version;
        const disabled = !version || Boolean(asOf) || selected.length >= 3 && !selected.includes(version) ||
          Boolean(selectedFamily && selectedFamily !== item.research_family);
        return (
          <Checkbox
            checked={Boolean(version && selected.includes(version))}
            disabled={disabled}
            aria-label={`选择因子 ${shortHash(item.factor_id)} 进行比较`}
            onChange={(event) => toggleCompare(item, event.target.checked)}
          />
        );
      }
    },
    {
      title: "因子 ID",
      dataIndex: "factor_id",
      key: "factor_id",
      fixed: "left",
      width: 132,
      render: (value: string, item) => (
        <RouterLink
          className="table-factor-link"
          title={value}
          to={factorPath(value, { version: item.current_factor_version ?? undefined, asOf })}
        >
          {shortHash(value)}
        </RouterLink>
      )
    },
    { title: "研究家族", dataIndex: "research_family", key: "family", width: 190 },
    { title: "数据类别", dataIndex: "data_category", key: "category", width: 128 },
    {
      title: "研究结论",
      dataIndex: "latest_recorded_decision",
      key: "decision",
      width: 142,
      render: (value: "ADMITTED" | "REJECTED") => <DecisionBadge decision={value} />
    },
    {
      title: "权威状态",
      dataIndex: "authority_status",
      key: "authority",
      width: 238,
      render: (value: FactorAuthorityStatus) => <AuthorityBadge authority={value} />
    },
    { title: "版本数", dataIndex: "version_count", key: "versions", align: "right", width: 84 },
    {
      title: "当前版本",
      dataIndex: "current_factor_version",
      key: "current",
      width: 132,
      render: (value: string | null) => value ? <code>{value}</code> : <span className="muted">无当前版本</span>
    },
    { title: "研究尝试 N", dataIndex: "experiment_attempt_n", key: "attempts", align: "right", width: 112 },
    { title: "证据", dataIndex: "evidence_status", key: "evidence", width: 94 }
  ];

  const empty = status === "ADMITTED" ? (
    <div className="factor-empty-inline">
      <strong>正式因子库仍为 0</strong>
      <span>当前没有因子通过全部 G1 门；这是真实研究结论。</span>
      <Button type="link" onClick={() => setFilter("status", "ALL")}>查看全部研究证据</Button>
    </div>
  ) : "当前筛选没有研究因子";

  const evidence = researchEvidence("因子目录证据", meta, {
    facts: [
      { label: "正式库", value: String(data.counters.formal_library_count) },
      { label: "已研究因子", value: String(data.counters.researched_factor_count) },
      { label: "当前权威 REJECT", value: String(data.counters.authoritative_rejected_count) },
      { label: "排序", value: data.sort.join(" → ") }
    ]
  });

  return (
    <div className="page-stack factor-page">
      <PageHeader
        eyebrow="FACTOR FACTORY"
        title="当前有什么可用因子，为什么还没有入库"
        description="目录只呈现已进入 G1 的研究因子；REJECT 是研究结果，不是系统运行失败。"
        status="OBSERVING"
        evidence={evidence}
        {...researchHeaderProps(meta)}
      />
      {query.isFetching ? <RefreshNotice asOf={meta.as_of} generatedAt={meta.generated_at} /> : null}
      <HistoricalBanner visible={Boolean(data.historical_response_banner)} />

      <section className="factor-library-hero" aria-labelledby="factor-library-heading">
        <div>
          <span className="section-kicker">G1 · CURRENT AUTHORITY</span>
          <h2 id="factor-library-heading">正式因子库 0：当前没有因子满足全部准入门</h2>
          <p>已有研究证据完整保留，可继续用于方法诊断与下一轮假设设计；不因此推荐上线。</p>
        </div>
        <StatusBadge status="OBSERVING" />
      </section>

      <section className="metric-grid factor-counter-grid" aria-label="因子工厂关键事实">
        <MetricCard label="正式因子库" value={data.counters.formal_library_count} detail="当前权威 ADMITTED" />
        <MetricCard label="已研究因子" value={data.counters.researched_factor_count} detail="稳定因子身份，非实验行数" />
        <MetricCard label="当前权威 REJECT" value={data.counters.authoritative_rejected_count} detail="有证据的研究结论" tone="warning" />
        <MetricCard label="仅历史因子" value={data.counters.historical_only_count} detail="不代表当前权威版本" />
      </section>

      <section className="table-surface" aria-labelledby="factor-catalog-heading">
        <div className="section-heading factor-catalog-heading">
          <div>
            <span className="section-kicker">CATALOG</span>
            <h2 id="factor-catalog-heading">因子目录</h2>
          </div>
          <div className="factor-filters" aria-label="因子目录筛选">
            <Select
              aria-label="生命周期筛选"
              value={status}
              onChange={(value) => setFilter("status", value)}
              options={[
                { value: "ALL", label: "全部阶段" },
                { value: "ADMITTED", label: "已准入" },
                { value: "REJECTED", label: "未准入" },
                { value: "HISTORICAL_ONLY", label: "仅历史" }
              ]}
            />
            <Select
              aria-label="研究家族筛选"
              value={family}
              onChange={(value) => setFilter("family", value)}
              options={[{ value: "ALL", label: "全部家族" }, ...families.map((value) => ({ value, label: value }))]}
            />
            <Select
              aria-label="数据类别筛选"
              value={dataCategory}
              onChange={(value) => setFilter("data_category", value)}
              options={[{ value: "ALL", label: "全部数据" }, ...categories.map((value) => ({ value, label: value }))]}
            />
          </div>
        </div>

        {asOf ? (
          <Alert
            type="info"
            showIcon
            message="历史查询不允许因子比较"
            description="比较接口只支持最新当前权威版本。请先切到最新，避免把历史切片与最新权威结果混合。"
            action={<Button type="link" onClick={() => navigate("/factors")}>切到最新</Button>}
          />
        ) : null}

        <div className="factor-desktop-catalog">
          <DataTable
            label="因子目录"
            columns={columns}
            data={filtered}
            rowKey="factor_id"
            minimumWidth="wide"
            emptyText={empty}
          />
        </div>
        <div className="factor-mobile-cards" aria-label="移动端因子目录">
          {filtered.map((item) => (
            <article key={item.factor_id} className="factor-catalog-card">
              <div className="factor-card-heading">
                <RouterLink to={factorPath(item.factor_id, { version: item.current_factor_version ?? undefined, asOf })}>
                  <code title={item.factor_id}>{shortHash(item.factor_id)}</code>
                </RouterLink>
                <DecisionBadge decision={item.latest_recorded_decision} />
              </div>
              <p>{item.research_family} · {item.data_category}</p>
              <AuthorityBadge authority={item.authority_status} />
              <dl>
                <div><dt>阶段</dt><dd>{LIFECYCLE_LABELS[item.lifecycle_status]}</dd></div>
                <div><dt>版本</dt><dd>{item.version_count}</dd></div>
                <div><dt>研究 N</dt><dd>{item.experiment_attempt_n}</dd></div>
              </dl>
              <div className="factor-card-actions">
                <RouterLink to={factorPath(item.factor_id, { version: item.current_factor_version ?? undefined, asOf })}>查看证据</RouterLink>
                <Checkbox
                  aria-label={`选择因子 ${shortHash(item.factor_id)} 进行比较`}
                  checked={Boolean(item.current_factor_version && selected.includes(item.current_factor_version))}
                  disabled={!item.current_factor_version || Boolean(asOf) || selected.length >= 3 && !selected.includes(item.current_factor_version) || Boolean(selectedFamily && selectedFamily !== item.research_family)}
                  onChange={(event) => toggleCompare(item, event.target.checked)}
                >比较</Checkbox>
              </div>
            </article>
          ))}
          {!filtered.length ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={empty} /> : null}
        </div>
      </section>

      <section className="factor-compare-tray" aria-live="polite">
        <div>
          <SwapOutlined aria-hidden="true" />
          <span>已选 {selected.length}/3</span>
          {selectedItems.map((item) => <code key={item.factor_id}>{shortHash(item.factor_id)}</code>)}
        </div>
        <Button
          type="primary"
          disabled={Boolean(asOf) || selected.length < 2}
          onClick={() => navigate(comparePath(selected))}
        >
          严格比较所选因子
        </Button>
      </section>
      <p className="page-evidence-footer">目录只发出一个 catalog 请求，不批量拼详情；固定按研究家族、因子 ID 排序，不按收益或 IC 排名。</p>
    </div>
  );
}

function DetailPage({ factorId }: { factorId: string }) {
  const { asOf } = useAsOf();
  const { location } = useRouter();
  const version = new URLSearchParams(location.search).get("version") ?? undefined;
  const query = useQuery({
    queryKey: ["factor-detail", factorId, version ?? "current", asOf || "latest"],
    queryFn: ({ signal }) => fetchFactorDetail(factorId, version, asOf, signal),
    placeholderData: (previous) => previous
  });
  if (query.isPending) return <PageLoading label="正在核对单因子定义、十五门与聚合证据…" />;
  if (query.isError) return <PageError error={query.error} retry={() => query.refetch()} />;

  const { data, meta } = query.data;
  const sections = data.sections;
  const gates = Object.entries(sections.g1_statistics_and_all_gates.gates)
    .sort(([leftName, left], [rightName, right]) => Number(left.passed) - Number(right.passed) || leftName.localeCompare(rightName));
  const failed = gates.filter(([, gate]) => !gate.passed);
  const statistics = sections.g1_statistics_and_all_gates.statistics;
  const evidenceHashes = Object.fromEntries(data.evidence_hashes.map((value, index) => [`factor_evidence_${index + 1}`, value]));
  const evidence = researchEvidence("单因子证据", meta, {
    hashes: evidenceHashes,
    sources: data.source_refs,
    facts: [
      { label: "因子 ID", value: data.factor_id },
      { label: "版本", value: data.factor_version },
      { label: "记录判决", value: data.recorded_decision },
      { label: "权威状态", value: data.authority_status }
    ]
  });
  const gateColumns: DataColumn<{ name: string; gate: G1GateEvidence }>[] = [
    { title: "G1 门", dataIndex: "name", key: "name", width: 180, render: (value: string) => metricLabel(value) },
    { title: "结果", key: "passed", width: 116, render: (_value, row) => <StatusBadge status={row.gate.passed ? "PASS" : "FAIL"} compact /> },
    { title: "实际值", key: "actual", width: 260, render: (_value, row) => <MetricActual value={row.gate.actual} metric={row.name} /> },
    { title: "冻结规则", key: "rule", render: (_value, row) => <span className="factor-rule">{row.gate.rule}</span> }
  ];

  const windowData = WINDOWS.map((window) => ({ window, value: sections.six_oos_window_rank_ic[window] }));
  const stressData = Object.entries(sections.stress_max_drawdown).map(([period, value]) => ({ period, value }));
  const unavailable = [
    ["覆盖率", sections.coverage_ratio],
    ["分位收益 / 单调性", sections.quantile_returns_and_monotonicity],
    ["因子自相关", sections.factor_autocorrelation],
    ["候选池相关性", sections.candidate_pool_correlation]
  ] as const;
  const portfolio = sections.turnover_and_incremental_portfolio;

  return (
    <div className="page-stack factor-page">
      <PageHeader
        eyebrow="FACTOR TEAR SHEET"
        title="单因子研究证据"
        description="只展示已登记聚合证据；记录判决与当前权威状态始终分列。"
        status={meta.freshness_status}
        evidence={evidence}
        {...researchHeaderProps(meta)}
      />
      {query.isFetching ? <RefreshNotice asOf={meta.as_of} generatedAt={meta.generated_at} /> : null}
      <HistoricalBanner visible={Boolean(data.historical_response_banner)} />
      {data.fallback_to_latest_historical ? (
        <Alert
          type="warning"
          showIcon
          message="该因子没有当前权威版本"
          description="当前显示最新历史版本，仅用于追溯，不代表可用候选或当前结论。"
        />
      ) : null}
      <RouterLink className="factor-back-link" to={`/factors${asOf ? `?as_of=${encodeURIComponent(asOf)}` : ""}`}>
        <ArrowLeftOutlined /> 返回因子目录
      </RouterLink>
      <FactorTabs factorId={factorId} active="detail" version={data.factor_version} asOf={asOf} />

      <section className="factor-detail-hero">
        <div className="factor-definition">
          <span className="section-kicker">{sections.identity.research_family} · {sections.identity.data_category}</span>
          <h2><code title={data.factor_id}>{shortHash(data.factor_id)}</code> · {data.factor_version}</h2>
          <p>{sections.frozen_definition_and_direction.economic_rationale}</p>
          <div className="factor-formula">
            <span>冻结公式</span>
            <code>{sections.frozen_definition_and_direction.feature_or_formula}</code>
          </div>
        </div>
        <div className="factor-verdict-panel">
          <DecisionBadge decision={data.recorded_decision} />
          <AuthorityBadge authority={data.authority_status} />
          <dl>
            <div><dt>冻结方向</dt><dd>{sections.frozen_definition_and_direction.direction > 0 ? "+1 · 正向" : "−1 · 反向"}</dd></div>
            <div><dt>失败门</dt><dd>{failed.length} / 15</dd></div>
            <div><dt>研究尝试 N</dt><dd>{formatNumber(statistics.trial_count, 0)}</dd></div>
          </dl>
        </div>
      </section>

      <section className="metric-grid factor-stat-grid" aria-label="G1 关键统计">
        <MetricCard label="DSR 概率" value={formatPercent(statistics.dsr_probability)} detail="G1 阈值由冻结裁判解释" tone={statistics.dsr_probability < 0.95 ? "warning" : "default"} />
        <MetricCard label="Newey-West(10) t" value={formatNumber(statistics.hac_t, 2)} detail="方向冻结后的日频 RankIC" tone={statistics.hac_t < 3 ? "warning" : "default"} />
        <MetricCard label="平均 OOS RankIC" value={formatNumber(statistics.mean_oriented_oos_rank_ic, 4)} detail="六个冻结窗口聚合" />
        <MetricCard label="正向窗口" value={`${formatNumber(statistics.positive_oos_windows, 0)} / 6`} detail="不等于全部 G1 通过" />
      </section>

      <section className="table-surface" aria-labelledby="g1-gates-heading">
        <div className="section-heading">
          <div><span className="section-kicker">G1 · 15 GATES</span><h2 id="g1-gates-heading">全部准入门</h2></div>
          <span className="section-note">失败门优先显示；规则原文来自冻结报告</span>
        </div>
        {failed.length ? (
          <div className="factor-failed-summary" role="note">
            <CloseCircleFilled />
            <span>未通过：{failed.map(([name]) => metricLabel(name)).join("、")}</span>
          </div>
        ) : null}
        <DataTable
          label="G1 十五门"
          columns={gateColumns}
          data={gates.map(([name, gate]) => ({ name, gate }))}
          rowKey="name"
          minimumWidth="wide"
        />
      </section>

      <section className="two-column-support factor-health-grid">
        <article className="surface-panel">
          <div className="section-heading"><div><span className="section-kicker">PIT / SHIFT</span><h2>可用时点与复杂度</h2></div></div>
          <dl className="detail-list">
            <div><dt>PIT 哨兵</dt><dd><StatusBadge status={sections.pit_shift_and_complexity.pit_sentinel_pass ? "PASS" : "FAIL"} compact /></dd></div>
            <div><dt>shift 哨兵</dt><dd><StatusBadge status={sections.pit_shift_and_complexity.shift_sentinel_pass ? "PASS" : "FAIL"} compact /></dd></div>
            <div><dt>AST 节点</dt><dd>{sections.pit_shift_and_complexity.ast_nodes}</dd></div>
            <div><dt>表达式 token</dt><dd>{sections.pit_shift_and_complexity.expression_tokens}</dd></div>
            <div><dt>最大回看</dt><dd>{sections.pit_shift_and_complexity.max_lookback_days ?? "未登记"}</dd></div>
            <div><dt>所需回溯</dt><dd>{sections.pit_shift_and_complexity.required_backtrack_days ?? "未登记"}</dd></div>
          </dl>
        </article>
        <article className="surface-panel">
          <div className="section-heading"><div><span className="section-kicker">INDEPENDENCE</span><h2>因子库相关性</h2></div></div>
          <div className="factor-correlation-value">{formatNumber(sections.library_max_abs_correlation, 3)}</div>
          <p className="muted">候选与当前正式库的最大绝对 Spearman 相关；正式库为空时以 G1 已登记语义解释，不由页面重算。</p>
        </article>
      </section>

      <section className="split-charts factor-chart-grid" aria-label="稳定性聚合图">
        <div>
          <h3>六个 OOS 窗 RankIC</h3>
          <div className="chart-canvas factor-small-chart" role="img" aria-label="六个样本外窗口 RankIC 柱状图，零线用于识别方向变化">
            <Column
              data={windowData}
              xField="window"
              yField="value"
              height={280}
              colorField={() => "RankIC"}
              style={{ fill: "#315f7c" }}
              axis={{ y: { labelFormatter: (value: number) => Number(value).toFixed(4) } }}
              animate={false}
            />
          </div>
          <details className="accessible-data-table">
            <summary>查看六窗口精确数据</summary>
            <table><thead><tr><th>窗口</th><th>RankIC</th></tr></thead><tbody>{windowData.map((row) => <tr key={row.window}><td>{row.window}</td><td>{formatNumber(row.value, 4)}</td></tr>)}</tbody></table>
          </details>
        </div>
        <div>
          <h3>压力期最大回撤</h3>
          <div className="chart-canvas factor-small-chart" role="img" aria-label="三个冻结压力期最大回撤柱状图">
            <Column
              data={stressData}
              xField="period"
              yField="value"
              height={280}
              style={{ fill: "#735c93" }}
              axis={{ x: { labelAutoRotate: true }, y: { labelFormatter: (value: number) => `${(Number(value) * 100).toFixed(0)}%` } }}
              animate={false}
            />
          </div>
          <details className="accessible-data-table">
            <summary>查看压力期精确数据</summary>
            <table><thead><tr><th>压力期</th><th>最大回撤</th></tr></thead><tbody>{stressData.map((row) => <tr key={row.period}><td>{row.period}</td><td>{formatPercent(row.value)}</td></tr>)}</tbody></table>
          </details>
        </div>
      </section>

      <section className="table-surface" aria-labelledby="factor-portfolio-heading">
        <div className="section-heading"><div><span className="section-kicker">PORTFOLIO / COST</span><h2 id="factor-portfolio-heading">组合增量与成本压力</h2></div></div>
        <div className="factor-comparison-table-wrap" role="region" aria-label="组合与成本精确数据" tabIndex={0}>
          <table className="factor-metric-table">
            <thead><tr><th>口径</th><th>基线</th><th>候选</th></tr></thead>
            <tbody>
              <tr><th>净超额</th><td>{formatPercent(portfolio.baseline_net_excess, { signed: true })}</td><td>{formatPercent(portfolio.candidate_net_excess, { signed: true })}</td></tr>
              <tr><th>净 ICIR</th><td>{formatNumber(portfolio.baseline_net_icir, 3)}</td><td>{formatNumber(portfolio.candidate_net_icir, 3)}</td></tr>
              <tr><th>换手</th><td>{formatNumber(portfolio.baseline_turnover, 3)}</td><td>{formatNumber(portfolio.candidate_turnover, 3)}</td></tr>
              <tr><th>成本 2× 净超额</th><td>—</td><td>{formatPercent(sections.cost_and_slippage_stress.cost_2x_net_excess, { signed: true })}</td></tr>
              <tr><th>滑点 2× 净超额</th><td>—</td><td>{formatPercent(sections.cost_and_slippage_stress.slippage_2x_net_excess, { signed: true })}</td></tr>
            </tbody>
          </table>
        </div>
        <p className="chart-footnote">增量门以 G1 已登记 actual 为准；页面不从基线与候选两列反向重算裁判结果。</p>
      </section>

      <section className="surface-panel" aria-labelledby="factor-unavailable-heading">
        <div className="section-heading"><div><span className="section-kicker">EVIDENCE GAPS</span><h2 id="factor-unavailable-heading">未登记且未重算</h2></div></div>
        <div className="factor-unavailable-grid">
          {unavailable.map(([label, section]) => (
            <article key={label}>
              <MinusCircleFilled aria-hidden="true" />
              <div><strong>{label}</strong><span>{section.status} · recomputed=false</span></div>
            </article>
          ))}
        </div>
      </section>
      <p className="page-evidence-footer">当前没有逐日 RankIC、IC 分布、月度热图或分位收益序列；未画出的图不是遗漏，而是证据边界。</p>
    </div>
  );
}

function AdmissionsPage({ factorId }: { factorId: string }) {
  const { asOf } = useAsOf();
  const query = useQuery({
    queryKey: ["factor-admissions", factorId, asOf || "latest"],
    queryFn: ({ signal }) => fetchFactorAdmissionHistory(factorId, asOf, signal),
    placeholderData: (previous) => previous
  });
  if (query.isPending) return <PageLoading label="正在核对追加式因子准入历史…" />;
  if (query.isError) return <PageError error={query.error} retry={() => query.refetch()} />;
  const { data, meta } = query.data;
  const hashes = Object.fromEntries(data.items.flatMap((item, index) => [
    [`decision_${index + 1}_report`, item.report_sha256],
    [`decision_${index + 1}_evidence`, item.evidence_sha256]
  ]));
  const evidence = researchEvidence("因子准入历史证据", meta, {
    hashes,
    facts: [
      { label: "因子 ID", value: factorId },
      { label: "追加式记录", value: String(data.items.length) },
      { label: "append_only", value: String(data.append_only) }
    ]
  });
  const columns: DataColumn<FactorAdmissionItem>[] = [
    { title: "记录时间", dataIndex: "recorded_at", key: "recorded_at", width: 178, render: (value: string) => formatDateTime(value) },
    {
      title: "版本",
      dataIndex: "factor_version",
      key: "version",
      width: 132,
      render: (value: string) => <RouterLink className="table-factor-link" to={factorPath(factorId, { version: value, asOf })}>{value}</RouterLink>
    },
    { title: "记录判决", dataIndex: "recorded_decision", key: "decision", width: 142, render: (value: "ADMITTED" | "REJECTED") => <DecisionBadge decision={value} /> },
    { title: "当前权威解释", dataIndex: "authority_status", key: "authority", width: 238, render: (value: FactorAuthorityStatus) => <AuthorityBadge authority={value} /> },
    { title: "研究 N", dataIndex: "trial_count", key: "trials", align: "right", width: 94 },
    { title: "失败门", dataIndex: "failed_gates", key: "failed", width: 280, render: (value: string[]) => value.length ? value.map(metricLabel).join("、") : "无" },
    { title: "规则版本", dataIndex: "decision_rule_version", key: "rule", width: 132 },
    { title: "报告", dataIndex: "report_sha256", key: "report", width: 126, render: (value: string) => <code title={value}>{shortHash(value)}</code> },
    { title: "证据", dataIndex: "evidence_sha256", key: "evidence", width: 126, render: (value: string) => <code title={value}>{shortHash(value)}</code> }
  ];
  return (
    <div className="page-stack factor-page">
      <PageHeader
        eyebrow="ADMISSION HISTORY"
        title="旧判决保留，当前权威另列"
        description="准入账本只追加不覆盖；历史版本可回到对应 tear sheet 核对。"
        status={meta.freshness_status}
        evidence={evidence}
        {...researchHeaderProps(meta)}
      />
      {query.isFetching ? <RefreshNotice asOf={meta.as_of} generatedAt={meta.generated_at} /> : null}
      <HistoricalBanner visible={Boolean(data.historical_response_banner)} />
      <RouterLink className="factor-back-link" to={`/factors${asOf ? `?as_of=${encodeURIComponent(asOf)}` : ""}`}><ArrowLeftOutlined /> 返回因子目录</RouterLink>
      <FactorTabs factorId={factorId} active="admissions" asOf={asOf} />
      <section className="factor-library-hero append-only-hero">
        <div><span className="section-kicker">APPEND ONLY</span><h2>{data.items.length} 条准入判决，旧记录从未覆盖</h2><p><code title={factorId}>{shortHash(factorId)}</code> · 记录判决与 authority 分列。</p></div>
        <StatusBadge status="PASS" />
      </section>
      <section className="table-surface" aria-labelledby="admission-table-heading">
        <div className="section-heading"><div><span className="section-kicker">LEDGER ORDER</span><h2 id="admission-table-heading">准入历史</h2></div><span className="section-note">按记录时间升序</span></div>
        <DataTable label="因子准入历史" columns={columns} data={data.items} rowKey="decision_id" minimumWidth="wide" />
      </section>
      <p className="page-evidence-footer">历史行不因后续纠错而删除；authority 列说明当前如何解释该记录，不改写原 recorded_decision。</p>
    </div>
  );
}

function CompareSetup({ versions, asOf }: { versions: string[]; asOf: string }) {
  const { navigate } = useRouter();
  const historical = Boolean(asOf);
  return (
    <div className="page-stack factor-page">
      <header className="page-header factor-static-header">
        <div><div className="eyebrow">STRICT COMPARISON</div><div className="page-title-line"><h1>{historical ? "历史视图不能比较最新权威因子" : "请选择 2—3 个不同因子版本"}</h1><StatusBadge status="NOT_READY" /></div><p>{historical ? "比较接口没有历史 as_of 口径；先切到最新，避免混合时点。" : "从因子目录选择同一研究家族的当前权威版本。"}</p></div>
      </header>
      <section className="request-error factor-compare-setup" role="alert">
        <InfoCircleOutlined />
        <h2>{historical ? "比较已阻断，未发出请求" : `当前选择 ${versions.length} 个版本`}</h2>
        <div className="factor-version-list">{versions.map((version) => <code key={version}>{version}</code>)}</div>
        <div><Button onClick={() => navigate("/factors")}>返回目录</Button>{historical && versions.length >= 2 && versions.length <= 3 ? <Button type="primary" onClick={() => navigate(comparePath(versions))}>切到最新并比较</Button> : null}</div>
      </section>
    </div>
  );
}

function ComparePage() {
  const { asOf } = useAsOf();
  const { location, navigate } = useRouter();
  const versions = useMemo(() => new URLSearchParams(location.search).getAll("version"), [location.search]);
  const valid = versions.length >= 2 && versions.length <= 3 && new Set(versions).size === versions.length && versions.every((version) => VERSION.test(version));
  const query = useQuery({
    queryKey: ["factor-compare", ...versions],
    queryFn: ({ signal }) => fetchFactorCompare(versions, signal),
    enabled: valid && !asOf,
    retry: false
  });

  if (asOf || !valid) return <CompareSetup versions={versions} asOf={asOf} />;
  if (query.isPending) return <PageLoading label="正在由后端核对完整比较 fingerprint…" />;

  const remove = (version: string) => {
    const next = versions.filter((item) => item !== version);
    navigate(next.length ? comparePath(next) : "/factors");
  };
  if (query.isError) {
    const error = query.error instanceof UiQueryError ? query.error : new UiQueryError("QUERY_FAILED", "因子比较失败");
    return (
      <div className="page-stack factor-page">
        <header className="page-header factor-static-header"><div><div className="eyebrow">STRICT COMPARISON</div><div className="page-title-line"><h1>所选因子不具备严格可比性</h1><StatusBadge status="NOT_EVALUATED" /></div><p>没有保留旧图，也没有转换口径；请移除一个版本或返回目录。</p></div></header>
        <section className="request-error factor-conflict" role="alert">
          <div className="error-kicker">{error.code}</div><h2>{error.message}</h2>
          <div className="factor-version-list">{versions.map((version) => <span key={version}><code>{version}</code><Button type="link" onClick={() => remove(version)}>移除</Button></span>)}</div>
          <div><Button onClick={() => navigate("/factors")}>返回目录</Button><Button onClick={() => query.refetch()}>重新核对</Button></div>
        </section>
      </div>
    );
  }

  const { data, meta } = query.data;
  const evidence = researchEvidence("因子严格比较证据", meta, {
    facts: [
      { label: "比较版本数", value: String(data.factor_versions.length) },
      { label: "按表现排序", value: String(data.sorted_by_performance) },
      { label: "选择顺序", value: data.factor_versions.join(" → ") }
    ]
  });
  const lineData = data.items.flatMap((item) => WINDOWS.map((window) => ({
    window,
    version: item.factor_version,
    value: item.six_oos_window_rank_ic[window]
  })));
  const stressPeriods = Object.keys(data.items[0]!.stress_max_drawdown);
  const stressData = data.items.flatMap((item) => stressPeriods.map((period) => ({
    period,
    version: item.factor_version,
    value: item.stress_max_drawdown[period]!
  })));
  const portfolioRows: Array<[string, (item: FactorCompareItem) => number, "percent" | "number"]> = [
    ["基线净超额", (item) => item.portfolio.baseline_net_excess, "percent"],
    ["候选净超额", (item) => item.portfolio.candidate_net_excess, "percent"],
    ["基线净 ICIR", (item) => item.portfolio.baseline_net_icir, "number"],
    ["候选净 ICIR", (item) => item.portfolio.candidate_net_icir, "number"],
    ["候选换手", (item) => item.portfolio.candidate_turnover, "number"],
    ["成本 2× 净超额", (item) => item.cost_and_slippage.cost_2x_net_excess, "percent"],
    ["滑点 2× 净超额", (item) => item.cost_and_slippage.slippage_2x_net_excess, "percent"]
  ];

  return (
    <div className="page-stack factor-page">
      <PageHeader eyebrow="STRICT COMPARISON" title="只比较同口径的当前权威版本" description="后端 fingerprint 是唯一裁判；选择顺序保留，结果不按表现重排。" status={meta.freshness_status} evidence={evidence} {...researchHeaderProps(meta)} />
      {query.isFetching ? <RefreshNotice asOf={meta.as_of} generatedAt={meta.generated_at} /> : null}
      <RouterLink className="factor-back-link" to="/factors"><ArrowLeftOutlined /> 返回因子目录</RouterLink>
      <section className="factor-selection-strip" aria-label="比较选择">
        {data.items.map((item) => <span key={item.factor_version}><code>{item.factor_version}</code><small>{shortHash(item.factor_id)}</small><Button type="link" onClick={() => remove(item.factor_version)}>移除</Button></span>)}
      </section>
      <section className="surface-panel" aria-labelledby="fingerprint-heading">
        <div className="section-heading"><div><span className="section-kicker">COMPARISON FINGERPRINT</span><h2 id="fingerprint-heading">这些口径已由后端判定完全一致</h2></div><StatusBadge status="PASS" /></div>
        <dl className="factor-fingerprint-grid">{Object.entries(data.fingerprint).map(([key, value]) => <div key={key}><dt>{metricLabel(key)}</dt><dd><code title={value}>{value.length > 24 ? shortHash(value) : value}</code></dd></div>)}</dl>
      </section>
      <section className="chart-surface primary-chart" aria-labelledby="compare-windows-heading">
        <div className="section-heading"><div><span className="section-kicker">SIX OOS WINDOWS</span><h2 id="compare-windows-heading">六窗口 RankIC 稳定性</h2></div><span className="section-note">按 URL 选择顺序；不产生综合分</span></div>
        <div className="chart-canvas" role="img" aria-label="二至三个当前权威因子的六窗口 RankIC 折线比较图">
          <Line data={lineData} xField="window" yField="value" colorField="version" seriesField="version" height={330} point={{ size: 5 }} axis={{ y: { labelFormatter: (value: number) => Number(value).toFixed(4) } }} legend={{ color: { position: "top" } }} animate={false} />
        </div>
        <details className="accessible-data-table"><summary>查看六窗口比较精确数据</summary><table><thead><tr><th>窗口</th>{data.items.map((item) => <th key={item.factor_version}>{item.factor_version}</th>)}</tr></thead><tbody>{WINDOWS.map((window) => <tr key={window}><td>{window}</td>{data.items.map((item) => <td key={item.factor_version}>{formatNumber(item.six_oos_window_rank_ic[window], 4)}</td>)}</tr>)}</tbody></table></details>
      </section>
      <section className="chart-surface" aria-labelledby="compare-stress-heading">
        <div className="section-heading"><div><span className="section-kicker">STRESS PERIODS</span><h2 id="compare-stress-heading">压力期最大回撤</h2></div></div>
        <div className="chart-canvas" role="img" aria-label="二至三个当前权威因子的压力期最大回撤分组柱状图">
          <Column data={stressData} xField="period" yField="value" colorField="version" group height={320} axis={{ y: { labelFormatter: (value: number) => `${(Number(value) * 100).toFixed(0)}%` } }} legend={{ color: { position: "top" } }} animate={false} />
        </div>
        <details className="accessible-data-table"><summary>查看压力期比较精确数据</summary><table><thead><tr><th>压力期</th>{data.items.map((item) => <th key={item.factor_version}>{item.factor_version}</th>)}</tr></thead><tbody>{stressPeriods.map((period) => <tr key={period}><td>{period}</td>{data.items.map((item) => <td key={item.factor_version}>{formatPercent(item.stress_max_drawdown[period]!)}</td>)}</tr>)}</tbody></table></details>
      </section>
      <section className="table-surface" aria-labelledby="compare-portfolio-heading">
        <div className="section-heading"><div><span className="section-kicker">PORTFOLIO / COST</span><h2 id="compare-portfolio-heading">组合与成本精确比较</h2></div></div>
        <div className="factor-comparison-table-wrap" role="region" aria-label="因子组合与成本比较" tabIndex={0}><table className="factor-metric-table"><thead><tr><th>指标</th>{data.items.map((item) => <th key={item.factor_version}>{item.factor_version}</th>)}</tr></thead><tbody>{portfolioRows.map(([label, accessor, kind]) => <tr key={label}><th>{label}</th>{data.items.map((item) => <td key={item.factor_version}>{kind === "percent" ? formatPercent(accessor(item), { signed: true }) : formatNumber(accessor(item), 3)}</td>)}</tr>)}</tbody></table></div>
      </section>
      <p className="page-evidence-footer">比较响应只提供投影级证据；查看单因子来源与三层哈希请返回对应 tear sheet。页面未推断“最佳因子”。</p>
    </div>
  );
}

export default function FactorsPage() {
  const { location } = useRouter();
  if (location.pathname === "/factors") return <CatalogPage />;
  if (location.pathname === "/factors/compare") return <ComparePage />;
  const admission = location.pathname.match(/^\/factors\/([0-9a-f]{64})\/admissions$/);
  if (admission) return <AdmissionsPage factorId={admission[1]!} />;
  const detail = location.pathname.match(/^\/factors\/([0-9a-f]{64})$/);
  if (detail) return <DetailPage factorId={detail[1]!} />;
  return <PageError error={new UiQueryError("INVALID_ARGUMENT", "因子页面路径无效")} retry={() => window.location.assign("/factors")} />;
}

import { ArrowLeftOutlined, CloseCircleFilled, MinusCircleFilled } from "@ant-design/icons";
import { Column } from "@ant-design/charts";
import { useQuery } from "@tanstack/react-query";
import { Alert } from "antd";
import { fetchFactorDetail } from "../../api";
import { useAsOf } from "../../components/AppShell";
import { DataTable, type DataColumn } from "../../components/DataTable";
import { MetricCard } from "../../components/MetricCard";
import { PageHeader } from "../../components/PageHeader";
import { PageError, PageLoading, RefreshNotice } from "../../components/RequestState";
import { StatusBadge } from "../../components/StatusBadge";
import { formatNumber, formatPercent } from "../../format";
import { RouterLink, useRouter } from "../../routing";
import type { G1GateEvidence } from "../../types";
import {
  AUTHORITY_LABELS,
  AuthorityBadge,
  DecisionBadge,
  FactorTabs,
  HistoricalBanner,
  MetricActual,
  WINDOWS,
  dataCategoryLabel,
  metricLabel,
  researchEvidence,
  researchFamilyLabel,
  researchHeaderProps
} from "./presentation";

export function DetailPage({ factorId }: { factorId: string }) {
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
      { label: "记录判决", value: data.recorded_decision === "ADMITTED" ? "已准入" : "未准入" },
      { label: "权威状态", value: AUTHORITY_LABELS[data.authority_status] }
    ],
    technicalFacts: [
      { label: "因子 ID", value: data.factor_id },
      { label: "因子版本", value: data.factor_version }
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
          <span className="section-kicker" title={`${sections.identity.research_family} · ${sections.identity.data_category}`}>{researchFamilyLabel(sections.identity.research_family)} · {dataCategoryLabel(sections.identity.data_category)}</span>
          <h2 title={`${data.factor_id} · ${data.factor_version}`}>冻结因子定义</h2>
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
              <div><strong>{label}</strong><span title={`${section.status} · recomputed=false`}>未评估 · 未在前端补算</span></div>
            </article>
          ))}
        </div>
      </section>
      <p className="page-evidence-footer">当前没有逐日 RankIC、IC 分布、月度热图或分位收益序列；未画出的图不是遗漏，而是证据边界。</p>
    </div>
  );
}

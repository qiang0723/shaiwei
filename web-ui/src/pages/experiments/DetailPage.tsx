import { ArrowLeftOutlined, WarningFilled } from "@ant-design/icons";
import { Column } from "@ant-design/charts";
import { useQuery } from "@tanstack/react-query";
import { Alert, Tag } from "antd";
import { fetchExperimentDetail } from "../../api";
import { useAsOf } from "../../components/AppShell";
import { PageHeader } from "../../components/PageHeader";
import { PageError, PageLoading, RefreshNotice } from "../../components/RequestState";
import { formatDateTime, formatPercent } from "../../format";
import { RouterLink, useRouter } from "../../routing";
import type { ExperimentDetailData, ExperimentKind, JsonMetric } from "../../types";
import {
  AUTHORITY_LABELS,
  AuthorityBadge,
  DecisionValue,
  EVIDENCE_STATUS_LABELS,
  HistoricalBanner,
  KIND_LABELS,
  LIFECYCLE_LABELS,
  OUTCOME_COPY,
  OutcomeBadge,
  TIER_LABELS,
  decisionLabel,
  experimentEvidence,
  experimentHeaderProps,
  experimentPath,
  metricObject,
  researchFamilyLabel
} from "./presentation";

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
                <td><Tag color={passed ? "success" : "warning"} title={passed ? "PASS" : "REJECT"}>{passed ? "通过" : "未通过"}</Tag></td>
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
          {invalidated ? <Tag color="error">可复算 · 非权威</Tag> : <Tag color="warning" title="HISTORICAL_EFFECT_REJECTED">权威历史拒绝</Tag>}
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

export function DetailPage({ kind, experimentId }: { kind: ExperimentKind; experimentId: string }) {
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
      { label: "结论语义", value: OUTCOME_COPY[data.outcome_status].label },
      { label: "权威状态", value: AUTHORITY_LABELS[data.authority_status] },
      { label: "证据层级", value: TIER_LABELS[data.evidence_tier] }
    ],
    technicalFacts: [
      { label: "实验 ID", value: data.experiment_id },
      { label: "结论枚举", value: data.outcome_status },
      { label: "权威状态枚举", value: data.authority_status },
      { label: "证据层级枚举", value: data.evidence_tier },
      { label: "模型 / 引擎", value: data.model_or_engine },
      { label: "引擎版本", value: data.engine_version },
      { label: "随机种子", value: data.seed }
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
        description="先确认结论层级、当前权威与结果语义，再阅读已登记数值；页面不重算任何效果。"
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
          <div><dt>实验标识</dt><dd title={data.experiment_id}>已登记，技术证据可查</dd></div>
          <div><dt>实验类型</dt><dd>{KIND_LABELS[data.experiment_kind]}</dd></div>
          <div><dt>证据层级</dt><dd title={data.evidence_tier}>{TIER_LABELS[data.evidence_tier]}</dd></div>
          <div><dt>生命周期</dt><dd title={data.lifecycle_status}>{LIFECYCLE_LABELS[data.lifecycle_status]}</dd></div>
          <div><dt>研究家族</dt><dd title={data.research_family}>{researchFamilyLabel(data.research_family)}</dd></div>
          <div><dt>研究实现</dt><dd title={data.model_or_engine}>已登记</dd></div>
          <div><dt>实现版本</dt><dd title={data.engine_version}>已锁定</dd></div>
          <div><dt>记录时间</dt><dd>{formatDateTime(data.recorded_at)}</dd></div>
          <div><dt>训练区间</dt><dd>{data.train_period || "未登记"}</dd></div>
          <div><dt>验证区间</dt><dd>{data.valid_period || "未登记"}</dd></div>
          <div><dt>随机性控制</dt><dd title={data.seed}>{data.seed ? "已登记" : "未登记"}</dd></div>
          <div><dt>证据状态</dt><dd title={data.evidence_status}>{EVIDENCE_STATUS_LABELS[data.evidence_status]}</dd></div>
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
          <>
            <Alert type="warning" showIcon message={`登记了 ${data.failed_reasons.length} 项失败或限制原因`} description="业务结论已在页面上方说明；原始技术原因按需展开，不用机器错误名占据主视图。" />
            <details className="technical-details experiment-failure-details">
              <summary>查看原始技术原因</summary>
              <ul className="experiment-failure-list">{data.failed_reasons.map((reason) => <li key={reason}><WarningFilled /><code>{reason}</code></li>)}</ul>
            </details>
          </>
        ) : <p className="muted">没有登记失败原因；这不等于策略有效，只表示本记录未附失败项。</p>}
        <Alert
          type="info"
          showIcon
          message="没有逐日 NAV，页面不绘制净值、日回撤或交易时序"
          description="experiment_summary 只登记聚合证据；浏览器不会从其他文件、账本或端点补算。"
        />
      </section>
      <p className="page-evidence-footer">详情只消费一个类型化响应；结论字段按证据层级白名单渲染，未知键会阻断页面，不做通用数据倾倒。</p>
    </div>
  );
}

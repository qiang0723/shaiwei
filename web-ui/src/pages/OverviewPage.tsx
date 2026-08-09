import {
  ArrowRightOutlined,
  BellOutlined,
  CalendarOutlined,
  CheckCircleOutlined,
  DatabaseOutlined,
  ExclamationCircleOutlined,
  FundOutlined,
  SafetyCertificateOutlined,
  StockOutlined,
  SyncOutlined,
  WalletOutlined
} from "@ant-design/icons";
import { Alert, Button, Divider, Steps } from "antd";
import { useQuery } from "@tanstack/react-query";
import { fetchOverview } from "../api";
import { useAsOf } from "../components/AppShell";
import { MetricCard } from "../components/MetricCard";
import { PageHeader } from "../components/PageHeader";
import { PageError, PageLoading, RefreshNotice } from "../components/RequestState";
import { StatusBadge } from "../components/StatusBadge";
import {
  displayDate,
  formatMoney,
  formatNav,
  formatPercentagePoints,
  formatPercent,
  numericTone,
  reasonLabel,
  STATUS_LABELS
} from "../format";
import type { EvidencePayload } from "../types";
import { RouterLink } from "../routing";
import { PairedCheckpointSummary } from "./overview/PairedCheckpointSummary";

function route(path: string, asOf?: string) {
  return `${path}${asOf ? `?as_of=${encodeURIComponent(asOf)}` : ""}`;
}

export default function OverviewPage() {
  const { asOf } = useAsOf();
  const query = useQuery({
    queryKey: ["overview", asOf ?? "latest"],
    queryFn: ({ signal }) => fetchOverview(asOf, signal),
    placeholderData: (previous) => previous
  });

  if (query.isPending) return <PageLoading />;
  if (query.isError) return <PageError error={query.error} retry={() => query.refetch()} />;

  const { data: d } = query.data;
  const latest = d.forward.latest;
  const evidence: EvidencePayload = {
    title: "总览原子快照",
    snapshotId: d.snapshot_id,
    asOf: d.as_of,
    generatedAt: d.generated_at,
    hashes: {
      controlled_code_snapshot: d.evidence.controlled_code_snapshot,
      data_snapshot_sha256: d.evidence.data_snapshot_sha256,
      model_artifact_sha256: d.evidence.model_artifact_sha256,
      signal_sha256: d.evidence.signal_sha256,
      ...d.evidence.evidence_hashes
    },
    sources: d.evidence.source_refs,
    facts: [
      { label: "账本重放", value: STATUS_LABELS[d.evidence.replay_status] },
      { label: "北交所计数", value: String(d.evidence.bse_count) }
    ],
    technicalFacts: [
      { label: "快照范围", value: d.evidence.acceptance_scope },
      ...(d.runtime.first_failed_step ? [{ label: "核心首次失败技术步骤", value: d.runtime.first_failed_step }] : [])
    ]
  };

  const warning = d.overall_status !== "PASS";
  const actionSentence = d.action.rebalance_due
    ? `本期需要调仓，目标相对上一目标有 ${d.action.planned_trade_leg_count} 只证券发生变化。`
    : "本期不调仓，目标组合保持不变。";
  const decisionTitle = d.action.rebalance_due
    ? "需要调仓；先核对执行证据"
    : warning
      ? "无需调仓；核心已恢复，通知仍需关注"
      : "无需调仓；当前证据完整";

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="DECISION OVERVIEW"
        title="今日概览"
        description="系统、证据、行动与前瞻成熟度分列；短样本不作策略有效性结论。"
        status={d.overall_status}
        asOf={d.as_of}
        generatedAt={d.generated_at}
        evidence={evidence}
      />
      {query.isFetching ? <RefreshNotice asOf={d.as_of} generatedAt={d.generated_at} /> : null}

      <section className={`status-hero overview-command status-hero-${d.overall_status.toLowerCase()}`} aria-label="今日四轴判断">
        <div className="overview-command-summary">
          <div className="status-hero-main">
            <div className="status-hero-icon" aria-hidden="true">
              {warning ? <ExclamationCircleOutlined /> : <CheckCircleOutlined />}
            </div>
            <div>
              <div className="eyebrow">当前判断</div>
              <h2>{decisionTitle}</h2>
              <p>{actionSentence} Top30 单账户自然前瞻 {d.forward.forward_observation_count} 日；双账户同日检查点 {d.paired_checkpoint.live_dual_count} / {d.paired_checkpoint.minimum_live_dual_days} 日。</p>
            </div>
          </div>
          <div className="status-reasons" aria-label="需关注原因">
            {d.status_reason.length ? d.status_reason.map((item) => (
              <span key={item}>{reasonLabel(item)}</span>
            )) : <span>没有阻断或警告原因</span>}
          </div>
        </div>
        <div className="decision-axis-grid">
          <div><span>核心运行</span><StatusBadge status={d.runtime.task_status} /></div>
          <div><span>证据完整</span><StatusBadge status={d.evidence_status} /></div>
          <div><span>今日行动</span><strong>{d.action.rebalance_due ? "调仓" : "不调仓"}</strong></div>
          <div><span>结果成熟度</span><StatusBadge status={d.forward.performance_maturity} /></div>
          <div className="axis-time"><span>最新完整交易日</span><strong>{displayDate(d.latest_complete_trade_date)}</strong><small>技术证据已锁定</small></div>
        </div>
      </section>

      <section className="decision-grid" aria-labelledby="action-heading">
        <article className="action-panel">
          <div className="section-heading compact-heading">
            <div>
              <span className="section-kicker">ACTION</span>
              <h2 id="action-heading">今日行动</h2>
            </div>
            <StatusBadge status={d.action.execution_evidence_status} />
          </div>
          <div className="action-answer">
            <span>{d.action.rebalance_due ? "需要调仓" : "无需调仓"}</span>
            <strong>{d.action.rebalance_due ? "进入执行检查" : "保持当前实际持仓"}</strong>
          </div>
          <dl className="detail-list">
            <div><dt>信号日期</dt><dd>{displayDate(d.action.signal_date)}</dd></div>
            <div><dt>目标证券</dt><dd>{d.action.target_count} 只</dd></div>
            <div><dt>目标变更证券数</dt><dd>{d.action.planned_trade_leg_count} 只</dd></div>
            <div><dt>下一执行日</dt><dd>{displayDate(d.action.next_execution_date)}</dd></div>
          </dl>
          <RouterLink className="panel-link" to={route("/signals", asOf)}>
            查看信号事实 <ArrowRightOutlined />
          </RouterLink>
        </article>

        <article className="forward-hero" aria-labelledby="forward-heading">
          <div className="section-heading compact-heading">
            <div>
              <span className="section-kicker">FORWARD · AFTER FEES</span>
              <h2 id="forward-heading">前瞻净值差</h2>
            </div>
            <StatusBadge status={d.forward.performance_maturity} />
          </div>
          {latest ? (
            <>
              <div className={`forward-main-number ${numericTone(latest.forward_net_excess)}`}>
                {formatPercentagePoints(latest.forward_net_excess)}
              </div>
              <p className="forward-caption">
                最后工程回放日 {displayDate(d.forward.forward_anchor_trade_date)} 重新锚定；
                当前为 Top30 单账户 {d.forward.forward_observation_count} 个自然前瞻账户日；不等同于双账户检查点。
              </p>
              <div className="nav-comparison" aria-label="组合与中证800净值比较">
                <div>
                  <span><i className="series-key portfolio" aria-hidden="true" />模拟组合</span>
                  <strong>{formatNav(latest.forward_portfolio_nav)}</strong>
                </div>
                <div>
                  <span><i className="series-key benchmark" aria-hidden="true" />中证800</span>
                  <strong>{formatNav(latest.forward_benchmark_nav)}</strong>
                </div>
              </div>
              <div className="forward-guardrail">
                <span>同范围回撤</span>
                <strong className={numericTone(latest.forward_drawdown)}>
                  {formatPercent(latest.forward_drawdown)}
                </strong>
                <span>费用</span>
                <strong>{formatMoney(d.forward.forward_cumulative_fees)}</strong>
              </div>
            </>
          ) : (
            <div className="domain-empty">
              <strong>前瞻结果尚未形成</strong>
              <p>BACKFILL 只用于工程回放，不进入前瞻主结果。</p>
            </div>
          )}
          <RouterLink className="panel-link" to={route("/paper", asOf)}>
            查看完整组合证据 <ArrowRightOutlined />
          </RouterLink>
        </article>
      </section>

      <PairedCheckpointSummary checkpoint={d.paired_checkpoint} />

      <section aria-labelledby="diagnostics-heading">
        <div className="section-heading">
          <div>
            <span className="section-kicker">DIAGNOSTICS</span>
            <h2 id="diagnostics-heading">结果为何是这样</h2>
          </div>
          <span className="section-note">账户日 {displayDate(d.paper.account_day)}</span>
        </div>
        <div className="metric-grid five-up">
          <MetricCard label="模拟净资产" value={formatMoney(d.paper.net_asset)} detail="扣费后实际账户" icon={<WalletOutlined />} />
          <MetricCard label="现金比例" value={formatPercent(d.forward.forward_cash_ratio)} detail={`${formatMoney(d.paper.cash)} 未投资现金`} icon={<FundOutlined />} />
          <MetricCard label="实际持仓" value={`${d.paper.position_count} 只`} detail={`目标 ${d.action.target_count} 只`} icon={<StockOutlined />} />
          <MetricCard label="账本重放" value={<StatusBadge status={d.paper.replay_status} compact />} detail="独立事件 / 状态链" icon={<SyncOutlined />} />
          <MetricCard label="证据完整" value={d.required_evidence_complete ? "是" : "否"} detail={`.BJ = ${d.evidence.bse_count}`} icon={<SafetyCertificateOutlined />} />
        </div>
      </section>

      <section className="two-column-support">
        <article className="surface-panel" aria-labelledby="evidence-chain-heading">
          <div className="section-heading compact-heading">
            <div>
              <span className="section-kicker">LINEAGE</span>
              <h2 id="evidence-chain-heading">证据链</h2>
            </div>
            <StatusBadge status={d.evidence_status} />
          </div>
          <Steps
            direction="vertical"
            size="small"
            items={[
              { title: "数据证据已校验", description: "完整标识可在技术证据中查看", status: "finish", icon: <DatabaseOutlined /> },
              { title: "模型证据已校验", description: "模型产物与本次信号一致", status: "finish" },
              { title: "信号已登记", description: `信号日期 ${displayDate(d.action.signal_date)}`, status: "finish" },
              { title: "执行证据", description: STATUS_LABELS[d.action.execution_evidence_status], status: d.action.execution_evidence_status === "NOT_DUE" ? "wait" : "finish", icon: <CalendarOutlined /> },
              { title: "模拟仓与重放", description: STATUS_LABELS[d.paper.replay_status], status: d.paper.replay_status === "PASS" ? "finish" : "error" }
            ]}
          />
        </article>

        <article className="surface-panel" aria-labelledby="runtime-heading">
          <div className="section-heading compact-heading">
            <div>
              <span className="section-kicker">OPERATIONS</span>
              <h2 id="runtime-heading">运行与通知分列</h2>
            </div>
          </div>
          <div className="split-status-row">
            <div><span>核心任务</span><StatusBadge status={d.runtime.task_status} /></div>
            <div><span>通知通道</span><StatusBadge status={d.runtime.notification.status} /></div>
          </div>
          <Divider />
          {d.runtime.failed_attempt_count || d.runtime.notification.failed_attempt_count ? (
            <Alert
              type="warning"
              showIcon
              message="失败尝试已保留，后续恢复不覆盖历史"
              description={`核心周期${d.runtime.recovered ? "曾失败，现已恢复" : "仍需处理"}；通知通道有 ${d.runtime.notification.recovered_message_count} 条失败后恢复记录。原始技术错误名可在技术证据中核对。`}
            />
          ) : (
            <Alert type="success" showIcon message="当前范围没有失败尝试" />
          )}
          <div className="operation-facts">
            <span><BellOutlined /> 通知尝试失败 {d.runtime.notification.failed_attempt_count}</span>
            <span><SyncOutlined /> 核心运行尝试 {d.runtime.attempt_count}</span>
            <span><SafetyCertificateOutlined /> 重复投递风险 {d.runtime.notification.duplicate_delivery_risk ? "存在" : "无"}</span>
          </div>
          <Button type="link" className="inline-link" onClick={() => query.refetch()}>
            刷新当前原子快照
          </Button>
        </article>
      </section>

      <footer className="page-evidence-footer">
        <span>技术证据已锁定</span>
        <span>策略结果成熟度：{STATUS_LABELS[d.forward.performance_maturity]}</span>
        <span>覆盖率：{STATUS_LABELS[d.forward.coverage_status]}</span>
        <span>年化 / Sharpe / 信息比率：已按门槛隐藏</span>
      </footer>
    </div>
  );
}

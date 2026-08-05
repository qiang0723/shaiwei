import {
  AccountBookOutlined,
  ArrowDownOutlined,
  FileSearchOutlined,
  FundOutlined,
  SafetyCertificateOutlined,
  WalletOutlined
} from "@ant-design/icons";
import { Line } from "@ant-design/charts";
import { useQuery } from "@tanstack/react-query";
import { Button, Descriptions, Drawer, Empty, Segmented } from "antd";
import { useRef, useState } from "react";
import { fetchPaperBundle } from "../api";
import { DataTable, type DataColumn } from "../components/DataTable";
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
  STATUS_LABELS
} from "../format";
import type {
  EvidencePayload,
  ForwardPoint,
  NavPoint,
  PaperAccountId,
  Position
} from "../types";

const PAPER_ACCOUNTS: Record<
  PaperAccountId,
  { name: string; role: string; targetCount: number; automation: string }
> = {
  model_baseline: {
    name: "主账户 · Top30",
    role: "生产基线账户",
    targetCount: 30,
    automation: "生产日更已启用"
  },
  model_top20: {
    name: "比较账户 · Top20",
    role: "独立比较账户",
    targetCount: 20,
    automation: "生产自动日更未启用"
  }
};

function ForwardEvidenceTable({ series }: { series: ForwardPoint[] }) {
  return (
    <div className="short-series-evidence">
      <div className="short-series-message" role="status">
        <strong>{series.length ? "样本不足，不绘制趋势" : "尚无自然前瞻账户日"}</strong>
        <span>{series.length ? "连续趋势至少需要 8 个可比前瞻账户日；当前展示精确值，不扩大短样本确定性。" : "工程回放只用于核验持仓、现金与账务，不作为前瞻表现。"}</span>
      </div>
      {series.length ? <div className="compact-value-table" role="region" aria-label="前瞻观察精确值" tabIndex={0}>
        <table>
          <thead><tr><th>日期</th><th>组合净值</th><th>中证800</th><th>净值差</th><th>回撤</th></tr></thead>
          <tbody>{series.map((point) => (
            <tr key={point.trade_date}>
              <td>{displayDate(point.trade_date)}</td>
              <td>{formatNav(point.forward_portfolio_nav)}</td>
              <td>{formatNav(point.forward_benchmark_nav)}</td>
              <td className={numericTone(point.forward_net_excess)}>{formatPercentagePoints(point.forward_net_excess)}</td>
              <td className={numericTone(point.forward_drawdown)}>{formatPercent(point.forward_drawdown)}</td>
            </tr>
          ))}</tbody>
        </table>
      </div> : null}
    </div>
  );
}

export default function PaperPage() {
  const { asOf } = useAsOf();
  const [accountId, setAccountId] = useState<PaperAccountId>("model_baseline");
  const [historyMode, setHistoryMode] = useState<string>("前瞻专属");
  const [selectedDay, setSelectedDay] = useState<NavPoint | null>(null);
  const dayTrigger = useRef<HTMLElement | null>(null);
  const query = useQuery({
    queryKey: ["paper-bundle", accountId, asOf ?? "latest"],
    queryFn: ({ signal }) => fetchPaperBundle(asOf, signal, accountId)
  });

  if (query.isPending) return <PageLoading label={`正在核对${PAPER_ACCOUNTS[accountId].name}的四个同快照响应…`} />;
  if (query.isError) return <PageError error={query.error} retry={() => query.refetch()} />;

  const bundle = query.data;
  const { portfolio, nav, forward, replay, meta } = bundle;
  const account = PAPER_ACCOUNTS[accountId];
  const evidence: EvidencePayload = {
    title: "模拟组合证据",
    snapshotId: bundle.snapshotId,
    asOf: bundle.asOf,
    generatedAt: bundle.generatedAt,
    hashes: { ...meta.evidence_hashes, ...portfolio.evidence_hashes },
    sources: meta.source_refs,
    facts: [
      { label: "账本重放", value: STATUS_LABELS[replay.status] },
      { label: "北交所计数", value: String(replay.bse_count) }
    ],
    technicalFacts: [
      { label: "账户 ID", value: portfolio.account_id },
      { label: "执行策略版本", value: portfolio.execution_policy_version },
      { label: "观察类型枚举", value: portfolio.mode }
    ]
  };

  const forwardChart = forward.series.flatMap((point) => [
    { date: point.trade_date, series: "模拟组合 · 前瞻", value: Number(point.forward_portfolio_nav) },
    { date: point.trade_date, series: "中证800 · 前瞻", value: Number(point.forward_benchmark_nav) }
  ]);
  const auditChart = nav.series.flatMap((point) => [
    { date: point.trade_date, series: `模拟组合 · ${point.mode === "FORWARD" ? "前瞻" : "工程回放"}`, value: Number(point.normalized_nav) },
    { date: point.trade_date, series: `中证800 · ${point.mode === "FORWARD" ? "前瞻" : "工程回放"}`, value: Number(point.benchmark_nav) }
  ]);
  const drawdownChart = forward.series.map((point) => ({
    date: point.trade_date,
    series: "前瞻回撤",
    value: Number(point.forward_drawdown)
  }));
  const maxDrawdown = Math.min(...nav.series.map((item) => Number(item.drawdown)));

  const positionColumns: DataColumn<Position>[] = [
    {
      title: "中文简称 / 代码",
      dataIndex: "ts_code",
      key: "ts_code",
      fixed: "left",
      width: 168,
      render: (value: string, record) => (
        <div className="security-name-cell">
          <strong
            title={record.security_name_source === "NAMECHANGE_PIT" ? "证券更名时点记录" : record.security_name_source === "STOCK_BASIC_CURRENT_FALLBACK" ? "A股基础信息当前简称；非历史PIT名称" : "名称来源尚未覆盖"}
          >
            {record.security_name ?? "名称待同步"}
          </strong>
          <code className="security-code">{value}</code>
        </div>
      )
    },
    { title: "数量", dataIndex: "quantity", key: "quantity", align: "right", width: 92 },
    {
      title: "实际权重",
      dataIndex: "actual_weight",
      key: "actual_weight",
      align: "right",
      width: 116,
      render: (value: string) => formatPercent(value)
    },
    {
      title: "持仓市值",
      dataIndex: "market_value",
      key: "market_value",
      align: "right",
      width: 142,
      render: (value: string) => formatMoney(value)
    },
    {
      title: "成本基础",
      dataIndex: "cost_basis",
      key: "cost_basis",
      align: "right",
      width: 142,
      render: (value: string) => formatMoney(value)
    },
    {
      title: "未实现盈亏",
      dataIndex: "unrealized_pnl",
      key: "unrealized_pnl",
      align: "right",
      width: 142,
      render: (value: string) => <span className={numericTone(value)}>{formatMoney(value)}</span>
    },
    {
      title: "已实现盈亏",
      dataIndex: "realized_pnl",
      key: "realized_pnl",
      align: "right",
      width: 142,
      render: (value: string) => <span className={numericTone(value)}>{formatMoney(value)}</span>
    },
    {
      title: "估值日",
      dataIndex: "price_date",
      key: "price_date",
      width: 112,
      render: displayDate
    },
    {
      title: "陈旧日",
      dataIndex: "stale_trade_days",
      key: "stale_trade_days",
      align: "right",
      width: 90,
      render: (value: number) => (value ? `${value} 日` : "0 日")
    }
  ];

  const dayColumns: DataColumn<NavPoint>[] = [
    {
      title: "账户日",
      dataIndex: "trade_date",
      key: "trade_date",
      render: (value: string, record) => (
        <Button
          type="link"
          className="table-link"
          onClick={(event) => {
            dayTrigger.current = event.currentTarget;
            setSelectedDay(record);
          }}
        >
          {displayDate(value)}
        </Button>
      )
    },
    { title: "观察类型", dataIndex: "mode", key: "mode", render: (value: string) => <span className={`mode-label mode-${value.toLowerCase()}`} title={value}>{value === "FORWARD" ? "前瞻观察" : "工程回放"}</span> },
    { title: "组合净值", dataIndex: "normalized_nav", key: "normalized_nav", align: "right", render: formatNav },
    { title: "中证800", dataIndex: "benchmark_nav", key: "benchmark_nav", align: "right", render: formatNav },
    { title: "净值差", dataIndex: "net_excess", key: "net_excess", align: "right", render: (value: string) => <span className={numericTone(value)}>{formatPercentagePoints(value)}</span> },
    { title: "回撤", dataIndex: "drawdown", key: "drawdown", align: "right", render: (value: string) => <span className={numericTone(value)}>{formatPercent(value)}</span> },
    { title: "现金比例", dataIndex: "cash_ratio", key: "cash_ratio", align: "right", render: (value: string) => formatPercent(value) },
    { title: "换手", dataIndex: "turnover", key: "turnover", align: "right", render: (value: string) => formatPercent(value) }
  ];

  const chartConfig = {
      xField: "date",
      yField: "value",
      colorField: "series",
      height: 320,
      axis: {
        x: { title: false },
        y: { title: "归一化净值", labelFormatter: (value: number) => Number(value).toFixed(3) }
      },
      legend: { color: { position: "top" } },
      tooltip: { title: "date" },
      interaction: { tooltip: { shared: true } },
      animate: false
    };

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="PAPER PORTFOLIO"
        title="模拟组合"
        description="目标、订单、成交、持仓与现金严格分开；短样本只展示已登记账户事实。"
        status={replay.status}
        asOf={bundle.asOf}
        generatedAt={bundle.generatedAt}
        evidence={evidence}
      />
      {query.isFetching ? (
        <RefreshNotice asOf={bundle.asOf} generatedAt={bundle.generatedAt} />
      ) : null}

      <section className="account-selector-surface" aria-labelledby="paper-account-selector-heading">
        <div>
          <span className="section-kicker">ACCOUNT SCOPE</span>
          <h2 id="paper-account-selector-heading">选择模拟账户</h2>
          <p>切换只改变本页读取的账户证据；总览、信号和生产基线仍使用 Top30。</p>
        </div>
        <Segmented
          aria-label="选择模拟账户"
          block
          options={[
            { label: "主账户 · Top30", value: "model_baseline" },
            { label: "比较账户 · Top20", value: "model_top20" }
          ]}
          value={accountId}
          onChange={(value) => {
            setSelectedDay(null);
            setHistoryMode("前瞻专属");
            setAccountId(value as PaperAccountId);
          }}
        />
      </section>

      {accountId === "model_top20" ? (
        <div className="account-boundary-notice" role="status">
          <SafetyCertificateOutlined aria-hidden="true" />
          <div>
            <strong>
              {forward.forward_observation_count === 0
                ? "Top20 当前只完成工程回放，不能与 Top30 比较策略优劣"
                : "Top20 已开始自然前瞻，但样本仍不足以与 Top30 比较策略优劣"}
            </strong>
            <span>自然前瞻 {forward.forward_observation_count} 日 · {account.automation}；本页只展示可重放的持仓、现金和账户日证据。</span>
          </div>
        </div>
      ) : null}

      <section className="identity-strip" aria-label="模拟组合身份">
        <div><span>账户</span><strong title={portfolio.account_id}>{account.name}</strong></div>
        <div><span>执行规则</span><strong title={portfolio.execution_policy_version}>固定模拟规则</strong></div>
        <div><span>基准</span><strong>000906.SH · 中证800</strong></div>
        <div><span>账户角色</span><strong>{account.role} · 目标{account.targetCount}只</strong></div>
        <div><span>账本重放</span><StatusBadge status={replay.status} compact /></div>
      </section>

      <section className="chart-surface primary-chart" aria-labelledby="paper-performance-heading">
        <div className="section-heading">
          <div>
            <span className="section-kicker">FORWARD · ANCHORED</span>
            <h2 id="paper-performance-heading">前瞻组合与中证800</h2>
          </div>
          <div className="chart-meta">
            <span>{forward.forward_anchor_trade_date ? `锚点 ${displayDate(forward.forward_anchor_trade_date)}` : "前瞻锚点未形成"}</span>
            <StatusBadge status={forward.performance_maturity} />
          </div>
        </div>
        <div className="chart-summary-grid">
          <MetricCard
            label="最新前瞻净值差"
            value={forward.latest ? formatPercentagePoints(forward.latest.forward_net_excess) : "未就绪"}
            detail={`${forward.forward_observation_count} 个 FORWARD 账户日`}
            tone={forward.latest && Number(forward.latest.forward_net_excess) < 0 ? "negative" : "default"}
          />
          <MetricCard
            label="同范围回撤"
            value={forward.latest ? formatPercent(forward.latest.forward_drawdown) : "—"}
            detail="从前瞻锚点起算"
            tone="negative"
          />
          <MetricCard label="覆盖率" value={<StatusBadge status={forward.coverage_status} compact />} detail={forward.coverage_reason} />
        </div>
        {forward.series.length >= 8 ? (
          <>
            <div className="chart-canvas" role="img" aria-label="前瞻模拟组合与中证800归一化净值折线图">
              <Line {...chartConfig} data={forwardChart} />
            </div>
            <details className="accessible-data-table">
              <summary>查看图表等价数据</summary>
              <table>
                <thead><tr><th>日期</th><th>组合净值</th><th>基准净值</th><th>净值差</th><th>回撤</th></tr></thead>
                <tbody>{forward.series.map((point) => (
                  <tr key={point.trade_date}><td>{point.trade_date}</td><td>{formatNav(point.forward_portfolio_nav)}</td><td>{formatNav(point.forward_benchmark_nav)}</td><td>{formatPercentagePoints(point.forward_net_excess)}</td><td>{formatPercent(point.forward_drawdown)}</td></tr>
                ))}</tbody>
              </table>
            </details>
          </>
        ) : <ForwardEvidenceTable series={forward.series} />}
        <div className="chart-footnote">
          <span>账户：{account.name}</span><span>观察类型：仅自然前瞻</span><span>基准：000906.SH</span><span>费用：实际成交费用</span><span title={portfolio.execution_policy_version}>策略：固定模拟规则</span>
        </div>
      </section>

      <section aria-labelledby="account-heading">
        <div className="section-heading">
          <div><span className="section-kicker">ACCOUNTING</span><h2 id="account-heading">当前账户</h2></div>
          <span className="section-note">会计恒等由 P3-0 查询层 fail closed</span>
        </div>
        <div className="metric-grid five-up">
          <MetricCard label="净资产" value={formatMoney(portfolio.net_asset)} detail={displayDate(portfolio.as_of)} icon={<WalletOutlined />} />
          <MetricCard label="现金" value={formatMoney(portfolio.cash)} detail={formatPercent(portfolio.cash_ratio)} icon={<FundOutlined />} />
          <MetricCard label="持仓市值" value={formatMoney(portfolio.market_value)} detail={`${portfolio.position_count} 只实际持仓`} icon={<AccountBookOutlined />} />
          <MetricCard label="累计费用" value={formatMoney(portfolio.cumulative_fees)} detail="实际模拟成交" />
          <MetricCard label="累计分红" value={formatMoney(portfolio.cumulative_dividends)} detail="已登记公司行为" />
        </div>
      </section>

      <section className="chart-surface" aria-labelledby="audit-heading">
        <div className="section-heading">
          <div><span className="section-kicker">AUDIT HISTORY</span><h2 id="audit-heading">全账户审计历史</h2></div>
          <Segmented options={["前瞻专属", "全账户"]} value={historyMode} onChange={(value) => setHistoryMode(String(value))} />
        </div>
        {historyMode === "前瞻专属" && forward.series.length >= 8 ? (
          <div className="split-charts">
            <div>
              <h3>锚定净值</h3>
              <Line {...chartConfig} data={forwardChart} height={260} />
            </div>
            <div>
              <h3>同范围回撤</h3>
              <Line
                {...chartConfig}
                data={drawdownChart}
                height={260}
                axis={{ x: { title: false }, y: { title: "回撤", labelFormatter: (value: number) => `${(Number(value) * 100).toFixed(1)}%` } }}
              />
            </div>
          </div>
        ) : historyMode === "全账户" && nav.series.length >= 8 ? (
          <>
            <div className="audit-boundary-note"><ArrowDownOutlined /> BACKFILL 仅作工程与账务审计，FORWARD 才是自然观察；两段不合并为前瞻结论。</div>
            <Line {...chartConfig} data={auditChart} height={300} />
          </>
        ) : (
          <div className="short-audit-summary">
            <ArrowDownOutlined aria-hidden="true" />
            <div>
              {historyMode === "前瞻专属" ? (
                <>
                  <strong>前瞻序列共 {forward.series.length} 个账户日，不绘制趋势</strong>
                  <p>仅陈述锚点后的自然观察，工程回放不进入本范围；精确值见上方前瞻表及下方账户日证据。</p>
                </>
              ) : (
                <>
                  <strong>全账户审计序列共 {nav.series.length} 个账户日，不绘制趋势</strong>
                  <p>工程回放 {replay.mode_counts.BACKFILL ?? 0} 日只作工程与账务审计；前瞻观察 {replay.mode_counts.FORWARD ?? 0} 日是自然观察。逐日精确值见下方“账户日与证据”。</p>
                </>
              )}
            </div>
          </div>
        )}
        <div className="chart-footnote"><span>全账户最大回撤 {formatPercent(maxDrawdown)}</span><span>工程回放 {replay.mode_counts.BACKFILL ?? 0} 日</span><span>前瞻观察 {replay.mode_counts.FORWARD ?? 0} 日</span></div>
      </section>

      <section className="table-surface" aria-labelledby="positions-heading">
        <div className="section-heading">
          <div><span className="section-kicker">ACTUAL POSITIONS</span><h2 id="positions-heading">实际持仓</h2></div>
          <span className="section-note">中文简称按账户日解析；股票代码保留为审计标识</span>
        </div>
        <DataTable
          label="实际持仓横向滚动表格"
          rowKey="ts_code"
          columns={positionColumns}
          data={portfolio.positions}
          minimumWidth="wide"
          emptyText={<Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前没有实际持仓" />}
        />
      </section>

      <section className="table-surface" aria-labelledby="account-days-heading">
        <div className="section-heading">
          <div><span className="section-kicker">DAY LEDGER</span><h2 id="account-days-heading">账户日与证据</h2></div>
          <span className="section-note">点击账户日查看同一产物字段</span>
        </div>
        <DataTable
          label="账户日证据横向滚动表格"
          rowKey="trade_date"
          columns={dayColumns}
          data={nav.series}
          minimumWidth="medium"
        />
        <div className="contract-gap-note">
          <FileSearchOutlined /> P3-0 尚未开放订单 / 成交明细 HTTP 端点；本阶段不绕过 API 读取文件补齐。
        </div>
      </section>

      <section className="replay-strip" aria-label="重放摘要">
        <SafetyCertificateOutlined />
        <div><strong>不可变账本独立重放：{STATUS_LABELS[replay.status]}</strong><span>{replay.run_count} 个账户日 · {replay.event_count} 个事件 · {replay.order_count} 笔订单 · {replay.fill_count} 笔成交 · 北交所 {replay.bse_count} 只</span></div>
        <span>证据已校验</span>
      </section>

      <Drawer
        title={selectedDay ? `${displayDate(selectedDay.trade_date)} 账户日证据` : "账户日证据"}
        open={selectedDay !== null}
        onClose={() => {
          setSelectedDay(null);
          window.setTimeout(() => dayTrigger.current?.focus(), 0);
        }}
        width={520}
        destroyOnHidden
      >
        {selectedDay ? (
          <><Descriptions column={1} bordered size="small">
            <Descriptions.Item label="观察类型"><span className={`mode-label mode-${selectedDay.mode.toLowerCase()}`} title={selectedDay.mode}>{selectedDay.mode === "FORWARD" ? "前瞻观察" : "工程回放"}</span></Descriptions.Item>
            <Descriptions.Item label="组合净值">{formatNav(selectedDay.normalized_nav)}</Descriptions.Item>
            <Descriptions.Item label="中证800">{formatNav(selectedDay.benchmark_nav)}</Descriptions.Item>
            <Descriptions.Item label="全账户净值差">{formatPercentagePoints(selectedDay.net_excess)}</Descriptions.Item>
            <Descriptions.Item label="回撤">{formatPercent(selectedDay.drawdown)}</Descriptions.Item>
            <Descriptions.Item label="换手">{formatPercent(selectedDay.turnover)}</Descriptions.Item>
            <Descriptions.Item label="现金比例">{formatPercent(selectedDay.cash_ratio)}</Descriptions.Item>
            <Descriptions.Item label="当日费用">{formatMoney(selectedDay.daily_fees)}</Descriptions.Item>
          </Descriptions>
          <details className="technical-details drawer-technical-details">
            <summary>查看账户日技术标识</summary>
            <dl><div><dt>产物校验值</dt><dd><code className="full-hash">{selectedDay.artifact_sha256}</code></dd></div></dl>
          </details></>
        ) : null}
      </Drawer>
    </div>
  );
}

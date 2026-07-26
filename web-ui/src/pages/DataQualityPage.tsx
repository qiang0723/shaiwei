import {
  CheckCircleOutlined,
  DatabaseOutlined,
  FileProtectOutlined,
  SafetyCertificateOutlined,
  WarningOutlined
} from "@ant-design/icons";
import { Alert } from "antd";
import { useQuery } from "@tanstack/react-query";
import { fetchDataQuality } from "../api";
import { useAsOf } from "../components/AppShell";
import { DataTable, type DataColumn } from "../components/DataTable";
import { MetricCard } from "../components/MetricCard";
import { PageHeader } from "../components/PageHeader";
import { PageError, PageLoading, RefreshNotice } from "../components/RequestState";
import { StatusBadge } from "../components/StatusBadge";
import { displayDate, formatDateTime, formatNumber, STATUS_LABELS } from "../format";
import { dataVerdictCopy } from "../operationsPresentation";
import type { EvidencePayload, IncrementalBatch, JsonMetric, SentinelResult } from "../types";

interface SourceCount {
  source_api: string;
  batch_count: number;
}

interface DisplayBatch extends IncrementalBatch {
  display_index: number;
}

const SOURCE_API_LABELS: Record<string, string> = {
  "tushare.adj_factor": "复权因子",
  "tushare.balancesheet": "资产负债表",
  "tushare.balancesheet_vip": "资产负债表补充源",
  "tushare.cashflow": "现金流量表",
  "tushare.cashflow_vip": "现金流量表补充源",
  "tushare.daily": "A股日行情",
  "tushare.daily_basic": "日频估值指标",
  "tushare.dividend": "分红送股",
  "tushare.income": "利润表",
  "tushare.income_vip": "利润表补充源",
  "tushare.index_daily": "指数日行情",
  "tushare.index_member_all": "指数成分",
  "tushare.index_weight": "指数权重",
  "tushare.moneyflow": "个股资金流",
  "tushare.moneyflow_dc": "东方财富资金流",
  "tushare.moneyflow_ths": "同花顺资金流",
  "tushare.namechange": "证券更名",
  "tushare.stock_basic": "A股基础信息",
  "tushare.suspend_d": "停复牌记录",
  "tushare.trade_cal": "交易日历"
};

function sourceApiLabel(value: string) {
  return SOURCE_API_LABELS[value] ?? "已登记数据来源";
}

function metricValue(value: JsonMetric): string {
  if (value === null) return "空值";
  if (typeof value === "boolean") return value ? "是" : "否";
  if (typeof value === "number") return Number.isInteger(value) ? formatNumber(value, 0) : formatNumber(value, 6);
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return `${value.length} 项`;
  return `${Object.keys(value).length} 个字段`;
}

function SentinelCard({ result }: { result: SentinelResult }) {
  return (
    <article className="sentinel-card">
      <div className="sentinel-card-heading">
        <div>
          <strong>{result.sentinel}</strong>
          <span>{result.accepted_for_signal ? "允许生成信号" : "阻断信号"}</span>
        </div>
        <StatusBadge status={result.status} compact />
      </div>
      <div className="sentinel-facts">
        <span>异常 <strong>{formatNumber(result.anomaly_count, 0)}</strong></span>
        <span>指标 <strong>{formatNumber(Object.keys(result.metrics).length, 0)}</strong></span>
      </div>
      <details className="sentinel-metrics">
        <summary>查看脱敏指标</summary>
        <dl>
          {Object.entries(result.metrics).map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd title={typeof value === "object" ? JSON.stringify(value) : undefined}>
                {metricValue(value)}
              </dd>
            </div>
          ))}
        </dl>
      </details>
    </article>
  );
}

export default function DataQualityPage() {
  const { asOf } = useAsOf();
  const query = useQuery({
    queryKey: ["data-quality", asOf || "latest"],
    queryFn: ({ signal }) => fetchDataQuality(asOf, signal),
    placeholderData: (previous) => previous
  });

  if (query.isPending) return <PageLoading label="正在核对数据质量证据…" />;
  if (query.isError) return <PageError error={query.error} retry={() => query.refetch()} />;

  const { data: d, meta } = query.data;
  const verdictCopy = dataVerdictCopy(d.status);
  const evidence: EvidencePayload = {
    title: "数据质量原子快照",
    snapshotId: meta.snapshot_id,
    asOf: meta.as_of,
    generatedAt: meta.generated_at,
    hashes: {
      data_snapshot_sha256: d.data_snapshot_sha256,
      code_snapshot_sha256: d.code_snapshot_sha256,
      sentinel_report_sha256: d.sentinel_gate.report_sha256,
      ...meta.evidence_hashes
    },
    sources: meta.source_refs,
    facts: [
      { label: "数据结论", value: STATUS_LABELS[d.status] },
      { label: "证据强度", value: STATUS_LABELS[d.evidence_status] },
      { label: "原始文件重验", value: STATUS_LABELS[d.batch_chain.raw_parquet_rehash_status] }
    ],
    technicalFacts: [
      { label: "哨兵绑定状态", value: d.sentinel_gate.binding_status },
      { label: "哨兵证据提示", value: d.sentinel_gate.evidence_warning },
      ...d.batch_chain.incremental_batches.flatMap((batch, index) => [
        { label: `批次 ${index + 1} 编号`, value: batch.batch_id },
        { label: `批次 ${index + 1} 内容校验值`, value: batch.content_sha256 }
      ])
    ]
  };
  const sources: SourceCount[] = Object.entries(d.batch_chain.source_api_batch_counts)
    .map(([source_api, batch_count]) => ({ source_api, batch_count }))
    .sort((left, right) => right.batch_count - left.batch_count || left.source_api.localeCompare(right.source_api));

  const batches: DisplayBatch[] = d.batch_chain.incremental_batches.map((batch, index) => ({
    ...batch,
    display_index: index + 1
  }));
  const batchColumns: DataColumn<DisplayBatch>[] = [
    {
      title: "批次",
      dataIndex: "display_index",
      key: "display_index",
      fixed: "left",
      render: (_value, row) => `第 ${row.display_index} 批`
    },
    { title: "来源", dataIndex: "source_api", key: "source_api", render: (value: string) => <span title={value}>{sourceApiLabel(value)}</span> },
    {
      title: "行数",
      dataIndex: "row_count",
      key: "row_count",
      align: "right",
      render: (_value, row) => formatNumber(row.row_count, 0)
    },
    {
      title: "采集时刻",
      dataIndex: "ingest_time",
      key: "ingest_time",
      render: (_value, row) => formatDateTime(row.ingest_time)
    }
  ];
  const sourceColumns: DataColumn<SourceCount>[] = [
    { title: "数据来源", dataIndex: "source_api", key: "source_api", fixed: "left", render: (value: string) => <span title={value}>{sourceApiLabel(value)}</span> },
    {
      title: "登记批次",
      dataIndex: "batch_count",
      key: "batch_count",
      align: "right",
      render: (_value, row) => formatNumber(row.batch_count, 0)
    }
  ];

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="DATA QUALITY"
        title="数据质量"
        description="数据门、证据强度与未评估范围分列；账本一致不等于原始文件已重验。"
        status={d.status}
        asOf={d.as_of}
        generatedAt={meta.generated_at}
        evidence={evidence}
      />
      {query.isFetching ? <RefreshNotice asOf={d.as_of} generatedAt={meta.generated_at} /> : null}

      <section className="operations-hero" aria-label="数据结论与证据强度">
        <article className={`operations-hero-primary ${verdictCopy.tone}`}>
          <div className={`operations-hero-icon ${verdictCopy.tone}`} aria-hidden="true">
            {d.status === "PASS" ? <CheckCircleOutlined /> : <WarningOutlined />}
          </div>
          <div>
            <span className="section-kicker">DATA VERDICT</span>
            <h2>{verdictCopy.title}</h2>
            <p>{verdictCopy.detail}</p>
          </div>
          <StatusBadge status={d.status} />
        </article>
        <article className="operations-hero-warning">
          <div className="operations-hero-icon warning" aria-hidden="true"><WarningOutlined /></div>
          <div>
            <span className="section-kicker">EVIDENCE STRENGTH</span>
            <h2>证据仍有明确缺口，不能宣称全量重验</h2>
            <p>哨兵报告与运行身份一致，但没有历史完整性绑定；原始文件未挂载、未重新校验。</p>
          </div>
          <StatusBadge status={d.evidence_status} />
        </article>
      </section>

      <section aria-labelledby="quality-scale-heading">
        <div className="section-heading">
          <div>
            <span className="section-kicker">SCALE & CUT</span>
            <h2 id="quality-scale-heading">证据切片与规模</h2>
          </div>
          <span className="section-note">数据证据已锁定</span>
        </div>
        <div className="metric-grid operations-metric-grid">
          <MetricCard label="最新完整交易日" value={displayDate(d.as_of)} detail={formatDateTime(d.daily_increment.terminal_finished_at)} icon={<DatabaseOutlined />} />
          <MetricCard label="当日市场行数" value={formatNumber(d.daily_increment.market_row_count, 0)} detail={`${d.daily_increment.batch_count} 个日增量批次`} icon={<FileProtectOutlined />} />
          <MetricCard label="登记批次" value={formatNumber(d.batch_chain.registered_batch_count, 0)} detail={`${formatNumber(d.batch_chain.registered_row_count, 0)} 行登记身份`} icon={<DatabaseOutlined />} />
          <MetricCard label="来源 API" value={`${d.batch_chain.source_api_count} 个`} detail="截止日运行完成时刻" icon={<SafetyCertificateOutlined />} />
          <MetricCard label="北交所证券" value="0" detail="市场批次 / 返回值 / S1 引用均为 0" tone="positive" icon={<CheckCircleOutlined />} />
          <MetricCard label="原始文件重验" value={<StatusBadge status={d.batch_chain.raw_parquet_rehash_status} compact />} detail="当前查询未挂载原始文件，因此不宣称完成全量重验" tone="warning" icon={<WarningOutlined />} />
        </div>
      </section>

      <section aria-labelledby="sentinel-heading">
        <div className="section-heading">
          <div>
            <span className="section-kicker">S1—S10</span>
            <h2 id="sentinel-heading">数据哨兵矩阵</h2>
          </div>
          <div className="chart-meta">
            <StatusBadge status={d.sentinel_gate.status} compact />
            <span>异常合计 {d.sentinel_gate.sentinels.reduce((sum, item) => sum + item.anomaly_count, 0)}</span>
          </div>
        </div>
        <div className="sentinel-grid">
          {d.sentinel_gate.sentinels.map((item) => <SentinelCard result={item} key={item.sentinel} />)}
        </div>
        <Alert
          className="operations-boundary-alert"
          type="warning"
          showIcon
          message="哨兵报告未被历史运行完整性证据绑定"
          description="哨兵内容与当前运行身份一致，但历史运行没有绑定该报告的完整性校验值；因此只用于当前只读切片核对。"
        />
      </section>

      <section className="table-surface" aria-labelledby="batch-heading">
        <div className="section-heading">
          <div>
            <span className="section-kicker">DAILY INCREMENT</span>
            <h2 id="batch-heading">当日新增原始批次登记</h2>
          </div>
          <span className="section-note">主视图只显示来源、行数与采集时刻</span>
        </div>
        <DataTable
          label="当日新增批次"
          columns={batchColumns}
          data={batches}
          rowKey="batch_id"
          minimumWidth="medium"
        />
      </section>

      <section className="two-column-support">
        <article className="table-surface" aria-labelledby="source-heading">
          <div className="section-heading compact-heading">
            <div>
              <span className="section-kicker">SOURCE MIX</span>
              <h2 id="source-heading">登记来源</h2>
            </div>
          </div>
          <DataTable
            label="登记来源批次数"
            columns={sourceColumns}
            data={sources}
            rowKey="source_api"
            minimumWidth="medium"
          />
        </article>
        <article className="surface-panel" aria-labelledby="quality-boundary-heading">
          <div className="section-heading compact-heading">
            <div>
              <span className="section-kicker">BOUNDARIES</span>
              <h2 id="quality-boundary-heading">能说什么，不能说什么</h2>
            </div>
          </div>
          <ul className="evidence-boundary-list">
            <li><strong>可以：</strong>截止运行完成时刻的登记身份链与日运行快照一致。</li>
            <li><strong>可以：</strong>当前哨兵内容、信号和代码/数据身份相互一致。</li>
            <li><strong>不可以：</strong>宣称查询时重新读取并校验全部原始文件。</li>
            <li><strong>不可以：</strong>把数据门 PASS 扩大解释为模型或策略有效。</li>
          </ul>
          <div className="page-evidence-footer">
            <span>批次链已校验</span>
            <span>哨兵报告已校验</span>
            <span>代码与数据证据已锁定</span>
          </div>
        </article>
      </section>
    </div>
  );
}

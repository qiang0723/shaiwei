import {
  AimOutlined,
  CalendarOutlined,
  FileSearchOutlined,
  SafetyCertificateOutlined,
  SwapOutlined
} from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { Descriptions, Drawer, Empty, Input, Select } from "antd";
import { useRef, useState } from "react";
import { fetchSignal } from "../api";
import { DataTable, type DataColumn } from "../components/DataTable";
import { useAsOf } from "../components/AppShell";
import { MetricCard } from "../components/MetricCard";
import { PageHeader } from "../components/PageHeader";
import { PageError, PageLoading, RefreshNotice } from "../components/RequestState";
import { StatusBadge } from "../components/StatusBadge";
import {
  displayDate,
  formatDateTime,
  formatNumber,
  formatPercent,
  numericTone,
  shortHash
} from "../format";
import type { EvidencePayload, SignalTarget } from "../types";

const CHANGE_LABELS: Record<SignalTarget["target_change"], string> = {
  ADDED: "新增",
  RETAINED: "保留",
  REMOVED: "移除"
};

export default function SignalsPage() {
  const { asOf } = useAsOf();
  const [change, setChange] = useState<string>("ALL");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<SignalTarget | null>(null);
  const rowTrigger = useRef<HTMLElement | null>(null);
  const query = useQuery({
    queryKey: ["latest-signal", asOf ?? "latest"],
    queryFn: ({ signal }) => fetchSignal(asOf, signal),
    placeholderData: (previous) => previous
  });

  if (query.isPending) return <PageLoading label="正在核对不可变信号与实际权重参照…" />;
  if (query.isError) return <PageError error={query.error} retry={() => query.refetch()} />;

  const { data: d, meta } = query.data;
  const evidence: EvidencePayload = {
    title: "信号与股票池证据",
    snapshotId: meta.snapshot_id,
    asOf: meta.as_of,
    generatedAt: meta.generated_at,
    hashes: {
      signal_sha256: d.signal_sha256,
      source_file_sha256: d.source_file_sha256,
      code_snapshot_sha256: d.code_snapshot_sha256,
      data_snapshot_sha256: d.data_snapshot_sha256,
      qlib_artifact_sha256: d.qlib_artifact_sha256,
      model_spec_sha256: d.model_spec_sha256,
      model_artifact_sha256: d.model_artifact_sha256,
      actual_weight_artifact_sha256: d.actual_weight_artifact_sha256
    },
    sources: [d.source_ref],
    facts: [
      { label: "信号日期", value: d.signal_date },
      { label: "实际权重参照日", value: d.actual_weight_as_of },
      { label: "北交所计数", value: String(d.bse_count) }
    ]
  };

  const filtered = d.targets.filter(
    (item) =>
      (change === "ALL" || item.target_change === change) &&
      (!search || item.ts_code.toLowerCase().includes(search.trim().toLowerCase()))
  );
  const changeCounts = d.targets.reduce<Record<string, number>>((counts, item) => {
    counts[item.target_change] = (counts[item.target_change] ?? 0) + 1;
    return counts;
  }, {});

  const columns: DataColumn<SignalTarget>[] = [
    { title: "排名", dataIndex: "rank", key: "rank", width: 76, align: "right", sorter: (a, b) => a.rank - b.rank },
    {
      title: "证券",
      dataIndex: "ts_code",
      key: "ts_code",
      fixed: "left",
      width: 126,
      render: (value: string, record) => (
        <button
          className="security-detail-button"
          onClick={(event) => {
            rowTrigger.current = event.currentTarget;
            setSelected(record);
          }}
        >
          {value}
        </button>
      )
    },
    {
      title: "目标变化",
      dataIndex: "target_change",
      key: "target_change",
      width: 100,
      render: (value: SignalTarget["target_change"]) => <span className={`change-label change-${value.toLowerCase()}`}>{CHANGE_LABELS[value]}</span>
    },
    { title: "目标权重", dataIndex: "target_weight", key: "target_weight", align: "right", width: 118, render: (value: string) => formatPercent(value) },
    { title: `实际权重 · ${displayDate(d.actual_weight_as_of)}`, dataIndex: "actual_weight", key: "actual_weight", align: "right", width: 178, render: (value: string) => formatPercent(value) },
    {
      title: "目标权重差",
      dataIndex: "planned_weight_delta",
      key: "planned_weight_delta",
      align: "right",
      width: 132,
      render: (value: string) => <span className={numericTone(value)}>{formatPercent(value, { signed: true })}</span>
    },
    { title: "模型分数", dataIndex: "score", key: "score", align: "right", width: 120, render: (value: number) => formatNumber(value, 6) },
    {
      title: "执行证据",
      key: "execution",
      width: 150,
      render: () => <StatusBadge status={d.execution_evidence_status} compact />
    }
  ];

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="UNIVERSE & SIGNAL"
        title="股票池与信号"
        description="目标权重与最近实际持仓并列；目标差不是订单，执行日前不预测可成交性。"
        status={d.execution_evidence_status}
        asOf={meta.as_of}
        generatedAt={d.generated_at}
        evidence={evidence}
      />
      {query.isFetching ? (
        <RefreshNotice asOf={meta.as_of} generatedAt={meta.generated_at} />
      ) : null}

      <section className="signal-decision-hero">
        <div>
          <span className="section-kicker">LATEST IMMUTABLE SIGNAL</span>
          <h2>{d.rebalance_due ? "本期需要调仓" : "本期不调仓，目标组合保持"}</h2>
          <p>
            信号生成于 {formatDateTime(d.generated_at)}；执行证据
            <strong> {d.execution_evidence_status}</strong>，下一执行日
            <strong> {displayDate(d.next_execution_date)}</strong>。
          </p>
        </div>
        <div className="signal-identity">
          <span>信号 SHA-256</span>
          <code>{shortHash(d.signal_sha256)}</code>
          <small>数据截至 {formatDateTime(d.data_complete_at)}</small>
        </div>
      </section>

      <section aria-labelledby="signal-summary-heading">
        <div className="section-heading">
          <div><span className="section-kicker">DECISION FACTS</span><h2 id="signal-summary-heading">信号事实</h2></div>
          <StatusBadge status={d.metric_status} />
        </div>
        <div className="metric-grid five-up">
          <MetricCard label="目标证券" value={`${d.target_count} 只`} detail={`新增 ${changeCounts.ADDED ?? 0} · 保留 ${changeCounts.RETAINED ?? 0}`} icon={<AimOutlined />} />
          <MetricCard label="目标变更证券数" value={`${d.planned_trade_leg_count} 只`} detail={d.rebalance_due ? "当前目标相对上一目标" : "非调仓日固定为 0"} icon={<SwapOutlined />} />
          <MetricCard label="已执行订单腿" value={d.executed_trade_leg_count == null ? "待证据" : `${d.executed_trade_leg_count} 条`} detail="仅来自执行日对账" />
          <MetricCard label="执行证据" value={<StatusBadge status={d.execution_evidence_status} compact />} detail={displayDate(d.next_execution_date)} icon={<CalendarOutlined />} />
          <MetricCard label="北交所" value={`${d.bse_count} 只`} detail="非 0 将整页阻断" icon={<SafetyCertificateOutlined />} />
        </div>
      </section>

      {d.execution_evidence_status === "NOT_DUE" ? (
        <section className="not-due-banner" role="status">
          <CalendarOutlined />
          <div>
            <strong>执行日证据尚未到期</strong>
            <span>停牌、方向性涨跌停、真实开盘、成交、换手和成本不会被预测或补零。</span>
          </div>
        </section>
      ) : null}

      <section className="table-surface" aria-labelledby="targets-heading">
        <div className="section-heading signal-table-heading">
          <div><span className="section-kicker">TARGET BOOK</span><h2 id="targets-heading">目标股票池</h2></div>
          <div className="table-filters" aria-label="目标股票池筛选">
            <Input.Search
              allowClear
              placeholder="搜索证券代码"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              aria-label="搜索证券代码"
            />
            <Select
              aria-label="按目标变化筛选"
              value={change}
              onChange={setChange}
              options={[
                { value: "ALL", label: "全部变化" },
                { value: "ADDED", label: "新增" },
                { value: "RETAINED", label: "保留" },
                { value: "REMOVED", label: "移除" }
              ]}
            />
          </div>
        </div>
        <DataTable
          label="目标股票池横向滚动表格"
          rowKey="ts_code"
          columns={columns}
          data={filtered}
          minimumWidth="wide"
          emptyText={<Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前筛选没有目标" />}
        />
        <div className="table-caption">
          目标权重来自不可变信号；实际权重来自 {displayDate(d.actual_weight_as_of)} 已完成模拟账户日；目标权重差只用于诊断，不代表订单或成交。
        </div>
      </section>

      <section className="model-evidence-strip" aria-label="信号证据身份">
        <FileSearchOutlined />
        <div><span>模型产物</span><code>{shortHash(d.model_artifact_sha256)}</code></div>
        <div><span>qlib 产物</span><code>{shortHash(d.qlib_artifact_sha256)}</code></div>
        <div><span>代码快照</span><code>{shortHash(d.code_snapshot_sha256)}</code></div>
        <div><span>数据快照</span><code>{shortHash(d.data_snapshot_sha256)}</code></div>
      </section>

      <Drawer
        title={selected ? `${selected.ts_code} · 信号事实` : "证券信号事实"}
        open={selected !== null}
        onClose={() => {
          setSelected(null);
          window.setTimeout(() => rowTrigger.current?.focus(), 0);
        }}
        width={520}
        destroyOnHidden
      >
        {selected ? (
          <>
            <Descriptions column={1} bordered size="small">
              <Descriptions.Item label="排名">{selected.rank}</Descriptions.Item>
              <Descriptions.Item label="目标变化">{CHANGE_LABELS[selected.target_change]}</Descriptions.Item>
              <Descriptions.Item label="目标权重">{formatPercent(selected.target_weight)}</Descriptions.Item>
              <Descriptions.Item label={`实际权重 · ${displayDate(d.actual_weight_as_of)}`}>{formatPercent(selected.actual_weight)}</Descriptions.Item>
              <Descriptions.Item label="目标权重差"><span className={numericTone(selected.planned_weight_delta)}>{formatPercent(selected.planned_weight_delta, { signed: true })}</span></Descriptions.Item>
              <Descriptions.Item label="模型分数">{formatNumber(selected.score, 6)}</Descriptions.Item>
              <Descriptions.Item label="执行证据"><StatusBadge status={d.execution_evidence_status} /></Descriptions.Item>
              <Descriptions.Item label="实际权重产物"><code className="full-hash">{d.actual_weight_artifact_sha256}</code></Descriptions.Item>
              <Descriptions.Item label="信号哈希"><code className="full-hash">{d.signal_sha256}</code></Descriptions.Item>
            </Descriptions>
            <div className="contract-gap-note">
              暂无可审计的因子贡献分解；不展示 AI 置信度或前端推断。
            </div>
          </>
        ) : null}
      </Drawer>
    </div>
  );
}

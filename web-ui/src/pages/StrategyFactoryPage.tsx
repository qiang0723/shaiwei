import {
  ApartmentOutlined,
  ExperimentOutlined,
  SafetyCertificateOutlined,
  StopOutlined,
  ThunderboltOutlined
} from "@ant-design/icons";
import { Alert } from "antd";
import { useQuery } from "@tanstack/react-query";
import { MetricCard } from "../components/MetricCard";
import { PageHeader } from "../components/PageHeader";
import { PageError, PageLoading, RefreshNotice } from "../components/RequestState";
import { fetchStrategyFactory } from "../strategyFactoryApi";
import type { EvidencePayload } from "../types";
import {
  ProgramCatalog,
  ResearchMatrix,
  UniverseMap
} from "./strategy-factory/presentation";
import { ProposalWorkbench } from "./strategy-factory/ProposalWorkbench";

export default function StrategyFactoryPage() {
  const query = useQuery({
    queryKey: ["strategy-factory", "frozen-current"],
    queryFn: ({ signal }) => fetchStrategyFactory(signal),
    placeholderData: (previous) => previous
  });

  if (query.isPending) return <PageLoading label="正在核验多股票池研究证据…" />;
  if (query.isError) return <PageError error={query.error} retry={() => query.refetch()} />;

  const envelope = query.data;
  const data = envelope.data;
  const summary = data.summary;
  const evidence: EvidencePayload = {
    title: "多股票池策略工厂原子快照",
    snapshotId: envelope.meta.snapshot_id,
    asOf: envelope.meta.as_of,
    generatedAt: envelope.meta.generated_at,
    hashes: envelope.meta.evidence_hashes,
    sources: envelope.meta.source_refs,
    facts: [
      { label: "登记股票池", value: String(summary.registered_universe_count) },
      { label: "可建立草案", value: String(summary.research_eligible_universe_count) },
      { label: "正式因子准入", value: String(summary.admitted_factor_count) },
      { label: "活跃授权任务", value: String(summary.active_authorized_task_count) }
    ],
    technicalFacts: [
      { label: "查询边界", value: "GET/HEAD only" },
      { label: "真实研究运行", value: String(data.invariants.real_research_runs) },
      { label: "外部调用", value: String(data.invariants.external_calls_made) },
      { label: "北交所计数", value: String(data.invariants.bse_count) }
    ]
  };

  return (
    <div className="page-stack factory-page">
      <PageHeader
        eyebrow="MULTI-UNIVERSE RESEARCH FACTORY"
        title="策略工厂"
        description="把股票池、研究家族、尝试次数和权威裁决放进同一证据链；草案不等于执行。"
        status="WARN"
        asOf={envelope.meta.as_of}
        generatedAt={envelope.meta.generated_at}
        evidence={evidence}
        asOfLabel="证据冻结"
        generatedAtLabel="投影生成"
      />
      {query.isFetching ? <RefreshNotice asOf={envelope.meta.as_of} generatedAt={envelope.meta.generated_at} /> : null}

      <section className="factory-command" aria-labelledby="factory-decision">
        <div>
          <span className="section-kicker">CURRENT DECISION</span>
          <h2 id="factory-decision">5个股票池可以继续研究，但当前没有新策略获准执行</h2>
          <p>正式因子库仍为0。已有拒绝、合同停止和数据阻断不是无效产出，而是下一批研究必须继承的边界。</p>
        </div>
        <div className="factory-command-state">
          <span>当前行动</span>
          <strong>只建立有界草案</strong>
          <small>未提交 · 未冻结 · 未运行</small>
        </div>
      </section>

      <div className="metric-grid five-up factory-metrics">
        <MetricCard label="可研究股票池" value={`${summary.research_eligible_universe_count} / ${summary.registered_universe_count}`} detail="具备数据与PIT条件" icon={<ApartmentOutlined />} />
        <MetricCard label="数据/PIT阻断" value={summary.blocked_universe_count} detail="不可绕过建立因子任务" tone="warning" icon={<StopOutlined />} />
        <MetricCard label="正式因子准入" value={summary.admitted_factor_count} detail={`${summary.factor_admission_decision_count}条裁决已核验`} tone="warning" icon={<SafetyCertificateOutlined />} />
        <MetricCard label="既有生产策略" value={summary.existing_production_strategy_count} detail="仍仅中证800主策略" icon={<ThunderboltOutlined />} />
        <MetricCard label="活跃授权任务" value={summary.active_authorized_task_count} detail="本轮没有真实研究执行" icon={<ExperimentOutlined />} />
      </div>

      <Alert
        className="factory-alert"
        type="warning"
        showIcon
        message={`${summary.authoritative_reject_program_count}个工作包权威拒绝，${summary.stopped_contract_program_count}个批次因审查合同停止`}
        description="拒绝不代表股票池无效；合同停止也不代表候选效果失败。两类坏消息均保留，并禁止同批补发或调门槛。"
      />

      <section className="surface-panel factory-section" aria-labelledby="universe-map-heading">
        <div className="section-heading">
          <div>
            <span className="section-kicker">UNIVERSE MAP</span>
            <h2 id="universe-map-heading">股票池研究地图</h2>
          </div>
          <span className="section-note">默认按权威目录顺序，不按表现排序</span>
        </div>
        <UniverseMap universes={data.universes} />
      </section>

      <section className="surface-panel factory-section" aria-labelledby="matrix-heading">
        <div className="section-heading">
          <div>
            <span className="section-kicker">POOL × RESEARCH FAMILY</span>
            <h2 id="matrix-heading">股票池 × 研究家族</h2>
          </div>
          <span className="section-note">只显示证据层与裁决，不展示收益热力色</span>
        </div>
        <ResearchMatrix families={data.research_families} universes={data.universes} matrix={data.matrix} />
      </section>

      <section className="factory-section" aria-labelledby="program-heading">
        <div className="section-heading">
          <div>
            <span className="section-kicker">RESEARCH EVIDENCE</span>
            <h2 id="program-heading">已有研究工作包</h2>
          </div>
          <span className="section-note">生成尝试、评价单元、效果读取分开计数</span>
        </div>
        <ProgramCatalog programs={data.programs} universes={data.universes} />
      </section>

      <section className="surface-panel factory-section" aria-labelledby="draft-heading">
        <div className="section-heading">
          <div>
            <span className="section-kicker">LOCAL PROPOSAL CONTROL</span>
            <h2 id="draft-heading">非权威提案工作台</h2>
          </div>
          <span className="factory-readonly-label">本机持久化 · 人工复核止步</span>
        </div>
        <ProposalWorkbench data={data} />
      </section>

      <section className="factory-empty-task" aria-label="当前研究任务">
        <div>
          <span className="section-kicker">AUTHORIZED TASKS</span>
          <h2>当前没有活跃授权任务</h2>
          <p>页面可规划研究，但不会自动创建下一批、消费DeepSeek额度或打开封存效果。</p>
        </div>
        <SafetyCertificateOutlined aria-hidden="true" />
      </section>
    </div>
  );
}

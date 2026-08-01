import {
  CheckCircleFilled,
  CloseCircleFilled,
  HistoryOutlined,
  InfoCircleFilled,
  SafetyCertificateFilled,
  WarningFilled
} from "@ant-design/icons";
import { Alert, Tag } from "antd";
import { formatNumber, formatPercent } from "../../format";
import type {
  ApiMeta,
  EvidencePayload,
  ExperimentAuthorityStatus,
  ExperimentEvidenceTier,
  ExperimentKind,
  ExperimentLifecycleStatus,
  ExperimentOutcome,
  JsonMetric
} from "../../types";

export const KIND_LABELS: Record<ExperimentKind, string> = {
  research_experiment: "研究实验",
  p2_engineering_run: "P2 工程运行",
  p2_effect_original: "P2 原效果（失效）",
  p2_effect_correction: "P2 权威纠错"
};

export function researchFamilyLabel(value: string) {
  if (value === "p1-moneyflow-v1") return "资金流研究";
  if (value === "stage1-gp-preflight-v1") return "GP 预检研究";
  if (value.includes("star50") || value.includes("p2")) return "科创50研究";
  if (value.includes("d1") || value.includes("llm")) return "LLM 发现研究";
  return "其他研究记录";
}

export const TIER_LABELS: Record<ExperimentEvidenceTier, string> = {
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

export const AUTHORITY_LABELS: Record<ExperimentAuthorityStatus, string> = {
  AUTHORITATIVE_CURRENT: "当前权威",
  AUTHORITATIVE_STOP: "权威停止",
  DISCOVERY_ONLY: "仅发现层",
  HISTORICAL_NON_AUTHORITATIVE: "历史非权威",
  INVALIDATED_METHOD: "方法已失效",
  PROVISIONAL_HISTORICAL: "历史暂定",
  RECORDED_EXPERIMENT: "仅登记实验",
  SUPERSEDED_ENGINEERING_GENERATION: "被替代工程代"
};

export const EVIDENCE_STATUS_LABELS = {
  VERIFIED: "已核验",
  LEDGER_RECORDED_PROVISIONAL: "账本已登记，证据暂定"
} as const;

const MACHINE_VALUE_LABELS: Record<string, string> = {
  PASS: "通过",
  FAIL: "失败",
  FAILED: "失败",
  REJECT: "拒绝",
  REJECTED: "拒绝",
  ADMITTED: "已准入",
  NOT_READY: "未就绪",
  NOT_EVALUATED: "未评估",
  NOT_APPLICABLE: "不适用",
  NO_GO: "不通过",
  GO: "通过"
};

export const LIFECYCLE_LABELS: Record<ExperimentLifecycleStatus, string> = {
  COMPLETED: "已完成记录",
  DISCOVERY_ATTEMPT: "发现尝试",
  DISCOVERY_EVALUATED: "发现期已评估",
  ENGINEERING_GO_ONLY: "仅工程通过",
  FAILED: "执行失败",
  REJECT: "发现层拒绝",
  REJECTED: "研究拒绝",
  REVIEW_STOPPED: "复核停止"
};

export const OUTCOME_COPY: Record<ExperimentOutcome, {
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
    description: "已有 G1 拒绝结论；这是研究结果，不是系统故障。",
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
    label: "仅工程通过",
    description: "只证明数据与工程通路，不代表策略有效。",
    tone: "neutral"
  },
  HISTORICAL_EFFECT_REJECTED: {
    label: "历史效果拒绝",
    description: "当前权威历史效果结论为拒绝，且没有生产授权。",
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

export function decisionLabel(key: string) {
  return DECISION_LABELS[key] ?? key.replaceAll("_", " ");
}

function outcomeIcon(outcome: ExperimentOutcome) {
  const tone = OUTCOME_COPY[outcome].tone;
  if (tone === "positive") return <CheckCircleFilled />;
  if (tone === "negative") return <CloseCircleFilled />;
  if (tone === "warning") return <WarningFilled />;
  return <InfoCircleFilled />;
}

export function OutcomeBadge({ outcome, showMachineCode = false }: { outcome: ExperimentOutcome; showMachineCode?: boolean }) {
  const copy = OUTCOME_COPY[outcome];
  return (
    <Tag
      className={`experiment-outcome experiment-outcome-${copy.tone}`}
      icon={outcomeIcon(outcome)}
      title={`${copy.label} · ${outcome}`}
      aria-label={`${copy.label}，机器状态 ${outcome}`}
    >
      {copy.label}{showMachineCode ? ` · ${outcome}` : ""}
    </Tag>
  );
}

export function AuthorityBadge({
  authority,
  showMachineCode = false
}: {
  authority: ExperimentAuthorityStatus;
  showMachineCode?: boolean;
}) {
  const current = authority === "AUTHORITATIVE_CURRENT" || authority === "AUTHORITATIVE_STOP";
  return (
    <Tag
      className={`experiment-authority experiment-authority-${current ? "current" : "historical"}`}
      icon={current ? <SafetyCertificateFilled /> : <HistoryOutlined />}
      title={`${AUTHORITY_LABELS[authority]} · ${authority}`}
      aria-label={`${AUTHORITY_LABELS[authority]}，机器状态 ${authority}`}
    >
      {AUTHORITY_LABELS[authority]}{showMachineCode ? ` · ${authority}` : ""}
    </Tag>
  );
}

export function HistoricalBanner({ visible }: { visible: boolean }) {
  if (!visible) return null;
  return (
    <Alert
      className="experiment-history-banner"
      type="warning"
      showIcon
      message="历史记录已应用当前权威覆盖"
      description="记录按查询截止日期裁剪，但权威解释使用当前已知纠错；这是按当前知识回看，不是重演当时状态。"
    />
  );
}

export function experimentEvidence(
  title: string,
  meta: ApiMeta,
  options: {
    hashes?: Record<string, string>;
    sources?: string[];
    facts?: Array<{ label: string; value: string }>;
    technicalFacts?: Array<{ label: string; value: string }>;
  } = {}
): EvidencePayload {
  return {
    title,
    snapshotId: meta.snapshot_id,
    asOf: meta.as_of,
    generatedAt: meta.generated_at,
    hashes: { ...meta.evidence_hashes, ...options.hashes },
    sources: options.sources ?? meta.source_refs,
    facts: options.facts,
    technicalFacts: options.technicalFacts
  };
}

export function experimentHeaderProps(meta: ApiMeta) {
  return {
    asOf: meta.as_of,
    generatedAt: meta.generated_at,
    asOfLabel: "查询截止",
    generatedAtLabel: "研究投影生成"
  };
}

export function experimentPath(kind: ExperimentKind, experimentId: string, search = "") {
  return `/experiments/${kind}/${encodeURIComponent(experimentId)}${search}`;
}

function formatDecisionNumber(value: number, key: string) {
  if (/net_excess|drawdown/.test(key)) return formatPercent(value, { signed: /net_excess/.test(key) });
  if (/rank_ic/.test(key)) return formatNumber(value, 4);
  return formatNumber(value, Number.isInteger(value) ? 0 : 3);
}

export function DecisionValue({ value, metric }: { value: JsonMetric; metric: string }) {
  if (value === null) return <span className="muted">未登记</span>;
  if (typeof value === "boolean") return <span>{value ? "是" : "否"}</span>;
  if (typeof value === "number") return <span>{formatDecisionNumber(value, metric)}</span>;
  if (typeof value === "string") {
    if (/sha|hash|identity|_id$|version/.test(metric) || value.length >= 32 && /^[0-9a-f]+$/.test(value)) {
      return <span title={value}>已登记，技术标识可查</span>;
    }
    if (MACHINE_VALUE_LABELS[value]) return <span title={value}>{MACHINE_VALUE_LABELS[value]}</span>;
    if (/^[A-Z][A-Z0-9_]+$/.test(value)) return <span title={value}>已登记技术状态</span>;
    return <span>{value}</span>;
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

export function metricObject(value: JsonMetric | undefined): Record<string, JsonMetric> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return {};
  return value;
}

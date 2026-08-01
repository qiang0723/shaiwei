import {
  CheckCircleFilled,
  CloseCircleFilled,
  FileSearchOutlined,
  HistoryOutlined,
  SafetyCertificateFilled
} from "@ant-design/icons";
import { Alert, Tag } from "antd";
import { formatNumber, formatPercent } from "../../format";
import { RouterLink } from "../../routing";
import type {
  ApiMeta,
  EvidencePayload,
  FactorAuthorityStatus,
  FactorLifecycleStatus,
  JsonMetric
} from "../../types";

export const VERSION = /^[0-9a-f]{12}$/;
export const WINDOWS = ["W1", "W2", "W3", "W4", "W5", "W6"] as const;

const RESEARCH_FAMILY_LABELS: Record<string, string> = {
  "p1-moneyflow-v1": "资金流研究",
  "stage1-gp-preflight-v1": "GP 预检研究"
};

const DATA_CATEGORY_LABELS: Record<string, string> = {
  moneyflow: "资金流数据",
  price_volume: "量价数据"
};

export function researchFamilyLabel(value: string) {
  return RESEARCH_FAMILY_LABELS[value] ?? "其他研究家族";
}

export function dataCategoryLabel(value: string) {
  return DATA_CATEGORY_LABELS[value] ?? "其他研究数据";
}

export const AUTHORITY_LABELS: Record<FactorAuthorityStatus, string> = {
  AUTHORITATIVE_CURRENT: "当前权威",
  HISTORICAL_NON_AUTHORITATIVE: "历史非权威",
  SUPERSEDED_ENGINEERING_GENERATION: "被替代工程版本",
  INVALIDATED: "已失效"
};

export const LIFECYCLE_LABELS: Record<FactorLifecycleStatus, string> = {
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

export function AuthorityBadge({ authority }: { authority: FactorAuthorityStatus }) {
  const current = authority === "AUTHORITATIVE_CURRENT";
  return (
    <Tag
      className={`factor-authority factor-authority-${current ? "current" : "historical"}`}
      icon={current ? <SafetyCertificateFilled /> : <HistoryOutlined />}
      title={`${AUTHORITY_LABELS[authority]} · ${authority}`}
      aria-label={`${AUTHORITY_LABELS[authority]}，机器状态 ${authority}`}
    >
      {AUTHORITY_LABELS[authority]}
    </Tag>
  );
}

export function DecisionBadge({ decision }: { decision: "ADMITTED" | "REJECTED" }) {
  return (
    <Tag
      className={`factor-decision factor-decision-${decision.toLowerCase()}`}
      icon={decision === "ADMITTED" ? <CheckCircleFilled /> : <CloseCircleFilled />}
      title={`${decision === "ADMITTED" ? "已准入" : "未准入"} · ${decision}`}
      aria-label={`${decision === "ADMITTED" ? "已准入" : "未准入"}，机器状态 ${decision}`}
    >
      {decision === "ADMITTED" ? "已准入" : "未准入"}
    </Tag>
  );
}

export function HistoricalBanner({ visible }: { visible: boolean }) {
  if (!visible) return null;
  return (
    <Alert
      className="factor-history-banner"
      type="warning"
      showIcon
      message="历史记录已应用当前权威覆盖"
      description="事件按查询截止日期裁剪，但权威解释使用当前已知纠错；这是按当前知识回看，不是重演当时的权威状态。"
    />
  );
}

export function researchEvidence(
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

export function researchHeaderProps(meta: ApiMeta) {
  return {
    asOf: meta.as_of,
    generatedAt: meta.generated_at,
    asOfLabel: "查询截止",
    generatedAtLabel: "研究投影生成"
  };
}

export function factorPath(factorId: string, options: { version?: string; asOf?: string } = {}) {
  const search = new URLSearchParams();
  if (options.version) search.set("version", options.version);
  if (options.asOf) search.set("as_of", options.asOf);
  return `/factors/${factorId}${search.size ? `?${search.toString()}` : ""}`;
}

export function admissionsPath(factorId: string, asOf?: string) {
  return `/factors/${factorId}/admissions${asOf ? `?as_of=${encodeURIComponent(asOf)}` : ""}`;
}

export function comparePath(versions: string[]) {
  const search = new URLSearchParams();
  versions.forEach((version) => search.append("version", version));
  return `/factors/compare?${search.toString()}`;
}

export function metricLabel(key: string) {
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

export function MetricActual({ value, metric }: { value: JsonMetric; metric: string }) {
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

export function FactorTabs({
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

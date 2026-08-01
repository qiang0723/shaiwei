import { SafetyCertificateFilled } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { Button, Empty, Select, Tag } from "antd";
import { useMemo } from "react";
import { fetchExperimentCatalog } from "../../api";
import { useAsOf } from "../../components/AppShell";
import { DataTable, type DataColumn } from "../../components/DataTable";
import { MetricCard } from "../../components/MetricCard";
import { PageHeader } from "../../components/PageHeader";
import { PageError, PageLoading, RefreshNotice } from "../../components/RequestState";
import { formatDateTime } from "../../format";
import { RouterLink, useRouter } from "../../routing";
import type {
  ExperimentAuthorityStatus,
  ExperimentCatalogItem,
  ExperimentEvidenceTier,
  ExperimentKind,
  ExperimentLifecycleStatus,
  ExperimentOutcome
} from "../../types";
import {
  AUTHORITY_LABELS,
  AuthorityBadge,
  EVIDENCE_STATUS_LABELS,
  HistoricalBanner,
  KIND_LABELS,
  LIFECYCLE_LABELS,
  OUTCOME_COPY,
  OutcomeBadge,
  TIER_LABELS,
  experimentEvidence,
  experimentHeaderProps,
  experimentPath,
  researchFamilyLabel
} from "./presentation";

const FILTER_KEYS = [
  "experiment_kind",
  "research_family",
  "evidence_tier",
  "authority_status",
  "lifecycle_status",
  "outcome_status",
  "evidence_status"
] as const;

export function CatalogPage() {
  const { asOf } = useAsOf();
  const { location, navigate } = useRouter();
  const parameters = useMemo(() => new URLSearchParams(location.search), [location.search]);
  const rawOffset = parameters.get("offset") ?? "0";
  const offset = /^\d+$/.test(rawOffset) ? Number(rawOffset) : Number.NaN;
  const filters = Object.fromEntries(
    FILTER_KEYS.map((key) => [key, parameters.get(key) || undefined])
  ) as Record<(typeof FILTER_KEYS)[number], string | undefined>;

  const query = useQuery({
    queryKey: ["experiment-catalog", asOf || "latest", ...FILTER_KEYS.map((key) => filters[key] ?? "ALL"), rawOffset],
    queryFn: ({ signal }) => fetchExperimentCatalog({
      experimentKind: filters.experiment_kind,
      researchFamily: filters.research_family,
      evidenceTier: filters.evidence_tier,
      authorityStatus: filters.authority_status,
      lifecycleStatus: filters.lifecycle_status,
      outcomeStatus: filters.outcome_status,
      evidenceStatus: filters.evidence_status,
      asOf,
      offset
    }, signal)
  });

  if (query.isPending) return <PageLoading label="正在核对实验目录、权威覆盖与分页身份…" />;
  if (query.isError) return <PageError error={query.error} retry={() => query.refetch()} />;

  const { data, meta } = query.data;
  const setFilter = (key: (typeof FILTER_KEYS)[number], value: string) => {
    const next = new URLSearchParams(location.search);
    if (value === "ALL") next.delete(key);
    else next.set(key, value);
    next.delete("offset");
    navigate(`/experiments${next.size ? `?${next.toString()}` : ""}`);
  };
  const setOffset = (value: number | null) => {
    if (value === null) return;
    const next = new URLSearchParams(location.search);
    if (value === 0) next.delete("offset");
    else next.set("offset", String(value));
    navigate(`/experiments${next.size ? `?${next.toString()}` : ""}`);
  };
  const search = location.search;
  const humanExperimentLabel = (index: number) => `实验 ${data.page.offset + index + 1}`;
  const columns: DataColumn<ExperimentCatalogItem>[] = [
    {
      title: "实验",
      dataIndex: "experiment_id",
      key: "experiment_id",
      fixed: "left",
      width: 190,
      render: (value: string, item, index) => (
        <RouterLink
          className="table-factor-link"
          title={`技术标识：${value}`}
          aria-label={`查看${humanExperimentLabel(index)}的类型化证据，技术标识 ${value}`}
          to={experimentPath(item.experiment_kind, value, search)}
        >
          {humanExperimentLabel(index)}
        </RouterLink>
      )
    },
    {
      title: "结论语义",
      dataIndex: "outcome_status",
      key: "outcome",
      width: 250,
      render: (value: ExperimentOutcome) => <OutcomeBadge outcome={value} />
    },
    {
      title: "权威状态",
      dataIndex: "authority_status",
      key: "authority",
      width: 270,
      render: (value: ExperimentAuthorityStatus) => <AuthorityBadge authority={value} />
    },
    { title: "证据层级", dataIndex: "evidence_tier", key: "tier", width: 230, render: (value: ExperimentEvidenceTier) => TIER_LABELS[value] },
    { title: "研究家族", dataIndex: "research_family", key: "family", width: 230, render: (value: string) => <span title={value}>{researchFamilyLabel(value)}</span> },
    { title: "实验类型", dataIndex: "experiment_kind", key: "kind", width: 180, render: (value: ExperimentKind) => KIND_LABELS[value] },
    { title: "失败项", dataIndex: "failed_reason_count", key: "failures", align: "right", width: 80 },
    { title: "记录时间", dataIndex: "recorded_at", key: "recorded", width: 190, render: formatDateTime },
    { title: "证据", dataIndex: "evidence_status", key: "evidence", width: 190, render: (value: keyof typeof EVIDENCE_STATUS_LABELS) => EVIDENCE_STATUS_LABELS[value] }
  ];
  const pageNumber = Math.floor(data.page.offset / data.page.limit) + 1;
  const pageCount = Math.max(1, Math.ceil(data.counters.filtered_count / data.page.limit));
  const evidence = experimentEvidence("实验目录证据", meta, {
    facts: [
      { label: "投影记录", value: String(data.counters.projected_total_count) },
      { label: "历史切片", value: String(data.counters.as_of_count) },
      { label: "筛选后", value: String(data.counters.filtered_count) },
      { label: "按表现排序", value: data.sorted_by_performance ? "是" : "否" }
    ],
    technicalFacts: [
      { label: "目录协议", value: data.catalog_protocol_id },
      { label: "固定排序字段", value: data.sort.join(" → ") }
    ]
  });

  const filterSpecs: Array<{
    key: (typeof FILTER_KEYS)[number];
    label: string;
    values: string[];
    valueLabel?: (value: string) => string;
  }> = [
    { key: "outcome_status", label: "结论语义筛选", values: data.available_filters.outcome_status, valueLabel: (value) => OUTCOME_COPY[value as ExperimentOutcome].label },
    { key: "authority_status", label: "权威状态筛选", values: data.available_filters.authority_status, valueLabel: (value) => AUTHORITY_LABELS[value as ExperimentAuthorityStatus] },
    { key: "evidence_tier", label: "证据层级筛选", values: data.available_filters.evidence_tier, valueLabel: (value) => TIER_LABELS[value as ExperimentEvidenceTier] },
    { key: "research_family", label: "研究家族筛选", values: data.available_filters.research_family, valueLabel: (value) => `研究家族 ${data.available_filters.research_family.indexOf(value) + 1}` },
    { key: "experiment_kind", label: "实验类型筛选", values: data.available_filters.experiment_kind, valueLabel: (value) => KIND_LABELS[value as ExperimentKind] },
    { key: "lifecycle_status", label: "生命周期筛选", values: data.available_filters.lifecycle_status, valueLabel: (value) => LIFECYCLE_LABELS[value as ExperimentLifecycleStatus] },
    { key: "evidence_status", label: "证据状态筛选", values: data.available_filters.evidence_status, valueLabel: (value) => EVIDENCE_STATUS_LABELS[value as keyof typeof EVIDENCE_STATUS_LABELS] }
  ];

  return (
    <div className="page-stack experiment-page">
      <PageHeader
        eyebrow="MODEL / BACKTEST EVIDENCE"
        title="研究证据"
        description="运行、发现、判决、工程与历史效果分层；一条记录不等于一个有效模型。"
        status={meta.freshness_status}
        evidence={evidence}
        {...experimentHeaderProps(meta)}
      />
      {query.isFetching ? <RefreshNotice asOf={meta.as_of} generatedAt={meta.generated_at} /> : null}
      <HistoricalBanner visible={Boolean(data.historical_response_banner)} />

      <section className="experiment-scope-hero" aria-labelledby="experiment-scope-heading">
        <div>
          <span className="section-kicker">EVIDENCE SCOPE</span>
          <h2 id="experiment-scope-heading">
            {data.counters.projected_total_count} 条实验记录，不是 {data.counters.projected_total_count} 个有效模型
          </h2>
          <p>先看证据层级与权威状态，再看已登记结果；页面不提供成功率、收益排名或“最佳策略”。</p>
        </div>
        <Tag icon={<SafetyCertificateFilled />}>只读 · 不做排名</Tag>
      </section>

      <section className="metric-grid experiment-kind-grid" aria-label="实验记录类型计数">
        <MetricCard label="通用研究实验" value={data.counters.kind_counts.research_experiment} detail="含基线、影子、GP、G1 与 D1" />
        <MetricCard label="P2 工程运行" value={data.counters.kind_counts.p2_engineering_run} detail="只证明工程通路" />
        <MetricCard label="P2 失效方法" value={data.counters.kind_counts.p2_effect_original} detail="旧数值非权威" tone="warning" />
        <MetricCard label="P2 权威纠错" value={data.counters.kind_counts.p2_effect_correction} detail="当前历史效果裁决" tone="warning" />
      </section>

      <section className="table-surface" aria-labelledby="experiment-catalog-heading">
        <div className="section-heading experiment-catalog-heading">
          <div>
            <span className="section-kicker">CATALOG · BACKEND PAGINATED</span>
            <h2 id="experiment-catalog-heading">实验目录</h2>
            <p>历史切片 {data.counters.as_of_count} 条 · 筛选后 {data.counters.filtered_count} 条 · 当前第 {pageNumber}/{pageCount} 页</p>
          </div>
        </div>
        <details className="filter-disclosure">
          <summary>精确筛选 · 7 项</summary>
          <div className="experiment-filters" aria-label="实验目录筛选">
            {filterSpecs.map((spec) => (
              <Select
                key={spec.key}
                aria-label={spec.label}
                value={filters[spec.key] ?? "ALL"}
                onChange={(value) => setFilter(spec.key, value)}
                options={[
                  { value: "ALL", label: spec.label.replace("筛选", "：全部") },
                  ...spec.values.map((value) => ({ value, label: spec.valueLabel ? spec.valueLabel(value) : value, title: value }))
                ]}
              />
            ))}
          </div>
        </details>

        <div className="experiment-desktop-catalog">
          <DataTable
            label="实验目录"
            columns={columns}
            data={data.items}
            rowKey={(item) => `${item.experiment_kind}|${item.experiment_id}`}
            minimumWidth="wide"
            emptyText="当前精确筛选没有实验记录"
          />
        </div>
        <div className="experiment-mobile-cards" role="table" aria-label="移动端实验目录">
          <div className="experiment-mobile-header" role="row">
            <span role="columnheader">实验</span>
            <span role="columnheader">结论</span>
            <span role="columnheader">权威状态</span>
          </div>
          {data.items.map((item, index) => (
            <article
              key={`${item.experiment_kind}|${item.experiment_id}`}
              className="experiment-catalog-card"
              role="row"
            >
              <div className="experiment-mobile-id" role="cell">
                <RouterLink
                  to={experimentPath(item.experiment_kind, item.experiment_id, search)}
                  title={`技术标识：${item.experiment_id}`}
                  aria-label={`查看${humanExperimentLabel(index)}的类型化证据，技术标识 ${item.experiment_id}`}
                >
                  <span className="experiment-human-id">{humanExperimentLabel(index)}</span>
                </RouterLink>
                <small>{KIND_LABELS[item.experiment_kind]}</small>
              </div>
              <div className="experiment-mobile-status" role="cell">
                <OutcomeBadge outcome={item.outcome_status} showMachineCode={false} />
              </div>
              <div className="experiment-mobile-status" role="cell">
                <AuthorityBadge authority={item.authority_status} showMachineCode={false} />
              </div>
            </article>
          ))}
          {!data.items.length ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前精确筛选没有实验记录" /> : null}
        </div>
        <div className="experiment-pagination" aria-label="实验目录分页">
          <Button disabled={!data.page.has_previous} onClick={() => setOffset(data.page.previous_offset)}>上一页</Button>
          <span>第 {pageNumber} / {pageCount} 页 · 每页 {data.page.limit} 条</span>
          <Button disabled={!data.page.has_more} onClick={() => setOffset(data.page.next_offset)}>下一页</Button>
        </div>
      </section>
      <p className="page-evidence-footer">目录每次只读取一个后台分页响应；不批量拉取详情，不按结果重排，不跨快照拼页。</p>
    </div>
  );
}

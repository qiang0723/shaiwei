import { ArrowLeftOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { fetchFactorAdmissionHistory } from "../../api";
import { useAsOf } from "../../components/AppShell";
import { DataTable, type DataColumn } from "../../components/DataTable";
import { PageHeader } from "../../components/PageHeader";
import { PageError, PageLoading, RefreshNotice } from "../../components/RequestState";
import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime } from "../../format";
import { RouterLink } from "../../routing";
import type { FactorAdmissionItem, FactorAuthorityStatus } from "../../types";
import {
  AuthorityBadge,
  DecisionBadge,
  FactorTabs,
  HistoricalBanner,
  factorPath,
  metricLabel,
  researchEvidence,
  researchHeaderProps
} from "./presentation";

export function AdmissionsPage({ factorId }: { factorId: string }) {
  const { asOf } = useAsOf();
  const query = useQuery({
    queryKey: ["factor-admissions", factorId, asOf || "latest"],
    queryFn: ({ signal }) => fetchFactorAdmissionHistory(factorId, asOf, signal),
    placeholderData: (previous) => previous
  });
  if (query.isPending) return <PageLoading label="正在核对追加式因子准入历史…" />;
  if (query.isError) return <PageError error={query.error} retry={() => query.refetch()} />;
  const { data, meta } = query.data;
  const hashes = Object.fromEntries(data.items.flatMap((item, index) => [
    [`decision_${index + 1}_report`, item.report_sha256],
    [`decision_${index + 1}_evidence`, item.evidence_sha256]
  ]));
  const evidence = researchEvidence("因子准入历史证据", meta, {
    hashes,
    facts: [
      { label: "追加式记录", value: String(data.items.length) },
      { label: "是否只追加", value: data.append_only ? "是" : "否" }
    ],
    technicalFacts: [
      { label: "因子 ID", value: factorId },
      ...data.items.flatMap((item, index) => [
        { label: `记录 ${index + 1} 因子版本`, value: item.factor_version },
        { label: `记录 ${index + 1} 规则版本`, value: item.decision_rule_version }
      ])
    ]
  });
  const columns: DataColumn<FactorAdmissionItem>[] = [
    { title: "记录时间", dataIndex: "recorded_at", key: "recorded_at", width: 178, render: (value: string) => formatDateTime(value) },
    {
      title: "版本",
      dataIndex: "factor_version",
      key: "version",
      width: 132,
      render: (value: string) => <RouterLink className="table-factor-link" title={value} to={factorPath(factorId, { version: value, asOf })}>查看该版本</RouterLink>
    },
    { title: "记录判决", dataIndex: "recorded_decision", key: "decision", width: 142, render: (value: "ADMITTED" | "REJECTED") => <DecisionBadge decision={value} /> },
    { title: "当前权威解释", dataIndex: "authority_status", key: "authority", width: 238, render: (value: FactorAuthorityStatus) => <AuthorityBadge authority={value} /> },
    { title: "研究 N", dataIndex: "trial_count", key: "trials", align: "right", width: 94 },
    { title: "失败门", dataIndex: "failed_gates", key: "failed", width: 280, render: (value: string[]) => value.length ? value.map(metricLabel).join("、") : "无" },
    { title: "规则", dataIndex: "decision_rule_version", key: "rule", width: 132, render: (value: string) => <span title={value}>已锁定</span> },
    { title: "报告", dataIndex: "report_sha256", key: "report", width: 126, render: (value: string) => <span title={value}>已校验</span> },
    { title: "证据", dataIndex: "evidence_sha256", key: "evidence", width: 126, render: (value: string) => <span title={value}>已校验</span> }
  ];
  return (
    <div className="page-stack factor-page">
      <PageHeader
        eyebrow="ADMISSION HISTORY"
        title="旧判决保留，当前权威另列"
        description="准入账本只追加不覆盖；历史版本可回到对应 tear sheet 核对。"
        status={meta.freshness_status}
        evidence={evidence}
        {...researchHeaderProps(meta)}
      />
      {query.isFetching ? <RefreshNotice asOf={meta.as_of} generatedAt={meta.generated_at} /> : null}
      <HistoricalBanner visible={Boolean(data.historical_response_banner)} />
      <RouterLink className="factor-back-link" to={`/factors${asOf ? `?as_of=${encodeURIComponent(asOf)}` : ""}`}><ArrowLeftOutlined /> 返回因子目录</RouterLink>
      <FactorTabs factorId={factorId} active="admissions" asOf={asOf} />
      <section className="factor-library-hero append-only-hero">
        <div><span className="section-kicker">APPEND ONLY</span><h2>{data.items.length} 条准入判决，旧记录从未覆盖</h2><p title={factorId}>记录判决与当前权威解释分列，完整因子标识见技术证据。</p></div>
        <StatusBadge status="PASS" />
      </section>
      <section className="table-surface" aria-labelledby="admission-table-heading">
        <div className="section-heading"><div><span className="section-kicker">LEDGER ORDER</span><h2 id="admission-table-heading">准入历史</h2></div><span className="section-note">按记录时间升序</span></div>
        <DataTable label="因子准入历史" columns={columns} data={data.items} rowKey="decision_id" minimumWidth="wide" />
      </section>
      <p className="page-evidence-footer">历史行不因后续纠错而删除；“当前权威解释”说明现在如何理解该记录，不改写原始判决。</p>
    </div>
  );
}

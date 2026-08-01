import { SwapOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Checkbox, Empty, Select } from "antd";
import { useEffect, useMemo, useState } from "react";
import { fetchFactorCatalog } from "../../api";
import { useAsOf } from "../../components/AppShell";
import { DataTable, type DataColumn } from "../../components/DataTable";
import { MetricCard } from "../../components/MetricCard";
import { PageHeader } from "../../components/PageHeader";
import { PageError, PageLoading, RefreshNotice } from "../../components/RequestState";
import { StatusBadge } from "../../components/StatusBadge";
import { RouterLink, useRouter } from "../../routing";
import type { FactorAuthorityStatus, FactorCatalogItem } from "../../types";
import {
  AuthorityBadge,
  DecisionBadge,
  HistoricalBanner,
  LIFECYCLE_LABELS,
  comparePath,
  dataCategoryLabel,
  factorPath,
  researchEvidence,
  researchFamilyLabel,
  researchHeaderProps
} from "./presentation";

export function CatalogPage() {
  const { asOf } = useAsOf();
  const { location, navigate } = useRouter();
  const parameters = useMemo(() => new URLSearchParams(location.search), [location.search]);
  const requestedStatus = parameters.get("status") ?? "ALL";
  const status = (["ALL", "ADMITTED", "REJECTED", "HISTORICAL_ONLY"] as const).includes(
    requestedStatus as "ALL"
  ) ? requestedStatus as "ALL" | "ADMITTED" | "REJECTED" | "HISTORICAL_ONLY" : "ALL";
  const family = parameters.get("family") ?? "ALL";
  const dataCategory = parameters.get("data_category") ?? "ALL";
  const [selected, setSelected] = useState<string[]>([]);
  useEffect(() => setSelected([]), [asOf]);

  const query = useQuery({
    queryKey: ["factor-catalog", asOf || "latest"],
    queryFn: ({ signal }) => fetchFactorCatalog({ status: "ALL", asOf }, signal),
    placeholderData: (previous) => previous
  });

  if (query.isPending) return <PageLoading label="正在核对因子目录与当前权威覆盖…" />;
  if (query.isError) return <PageError error={query.error} retry={() => query.refetch()} />;

  const { data, meta } = query.data;
  const families = [...new Set(data.items.map((item) => item.research_family))].sort();
  const categories = [...new Set(data.items.map((item) => item.data_category))].sort();
  const filtered = data.items.filter((item) => {
    if (status === "ADMITTED" && item.lifecycle_status !== "ADMITTED") return false;
    if (status === "REJECTED" && item.lifecycle_status !== "REJECTED") return false;
    if (status === "HISTORICAL_ONLY" && item.authority_status === "AUTHORITATIVE_CURRENT") return false;
    if (family !== "ALL" && item.research_family !== family) return false;
    if (dataCategory !== "ALL" && item.data_category !== dataCategory) return false;
    return true;
  });
  const selectedItems = data.items.filter((item) =>
    item.current_factor_version ? selected.includes(item.current_factor_version) : false
  );
  const selectedFamily = selectedItems[0]?.research_family;
  const factorLabel = (factorId: string) => `因子 ${data.items.findIndex((item) => item.factor_id === factorId) + 1}`;

  const setFilter = (key: "status" | "family" | "data_category", value: string) => {
    const next = new URLSearchParams(location.search);
    if (value === "ALL") next.delete(key);
    else next.set(key, value);
    navigate(`/factors${next.size ? `?${next.toString()}` : ""}`);
  };

  const toggleCompare = (item: FactorCatalogItem, checked: boolean) => {
    const version = item.current_factor_version;
    if (!version || asOf) return;
    setSelected((current) => checked ? [...current, version] : current.filter((value) => value !== version));
  };

  const columns: DataColumn<FactorCatalogItem>[] = [
    {
      title: "比较",
      key: "compare",
      width: 68,
      render: (_value, item) => {
        const version = item.current_factor_version;
        const disabled = !version || Boolean(asOf) || selected.length >= 3 && !selected.includes(version) ||
          Boolean(selectedFamily && selectedFamily !== item.research_family);
        return (
          <Checkbox
            checked={Boolean(version && selected.includes(version))}
            disabled={disabled}
            aria-label={`选择${factorLabel(item.factor_id)} 进行比较`}
            onChange={(event) => toggleCompare(item, event.target.checked)}
          />
        );
      }
    },
    {
      title: "因子",
      dataIndex: "factor_id",
      key: "factor_id",
      fixed: "left",
      width: 132,
      render: (value: string, item) => (
        <RouterLink
          className="table-factor-link"
          title={value}
          to={factorPath(value, { version: item.current_factor_version ?? undefined, asOf })}
        >
          {factorLabel(value)}
        </RouterLink>
      )
    },
    { title: "研究家族", dataIndex: "research_family", key: "family", width: 190, render: (value: string) => <span title={value}>{researchFamilyLabel(value)}</span> },
    { title: "数据类别", dataIndex: "data_category", key: "category", width: 128, render: (value: string) => <span title={value}>{dataCategoryLabel(value)}</span> },
    {
      title: "研究结论",
      dataIndex: "latest_recorded_decision",
      key: "decision",
      width: 142,
      render: (value: "ADMITTED" | "REJECTED") => <DecisionBadge decision={value} />
    },
    {
      title: "权威状态",
      dataIndex: "authority_status",
      key: "authority",
      width: 238,
      render: (value: FactorAuthorityStatus) => <AuthorityBadge authority={value} />
    },
    { title: "版本数", dataIndex: "version_count", key: "versions", align: "right", width: 84 },
    {
      title: "当前版本",
      dataIndex: "current_factor_version",
      key: "current",
      width: 132,
      render: (value: string | null) => value ? <span title={value}>可比较版本</span> : <span className="muted">无当前版本</span>
    },
    { title: "研究尝试 N", dataIndex: "experiment_attempt_n", key: "attempts", align: "right", width: 112 },
    { title: "证据", dataIndex: "evidence_status", key: "evidence", width: 94, render: () => "已核验" }
  ];

  const empty = status === "ADMITTED" ? (
    <div className="factor-empty-inline">
      <strong>正式因子库仍为 0</strong>
      <span>当前没有因子通过全部 G1 门；这是真实研究结论。</span>
      <Button type="link" onClick={() => setFilter("status", "ALL")}>查看全部研究证据</Button>
    </div>
  ) : "当前筛选没有研究因子";

  const evidence = researchEvidence("因子目录证据", meta, {
    facts: [
      { label: "正式库", value: String(data.counters.formal_library_count) },
      { label: "已研究因子", value: String(data.counters.researched_factor_count) },
      { label: "当前权威未准入", value: String(data.counters.authoritative_rejected_count) }
    ],
    technicalFacts: [
      { label: "目录排序字段", value: data.sort.join(" → ") },
      ...data.items.filter((item) => item.current_factor_version).map((item) => ({
        label: `${factorLabel(item.factor_id)} 当前版本`,
        value: item.current_factor_version!
      }))
    ]
  });

  return (
    <div className="page-stack factor-page">
      <PageHeader
        eyebrow="FACTOR FACTORY"
        title="因子工厂"
        description="当前权威准入、未准入与历史证据分列；研究拒绝不是系统运行失败。"
        status="OBSERVING"
        evidence={evidence}
        {...researchHeaderProps(meta)}
      />
      {query.isFetching ? <RefreshNotice asOf={meta.as_of} generatedAt={meta.generated_at} /> : null}
      <HistoricalBanner visible={Boolean(data.historical_response_banner)} />

      <section className="factor-library-hero" aria-labelledby="factor-library-heading">
        <div>
          <span className="section-kicker">G1 · CURRENT AUTHORITY</span>
          <h2 id="factor-library-heading">正式因子库 0：当前没有因子满足全部准入门</h2>
          <p>已有研究证据完整保留，可继续用于方法诊断与下一轮假设设计；不因此推荐上线。</p>
        </div>
        <StatusBadge status="OBSERVING" />
      </section>

      <section className="metric-grid factor-counter-grid" aria-label="因子工厂关键事实">
        <MetricCard label="正式因子库" value={data.counters.formal_library_count} detail="当前权威已准入" />
        <MetricCard label="已研究因子" value={data.counters.researched_factor_count} detail="稳定因子身份，非实验行数" />
        <MetricCard label="当前权威未准入" value={data.counters.authoritative_rejected_count} detail="有证据的研究结论" tone="warning" />
        <MetricCard label="仅历史因子" value={data.counters.historical_only_count} detail="不代表当前权威版本" />
      </section>

      <section className="table-surface" aria-labelledby="factor-catalog-heading">
        <div className="section-heading factor-catalog-heading">
          <div>
            <span className="section-kicker">CATALOG</span>
            <h2 id="factor-catalog-heading">因子目录</h2>
          </div>
          <details className="filter-disclosure">
            <summary>精确筛选 · 3 项</summary>
            <div className="factor-filters" aria-label="因子目录筛选">
            <Select
              aria-label="生命周期筛选"
              value={status}
              onChange={(value) => setFilter("status", value)}
              options={[
                { value: "ALL", label: "全部阶段" },
                { value: "ADMITTED", label: "已准入" },
                { value: "REJECTED", label: "未准入" },
                { value: "HISTORICAL_ONLY", label: "仅历史" }
              ]}
            />
            <Select
              aria-label="研究家族筛选"
              value={family}
              onChange={(value) => setFilter("family", value)}
              options={[{ value: "ALL", label: "全部家族" }, ...families.map((value) => ({ value, label: researchFamilyLabel(value), title: value }))]}
            />
            <Select
              aria-label="数据类别筛选"
              value={dataCategory}
              onChange={(value) => setFilter("data_category", value)}
              options={[{ value: "ALL", label: "全部数据" }, ...categories.map((value) => ({ value, label: dataCategoryLabel(value), title: value }))]}
            />
            </div>
          </details>
        </div>

        {asOf ? (
          <Alert
            type="info"
            showIcon
            message="历史查询不允许因子比较"
            description="比较接口只支持最新当前权威版本。请先切到最新，避免把历史切片与最新权威结果混合。"
            action={<Button type="link" onClick={() => navigate("/factors")}>切到最新</Button>}
          />
        ) : null}

        <div className="factor-desktop-catalog">
          <DataTable
            label="因子目录"
            columns={columns}
            data={filtered}
            rowKey="factor_id"
            minimumWidth="wide"
            emptyText={empty}
          />
        </div>
        <div className="factor-mobile-cards" aria-label="移动端因子目录">
          {filtered.map((item) => (
            <article key={item.factor_id} className="factor-catalog-card">
              <div className="factor-card-heading">
                <RouterLink to={factorPath(item.factor_id, { version: item.current_factor_version ?? undefined, asOf })}>
                  <span title={item.factor_id}>{factorLabel(item.factor_id)}</span>
                </RouterLink>
                <DecisionBadge decision={item.latest_recorded_decision} />
              </div>
              <p title={`${item.research_family} · ${item.data_category}`}>{researchFamilyLabel(item.research_family)} · {dataCategoryLabel(item.data_category)}</p>
              <AuthorityBadge authority={item.authority_status} />
              <dl>
                <div><dt>阶段</dt><dd>{LIFECYCLE_LABELS[item.lifecycle_status]}</dd></div>
                <div><dt>版本</dt><dd>{item.version_count}</dd></div>
                <div><dt>研究 N</dt><dd>{item.experiment_attempt_n}</dd></div>
              </dl>
              <div className="factor-card-actions">
                <RouterLink to={factorPath(item.factor_id, { version: item.current_factor_version ?? undefined, asOf })}>查看证据</RouterLink>
                <Checkbox
                  aria-label={`选择${factorLabel(item.factor_id)} 进行比较`}
                  checked={Boolean(item.current_factor_version && selected.includes(item.current_factor_version))}
                  disabled={!item.current_factor_version || Boolean(asOf) || selected.length >= 3 && !selected.includes(item.current_factor_version) || Boolean(selectedFamily && selectedFamily !== item.research_family)}
                  onChange={(event) => toggleCompare(item, event.target.checked)}
                >比较</Checkbox>
              </div>
            </article>
          ))}
          {!filtered.length ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={empty} /> : null}
        </div>
      </section>

      <section className="factor-compare-tray" aria-live="polite">
        <div>
          <SwapOutlined aria-hidden="true" />
          <span>已选 {selected.length}/3</span>
          {selectedItems.map((item, index) => <span key={item.factor_id} title={item.factor_id}>因子 {index + 1}</span>)}
        </div>
        <Button
          type="primary"
          disabled={Boolean(asOf) || selected.length < 2}
          onClick={() => navigate(comparePath(selected))}
        >
          严格比较所选因子
        </Button>
      </section>
      <p className="page-evidence-footer">目录只发出一次分页读取，不批量拼详情；固定按研究家族和稳定因子标识排序，不按收益或 IC 排名。</p>
    </div>
  );
}

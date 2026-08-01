import { ArrowLeftOutlined, InfoCircleOutlined } from "@ant-design/icons";
import { Column, Line } from "@ant-design/charts";
import { useQuery } from "@tanstack/react-query";
import { Button } from "antd";
import { useMemo } from "react";
import { fetchFactorCompare, UiQueryError } from "../../api";
import { useAsOf } from "../../components/AppShell";
import { PageHeader } from "../../components/PageHeader";
import { PageLoading, RefreshNotice } from "../../components/RequestState";
import { StatusBadge } from "../../components/StatusBadge";
import { formatNumber, formatPercent } from "../../format";
import { RouterLink, useRouter } from "../../routing";
import type { FactorCompareItem } from "../../types";
import {
  VERSION,
  WINDOWS,
  comparePath,
  metricLabel,
  researchEvidence,
  researchHeaderProps
} from "./presentation";

function CompareSetup({ versions, asOf }: { versions: string[]; asOf: string }) {
  const { navigate } = useRouter();
  const historical = Boolean(asOf);
  return (
    <div className="page-stack factor-page">
      <header className="page-header factor-static-header">
        <div><div className="eyebrow">STRICT COMPARISON</div><div className="page-title-line"><h1>{historical ? "历史视图不能比较最新权威因子" : "请选择 2—3 个不同因子版本"}</h1><StatusBadge status="NOT_READY" /></div><p>{historical ? "比较接口没有历史 as_of 口径；先切到最新，避免混合时点。" : "从因子目录选择同一研究家族的当前权威版本。"}</p></div>
      </header>
      <section className="request-error factor-compare-setup" role="alert">
        <InfoCircleOutlined />
        <h2>{historical ? "比较已阻断，未发出请求" : `当前选择 ${versions.length} 个版本`}</h2>
        <div className="factor-version-list">{versions.map((version, index) => <span key={version} title={version}>因子 {index + 1}</span>)}</div>
        <div><Button onClick={() => navigate("/factors")}>返回目录</Button>{historical && versions.length >= 2 && versions.length <= 3 ? <Button type="primary" onClick={() => navigate(comparePath(versions))}>切到最新并比较</Button> : null}</div>
      </section>
    </div>
  );
}

export function ComparePage() {
  const { asOf } = useAsOf();
  const { location, navigate } = useRouter();
  const versions = useMemo(() => new URLSearchParams(location.search).getAll("version"), [location.search]);
  const valid = versions.length >= 2 && versions.length <= 3 && new Set(versions).size === versions.length && versions.every((version) => VERSION.test(version));
  const query = useQuery({
    queryKey: ["factor-compare", ...versions],
    queryFn: ({ signal }) => fetchFactorCompare(versions, signal),
    enabled: valid && !asOf,
    retry: false
  });

  if (asOf || !valid) return <CompareSetup versions={versions} asOf={asOf} />;
  if (query.isPending) return <PageLoading label="正在由后端核对比较口径是否完全一致…" />;

  const remove = (version: string) => {
    const next = versions.filter((item) => item !== version);
    navigate(next.length ? comparePath(next) : "/factors");
  };
  if (query.isError) {
    const error = query.error instanceof UiQueryError ? query.error : new UiQueryError("QUERY_FAILED", "因子比较失败");
    return (
      <div className="page-stack factor-page">
        <header className="page-header factor-static-header"><div><div className="eyebrow">STRICT COMPARISON</div><div className="page-title-line"><h1>所选因子不具备严格可比性</h1><StatusBadge status="NOT_EVALUATED" /></div><p>没有保留旧图，也没有转换口径；请移除一个版本或返回目录。</p></div></header>
        <section className="request-error factor-conflict" role="alert">
          <div className="error-kicker">比较已阻断</div><h2>{error.message}</h2>
          <div className="factor-version-list">{versions.map((version, index) => <span key={version} title={version}>因子 {index + 1}<Button type="link" onClick={() => remove(version)}>移除</Button></span>)}</div>
          <details className="technical-details request-technical-details"><summary>查看技术诊断信息</summary><dl><div><dt>错误码</dt><dd><code>{error.code}</code></dd></div></dl></details>
          <div><Button onClick={() => navigate("/factors")}>返回目录</Button><Button onClick={() => query.refetch()}>重新核对</Button></div>
        </section>
      </div>
    );
  }

  const { data, meta } = query.data;
  const compareLabel = (version: string) => `因子 ${data.factor_versions.indexOf(version) + 1}`;
  const evidence = researchEvidence("因子严格比较证据", meta, {
    facts: [
      { label: "比较版本数", value: String(data.factor_versions.length) },
      { label: "按表现排序", value: data.sorted_by_performance ? "是" : "否" }
    ],
    technicalFacts: [
      ...data.factor_versions.map((value, index) => ({ label: `因子 ${index + 1} 版本`, value })),
      ...Object.entries(data.fingerprint).map(([key, value]) => ({ label: `比较口径：${metricLabel(key)}`, value }))
    ]
  });
  const lineData = data.items.flatMap((item) => WINDOWS.map((window) => ({
    window,
    version: compareLabel(item.factor_version),
    value: item.six_oos_window_rank_ic[window]
  })));
  const stressPeriods = Object.keys(data.items[0]!.stress_max_drawdown);
  const stressData = data.items.flatMap((item) => stressPeriods.map((period) => ({
    period,
    version: compareLabel(item.factor_version),
    value: item.stress_max_drawdown[period]!
  })));
  const portfolioRows: Array<[string, (item: FactorCompareItem) => number, "percent" | "number"]> = [
    ["基线净超额", (item) => item.portfolio.baseline_net_excess, "percent"],
    ["候选净超额", (item) => item.portfolio.candidate_net_excess, "percent"],
    ["基线净 ICIR", (item) => item.portfolio.baseline_net_icir, "number"],
    ["候选净 ICIR", (item) => item.portfolio.candidate_net_icir, "number"],
    ["候选换手", (item) => item.portfolio.candidate_turnover, "number"],
    ["成本 2× 净超额", (item) => item.cost_and_slippage.cost_2x_net_excess, "percent"],
    ["滑点 2× 净超额", (item) => item.cost_and_slippage.slippage_2x_net_excess, "percent"]
  ];

  return (
    <div className="page-stack factor-page">
      <PageHeader eyebrow="STRICT COMPARISON" title="只比较同口径的当前权威版本" description="后端一致性校验是唯一裁判；选择顺序保留，结果不按表现重排。" status={meta.freshness_status} evidence={evidence} {...researchHeaderProps(meta)} />
      {query.isFetching ? <RefreshNotice asOf={meta.as_of} generatedAt={meta.generated_at} /> : null}
      <RouterLink className="factor-back-link" to="/factors"><ArrowLeftOutlined /> 返回因子目录</RouterLink>
      <section className="factor-selection-strip" aria-label="比较选择">
        {data.items.map((item) => <span key={item.factor_version} title={`${item.factor_id} · ${item.factor_version}`}><strong>{compareLabel(item.factor_version)}</strong><small>当前权威版本</small><Button type="link" onClick={() => remove(item.factor_version)}>移除</Button></span>)}
      </section>
      <section className="surface-panel" aria-labelledby="fingerprint-heading">
        <div className="section-heading"><div><span className="section-kicker">COMPARISON CONTRACT</span><h2 id="fingerprint-heading">这些口径已由后端判定完全一致</h2></div><StatusBadge status="PASS" /></div>
        <dl className="factor-fingerprint-grid">{Object.entries(data.fingerprint).map(([key, value]) => <div key={key}><dt>{metricLabel(key)}</dt><dd title={value}>已核对一致</dd></div>)}</dl>
      </section>
      <section className="chart-surface primary-chart" aria-labelledby="compare-windows-heading">
        <div className="section-heading"><div><span className="section-kicker">SIX OOS WINDOWS</span><h2 id="compare-windows-heading">六窗口 RankIC 稳定性</h2></div><span className="section-note">按 URL 选择顺序；不产生综合分</span></div>
        <div className="chart-canvas" role="img" aria-label="二至三个当前权威因子的六窗口 RankIC 折线比较图">
          <Line data={lineData} xField="window" yField="value" colorField="version" seriesField="version" height={330} point={{ size: 5 }} axis={{ y: { labelFormatter: (value: number) => Number(value).toFixed(4) } }} legend={{ color: { position: "top" } }} animate={false} />
        </div>
        <details className="accessible-data-table"><summary>查看六窗口比较精确数据</summary><table><thead><tr><th>窗口</th>{data.items.map((item) => <th key={item.factor_version}>{compareLabel(item.factor_version)}</th>)}</tr></thead><tbody>{WINDOWS.map((window) => <tr key={window}><td>{window}</td>{data.items.map((item) => <td key={item.factor_version}>{formatNumber(item.six_oos_window_rank_ic[window], 4)}</td>)}</tr>)}</tbody></table></details>
      </section>
      <section className="chart-surface" aria-labelledby="compare-stress-heading">
        <div className="section-heading"><div><span className="section-kicker">STRESS PERIODS</span><h2 id="compare-stress-heading">压力期最大回撤</h2></div></div>
        <div className="chart-canvas" role="img" aria-label="二至三个当前权威因子的压力期最大回撤分组柱状图">
          <Column data={stressData} xField="period" yField="value" colorField="version" group height={320} axis={{ y: { labelFormatter: (value: number) => `${(Number(value) * 100).toFixed(0)}%` } }} legend={{ color: { position: "top" } }} animate={false} />
        </div>
        <details className="accessible-data-table"><summary>查看压力期比较精确数据</summary><table><thead><tr><th>压力期</th>{data.items.map((item) => <th key={item.factor_version}>{compareLabel(item.factor_version)}</th>)}</tr></thead><tbody>{stressPeriods.map((period) => <tr key={period}><td>{period}</td>{data.items.map((item) => <td key={item.factor_version}>{formatPercent(item.stress_max_drawdown[period]!)}</td>)}</tr>)}</tbody></table></details>
      </section>
      <section className="table-surface" aria-labelledby="compare-portfolio-heading">
        <div className="section-heading"><div><span className="section-kicker">PORTFOLIO / COST</span><h2 id="compare-portfolio-heading">组合与成本精确比较</h2></div></div>
        <div className="factor-comparison-table-wrap" role="region" aria-label="因子组合与成本比较" tabIndex={0}><table className="factor-metric-table"><thead><tr><th>指标</th>{data.items.map((item) => <th key={item.factor_version}>{compareLabel(item.factor_version)}</th>)}</tr></thead><tbody>{portfolioRows.map(([label, accessor, kind]) => <tr key={label}><th>{label}</th>{data.items.map((item) => <td key={item.factor_version}>{kind === "percent" ? formatPercent(accessor(item), { signed: true }) : formatNumber(accessor(item), 3)}</td>)}</tr>)}</tbody></table></div>
      </section>
      <p className="page-evidence-footer">比较响应只提供投影级证据；查看单因子来源与完整技术校验值请返回对应研究证据页。页面未推断“最佳因子”。</p>
    </div>
  );
}

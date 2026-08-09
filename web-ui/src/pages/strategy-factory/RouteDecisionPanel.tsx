import { PauseCircleOutlined, SafetyCertificateOutlined } from "@ant-design/icons";
import { Alert } from "antd";
import { MetricCard } from "../../components/MetricCard";
import { displayDate } from "../../format";
import type { StrategyFactoryRouteDecision } from "../../strategyFactoryTypes";

export function RouteDecisionPanel({ route }: { route: StrategyFactoryRouteDecision }) {
  const goal = route.primary_goal;
  return (
    <section className="surface-panel factory-section" aria-labelledby="factory-current-route">
      <div className="section-heading">
        <div><span className="section-kicker">CURRENT ROUTE · 2026-08-09</span><h2 id="factory-current-route">{route.headline}</h2></div>
        <span className="factory-readonly-label"><PauseCircleOutlined /> 纠偏观察</span>
      </div>
      <p>{route.summary}</p>
      <div className="metric-grid five-up">
        <MetricCard label="双账户自然日" value={`${goal.live_dual_days_at_freeze} / ${goal.minimum_live_dual_days}`} detail="R2-1 当前主目标" />
        <MetricCard label="自然调仓周期" value={`${goal.live_dual_rebalances_at_freeze} / ${goal.minimum_live_dual_rebalances}`} detail="门槛未到" />
        <MetricCard label="M7候选" value={route.m7.candidate_count} detail="数据门未通过" tone="warning" />
        <MetricCard label="M7效果读取" value={route.m7.effect_read_count} detail="未进入效果阶段" />
        <MetricCard label="计划验收日" value={displayDate(goal.expected_first_due_execution_date)} detail="实际以证据为准" />
      </div>
      <Alert
        type="warning"
        showIcon
        icon={<SafetyCertificateOutlined />}
        message="新研究路线暂停，不代表平台没有研究能力"
        description={`${route.capability_note} 当前暂停：${route.paused_work.join("、")}。`}
      />
    </section>
  );
}

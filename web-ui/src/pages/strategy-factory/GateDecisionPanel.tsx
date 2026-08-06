import type {
  StrategyFactoryGateDecision,
  StrategyFactoryUniverse
} from "../../strategyFactoryTypes";

export function GateDecisionPanel({
  decision,
  universes
}: {
  decision: StrategyFactoryGateDecision;
  universes: StrategyFactoryUniverse[];
}) {
  const names = new Map(universes.map((item) => [item.universe_id, item.display_name]));
  const scope = decision.universe_ids.map((id) => names.get(id) ?? id).join("、");

  return (
    <section className="factory-gate-decision" aria-labelledby="factory-gate-heading">
      <div className="factory-gate-heading">
        <div>
          <span className="section-kicker">LATEST AUTHORITATIVE DATA GATE</span>
          <h2 id="factory-gate-heading">{decision.display_name}：数据证据阻断，未评价策略效果</h2>
          <p>{decision.blocked_reason}</p>
        </div>
        <span className="factory-badge factory-badge-warning" title={decision.terminal_state}>
          数据阻断
        </span>
      </div>

      <p className="factory-gate-scope"><strong>研究范围</strong>{scope}</p>
      <dl className="factory-gate-metrics">
        <div><dt>冲突身份组</dt><dd>{decision.conflict_group_count}</dd></div>
        <div><dt>仅当前观察版本</dt><dd>{decision.forward_only_group_count}</dd></div>
        <div><dt>历史版本链可恢复</dt><dd>{decision.pit_resolved_group_count}</dd></div>
        <div><dt>策略效果</dt><dd>未评价</dd></div>
      </dl>

      <div className="factory-gate-next">
        <span>下一合法动作</span>
        <strong>{decision.next_action}</strong>
      </div>

      <details className="factory-gate-evidence">
        <summary>查看技术证据</summary>
        <dl>
          <div><dt>权威裁决</dt><dd>{decision.verdict}</dd></div>
          <div><dt>证据层</dt><dd>{decision.evidence_tier}</dd></div>
          <div><dt>Release scope</dt><dd>{decision.release_scope_sha256}</dd></div>
          <div><dt>Run ID</dt><dd>{decision.run_id}</dd></div>
          <div><dt>独立审计</dt><dd>{decision.independent_audit_sha256}</dd></div>
          <div><dt>Registry event</dt><dd>{decision.registry_event_sha256}</dd></div>
          <div><dt>证据提交</dt><dd>{decision.evidence_commit}</dd></div>
          <div><dt>路线复盘提交</dt><dd>{decision.route_review_commit}</dd></div>
        </dl>
      </details>
    </section>
  );
}

import { Button } from "antd";
import { useMemo, useState } from "react";
import type {
  StrategyFactoryData,
  StrategyFactoryFamily,
  StrategyFactoryMatrixCell,
  StrategyFactoryOutcome,
  StrategyFactoryProgram,
  StrategyFactoryUniverse
} from "../../strategyFactoryTypes";

const OUTCOME_LABELS: Record<string, string> = {
  PRODUCTION_CURRENT_EXISTING: "既有生产",
  REJECT_CURRENT_PROGRAMS: "已有研究拒绝",
  NOT_EVALUATED: "尚未评价",
  STOPPED_CONTRACT: "合同停止",
  REJECT: "历史拒绝"
};

const TIER_LABELS: Record<string, string> = {
  PRODUCTION_CURRENT: "生产与前瞻证据",
  HISTORICAL_EFFECT_AUDITED: "历史效果已审计",
  SOURCE_GO_ONLY: "仅数据源可用",
  SECONDARY_SOURCE_GO_ONLY: "仅二级来源可用",
  PROTOCOL_ONLY: "仅协议身份",
  DISCOVERY_ONLY: "仅发现期证据",
  NOT_EVALUATED: "尚未评价"
};

const DATA_LABELS: Record<string, string> = {
  READY: "数据与PIT可研究",
  BLOCKED_OFFICIAL_LINEAGE: "官方谱系阻断",
  DATA_GATE_REQUIRED: "尚待数据门"
};

function tone(value: string): string {
  if (value === "READY" || value === "PRODUCTION_CURRENT_EXISTING") return "positive";
  if (value.includes("REJECT") || value.includes("STOPPED")) return "negative";
  if (value.includes("BLOCKED") || value.includes("REQUIRED")) return "warning";
  return "neutral";
}

export function BusinessBadge({ value, label }: { value: string; label?: string }) {
  return (
    <span className={`factory-badge factory-badge-${tone(value)}`} title={value}>
      {label ?? OUTCOME_LABELS[value] ?? DATA_LABELS[value] ?? value}
    </span>
  );
}

export function UniverseMap({ universes }: { universes: StrategyFactoryUniverse[] }) {
  return (
    <div className="factory-table-scroll" role="region" aria-label="股票池研究地图" tabIndex={0}>
      <table className="factory-table">
        <thead>
          <tr>
            <th>股票池</th>
            <th>数据与PIT</th>
            <th>当前研究结论</th>
            <th>证据层</th>
            <th>下一合法动作</th>
          </tr>
        </thead>
        <tbody>
          {universes.map((universe) => (
            <tr key={universe.universe_id}>
              <td>
                <strong>{universe.display_name}</strong>
                <small>
                  {universe.identity_kind === "CUSTOM_RULE_BASED" ? "自建规则池" : "官方指数"}
                  {universe.official_index_code ? ` · ${universe.official_index_code}` : ""}
                </small>
              </td>
              <td><BusinessBadge value={universe.data_status} /></td>
              <td><BusinessBadge value={universe.authoritative_outcome} /></td>
              <td>{TIER_LABELS[universe.evidence_tier] ?? universe.evidence_tier}</td>
              <td>
                <strong>{universe.research_draft_eligible ? "可建立研究草案" : "暂不可研究因子"}</strong>
                <small>{universe.blocker ?? "仍须按批次冻结协议并取得独立授权"}</small>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function cellOutcome(cell: StrategyFactoryMatrixCell): string {
  const outcomes = cell.authoritative_outcomes;
  if (outcomes.includes("REJECT")) return "REJECT";
  if (outcomes.includes("STOPPED_CONTRACT")) return "STOPPED_CONTRACT";
  if (outcomes.includes("PRODUCTION_CURRENT_EXISTING")) return "PRODUCTION_CURRENT_EXISTING";
  return outcomes[0] ?? "NOT_EVALUATED";
}

export function ResearchMatrix({
  families,
  universes,
  matrix
}: {
  families: StrategyFactoryFamily[];
  universes: StrategyFactoryUniverse[];
  matrix: StrategyFactoryMatrixCell[];
}) {
  const [familyId, setFamilyId] = useState(families.find((item) => item.family_id === "price_volume")?.family_id ?? families[0]?.family_id ?? "");
  const selected = families.find((item) => item.family_id === familyId);
  return (
    <>
      <div className="factory-family-tabs" role="tablist" aria-label="选择研究家族">
        {families.map((family) => (
          <button
            key={family.family_id}
            type="button"
            role="tab"
            aria-selected={family.family_id === familyId}
            className={family.family_id === familyId ? "active" : ""}
            onClick={() => setFamilyId(family.family_id)}
          >
            {family.display_name}
          </button>
        ))}
      </div>
      <div className="factory-matrix-list" aria-label={`${selected?.display_name ?? "研究家族"}跨股票池状态`}>
        {universes.map((universe) => {
          const cell = matrix.find((item) => item.family_id === familyId && item.universe_id === universe.universe_id);
          const outcome = cell ? cellOutcome(cell) : "NOT_EVALUATED";
          return (
            <article key={universe.universe_id}>
              <div>
                <strong>{universe.display_name}</strong>
                <small>{universe.identity_kind === "CUSTOM_RULE_BASED" ? "规则池" : "官方池"}</small>
              </div>
              <BusinessBadge value={outcome} />
              <p>{cell?.program_ids.length ? `${cell.program_ids.length} 个已登记工作包` : "尚无该家族的权威评价"}</p>
            </article>
          );
        })}
      </div>
      <p className="factory-method-note">该视图展示研究家族覆盖，不是因子表现热力图；正式因子库当前仍为0。</p>
    </>
  );
}

export function ProgramCatalog({
  programs,
  universes
}: {
  programs: StrategyFactoryProgram[];
  universes: StrategyFactoryUniverse[];
}) {
  const names = new Map(universes.map((item) => [item.universe_id, item.display_name]));
  return (
    <div className="factory-program-list">
      {programs.map((program) => (
        <article key={program.program_id}>
          <div className="factory-program-heading">
            <div>
              <strong>{program.display_name}</strong>
              <small>{program.universe_ids.map((id) => names.get(id) ?? id).join(" / ")}</small>
            </div>
            <BusinessBadge value={program.authoritative_outcome} />
          </div>
          <p>{program.summary}</p>
          <dl>
            <div><dt>生成尝试</dt><dd>{program.generation_attempt_count}</dd></div>
            <div><dt>评价单元</dt><dd>{program.evaluation_unit_count}</dd></div>
            <div><dt>打开效果</dt><dd>{program.effect_test_count}</dd></div>
          </dl>
          <footer><span>下一步</span>{program.next_action}</footer>
        </article>
      ))}
    </div>
  );
}

export function DraftPlanner({ data }: { data: StrategyFactoryData }) {
  const eligibleUniverses = data.universes.filter((item) => data.draft_template.eligible_universe_ids.includes(item.universe_id));
  const eligibleFamilies = data.research_families.filter((item) => data.draft_template.eligible_family_ids.includes(item.family_id));
  const initialUniverse = eligibleUniverses.find((item) => item.universe_id === "star50-official-pit-v2")?.universe_id ?? eligibleUniverses[0]?.universe_id ?? "";
  const initialFamily = eligibleFamilies.find((item) => item.family_id === "price_volume")?.family_id ?? eligibleFamilies[0]?.family_id ?? "";
  const [selectedUniverses, setSelectedUniverses] = useState<string[]>(initialUniverse ? [initialUniverse] : []);
  const [familyId, setFamilyId] = useState(initialFamily);
  const [candidateCount, setCandidateCount] = useState(8);
  const [previewed, setPreviewed] = useState(false);
  const selectedNames = useMemo(
    () => eligibleUniverses.filter((item) => selectedUniverses.includes(item.universe_id)).map((item) => item.display_name),
    [eligibleUniverses, selectedUniverses]
  );
  const familyName = eligibleFamilies.find((item) => item.family_id === familyId)?.display_name ?? "未选择";

  function toggleUniverse(id: string) {
    setPreviewed(false);
    setSelectedUniverses((current) => {
      if (current.includes(id)) return current.filter((item) => item !== id);
      if (current.length >= data.draft_template.maximum_universe_count) return current;
      return [...current, id];
    });
  }

  return (
    <div className="factory-draft-grid">
      <div className="factory-draft-form">
        <fieldset>
          <legend>1. 选择股票池（最多{data.draft_template.maximum_universe_count}个）</legend>
          <div className="factory-check-list">
            {eligibleUniverses.map((universe) => (
              <label key={universe.universe_id}>
                <input
                  type="checkbox"
                  checked={selectedUniverses.includes(universe.universe_id)}
                  onChange={() => toggleUniverse(universe.universe_id)}
                />
                <span>{universe.display_name}<small>{universe.identity_kind === "CUSTOM_RULE_BASED" ? "自建规则池" : "官方池"}</small></span>
              </label>
            ))}
          </div>
        </fieldset>
        <div className="factory-field-row">
          <label>
            <span>2. 研究机制</span>
            <select value={familyId} onChange={(event) => { setFamilyId(event.target.value); setPreviewed(false); }}>
              {eligibleFamilies.map((family) => <option key={family.family_id} value={family.family_id}>{family.display_name}</option>)}
            </select>
          </label>
          <label>
            <span>3. 候选上限</span>
            <select value={candidateCount} onChange={(event) => { setCandidateCount(Number(event.target.value)); setPreviewed(false); }}>
              {[8, 12, 24].filter((value) => value <= data.draft_template.maximum_candidate_count).map((value) => <option key={value} value={value}>{value}个</option>)}
            </select>
          </label>
        </div>
        <Button type="primary" disabled={!selectedUniverses.length || !familyId} onClick={() => setPreviewed(true)}>
          生成本地草案预览
        </Button>
        <p className="factory-method-note">不会发送网络请求，不会生成任务，不会调用DeepSeek。</p>
      </div>
      <aside className={`factory-draft-preview ${previewed ? "ready" : ""}`} aria-live="polite">
        <span className="section-kicker">DRAFT · NOT SUBMITTED</span>
        <h3>{previewed ? `${familyName}有界研究草案` : "等待生成草案预览"}</h3>
        {previewed ? (
          <>
            <dl>
              <div><dt>股票池</dt><dd>{selectedNames.join("、")}</dd></div>
              <div><dt>候选上限</dt><dd>{candidateCount}个</dd></div>
              <div><dt>外部调用</dt><dd>未授权</dd></div>
              <div><dt>封存效果</dt><dd>未授权</dd></div>
              <div><dt>生产权限</dt><dd>无</dd></div>
            </dl>
            <p>下一步需另立结果前协议，冻结池矩阵、尝试N、数据/窗口、费用和停止条件，并由用户逐项批准。</p>
          </>
        ) : <p>{data.draft_template.disclaimer}</p>}
      </aside>
    </div>
  );
}

export function outcomeLabel(value: StrategyFactoryOutcome): string {
  return OUTCOME_LABELS[value] ?? value;
}

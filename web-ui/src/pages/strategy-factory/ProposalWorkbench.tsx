import { Alert, Button } from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import {
  cancelProposal,
  createProposal,
  getProposal,
  listProposals,
  submitProposal
} from "../../proposalControlApi";
import {
  FAMILY_CONTROLS,
  FIXED_PROPOSAL_AUTHORITY,
  type ProposalCreateInput,
  type ProposalEvent,
  type ProposalState,
  type ProposalView
} from "../../proposalControlTypes";
import type { StrategyFactoryData } from "../../strategyFactoryTypes";

const STATE_LABELS: Record<ProposalState, string> = {
  DRAFT: "提案草稿",
  REVIEW_REQUIRED: "已提交人工复核",
  CANCELLED: "已取消"
};
const EVENT_LABELS: Record<ProposalEvent["event_type"], string> = {
  PROPOSAL_CREATED: "保存非权威提案",
  SUBMITTED_FOR_REVIEW: "提交人工复核",
  CANCELLED_BY_PROPOSER: "取消提案"
};
const HYPOTHESIS_LABELS: Record<string, string> = {
  "incremental-flow-information-v1": "资金流相对基线包含增量信息",
  "pit-level-quality-value-v1": "时点可得的质量与估值水平",
  "pit-fundamental-change-v1": "时点可得的基本面变化",
  "bounded-price-volume-mechanism-v1": "有界量价机制",
  "benchmark-residual-structure-v1": "基准残差结构"
};
const MODE_LABELS = {
  DETERMINISTIC_CODE: "确定性代码生成",
  LLM_BOUNDED_DSL: "大模型受限 DSL 意向"
} as const;
const SCOPE_LABELS: Record<string, string> = {
  moneyflow_family: "资金流家族",
  fundamental_static_family: "静态基本面家族",
  fundamental_dynamic_family: "动态基本面家族",
  fundamental_joint_domain: "基本面联合敏感性",
  related_price_volume_domain: "相关价量全局敏感性",
  residual_risk_family: "残差风险家族"
};

function formatTime(value: string): string {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString("zh-CN", { hour12: false });
}

function ActionConfirmation({
  kind,
  pending,
  onCancel,
  onConfirm
}: {
  kind: "submit" | "cancel";
  pending: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const submit = kind === "submit";
  return (
    <div className={`proposal-confirm ${submit ? "" : "danger"}`} role="alertdialog" aria-labelledby="proposal-confirm-title">
      <strong id="proposal-confirm-title">{submit ? "确认提交人工复核？" : "确认取消这份提案？"}</strong>
      <p>{submit ? "提交后仍未冻结、未排队、未运行；该提案将变为只读。" : "取消会永久保留事件且不可恢复；如需调整只能新建提案。"}</p>
      <div className="proposal-actions">
        <Button onClick={onCancel} disabled={pending}>返回</Button>
        <Button danger={!submit} type="primary" onClick={onConfirm} loading={pending}>
          {submit ? "确认提交人工复核" : "确认取消提案"}
        </Button>
      </div>
    </div>
  );
}

function ProposalDetail({
  item,
  familyNames,
  universeNames,
  onChanged
}: {
  item: ProposalView;
  familyNames: Map<string, string>;
  universeNames: Map<string, string>;
  onChanged: (item: ProposalView) => void;
}) {
  const [confirm, setConfirm] = useState<"submit" | "cancel" | null>(null);
  const command = useMutation({
    mutationFn: () => confirm === "submit" ? submitProposal(item) : cancelProposal(item),
    onSuccess: (updated) => { setConfirm(null); onChanged(updated); }
  });
  const canonical = item.canonical_proposal;
  const request = canonical.request;
  const multiplicity = canonical.derived.multiplicity_context;
  const primaryAfter = multiplicity.primary.primary_planned_after;
  const sensitivityAfter = multiplicity.sensitivity?.sensitivity_planned_after;
  return (
    <article className="proposal-detail" aria-labelledby="proposal-detail-title">
      <header>
        <div>
          <span className="section-kicker">NON-AUTHORITATIVE PROPOSAL</span>
          <h3 id="proposal-detail-title">{familyNames.get(request.family_id) ?? request.family_id}</h3>
          <p>{STATE_LABELS[item.current_state]} · 未冻结 · 未排队 · 未运行</p>
        </div>
        <span className={`proposal-state proposal-state-${item.current_state.toLowerCase()}`}>{STATE_LABELS[item.current_state]}</span>
      </header>
      <dl className="proposal-facts">
        <div><dt>主研究池</dt><dd>{universeNames.get(request.home_universe_id) ?? request.home_universe_id}</dd></div>
        <div><dt>迁移观察池</dt><dd>{request.universe_ids.filter((id) => id !== request.home_universe_id).map((id) => universeNames.get(id) ?? id).join("、") || "无"}</dd></div>
        <div><dt>注册假设</dt><dd>{HYPOTHESIS_LABELS[request.hypothesis_id] ?? request.hypothesis_id}</dd></div>
        <div><dt>生成意向</dt><dd>{MODE_LABELS[request.generation_mode]}</dd></div>
        <div><dt>尝试/候选上限</dt><dd>{request.generation_attempt_cap} / {request.candidate_cap}</dd></div>
        <div><dt>调用/完成目标</dt><dd>{request.provider_call_intent_count} / {request.completed_response_target} · 均未授权</dd></div>
        <div><dt>未来费用意向</dt><dd>${request.provider_budget_usd} · 尚未授权</dd></div>
      </dl>
      <section className="proposal-multiplicity" aria-labelledby="proposal-multiplicity-title">
        <h4 id="proposal-multiplicity-title">多重检验背景（不是已发生尝试）</h4>
        <p>本阶段实际研究尝试增量 N={multiplicity.actual_research_attempt_increment}</p>
        <div><span>主要统计背景</span><strong>{SCOPE_LABELS[multiplicity.primary.scope_id] ?? multiplicity.primary.scope_id}</strong><small>历史 N={multiplicity.primary.prior_attempt_count} · 提案后计划背景 N={primaryAfter ?? "—"}</small></div>
        {multiplicity.sensitivity ? <div><span>全局敏感性</span><strong>{SCOPE_LABELS[multiplicity.sensitivity.scope_id] ?? multiplicity.sensitivity.scope_id}</strong><small>历史 N={multiplicity.sensitivity.prior_attempt_count} · 提案后计划背景 N={sensitivityAfter ?? "—"}</small></div> : <div><span>全局敏感性</span><strong>本家族不适用</strong><small>不制造额外统计口径</small></div>}
      </section>
      <div className="proposal-denials" aria-label="未授权能力">
        <span>协议冻结：无</span><span>执行发布：无</span><span>外部调用：无</span>
        <span>效果读取：无</span><span>前瞻：无</span><span>生产：无</span>
      </div>
      {command.isError ? <Alert type="error" showIcon message={command.error.message} /> : null}
      {confirm ? (
        <ActionConfirmation
          kind={confirm}
          pending={command.isPending}
          onCancel={() => setConfirm(null)}
          onConfirm={() => command.mutate()}
        />
      ) : (
        <div className="proposal-actions">
          {item.available_actions.includes("SUBMIT_FOR_REVIEW") ? <Button type="primary" onClick={() => setConfirm("submit")}>提交人工复核</Button> : null}
          {item.available_actions.includes("CANCEL") ? <Button danger onClick={() => setConfirm("cancel")}>{item.current_state === "REVIEW_REQUIRED" ? "撤回复核并取消" : "取消提案"}</Button> : null}
          {!item.available_actions.length ? <span className="proposal-no-action">该状态没有可用写动作</span> : null}
        </div>
      )}
      <section className="proposal-events" aria-labelledby="proposal-events-title">
        <h4 id="proposal-events-title">追加事件</h4>
        {item.events.length ? item.events.map((event) => (
          <div key={`${event.event_seq}-${event.event_type}`}>
            <span>{event.event_seq}</span>
            <strong>{EVENT_LABELS[event.event_type] ?? event.event_type}</strong>
            <time>{formatTime(event.recorded_at)}</time>
          </div>
        )) : <p>当前详情未返回事件；请刷新目录核验。</p>}
      </section>
      <details className="proposal-technical">
        <summary>查看提案技术身份</summary>
        <dl>
          <div><dt>提案编号</dt><dd>{item.proposal_id}</dd></div>
          <div><dt>提案版本身份</dt><dd>{item.proposal_request_sha256}</dd></div>
          <div><dt>事件序号</dt><dd>{item.current_event_seq}</dd></div>
        </dl>
      </details>
    </article>
  );
}

function ProposalCreator({
  data,
  controlReady,
  familyNames,
  universeNames,
  onCreated
}: {
  data: StrategyFactoryData;
  controlReady: boolean;
  familyNames: Map<string, string>;
  universeNames: Map<string, string>;
  onCreated: (item: ProposalView) => void;
}) {
  const [universeIds, setUniverseIds] = useState<string[]>([]);
  const [homeId, setHomeId] = useState("");
  const [familyId, setFamilyId] = useState("");
  const [mode, setMode] = useState<ProposalCreateInput["generation_mode"]>("DETERMINISTIC_CODE");
  const [attemptCap, setAttemptCap] = useState<8 | 12 | 24>(8);
  const [candidateCap, setCandidateCap] = useState(8);
  const [budget, setBudget] = useState("0.25");
  const [validDays, setValidDays] = useState(7);
  const [acknowledged, setAcknowledged] = useState(false);
  const eligible = data.universes.filter((item) => item.research_draft_eligible);
  const blocked = data.universes.filter((item) => !item.research_draft_eligible);
  const family = FAMILY_CONTROLS.find((item) => item.familyId === familyId);
  const save = useMutation({
    mutationFn: () => createProposal({
      template_id: "bounded-research-proposal-v1",
      template_version: 2,
      universe_ids: universeIds,
      home_universe_id: homeId,
      family_id: familyId,
      hypothesis_id: family?.hypothesisId ?? "",
      falsification_rule_id: "frozen-gates-reject-v1",
      generation_mode: mode,
      generation_attempt_cap: attemptCap,
      candidate_cap: candidateCap,
      provider_identity: mode === "LLM_BOUNDED_DSL" ? "TO_BE_REVIEWED_NOT_AUTHORIZED" : "NONE_NOT_APPLICABLE",
      provider_call_intent_count: mode === "LLM_BOUNDED_DSL" ? attemptCap : 0,
      completed_response_target: mode === "LLM_BOUNDED_DSL" ? attemptCap : 0,
      provider_budget_usd: mode === "LLM_BOUNDED_DSL" ? budget : "0.00",
      valid_days: validDays,
      authority: FIXED_PROPOSAL_AUTHORITY
    }),
    onSuccess: (created) => {
      onCreated(created);
      setUniverseIds([]); setHomeId(""); setFamilyId(""); setAcknowledged(false);
    }
  });

  function toggleUniverse(id: string) {
    setUniverseIds((current) => {
      const next = current.includes(id) ? current.filter((item) => item !== id) : current.length < 3 ? [...current, id] : current;
      if (!next.includes(homeId)) setHomeId(next[0] ?? "");
      return next;
    });
  }

  const canSave = Boolean(universeIds.length && homeId && family && acknowledged && candidateCap <= attemptCap && controlReady);
  return (
    <section className="proposal-create" aria-labelledby="proposal-create-title">
      <h3 id="proposal-create-title">新建提案</h3>
          <fieldset>
            <legend>1. 选择1—3个可研究股票池</legend>
            <div className="factory-check-list">
              {eligible.map((universe) => <label key={universe.universe_id}><input type="checkbox" checked={universeIds.includes(universe.universe_id)} onChange={() => toggleUniverse(universe.universe_id)} /><span>{universe.display_name}<small>{universe.existing_production ? "既有生产池，不代表新提案获准" : "仅具备提案资格"}</small></span></label>)}
            </div>
          </fieldset>
          {universeIds.length ? <fieldset><legend>2. 指定唯一主研究池</legend><div className="proposal-radio-list">{universeIds.map((id) => <label key={id}><input type="radio" name="home-universe" checked={homeId === id} onChange={() => setHomeId(id)} />{universeNames.get(id)}</label>)}</div></fieldset> : null}
          <div className="proposal-form-grid">
            <label><span>3. 研究家族</span><select aria-label="研究家族" value={familyId} onChange={(event) => { const id = event.target.value; const next = FAMILY_CONTROLS.find((item) => item.familyId === id); setFamilyId(id); setMode(next?.generationModes[0] ?? "DETERMINISTIC_CODE"); }}><option value="">请选择</option>{FAMILY_CONTROLS.map((item) => <option key={item.familyId} value={item.familyId}>{familyNames.get(item.familyId) ?? item.familyId}</option>)}</select></label>
            <label><span>4. 生成方式</span><select aria-label="生成方式" value={mode} disabled={!family} onChange={(event) => setMode(event.target.value as ProposalCreateInput["generation_mode"])}>{family?.generationModes.map((item) => <option key={item} value={item}>{MODE_LABELS[item]}</option>)}</select></label>
            <label><span>5. 尝试上限</span><select aria-label="尝试上限" value={attemptCap} onChange={(event) => { const next = Number(event.target.value) as 8 | 12 | 24; setAttemptCap(next); setCandidateCap((current) => Math.min(current, next)); }}><option value={8}>8次</option><option value={12}>12次</option><option value={24}>24次</option></select></label>
            <label><span>6. 候选上限</span><select aria-label="候选上限" value={candidateCap} onChange={(event) => setCandidateCap(Number(event.target.value))}>{[4, 8, 12, 24].filter((value) => value <= attemptCap).map((value) => <option key={value} value={value}>{value}个</option>)}</select></label>
            <label><span>7. 有效期</span><select aria-label="有效期" value={validDays} onChange={(event) => setValidDays(Number(event.target.value))}><option value={1}>1天</option><option value={7}>7天</option><option value={14}>14天</option></select></label>
            {mode === "LLM_BOUNDED_DSL" ? <label><span>8. 未来费用意向（非授权）</span><select aria-label="未来费用意向" value={budget} onChange={(event) => setBudget(event.target.value)}><option value="0.10">$0.10</option><option value="0.25">$0.25</option><option value="0.50">$0.50</option><option value="1.00">$1.00</option></select></label> : null}
          </div>
          {family ? <p className="proposal-hypothesis">注册假设：{HYPOTHESIS_LABELS[family.hypothesisId]}</p> : null}
          <label className="proposal-ack"><input type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} />我理解保存的只是非权威提案，未冻结、未排队、未运行。</label>
          {save.isError ? <Alert type="error" showIcon message={save.error.message} /> : null}
          <Button type="primary" disabled={!canSave} loading={save.isPending} onClick={() => save.mutate()}>保存提案</Button>
          <details className="proposal-blocked"><summary>3个当前阻断股票池</summary>{blocked.map((item) => <p key={item.universe_id}><strong>{item.display_name}</strong><span>{item.blocker}</span></p>)}</details>
    </section>
  );
}

function ProposalDirectory({
  items,
  selectedId,
  loading,
  refreshing,
  familyNames,
  universeNames,
  onSelect,
  onRefresh,
  onChanged
}: {
  items: ProposalView[];
  selectedId: string;
  loading: boolean;
  refreshing: boolean;
  familyNames: Map<string, string>;
  universeNames: Map<string, string>;
  onSelect: (id: string) => void;
  onRefresh: () => void;
  onChanged: (item: ProposalView) => void;
}) {
  const listed = items.find((item) => item.proposal_id === selectedId) ?? items[0];
  const detail = useQuery({
    queryKey: ["proposal-control", listed?.proposal_id],
    queryFn: ({ signal }) => getProposal(listed!.proposal_id, signal),
    enabled: Boolean(listed),
    retry: false
  });
  const selected = detail.data ?? listed;
  return (
    <section className="proposal-directory" aria-labelledby="proposal-directory-title">
      <div className="proposal-directory-heading"><h3 id="proposal-directory-title">提案目录</h3><Button onClick={onRefresh} loading={refreshing}>刷新</Button></div>
      {loading ? <p>正在读取本机提案真身…</p> : items.length ? <div className="proposal-list">{items.map((item, index) => <button key={item.proposal_id} type="button" className={selected?.proposal_id === item.proposal_id ? "active" : ""} onClick={() => onSelect(item.proposal_id)}><span>提案 {items.length - index}</span><strong>{familyNames.get(item.canonical_proposal.request.family_id) ?? item.canonical_proposal.request.family_id}</strong><small>{STATE_LABELS[item.current_state]} · 未运行</small></button>)}</div> : <div className="proposal-empty"><strong>尚无持久化提案</strong><p>左侧保存成功后才会进入目录；浏览器不会乐观伪造记录。</p></div>}
      {detail.isError ? <Alert type="warning" showIcon message={detail.error.message} description="目录状态仍保留；详情恢复前不显示写动作。" /> : null}
      {selected && !detail.isError ? <ProposalDetail item={selected} familyNames={familyNames} universeNames={universeNames} onChanged={onChanged} /> : null}
    </section>
  );
}

export function ProposalWorkbench({ data }: { data: StrategyFactoryData }) {
  const queryClient = useQueryClient();
  const directory = useQuery({ queryKey: ["proposal-control"], queryFn: ({ signal }) => listProposals(signal), retry: false });
  const [selectedId, setSelectedId] = useState("");
  const items = directory.data?.items ?? [];
  const familyNames = useMemo(() => new Map(data.research_families.map((item) => [item.family_id, item.display_name])), [data.research_families]);
  const universeNames = useMemo(() => new Map(data.universes.map((item) => [item.universe_id, item.display_name])), [data.universes]);
  useEffect(() => { if (!selectedId && items[0]) setSelectedId(items[0].proposal_id); }, [items, selectedId]);
  function replace(updated: ProposalView) {
    queryClient.setQueryData(["proposal-control"], { items: items.map((item) => item.proposal_id === updated.proposal_id ? updated : item) });
    queryClient.setQueryData(["proposal-control", updated.proposal_id], updated);
  }
  function add(created: ProposalView) {
    queryClient.setQueryData(["proposal-control"], { items: [created, ...items.filter((item) => item.proposal_id !== created.proposal_id)] });
    queryClient.setQueryData(["proposal-control", created.proposal_id], created);
    setSelectedId(created.proposal_id);
  }
  return <div className="proposal-workbench">
    <div className="proposal-capabilities" aria-label="提案控制权限"><strong>本机提案写入：允许</strong><span>协议冻结：未授权</span><span>执行：未授权</span><span>外部调用：未授权</span><span>效果读取：未授权</span><span>前瞻：未授权</span><span>生产：无</span></div>
    <Alert type="info" showIcon message="这里只保存非权威研究意图" description="保存或提交人工复核都不会冻结协议、排队、运行、调用 DeepSeek 或形成研究尝试 N。" />
    {directory.isError ? <Alert type="warning" showIcon message={directory.error.message} description="只读研究地图仍可使用；控制服务恢复前不会显示保存成功。" /> : null}
    <div className="proposal-layout">
      <ProposalCreator data={data} controlReady={!directory.isError && !directory.isPending} familyNames={familyNames} universeNames={universeNames} onCreated={add} />
      <ProposalDirectory items={items} selectedId={selectedId} loading={directory.isPending} refreshing={directory.isFetching} familyNames={familyNames} universeNames={universeNames} onSelect={setSelectedId} onRefresh={() => { void directory.refetch(); }} onChanged={replace} />
    </div>
  </div>;
}

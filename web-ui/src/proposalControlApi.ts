import type {
  CanonicalProposal,
  ProposalCreateInput,
  ProposalEvent,
  ProposalList,
  ProposalState,
  ProposalView
} from "./proposalControlTypes";

const CONTROL_PATH = "/control/v1/research/proposals";
const STATES = new Set<ProposalState>(["DRAFT", "REVIEW_REQUIRED", "CANCELLED"]);
const ACTIONS = new Set(["SUBMIT_FOR_REVIEW", "CANCEL"]);
let csrfToken = "";
const INTENT_STORAGE_KEY = "m5-proposal-control-intents-v1";
interface MutationIntent {
  identity: string;
  idempotencyKey: string;
}
let memoryIntents: MutationIntent[] = [];

const ERROR_MESSAGES: Record<string, string> = {
  SESSION_REQUIRED: "安全会话已过期，请刷新提案目录后重试。",
  ORIGIN_REJECTED: "当前入口不是获准的本机同源页面。",
  CSRF_REJECTED: "安全校验已失效，请刷新后重试。",
  ROLE_NOT_ALLOWED: "当前本机角色不能执行该动作。",
  PROPOSAL_NOT_FOUND: "提案不存在或已不可见。",
  IDEMPOTENCY_CONFLICT: "相同请求身份对应了不同内容，未写入任何变更。",
  STATE_CONFLICT: "提案状态已经变化，请刷新后按最新合法动作处理。",
  CONTRACT_INVALID: "提案内容不符合冻结合同，未保存。",
  UNIVERSE_NOT_ELIGIBLE: "所选股票池当前不具备提案资格。",
  RATE_LIMITED: "写入过于频繁，请稍后再试。",
  CONTROL_NOT_READY: "提案控制服务尚未就绪；只读研究地图不受影响。"
};

export class ProposalControlError extends Error {
  readonly code: string;
  constructor(code: string, message?: string) {
    super(ERROR_MESSAGES[code] ?? message ?? "提案控制请求失败。");
    this.name = "ProposalControlError";
    this.code = code;
  }
}

function record(value: unknown, name: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new ProposalControlError("INVALID_RESPONSE", `${name}格式无效。`);
  }
  return value as Record<string, unknown>;
}

function text(value: unknown, name: string): string {
  if (typeof value !== "string" || !value) {
    throw new ProposalControlError("INVALID_RESPONSE", `${name}缺失。`);
  }
  return value;
}

function proposal(value: unknown): ProposalView {
  const root = record(value, "提案");
  const currentState = text(root.current_state, "提案状态") as ProposalState;
  if (!STATES.has(currentState)) throw new ProposalControlError("INVALID_RESPONSE", "提案状态未知。");
  if (!Number.isInteger(root.current_event_seq) || Number(root.current_event_seq) < 1) {
    throw new ProposalControlError("INVALID_RESPONSE", "提案事件序号无效。");
  }
  const actions = Array.isArray(root.available_actions) ? root.available_actions : [];
  if (actions.some((item) => typeof item !== "string" || !ACTIONS.has(item))) {
    throw new ProposalControlError("INVALID_RESPONSE", "后端返回了未授权动作。");
  }
  const sha = text(root.proposal_request_sha256, "提案版本身份");
  if (!/^[0-9a-f]{64}$/.test(sha)) throw new ProposalControlError("INVALID_RESPONSE", "提案版本身份无效。");
  const events = Array.isArray(root.events) ? root.events : [];
  return {
    proposal_id: text(root.proposal_id, "提案编号"),
    current_state: currentState,
    current_event_seq: Number(root.current_event_seq),
    available_actions: actions as ProposalView["available_actions"],
    proposal_request_sha256: sha,
    canonical_proposal: record(root.canonical_proposal, "规范提案") as unknown as CanonicalProposal,
    events: events.map((item) => record(item, "提案事件") as unknown as ProposalEvent)
  };
}

function unwrap(value: unknown): unknown {
  const root = record(value, "控制响应");
  return "data" in root ? root.data : root;
}

async function decode(response: Response): Promise<unknown> {
  const token = response.headers.get("x-csrf-token");
  if (token) csrfToken = token;
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new ProposalControlError("INVALID_RESPONSE", "提案控制服务返回了无效响应。");
  }
  if (!response.ok) {
    const error = record(body, "错误响应").error;
    const detail = error && typeof error === "object" ? error as Record<string, unknown> : {};
    const code = typeof detail.code === "string" ? detail.code : "CONTROL_NOT_READY";
    if (code === "SESSION_REQUIRED" || code === "CSRF_REJECTED") csrfToken = "";
    throw new ProposalControlError(code, typeof detail.message === "string" ? detail.message : undefined);
  }
  return unwrap(body);
}

function requestId(): string {
  const crypto = globalThis.crypto;
  if (crypto?.randomUUID) return crypto.randomUUID();
  if (crypto?.getRandomValues) {
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
    return `m5id-${hex}`;
  }
  throw new ProposalControlError(
    "CONTROL_NOT_READY",
    "浏览器安全随机数能力不可用，写入已阻止且未发送。"
  );
}

function loadIntents(): MutationIntent[] {
  try {
    const stored = globalThis.sessionStorage?.getItem(INTENT_STORAGE_KEY);
    if (stored == null) return memoryIntents;
    const decoded = JSON.parse(stored);
    return Array.isArray(decoded) ? decoded.filter((item) => (
      item
      && typeof item.identity === "string"
      && typeof item.idempotencyKey === "string"
      && item.idempotencyKey.length >= 16
      && item.idempotencyKey.length <= 128
    )) : [];
  } catch {
    return memoryIntents;
  }
}

function saveIntents(items: MutationIntent[]): void {
  memoryIntents = items.slice(-20);
  try {
    globalThis.sessionStorage?.setItem(INTENT_STORAGE_KEY, JSON.stringify(memoryIntents));
  } catch {
    // In-memory retention still preserves retries within the current page lifetime.
  }
}

function mutationIntent(identity: string): MutationIntent {
  const existing = loadIntents().find((item) => item.identity === identity);
  if (existing) return existing;
  const created = { identity, idempotencyKey: requestId() };
  saveIntents([...loadIntents().filter((item) => item.identity !== identity), created]);
  return created;
}

async function commandIdFor(intent: MutationIntent): Promise<string> {
  const subtle = globalThis.crypto?.subtle;
  if (!subtle) {
    throw new ProposalControlError(
      "CONTROL_NOT_READY",
      "浏览器安全摘要能力不可用，命令已阻止且未发送。"
    );
  }
  let digest: ArrayBuffer;
  try {
    digest = await subtle.digest("SHA-256", new TextEncoder().encode(intent.idempotencyKey));
  } catch {
    throw new ProposalControlError(
      "CONTROL_NOT_READY",
      "命令安全身份生成失败，命令已阻止且未发送。"
    );
  }
  const hex = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
  return `m5cmd-${hex}`;
}

function clearIntent(identity: string): void {
  saveIntents(loadIntents().filter((item) => item.identity !== identity));
}

export async function listProposals(signal?: AbortSignal): Promise<ProposalList> {
  const response = await fetch(CONTROL_PATH, {
    method: "GET",
    cache: "no-store",
    credentials: "same-origin",
    headers: { Accept: "application/json" },
    signal
  });
  const data = await decode(response);
  const root = Array.isArray(data) ? { items: data } : record(data, "提案目录");
  if (!Array.isArray(root.items)) throw new ProposalControlError("INVALID_RESPONSE", "提案目录缺少列表。");
  return { items: root.items.map(proposal) };
}

async function write(path: string, body: unknown, intent: MutationIntent): Promise<ProposalView> {
  if (!csrfToken) await listProposals();
  let response: Response;
  try {
    response = await fetch(path, {
      method: "POST",
      cache: "no-store",
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": intent.idempotencyKey,
        "X-CSRF-Token": csrfToken
      },
      body: JSON.stringify(body)
    });
  } catch {
    throw new ProposalControlError("CONTROL_NOT_READY", "请求结果未知；重试将复用同一幂等身份。");
  }
  try {
    const result = proposal(await decode(response));
    clearIntent(intent.identity);
    return result;
  } catch (error) {
    throw error;
  }
}

export async function createProposal(body: ProposalCreateInput): Promise<ProposalView> {
  const identity = `create:${JSON.stringify(body)}`;
  return write(CONTROL_PATH, body, mutationIntent(identity));
}

export async function getProposal(proposalId: string, signal?: AbortSignal): Promise<ProposalView> {
  const response = await fetch(`${CONTROL_PATH}/${encodeURIComponent(proposalId)}`, {
    method: "GET",
    cache: "no-store",
    credentials: "same-origin",
    headers: { Accept: "application/json" },
    signal
  });
  return proposal(await decode(response));
}

export async function submitProposal(item: ProposalView): Promise<ProposalView> {
  const identity = `submit:${item.proposal_id}:${item.current_event_seq}:${item.proposal_request_sha256}`;
  const intent = mutationIntent(identity);
  return write(`${CONTROL_PATH}/${encodeURIComponent(item.proposal_id)}/commands/submit-review`, {
    command_id: await commandIdFor(intent),
    expected_event_seq: item.current_event_seq,
    proposal_request_sha256: item.proposal_request_sha256,
    reason_code: "READY_FOR_HUMAN_REVIEW"
  }, intent);
}

export async function cancelProposal(item: ProposalView): Promise<ProposalView> {
  const identity = `cancel:${item.proposal_id}:${item.current_event_seq}:${item.proposal_request_sha256}`;
  const intent = mutationIntent(identity);
  return write(`${CONTROL_PATH}/${encodeURIComponent(item.proposal_id)}/commands/cancel`, {
    command_id: await commandIdFor(intent),
    expected_event_seq: item.current_event_seq,
    proposal_request_sha256: item.proposal_request_sha256,
    reason_code: "NO_LONGER_NEEDED"
  }, intent);
}

export function resetProposalSessionForTest(): void {
  csrfToken = "";
  memoryIntents = [];
  try { globalThis.sessionStorage?.removeItem(INTENT_STORAGE_KEY); } catch { /* test cleanup */ }
}

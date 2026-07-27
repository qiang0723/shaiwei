import type { DataQualityData, NotificationData, SystemRunData } from "../types";
import {
  IMAGE_SHA256,
  MESSAGE_ID,
  booleanValue,
  date,
  hashMap,
  integer,
  noBse,
  nullableText,
  numberLike,
  record,
  safeReference,
  sha,
  status,
  stringArray,
  text,
  timestamp
} from "./core";

function assertOperationsStage(value: unknown, name: string): Record<string, unknown> {
  const stage = record(value, name);
  text(stage.stage, `${name}.stage`);
  status(stage.status, `${name}.status`);
  const attempts = integer(stage.attempt_count, `${name}.attempt_count`);
  const failures = integer(stage.failed_attempt_count, `${name}.failed_attempt_count`);
  if (failures > attempts) throw new Error(`${name} 失败次数超过尝试数`);
  const recovered = booleanValue(stage.recovered, `${name}.recovered`);
  if (stage.status === "PASS" && failures > 0 && !recovered) {
    throw new Error(`${name} 隐藏了失败后恢复`);
  }
  nullableText(stage.first_error_type, `${name}.first_error_type`);
  if (stage.terminal_finished_at !== null) {
    timestamp(stage.terminal_finished_at, `${name}.terminal_finished_at`);
  }
  nullableText(stage.terminal_run_id, `${name}.terminal_run_id`);
  if (stage.evidence_status !== undefined) status(stage.evidence_status, `${name}.evidence_status`);
  if (stage.run_count !== undefined) integer(stage.run_count, `${name}.run_count`);
  if (stage.event_count !== undefined) integer(stage.event_count, `${name}.event_count`);
  return stage;
}

export function assertDataQuality(value: unknown): asserts value is DataQualityData {
  const root = record(value, "数据质量");
  status(root.status, "数据质量 status");
  const evidenceStatus = status(root.evidence_status, "数据质量 evidence_status");
  if (evidenceStatus !== "WARN") throw new Error("数据质量未保留哨兵证据 WARN");
  date(root.as_of, "数据质量 as_of");
  const dataSnapshot = sha(root.data_snapshot_sha256, "数据质量 data_snapshot_sha256");
  sha(root.code_snapshot_sha256, "数据质量 code_snapshot_sha256");
  const reasons = stringArray(root.status_reasons, "数据质量 status_reasons");
  if (!reasons.includes("SENTINEL_REPORT_NOT_HASH_BOUND")) {
    throw new Error("数据质量缺少哨兵未哈希绑定警告");
  }

  const daily = assertOperationsStage(root.daily_increment, "数据质量 daily_increment");
  if (daily.stage !== "daily_increment") throw new Error("数据质量日增量阶段身份错误");
  integer(daily.batch_count, "数据质量 daily_increment.batch_count");
  integer(daily.market_row_count, "数据质量 daily_increment.market_row_count");
  if (sha(daily.data_snapshot_sha256, "数据质量 daily_increment.data_snapshot") !== dataSnapshot) {
    throw new Error("数据质量日增量快照不一致");
  }

  const chain = record(root.batch_chain, "数据质量 batch_chain");
  integer(chain.registered_batch_count, "数据质量 registered_batch_count");
  integer(chain.registered_row_count, "数据质量 registered_row_count");
  const sourceCount = integer(chain.source_api_count, "数据质量 source_api_count");
  const sourceCounts = record(chain.source_api_batch_counts, "数据质量 source_api_batch_counts");
  if (Object.keys(sourceCounts).length !== sourceCount) throw new Error("数据来源数量与明细不一致");
  Object.entries(sourceCounts).forEach(([key, count]) => {
    text(key, "数据来源名称");
    integer(count, `数据来源 ${key}`);
  });
  if (
    sha(chain.reconstructed_data_snapshot_sha256, "数据质量 reconstructed_data_snapshot") !==
    dataSnapshot
  ) {
    throw new Error("数据质量登记身份链快照不一致");
  }
  if (chain.raw_parquet_rehash_status !== "NOT_EVALUATED") {
    throw new Error("数据质量错误声称原始 Parquet 已重验");
  }
  text(chain.raw_parquet_rehash_reason, "数据质量 raw_parquet_rehash_reason");
  const incrementalCount = integer(chain.incremental_batch_count, "数据质量 incremental_batch_count");
  if (!Array.isArray(chain.incremental_batches) || chain.incremental_batches.length !== incrementalCount) {
    throw new Error("数据质量当日批次数与明细不一致");
  }
  const batchIds = new Set<string>();
  chain.incremental_batches.forEach((item, index) => {
    const batch = record(item, `数据质量 batch[${index}]`);
    const batchId = text(batch.batch_id, `数据质量 batch[${index}].batch_id`);
    if (batchIds.has(batchId)) throw new Error("数据质量当日批次身份重复");
    batchIds.add(batchId);
    text(batch.source_api, `数据质量 batch[${index}].source_api`);
    integer(batch.row_count, `数据质量 batch[${index}].row_count`);
    timestamp(batch.ingest_time, `数据质量 batch[${index}].ingest_time`);
    sha(batch.content_sha256, `数据质量 batch[${index}].content_sha256`);
  });

  const sentinel = record(root.sentinel_gate, "数据质量 sentinel_gate");
  status(sentinel.status, "数据质量 sentinel status");
  if (sentinel.evidence_status !== "WARN") throw new Error("哨兵证据 WARN 被覆盖");
  if (sentinel.binding_status !== "IDENTITY_MATCH_UNHASHED") throw new Error("哨兵绑定语义被改变");
  if (sentinel.evidence_warning !== "SENTINEL_REPORT_NOT_HASH_BOUND") {
    throw new Error("哨兵证据警告缺失");
  }
  timestamp(sentinel.report_generated_at, "数据质量 sentinel report_generated_at");
  sha(sentinel.report_sha256, "数据质量 sentinel report_sha256");
  stringArray(sentinel.required_failures, "数据质量 sentinel required_failures");
  if (!Array.isArray(sentinel.sentinels) || sentinel.sentinels.length !== 10) {
    throw new Error("数据质量哨兵必须恰含 S1-S10");
  }
  const expectedSentinels = new Set(Array.from({ length: 10 }, (_, index) => `S${index + 1}`));
  sentinel.sentinels.forEach((item, index) => {
    const result = record(item, `数据质量 sentinel[${index}]`);
    const name = text(result.sentinel, `数据质量 sentinel[${index}].sentinel`);
    if (!expectedSentinels.delete(name)) throw new Error("数据质量哨兵重复或未知");
    const resultStatus = status(result.status, `数据质量 ${name}.status`);
    const accepted = booleanValue(result.accepted_for_signal, `数据质量 ${name}.accepted`);
    integer(result.anomaly_count, `数据质量 ${name}.anomaly_count`);
    record(result.metrics, `数据质量 ${name}.metrics`);
    const allowed = name === "S10" ? new Set(["PASS", "NOT_APPLICABLE"]) : new Set(["PASS"]);
    if (accepted !== allowed.has(resultStatus)) throw new Error(`数据质量 ${name} 接受语义不一致`);
  });
  if (expectedSentinels.size) throw new Error("数据质量哨兵缺项");

  const bse = record(root.bse_gate, "数据质量 bse_gate");
  status(bse.status, "数据质量 bse_gate.status");
  ["validated_market_batch_bse_count", "returned_security_bse_count", "excluded_bse_reference_count"].forEach(
    (name) => {
      if (integer(bse[name], `数据质量 ${name}`) !== 0) throw new Error("数据质量北交所计数非零");
    }
  );
  noBse(value);
}

export function assertSystemRun(value: unknown): asserts value is SystemRunData {
  const root = record(value, "系统运行");
  const overall = status(root.status, "系统运行 status");
  const core = status(root.core_status, "系统运行 core_status");
  status(root.notification_status, "系统运行 notification_status");
  if (overall !== core) throw new Error("系统运行综合状态与核心状态不一致");
  date(root.as_of, "系统运行 as_of");
  const messageCount = integer(root.core_failure_message_count, "系统运行 core_failure_message_count");
  const messageIds = stringArray(root.core_failure_message_ids, "系统运行 core_failure_message_ids");
  if (messageIds.length !== messageCount || !messageIds.every((item) => MESSAGE_ID.test(item))) {
    throw new Error("系统运行核心故障消息身份无效");
  }
  const expectedStages = [
    "daily_increment",
    "sentinels",
    "next_open_reconciliation",
    "shadow_signal",
    "paper_cycle",
    "paper_replay"
  ];
  if (!Array.isArray(root.stages) || root.stages.length !== expectedStages.length) {
    throw new Error("系统运行阶段数量错误");
  }
  root.stages.forEach((item, index) => {
    const stage = assertOperationsStage(item, `系统运行 stage[${index}]`);
    if (stage.stage !== expectedStages[index]) throw new Error("系统运行阶段顺序错误");
  });

  const notifications = record(root.notifications, "系统运行 notifications");
  status(notifications.status, "系统运行 notifications.status");
  [
    "message_count",
    "attempt_count",
    "failed_attempt_count",
    "recovered_message_count",
    "legacy_unaddressable_attempt_count"
  ].forEach((name) => integer(notifications[name], `系统运行 notifications.${name}`));

  const release = record(root.release_identity, "系统运行 release_identity");
  status(release.status, "系统运行 release.status");
  status(release.audit_chain_status, "系统运行 release.audit_chain_status");
  timestamp(release.recorded_at, "系统运行 release.recorded_at");
  if (typeof release.image_id !== "string" || !IMAGE_SHA256.test(release.image_id)) {
    throw new Error("系统运行 release 镜像身份无效");
  }
  sha(release.code_snapshot_sha256, "系统运行 release.code_snapshot_sha256");
  if (typeof release.git_head !== "string" || !/^(?:[0-9a-f]{40}|[0-9a-f]{64})$/.test(release.git_head)) {
    throw new Error("系统运行 release Git 身份无效");
  }
  if (booleanValue(release.read_only_rootfs, "系统运行 release.read_only_rootfs") !== true) {
    throw new Error("系统运行 release 不是只读根");
  }
  stringArray(release.mount_destinations, "系统运行 release.mount_destinations").forEach((item) => {
    if (!item.startsWith("/workspace/")) throw new Error("系统运行 release 挂载目标无效");
  });
  if (release.live_container_identity_status !== "NOT_EVALUATED") {
    throw new Error("系统运行错误声称已读取实时容器身份");
  }
  text(release.live_container_identity_reason, "系统运行 release.live_container_identity_reason");
  sha(release.record_sha256, "系统运行 release.record_sha256");

  const heartbeat = record(root.scheduler_heartbeat, "系统运行 scheduler_heartbeat");
  if (heartbeat.status !== "RECORDED" || heartbeat.scope !== "RECORDED_HEARTBEAT_ONLY") {
    throw new Error("系统运行 scheduler 心跳范围被扩大");
  }
  text(heartbeat.recorded_status, "系统运行 scheduler recorded_status");
  text(heartbeat.detail, "系统运行 scheduler detail");
  timestamp(heartbeat.updated_at, "系统运行 scheduler updated_at");
  if (heartbeat.freshness_status !== "NOT_EVALUATED") {
    throw new Error("系统运行错误推导 scheduler 实时新鲜度");
  }
  noBse(value);
}

export function assertNotification(value: unknown): asserts value is NotificationData {
  const root = record(value, "通知详情");
  const messageId = text(root.message_id, "通知详情 message_id");
  if (!MESSAGE_ID.test(messageId)) throw new Error("通知详情 message_id 无效");
  const event = text(root.event, "通知详情 event");
  status(root.status, "通知详情 status");
  const attemptCount = integer(root.attempt_count, "通知详情 attempt_count");
  const failedCount = integer(root.failed_attempt_count, "通知详情 failed_attempt_count");
  if (failedCount > attemptCount) throw new Error("通知详情失败次数超过尝试数");
  booleanValue(root.recovered, "通知详情 recovered");
  const duplicateRisk = booleanValue(root.duplicate_delivery_risk, "通知详情 duplicate_delivery_risk");
  if (!Array.isArray(root.attempts) || root.attempts.length !== attemptCount) {
    throw new Error("通知详情尝试数与明细不一致");
  }
  if (duplicateRisk !== (attemptCount > 1)) throw new Error("通知详情重复投递风险语义不一致");
  const identities = new Set<string>();
  root.attempts.forEach((item, index) => {
    const attempt = record(item, `通知详情 attempt[${index}]`);
    const number = integer(attempt.attempt, `通知详情 attempt[${index}].attempt`);
    const maximum = integer(attempt.max_attempts, `通知详情 attempt[${index}].max_attempts`);
    if (number < 1 || maximum < number) throw new Error("通知详情尝试序号无效");
    const deliveredAt = timestamp(attempt.delivered_at, `通知详情 attempt[${index}].delivered_at`);
    if (attempt.message_id !== messageId || attempt.event !== event) throw new Error("通知详情尝试身份不一致");
    status(attempt.status, `通知详情 attempt[${index}].status`);
    if (typeof attempt.error_type !== "string") throw new Error("通知详情 error_type 格式错误");
    booleanValue(attempt.recovered, `通知详情 attempt[${index}].recovered`);
    booleanValue(attempt.retryable, `通知详情 attempt[${index}].retryable`);
    safeReference(attempt.source_ref, `通知详情 attempt[${index}].source_ref`);
    const identity = `${number}|${deliveredAt}`;
    if (identities.has(identity)) throw new Error("通知详情尝试身份重复");
    identities.add(identity);
  });
  noBse(value);
}

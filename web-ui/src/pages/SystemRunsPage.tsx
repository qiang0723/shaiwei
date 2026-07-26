import {
  BellOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  FileSearchOutlined,
  SyncOutlined,
  WarningOutlined
} from "@ant-design/icons";
import { Alert, Button, Descriptions, Drawer, Steps } from "antd";
import { useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { fetchNotification, fetchSystemRuns } from "../api";
import { useAsOf } from "../components/AppShell";
import { DataTable, type DataColumn } from "../components/DataTable";
import { MetricCard } from "../components/MetricCard";
import { PageHeader } from "../components/PageHeader";
import { PageError, PageLoading, RefreshNotice } from "../components/RequestState";
import { StatusBadge } from "../components/StatusBadge";
import { displayDate, formatDateTime, formatNumber, STATUS_LABELS } from "../format";
import { notificationCopy, systemCoreCopy } from "../operationsPresentation";
import type {
  EvidencePayload,
  NotificationAttempt,
  OperationsStage
} from "../types";

const STAGE_LABELS: Record<string, string> = {
  daily_increment: "日增量",
  sentinels: "数据哨兵",
  next_open_reconciliation: "次日开盘对账",
  shadow_signal: "影子信号",
  paper_cycle: "模拟仓",
  paper_replay: "独立重放"
};

function stageStepStatus(stage: OperationsStage): "finish" | "process" | "wait" | "error" {
  if (stage.status === "FAIL") return "error";
  if (["NOT_READY", "NOT_DUE", "NOT_APPLICABLE", "NOT_EVALUATED"].includes(stage.status)) return "wait";
  return "finish";
}

function NotificationDrawer({
  messageId,
  asOf,
  onClose
}: {
  messageId: string | null;
  asOf: string;
  onClose: () => void;
}) {
  const query = useQuery({
    queryKey: ["notification", messageId, asOf],
    queryFn: ({ signal }) => fetchNotification(messageId ?? "", asOf, signal),
    enabled: messageId !== null,
    retry: false
  });
  const columns: DataColumn<NotificationAttempt>[] = [
    {
      title: "尝试",
      dataIndex: "attempt",
      key: "attempt",
      align: "right",
      render: (_value, row) => `${row.attempt} / ${row.max_attempts}`
    },
    { title: "状态", dataIndex: "status", key: "status", render: (_value, row) => <StatusBadge status={row.status} compact /> },
    { title: "投递时刻", dataIndex: "delivered_at", key: "delivered_at", render: (_value, row) => formatDateTime(row.delivered_at) },
    { title: "可重试", dataIndex: "retryable", key: "retryable", render: (_value, row) => row.retryable ? "是" : "否" },
    { title: "恢复标记", dataIndex: "recovered", key: "recovered", render: (_value, row) => row.recovered ? "是" : "否" },
    { title: "失败原因", dataIndex: "error_type", key: "error_type", render: (_value, row) => row.error_type ? "投递失败（技术原因见下方）" : "—" }
  ];
  return (
    <Drawer
      title={<span><BellOutlined /> 通知投递证据</span>}
      open={messageId !== null}
      onClose={onClose}
      width={760}
      destroyOnHidden
    >
      {query.isPending ? <PageLoading label="正在读取独立通知证据切片…" /> : null}
      {query.isError ? <PageError error={query.error} retry={() => query.refetch()} /> : null}
      {query.data ? (
        <div className="notification-detail-stack">
          <Alert
            type="info"
            showIcon
            message="这是独立证据切片"
            description={`截至 ${displayDate(query.data.meta.as_of)}，技术证据已锁定；本切片不静默合并进系统页主结论。`}
          />
          <Descriptions column={1} size="small" bordered>
            <Descriptions.Item label="事件">核心周期故障通知</Descriptions.Item>
            <Descriptions.Item label="终态"><StatusBadge status={query.data.data.status} /></Descriptions.Item>
            <Descriptions.Item label="尝试 / 失败">{query.data.data.attempt_count} / {query.data.data.failed_attempt_count}</Descriptions.Item>
            <Descriptions.Item label="恢复">{query.data.data.recovered ? "是" : "否"}</Descriptions.Item>
            <Descriptions.Item label="重复投递风险">{query.data.data.duplicate_delivery_risk ? "存在" : "无"}</Descriptions.Item>
          </Descriptions>
          <DataTable
            label="通知逐次投递记录"
            columns={columns}
            data={query.data.data.attempts}
            rowKey="delivered_at"
            minimumWidth="wide"
          />
          <details className="technical-details drawer-technical-details">
            <summary>查看通知技术字段与脱敏来源</summary>
            <dl>
              <div><dt>消息编号</dt><dd><code>{query.data.data.message_id}</code></dd></div>
              <div><dt>事件枚举</dt><dd><code>{query.data.data.event}</code></dd></div>
              {query.data.data.attempts.map((attempt) => (
                <div key={`${attempt.attempt}-${attempt.delivered_at}`}>
                  <dt>第 {attempt.attempt} 次尝试</dt>
                  <dd><code>{attempt.error_type || "NO_ERROR"}</code><br /><code>{attempt.source_ref}</code></dd>
                </div>
              ))}
            </dl>
          </details>
          <p className="evidence-boundary">
            只显示后端批准的九字段和脱敏来源；不返回消息正文、Webhook、签名、环境变量或原始异常。
          </p>
        </div>
      ) : null}
    </Drawer>
  );
}

export default function SystemRunsPage() {
  const { asOf } = useAsOf();
  const [selectedMessage, setSelectedMessage] = useState<string | null>(null);
  const messageTrigger = useRef<HTMLElement | null>(null);
  const query = useQuery({
    queryKey: ["system-runs", asOf || "latest"],
    queryFn: ({ signal }) => fetchSystemRuns(asOf, signal),
    placeholderData: (previous) => previous
  });

  if (query.isPending) return <PageLoading label="正在重放最新系统运行证据…" />;
  if (query.isError) return <PageError error={query.error} retry={() => query.refetch()} />;

  const { data: d, meta } = query.data;
  const coreCopy = systemCoreCopy(d.core_status);
  const deliveryCopy = notificationCopy(d.notification_status);
  const evidence: EvidencePayload = {
    title: "系统运行原子快照",
    snapshotId: meta.snapshot_id,
    asOf: meta.as_of,
    generatedAt: meta.generated_at,
    hashes: {
      release_record_sha256: d.release_identity.record_sha256,
      release_code_snapshot_sha256: d.release_identity.code_snapshot_sha256,
      ...meta.evidence_hashes
    },
    sources: meta.source_refs,
    facts: [
      { label: "核心任务", value: STATUS_LABELS[d.core_status] },
      { label: "通知通道", value: STATUS_LABELS[d.notification_status] },
      { label: "发布审计链", value: STATUS_LABELS[d.release_identity.audit_chain_status] },
      { label: "实时容器身份", value: STATUS_LABELS[d.release_identity.live_container_identity_status] }
    ],
    technicalFacts: [
      { label: "镜像编号", value: d.release_identity.image_id },
      { label: "Git 身份", value: d.release_identity.git_head },
      { label: "Scheduler 记录状态", value: d.scheduler_heartbeat.recorded_status },
      { label: "Scheduler 记录详情", value: d.scheduler_heartbeat.detail },
      ...d.release_identity.mount_destinations.map((value, index) => ({ label: `只读挂载 ${index + 1}`, value })),
      ...d.stages.flatMap((stage) => [
        ...(stage.first_error_type ? [{ label: `${STAGE_LABELS[stage.stage] ?? stage.stage} 首次错误`, value: stage.first_error_type }] : []),
        ...(stage.terminal_run_id ? [{ label: `${STAGE_LABELS[stage.stage] ?? stage.stage} 运行编号`, value: stage.terminal_run_id }] : [])
      ])
    ]
  };
  const stageColumns: DataColumn<OperationsStage>[] = [
    { title: "步骤", dataIndex: "stage", key: "stage", fixed: "left", render: (_value, row) => STAGE_LABELS[row.stage] ?? row.stage },
    { title: "终态", dataIndex: "status", key: "status", render: (_value, row) => <StatusBadge status={row.status} compact /> },
    { title: "尝试", dataIndex: "attempt_count", key: "attempt_count", align: "right" },
    { title: "失败", dataIndex: "failed_attempt_count", key: "failed_attempt_count", align: "right" },
    { title: "恢复", dataIndex: "recovered", key: "recovered", render: (_value, row) => row.recovered ? "是" : "否" },
    { title: "首次错误", dataIndex: "first_error_type", key: "first_error_type", render: (_value, row) => row.first_error_type ? "存在（技术证据可查）" : "—" },
    { title: "终态时间", dataIndex: "terminal_finished_at", key: "terminal_finished_at", render: (_value, row) => formatDateTime(row.terminal_finished_at) },
    { title: "运行证据", dataIndex: "terminal_run_id", key: "terminal_run_id", render: (_value, row) => row.terminal_run_id ? "已登记" : "—" }
  ];

  const closeNotification = () => {
    setSelectedMessage(null);
    window.setTimeout(() => messageTrigger.current?.focus(), 0);
  };

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="SYSTEM OPERATIONS"
        title="系统运行"
        description="核心任务、通知与实时身份分列；最终通过不覆盖先前失败。"
        status={d.status}
        asOf={d.as_of}
        generatedAt={meta.generated_at}
        evidence={evidence}
      />
      {query.isFetching ? <RefreshNotice asOf={d.as_of} generatedAt={meta.generated_at} /> : null}

      <section className="system-status-hero" aria-label="核心任务与通知通道状态">
        <article className={coreCopy.tone}>
          <div className={`operations-hero-icon ${coreCopy.tone}`} aria-hidden="true"><SyncOutlined /></div>
          <div>
            <span className="section-kicker">CORE CYCLE</span>
            <h2>{coreCopy.title}</h2>
            <p>{coreCopy.detail} 当前登记 {d.core_failure_message_count} 个核心故障消息。</p>
          </div>
          <StatusBadge status={d.core_status} />
        </article>
        <article className={deliveryCopy.tone}>
          <div className={`operations-hero-icon ${deliveryCopy.tone}`} aria-hidden="true"><BellOutlined /></div>
          <div>
            <span className="section-kicker">DELIVERY CHANNEL</span>
            <h2>{deliveryCopy.title}</h2>
            <p>{deliveryCopy.detail} 当前 {d.notifications.attempt_count} 次尝试、{d.notifications.failed_attempt_count} 次失败、{d.notifications.recovered_message_count} 个恢复。</p>
          </div>
          <StatusBadge status={d.notification_status} />
        </article>
      </section>

      <section aria-labelledby="run-timeline-heading">
        <div className="section-heading">
          <div>
            <span className="section-kicker">CONTROLLED SEQUENCE</span>
            <h2 id="run-timeline-heading">最新日周期</h2>
          </div>
          <span className="section-note">周期日期 {displayDate(d.as_of)}</span>
        </div>
        <article className="surface-panel operations-timeline">
          <Steps
            responsive
            items={d.stages.map((stage) => ({
              title: STAGE_LABELS[stage.stage] ?? stage.stage,
              description: stage.recovered ? "失败后恢复" : STATUS_LABELS[stage.status],
              status: stageStepStatus(stage),
              icon: stage.recovered ? <SyncOutlined /> : undefined
            }))}
          />
        </article>
      </section>

      <section className="table-surface" aria-labelledby="stage-detail-heading">
        <div className="section-heading">
          <div>
            <span className="section-kicker">ATTEMPTS & RECOVERY</span>
            <h2 id="stage-detail-heading">步骤与恢复证据</h2>
          </div>
          <span className="section-note">终态通过不删除首次错误</span>
        </div>
        <DataTable
          label="系统运行步骤"
          columns={stageColumns}
          data={d.stages}
          rowKey="stage"
          minimumWidth="wide"
        />
        {d.stages.some((stage) => stage.recovered) ? (
          <Alert
            className="operations-boundary-alert"
            type="warning"
            showIcon
            message="已检测到失败后恢复"
            description={d.stages.filter((stage) => stage.recovered).map((stage) => `${STAGE_LABELS[stage.stage]}：曾失败，随后恢复；技术错误名可在技术证据中核对`).join("；")}
          />
        ) : null}
      </section>

      <section aria-labelledby="notification-heading">
        <div className="section-heading">
          <div>
            <span className="section-kicker">NOTIFICATIONS</span>
            <h2 id="notification-heading">飞书守护与告警</h2>
          </div>
          <StatusBadge status={d.notifications.status} />
        </div>
        <div className="metric-grid operations-metric-grid">
          <MetricCard label="可查看消息" value={formatNumber(d.notifications.message_count, 0)} detail="可打开独立投递证据" icon={<BellOutlined />} />
          <MetricCard label="投递尝试" value={formatNumber(d.notifications.attempt_count, 0)} detail={`${d.notifications.failed_attempt_count} 次失败`} tone={d.notifications.failed_attempt_count ? "warning" : "default"} icon={<SyncOutlined />} />
          <MetricCard label="恢复消息" value={formatNumber(d.notifications.recovered_message_count, 0)} detail="失败记录仍保留" icon={<CheckCircleOutlined />} />
          <MetricCard label="旧版不可查看" value={formatNumber(d.notifications.legacy_unaddressable_attempt_count, 0)} detail="缺少稳定消息编号，不伪造详情" tone="warning" icon={<WarningOutlined />} />
        </div>
        <article className="surface-panel core-message-panel">
          <div>
            <strong>核心故障消息</strong>
            <p>每条详情来自已登记运行证据，是独立切片，不反写本页结论。</p>
          </div>
          <div className="message-id-list">
            {d.core_failure_message_ids.map((messageId, index) => (
              <Button
                key={messageId}
                ref={(node) => { if (selectedMessage === messageId || d.core_failure_message_ids.length === 1) messageTrigger.current = node; }}
                icon={<FileSearchOutlined />}
                onClick={(event) => {
                  messageTrigger.current = event.currentTarget;
                  setSelectedMessage(messageId);
                }}
              >
                <span title={messageId}>查看故障消息 {index + 1}</span>
              </Button>
            ))}
          </div>
        </article>
      </section>

      <section className="two-column-support">
        <article className="surface-panel" aria-labelledby="release-heading">
          <div className="section-heading compact-heading">
            <div>
              <span className="section-kicker">REGISTERED RELEASE</span>
              <h2 id="release-heading">运行前登记身份</h2>
            </div>
            <StatusBadge status={d.release_identity.status} />
          </div>
          <dl className="detail-list">
            <div><dt>审计完整性链</dt><dd><StatusBadge status={d.release_identity.audit_chain_status} compact /></dd></div>
            <div><dt>登记时刻</dt><dd>{formatDateTime(d.release_identity.recorded_at)}</dd></div>
            <div><dt>代码证据</dt><dd>已锁定</dd></div>
            <div><dt>发布身份</dt><dd>已登记</dd></div>
            <div><dt>只读根</dt><dd>{d.release_identity.read_only_rootfs ? "是" : "否"}</dd></div>
            <div><dt>实时容器身份</dt><dd><StatusBadge status={d.release_identity.live_container_identity_status} compact /></dd></div>
          </dl>
          <p className="evidence-boundary">已登记发布身份与当前只读容器一致；这里只证明最后一次受控启动通过，不替代实时运维检查。</p>
          <div className="mount-chip-list" aria-label="只读挂载摘要">
            <span>{d.release_identity.mount_destinations.length} 个只读挂载已登记，完整路径见技术证据</span>
          </div>
        </article>

        <article className="surface-panel" aria-labelledby="heartbeat-heading">
          <div className="section-heading compact-heading">
            <div>
              <span className="section-kicker">RECORDED HEARTBEAT</span>
              <h2 id="heartbeat-heading">Scheduler 已登记心跳</h2>
            </div>
            <span className="recorded-badge"><ClockCircleOutlined /> 已登记</span>
          </div>
          <dl className="detail-list">
            <div><dt>记录状态</dt><dd>已保存</dd></div>
            <div><dt>记录内容</dt><dd>最近一次心跳记录可查</dd></div>
            <div><dt>记录时刻</dt><dd>{formatDateTime(d.scheduler_heartbeat.updated_at)}</dd></div>
            <div><dt>新鲜度推导</dt><dd><StatusBadge status={d.scheduler_heartbeat.freshness_status} compact /></dd></div>
          </dl>
          <Alert
            type="info"
            showIcon
            message="浏览器不推导实时健康"
            description="该字段只表示项目内最近一条已登记记录；实时 Docker inspect 不在 Web 权限内。"
          />
        </article>
      </section>

      <NotificationDrawer messageId={selectedMessage} asOf={d.as_of} onClose={closeNotification} />
    </div>
  );
}

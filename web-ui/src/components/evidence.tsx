import { CopyOutlined, SafetyCertificateOutlined } from "@ant-design/icons";
import { Alert, Button, Descriptions, Drawer, Empty, List, message } from "antd";
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode
} from "react";
import { displayDate, formatDateTime, shortHash } from "../format";
import type { EvidencePayload } from "../types";

interface EvidenceContextValue {
  openEvidence: (payload: EvidencePayload, trigger?: HTMLElement | null) => void;
}

const EvidenceContext = createContext<EvidenceContextValue | null>(null);

const TECHNICAL_LABELS: Record<string, string> = {
  bundle: "冻结证据包",
  controlled_code_snapshot: "受控代码快照",
  code_snapshot_sha256: "代码快照",
  release_code_snapshot_sha256: "发布代码快照",
  data_snapshot_sha256: "数据快照",
  reconstructed_data_snapshot_sha256: "重建数据快照",
  model_artifact_sha256: "模型产物",
  model_spec_sha256: "模型规格",
  qlib_artifact_sha256: "Qlib 研究产物",
  signal_sha256: "信号产物",
  source_file_sha256: "来源文件",
  actual_weight_artifact_sha256: "实际权重产物",
  sentinel_report_sha256: "哨兵报告",
  release_record_sha256: "发布登记"
};

function technicalLabel(value: string): string {
  if (TECHNICAL_LABELS[value]) return TECHNICAL_LABELS[value];
  if (value === "latest_paper_artifact_sha256") return "最新模拟组合产物";
  if (value === "latest_signal_file_sha256") return "最新信号文件";
  if (value === "latest_signal_sha256") return "最新信号记录";
  if (value === "notification_evidence_sha256") return "通知证据";
  if (value === "paper_account_rows_sha256") return "模拟账户账本";
  if (value === "paper_event_rows_sha256") return "模拟组合事件账本";
  if (value === "paper_run_rows_sha256") return "模拟组合运行账本";
  if (value === "previous_signal_file_sha256") return "上一期信号文件";
  if (value === "shadow_reconciliation_rows_sha256") return "影子执行核对账本";
  if (value === "shadow_run_rows_sha256") return "影子运行账本";
  if (/^paper_artifact_\d+_sha256$/.test(value)) return `模拟组合产物 ${value.split("_")[2]}`;
  if (/^reconciliation_artifact_\d+_sha256$/.test(value)) return `执行核对产物 ${value.split("_")[2]}`;
  if (/^data_shadow_signals_.+_sha256$/.test(value)) return "信号数据来源文件";
  if (value === "ledger_daily_runs.csv_sha256") return "每日运行账本";
  if (value === "ledger_ingest_batches.csv_sha256") return "数据采集批次账本";
  if (value === "ledger_paper_runs.csv_sha256") return "模拟组合运行账本";
  if (value === "ledger_shadow_reconciliations.csv_sha256") return "影子执行核对账本";
  if (value === "ledger_shadow_runs.csv_sha256") return "影子运行账本";
  if (/^logs_notifications_feishu_\d{8}\.jsonl_sha256$/.test(value)) return "通知通道记录";
  if (value === "logs_releases_scheduler_releases.jsonl_sha256") return "调度发布记录";
  if (value === "logs_scheduler_health.json_sha256") return "调度健康记录";
  if (/^logs_sentinels_.+_sha256$/.test(value)) return "数据哨兵报告";
  if (/^factor_evidence_\d+$/.test(value)) return `因子证据 ${value.split("_").at(-1)}`;
  if (/^experiment_evidence_\d+$/.test(value)) return `实验证据 ${value.split("_").at(-1)}`;
  if (/^decision_\d+_report$/.test(value)) return `判决报告 ${value.split("_")[1]}`;
  if (/^decision_\d+_evidence$/.test(value)) return `判决证据 ${value.split("_")[1]}`;
  return "其他完整性校验值";
}

export function useEvidence(): EvidenceContextValue {
  const value = useContext(EvidenceContext);
  if (!value) throw new Error("EvidenceProvider 缺失");
  return value;
}

export function EvidenceProvider({ children }: { children: ReactNode }) {
  const [payload, setPayload] = useState<EvidencePayload | null>(null);
  const returnFocus = useRef<HTMLElement | null>(null);
  const [messageApi, contextHolder] = message.useMessage();

  const openEvidence = useCallback((next: EvidencePayload, trigger?: HTMLElement | null) => {
    returnFocus.current = trigger ?? (document.activeElement as HTMLElement | null);
    setPayload(next);
  }, []);

  const close = useCallback(() => {
    setPayload(null);
    window.setTimeout(() => returnFocus.current?.focus(), 0);
  }, []);

  const context = useMemo(() => ({ openEvidence }), [openEvidence]);
  const copy = useCallback(
    async (value: string) => {
      try {
        await navigator.clipboard.writeText(value);
        messageApi.success("已复制证据值");
      } catch {
        messageApi.error("浏览器未允许复制，请手动选择文本");
      }
    },
    [messageApi]
  );

  return (
    <EvidenceContext.Provider value={context}>
      {contextHolder}
      {children}
      <Drawer
        className="evidence-drawer"
        title={
          <span>
            <SafetyCertificateOutlined /> {payload?.title ?? "证据"}
          </span>
        }
        open={payload !== null}
        onClose={close}
        width={560}
        destroyOnHidden
      >
        {payload ? (
          <div className="evidence-content">
            <Alert
              type="info"
              showIcon
              message="技术证据已锁定，可按需核验"
              description="日期和业务结论优先展示；哈希、快照编号与来源引用仅用于复核一致性。"
            />
            <Descriptions column={1} size="small" bordered>
              {payload.asOf ? (
                <Descriptions.Item label="数据截至">{displayDate(payload.asOf)}</Descriptions.Item>
              ) : null}
              {payload.generatedAt ? (
                <Descriptions.Item label="证据生成">
                  {formatDateTime(payload.generatedAt)}
                </Descriptions.Item>
              ) : null}
              {payload.facts?.map((fact) => (
                <Descriptions.Item label={fact.label} key={fact.label}>
                  {fact.value}
                </Descriptions.Item>
              ))}
            </Descriptions>
            <details className="technical-details evidence-technical-details">
              <summary>展开技术标识与来源</summary>
              {payload.snapshotId ? (
                <div className="technical-snapshot">
                  <span>证据快照编号</span>
                  <code title={payload.snapshotId}>{shortHash(payload.snapshotId)}</code>
                  <Button
                    type="text"
                    size="small"
                    aria-label="复制完整证据快照编号"
                    icon={<CopyOutlined />}
                    onClick={() => copy(payload.snapshotId ?? "")}
                  />
                </div>
              ) : null}
              {payload.technicalFacts?.length ? (
                <section>
                  <h2>技术字段</h2>
                  <Descriptions column={1} size="small" bordered>
                    {payload.technicalFacts.map((fact) => (
                      <Descriptions.Item label={fact.label} key={fact.label}>
                        <code className="source-ref">{fact.value}</code>
                      </Descriptions.Item>
                    ))}
                  </Descriptions>
                </section>
              ) : null}
              <section>
                <h2>完整性校验值</h2>
                {Object.keys(payload.hashes).length ? (
                  <List
                    size="small"
                    dataSource={Object.entries(payload.hashes)}
                    renderItem={([label, value]) => (
                      <List.Item
                        actions={[
                          <Button
                            key="copy"
                            type="text"
                            aria-label={`复制${technicalLabel(label)}`}
                            icon={<CopyOutlined />}
                            onClick={() => copy(value)}
                          />
                        ]}
                      >
                        <List.Item.Meta
                          title={technicalLabel(label)}
                          description={<code className="full-hash">{value}</code>}
                        />
                      </List.Item>
                    )}
                  />
                ) : (
                  <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前视图没有额外校验值" />
                )}
              </section>

              <section>
                <h2>只读来源引用</h2>
                {payload.sources.length ? (
                  <List
                    size="small"
                    dataSource={payload.sources}
                    renderItem={(source) => (
                      <List.Item>
                        <code className="source-ref">{source}</code>
                      </List.Item>
                    )}
                  />
                ) : (
                  <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="未返回来源引用" />
                )}
              </section>
            </details>
            <p className="evidence-boundary">
              证据抽屉只显示后端批准的脱敏引用；不提供打开文件、编辑、修数或重跑。
            </p>
          </div>
        ) : null}
      </Drawer>
    </EvidenceContext.Provider>
  );
}

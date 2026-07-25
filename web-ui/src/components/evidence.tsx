import { CopyOutlined, SafetyCertificateOutlined } from "@ant-design/icons";
import { Button, Descriptions, Drawer, Empty, List, message } from "antd";
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
            <Descriptions column={1} size="small" bordered>
              {payload.snapshotId ? (
                <Descriptions.Item label="快照">
                  <code title={payload.snapshotId}>{shortHash(payload.snapshotId)}</code>
                  <Button
                    type="text"
                    size="small"
                    aria-label="复制完整快照哈希"
                    icon={<CopyOutlined />}
                    onClick={() => copy(payload.snapshotId ?? "")}
                  />
                </Descriptions.Item>
              ) : null}
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

            <section>
              <h2>证据哈希</h2>
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
                          aria-label={`复制 ${label}`}
                          icon={<CopyOutlined />}
                          onClick={() => copy(value)}
                        />
                      ]}
                    >
                      <List.Item.Meta
                        title={label}
                        description={<code className="full-hash">{value}</code>}
                      />
                    </List.Item>
                  )}
                />
              ) : (
                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前视图没有额外哈希" />
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
            <p className="evidence-boundary">
              证据抽屉只显示后端批准的脱敏引用；不提供打开文件、编辑、修数或重跑。
            </p>
          </div>
        ) : null}
      </Drawer>
    </EvidenceContext.Provider>
  );
}

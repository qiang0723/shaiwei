import { ReloadOutlined, SafetyCertificateOutlined, SyncOutlined } from "@ant-design/icons";
import { Button, Skeleton } from "antd";
import { UiQueryError } from "../api";
import { displayDate, formatDateTime } from "../format";

export function PageLoading({ label = "正在核对只读证据…" }: { label?: string }) {
  return (
    <section className="request-state" role="status" aria-live="polite">
      <div className="loading-label">
        <SafetyCertificateOutlined aria-hidden="true" />
        <span>{label}</span>
      </div>
      <Skeleton active paragraph={{ rows: 8 }} />
    </section>
  );
}

export function RefreshNotice({ asOf, generatedAt }: { asOf: string; generatedAt: string }) {
  return (
    <div className="refresh-notice" role="status" aria-live="polite">
      <SyncOutlined spin aria-hidden="true" />
      <span>
        <strong>刷新中</strong>；当前仍显示截至 {displayDate(asOf)}、生成于 {formatDateTime(generatedAt)}
        的上一份已核验证据。
      </span>
    </div>
  );
}

export function PageError({ error, retry }: { error: unknown; retry: () => void }) {
  const queryError = error instanceof UiQueryError ? error : null;
  const code = queryError?.code ?? "UNEXPECTED_UI_ERROR";
  const message = queryError?.message ?? "页面无法核对当前证据";
  return (
    <section className="request-error" role="alert">
      <div className="error-kicker">只读查询已阻断</div>
      <h1>{message}</h1>
      <p className="muted">旧数字不会继续作为当前证据展示。</p>
      <Button icon={<ReloadOutlined />} onClick={retry}>
        重新读取
      </Button>
      <details className="technical-details request-technical-details">
        <summary>查看技术诊断信息</summary>
        <dl>
          <div><dt>错误码</dt><dd><code>{code}</code></dd></div>
          {queryError?.requestId ? <div><dt>请求编号</dt><dd><code>{queryError.requestId}</code></dd></div> : null}
        </dl>
        <p>这些字段用于排障和审计，不代表新的业务结论。</p>
      </details>
    </section>
  );
}

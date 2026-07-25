import { Button } from "antd";
import { FileSearchOutlined } from "@ant-design/icons";
import { displayDate, formatDateTime } from "../format";
import type { DomainStatus, EvidencePayload } from "../types";
import { useEvidence } from "./evidence";
import { StatusBadge } from "./StatusBadge";

export function PageHeader({
  eyebrow,
  title,
  description,
  status,
  asOf,
  generatedAt,
  evidence
}: {
  eyebrow: string;
  title: string;
  description: string;
  status: DomainStatus;
  asOf: string;
  generatedAt: string;
  evidence: EvidencePayload;
}) {
  const { openEvidence } = useEvidence();
  return (
    <header className="page-header">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <div className="page-title-line">
          <h1>{title}</h1>
          <StatusBadge status={status} />
        </div>
        <p>{description}</p>
      </div>
      <div className="page-header-meta">
        <div>
          <span>数据截至</span>
          <strong>{displayDate(asOf)}</strong>
        </div>
        <div>
          <span>证据生成</span>
          <strong>{formatDateTime(generatedAt)}</strong>
        </div>
        <Button icon={<FileSearchOutlined />} onClick={() => openEvidence(evidence)}>
          查看证据
        </Button>
      </div>
    </header>
  );
}

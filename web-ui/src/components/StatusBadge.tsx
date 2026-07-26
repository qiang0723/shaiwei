import {
  CheckCircleFilled,
  ClockCircleFilled,
  CloseCircleFilled,
  ExclamationCircleFilled,
  InfoCircleFilled,
  MinusCircleFilled,
  StopFilled
} from "@ant-design/icons";
import { Tag } from "antd";
import type { ReactNode } from "react";
import { STATUS_LABELS } from "../format";
import type { DomainStatus } from "../types";

const ICONS: Record<DomainStatus, ReactNode> = {
  PASS: <CheckCircleFilled />,
  WARN: <ExclamationCircleFilled />,
  FAIL: <CloseCircleFilled />,
  STALE: <ClockCircleFilled />,
  NOT_READY: <InfoCircleFilled />,
  NOT_APPLICABLE: <MinusCircleFilled />,
  NO_DATA: <StopFilled />,
  OBSERVING: <ClockCircleFilled />,
  NOT_DUE: <ClockCircleFilled />,
  NOT_EVALUATED: <MinusCircleFilled />
};

export function StatusBadge({
  status,
  compact: _compact = false
}: {
  status: DomainStatus;
  compact?: boolean;
}) {
  return (
    <Tag
      className={`status-badge status-${status.toLowerCase()}`}
      icon={ICONS[status]}
      title={`${STATUS_LABELS[status]} · ${status}`}
      aria-label={`${STATUS_LABELS[status]}，机器状态 ${status}`}
    >
      {STATUS_LABELS[status]}
    </Tag>
  );
}

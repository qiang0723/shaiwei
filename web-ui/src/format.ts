import type { DomainStatus } from "./types";

export const STATUS_LABELS: Record<DomainStatus, string> = {
  PASS: "通过",
  WARN: "需关注",
  FAIL: "失败",
  STALE: "已过期",
  NOT_READY: "未就绪",
  NOT_APPLICABLE: "不适用",
  NO_DATA: "无数据",
  OBSERVING: "观察中",
  NOT_DUE: "尚未到期",
  NOT_EVALUATED: "未评估"
};

const REASON_LABELS: Record<string, string> = {
  OPERATIONAL_WARN: "核心周期曾失败后恢复",
  NOTIFICATION_WARN: "通知通道曾失败后恢复",
  EVIDENCE_WARN: "证据链存在非阻断提示",
  PERFORMANCE_NOT_READY: "前瞻观察尚未达到展示门槛"
};

export function reasonLabel(reason: string): string {
  return REASON_LABELS[reason] ?? reason;
}

export function toNumber(value: string | number | null | undefined): number {
  const parsed = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(parsed)) {
    throw new Error("INVALID_NUMERIC_FIELD");
  }
  return parsed;
}

export function formatMoney(value: string | number | null | undefined): string {
  return new Intl.NumberFormat("zh-CN", {
    style: "currency",
    currency: "CNY",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(toNumber(value));
}

export function formatNumber(
  value: string | number | null | undefined,
  digits = 2
): string {
  return new Intl.NumberFormat("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits
  }).format(toNumber(value));
}

export function formatNav(value: string | number | null | undefined): string {
  return formatNumber(value, 4);
}

export function formatPercent(
  value: string | number | null | undefined,
  options: { signed?: boolean; digits?: number } = {}
): string {
  const number = toNumber(value);
  const scaled = number * 100;
  const digits = options.digits ?? 2;
  const threshold = 0.5 * 10 ** -digits;
  if (number !== 0 && Math.abs(scaled) < threshold) {
    return `${number > 0 ? "+" : "−"}<${threshold.toFixed(digits)}%`;
  }
  const sign = options.signed && scaled > 0 ? "+" : "";
  return `${sign}${formatNumber(scaled, digits)}%`;
}

export function formatPercentagePoints(
  value: string | number | null | undefined
): string {
  const number = toNumber(value);
  const scaled = number * 100;
  const sign = scaled > 0 ? "+" : "";
  return `${sign}${formatNumber(scaled, 2)} 个百分点`;
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false
  }).format(date);
}

export function displayDate(value: string | null | undefined): string {
  if (!value) return "待官方交易日证据";
  if (/^\d{8}$/.test(value)) {
    return `${value.slice(0, 4)}-${value.slice(4, 6)}-${value.slice(6, 8)}`;
  }
  return value;
}

export function shortHash(value: string | null | undefined): string {
  return value ? value.slice(0, 12) : "—";
}

export function numericTone(value: string | number | null | undefined): string {
  if (value == null) return "neutral-number";
  const number = toNumber(value);
  if (number > 0) return "positive-number";
  if (number < 0) return "negative-number";
  return "neutral-number";
}

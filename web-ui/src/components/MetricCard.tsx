import type { ReactNode } from "react";

export function MetricCard({
  label,
  value,
  detail,
  tone = "default",
  icon
}: {
  label: string;
  value: ReactNode;
  detail?: ReactNode;
  tone?: "default" | "positive" | "negative" | "warning";
  icon?: ReactNode;
}) {
  return (
    <article className={`metric-card metric-${tone}`}>
      <div className="metric-label">
        <span>{label}</span>
        {icon ? <span aria-hidden="true">{icon}</span> : null}
      </div>
      <div className="metric-value">{value}</div>
      {detail ? <div className="metric-detail">{detail}</div> : null}
    </article>
  );
}

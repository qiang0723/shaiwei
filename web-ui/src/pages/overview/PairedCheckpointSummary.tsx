import { CalendarOutlined, SafetyCertificateOutlined } from "@ant-design/icons";
import { MetricCard } from "../../components/MetricCard";
import { StatusBadge } from "../../components/StatusBadge";
import { displayDate } from "../../format";
import type { ForwardCheckpointData } from "../../forwardCheckpointTypes";

export function PairedCheckpointSummary({ checkpoint }: { checkpoint: ForwardCheckpointData }) {
  const status = checkpoint.status === "CHECKPOINT_OBSERVED"
    ? "PASS"
    : checkpoint.status === "BLOCKED_EVIDENCE"
      ? "FAIL"
      : "NOT_DUE";
  return (
    <section aria-labelledby="overview-paired-heading">
      <div className="section-heading">
        <div><span className="section-kicker">R2-1 · PAIRED CHECKPOINT</span><h2 id="overview-paired-heading">Top30 / Top20 同日自然前瞻</h2></div>
        <StatusBadge status={status} />
      </div>
      <div className="metric-grid five-up">
        <MetricCard label="协议 FORWARD" value={`${checkpoint.protocol_forward_count} 日`} detail={`受控补跑 ${checkpoint.controlled_catchup_count} 日`} />
        <MetricCard label="同日自然双账户" value={`${checkpoint.live_dual_count} / ${checkpoint.minimum_live_dual_days}`} detail="只计双方同日调度" icon={<SafetyCertificateOutlined />} />
        <MetricCard label="自然调仓周期" value={`${checkpoint.live_dual_rebalance_count} / ${checkpoint.minimum_live_dual_rebalances}`} detail="按信号调仓标记" />
        <MetricCard label="下一交易日" value={displayDate(checkpoint.next_official_open_date)} detail="官方开市日历" icon={<CalendarOutlined />} />
        <MetricCard label="计划验收日" value={displayDate(checkpoint.expected_first_due_execution_date)} detail="实际以证据为准" />
      </div>
      <div className="audit-boundary-note">
        <SafetyCertificateOutlined /> 检查点未到前不作 Top20 / Top30 胜负、有效性或切换生产结论；完整逐日证据见“模拟组合”。
      </div>
    </section>
  );
}

import { SafetyCertificateOutlined } from "@ant-design/icons";
import { MetricCard } from "../../components/MetricCard";
import { StatusBadge } from "../../components/StatusBadge";
import { displayDate, formatNav, formatPercentagePoints, numericTone } from "../../format";
import type { ForwardCheckpointData } from "../../forwardCheckpointTypes";

export function ForwardCheckpointPanel({ checkpoint }: { checkpoint: ForwardCheckpointData }) {
  const status = checkpoint.status === "CHECKPOINT_OBSERVED"
    ? "PASS"
    : checkpoint.status === "BLOCKED_EVIDENCE"
      ? "FAIL"
      : "NOT_DUE";
  return (
    <section className="surface-panel" aria-labelledby="paired-forward-heading">
      <div className="section-heading">
        <div>
          <span className="section-kicker">R2-1 · PAIRED FORWARD</span>
          <h2 id="paired-forward-heading">Top30 / Top20 同日自然前瞻检查点</h2>
        </div>
        <StatusBadge status={status} />
      </div>
      <div className="account-boundary-notice" role="status">
        <SafetyCertificateOutlined aria-hidden="true" />
        <div>
          <strong>{checkpoint.status === "NOT_DUE" ? "检查点未到期，当前不能比较策略优劣" : checkpoint.status === "CHECKPOINT_OBSERVED" ? "最小观察门槛已到，等待独立裁决" : "证据存在阻断，停止解释"}</strong>
          <span>协议 FORWARD {checkpoint.protocol_forward_count} 日，其中受控补跑 {checkpoint.controlled_catchup_count} 日；只有双账户同日自然运行进入 {checkpoint.live_dual_count} / {checkpoint.minimum_live_dual_days} 日检查点。</span>
        </div>
      </div>
      <div className="metric-grid five-up">
        <MetricCard label="协议 FORWARD" value={`${checkpoint.protocol_forward_count} 日`} detail={`含受控补跑 ${checkpoint.controlled_catchup_count} 日`} />
        <MetricCard label="同日自然双账户" value={`${checkpoint.live_dual_count} / ${checkpoint.minimum_live_dual_days}`} detail={`覆盖 ${checkpoint.expected_open_day_count} 个应到交易日`} />
        <MetricCard label="自然调仓周期" value={`${checkpoint.live_dual_rebalance_count} / ${checkpoint.minimum_live_dual_rebalances}`} detail="按信号调仓标记计数" />
        <MetricCard label="下一交易日" value={displayDate(checkpoint.next_official_open_date)} detail="上交所开市日历" />
        <MetricCard label="计划验收日" value={displayDate(checkpoint.expected_first_due_execution_date)} detail="仅计划，实际以证据为准" />
      </div>
      <div className="short-series-message" role="note">
        <strong>{checkpoint.live_dual_count < 8 ? "自然样本不足，不绘制趋势" : "自然样本仍只作检查点观察"}</strong>
        <span>锚点 {displayDate(checkpoint.anchor_trade_date)} 来自受控补跑，只用于把两账户归一到同一起点；以下差值不是胜负或有效性结论。</span>
      </div>
      {checkpoint.series.length ? (
        <div className="compact-value-table" role="region" aria-label="双账户自然前瞻精确值" tabIndex={0}>
          <table>
            <thead><tr><th>日期</th><th>Top30</th><th>Top20</th><th>Top20−Top30</th><th>调仓</th></tr></thead>
            <tbody>{checkpoint.series.map((point) => (
              <tr key={point.trade_date}>
                <td>{displayDate(point.trade_date)}</td>
                <td>{formatNav(point.top30.portfolio_nav)}</td>
                <td>{formatNav(point.top20.portfolio_nav)}</td>
                <td className={numericTone(point.top20_minus_top30_portfolio_nav)}>{formatPercentagePoints(point.top20_minus_top30_portfolio_nav)}</td>
                <td>{point.rebalance_due ? "是" : "否"}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}

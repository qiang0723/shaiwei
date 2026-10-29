# R2-1R1 连续区段自然前瞻检查点 · 协议（2026-10-29 冻结，实现前）

- 协议：`r2-1r1-continuous-segment-checkpoint-v1`；机器真身：`config/r2_1r1_continuous_segment_checkpoint_v1.yaml`（SHA-256 见 STATE）
- 状态：`FROZEN_DESCRIPTIVE_ONLY`；本协议推送前不写实现
- 草案与裁决：`docs/R2_1R1_CONTINUOUS_SEGMENT_CHECKPOINT_PROTOCOL_DRAFT_20261029.md`；用户 2026-10-29 对 D1–D3 均选建议项
- 后继于 `r2-1-forward-checkpoint-v1`（`4b78cad2…`）。v1 永久保持 `BLOCKED_EVIDENCE`，不改写、不补账、不改名。
- 研究尝试增量 0；生产切换授权无；不是策略效果试验

## 1. 已裁决口径

| 裁决 | 冻结内容 |
|---|---|
| D1 重置 | 以下三种情况重置区段：开市日不是 live-dual（缺口）；账户策略 SHA 变化；生产代码快照与前一个 live-dual 日不同。代码变化当日若本身是 live-dual，即作为新区段首日。一个区段只对应一个生产 release |
| D2 锁存 | 首个达到 20 日、2 次调仓的区段锁存终态，一次性生成唯一描述报告（write-once）；之后的缺口只披露，不撤销 |
| D3 评估器 | 离线只读 CLI + make 目标。累积期只出计数；达门后经用户放行，一次性输出与 v1 同口径的锚定净值描述。Web 不改 |

## 2. 规则

1. **live-dual 日**：沿用 v1 九条日谓词，见配置 `live_dual_day_predicates`。
2. **区段**：截至评估日的最大连续 SSE 开市日序列，每日都是 live-dual，且代码快照恒定。缺口不再导致 `BLOCKED`，只重置；全部缺口与重置次数都要披露。
3. **自然调仓**：区段内 live-dual 日上 `rebalance_due=true`；订单数为 0 也如实报告。
4. **锚点**：两账户在区段首日之前最后一个共同 PASS 状态。不计入观察，证据层常驻披露。
5. **门**：区段 ≥20 个 live-dual 日，且 ≥2 次自然调仓。
6. **终态**：`NOT_DUE` / `BLOCKED_EVIDENCE`（合同性失败，包括日历未覆盖评估日）/ `OBSERVED_WITH_EXECUTION_WARN` / `CHECKPOINT_OBSERVED`。
7. **描述输出**：与 v1 §6 同公式。锁存前禁止输出任何净值或收益数值；其余禁止项同 v1，另禁止把受控追赶或先前区段与锁存区段合并。
8. **日历**：ingest 账本中 `tushare.trade_cal` SSE 各参数键的最新批次。冻结时已覆盖到 2026-11-30；评估日超出覆盖即 `BLOCKED_EVIDENCE`，等日历入库后再评估。

## 3. 已知事实（冻结时，只读身份与时间列）

- 2026-08-03—10-28 共 57 个开市日：live-dual 45 日，缺口 12 日，分 9 段。缺口日见配置。
- 历史最长区段：08-17—09-10，19 日、1 次调仓。
- 两账户策略 SHA 全程不变。
- 10-22 起为 R2D 新生产，代码快照 `4e5244b6` → `8b5b8877`，含 ADR 0015 停牌沿用合同。
- **当前区段**：10-22 起 5 日，0 次调仓；锚点为执行日 10-21。
- 计划（不替代账本）：若无新缺口、无生产发布，调仓约在 11-02、11-16，最早到期约 2026-11-18。**检查点期间如需发布 scheduler，计数会重置。**

## 4. 下游与边界

- 锁存的 `CHECKPOINT_OBSERVED` / `OBSERVED_WITH_EXECUTION_WARN` 满足 RF-1 与 TP-F 正式小批的 R2-1 门。用户须先看到描述报告；正式批另须逐批授权与冻结 release。
- 只读账本与不可变产物；不改 scheduler、账户、信号、Web 或账本。
- v1 网页保持 `BLOCKED_EVIDENCE`。其冻结日历 2026-10-30 到期后，会再增加 `OFFICIAL_CALENDAR_COVERAGE_EXPIRED`，仅作披露。
- **序列（每步单独授权）**：
  1. 本协议推送；
  2. 评估器工程与合成测试；
  3. 只读进度运行（只出计数）；
  4. 达门后经用户放行，一次性生成描述报告并验收。
- 冻结后修改须显式作废并保留原文。

# M5-2B-R1 全局数据失败恢复协议（结果前冻结）

- 协议 ID：`m5-dynamic-fundamental-data-gate-recovery-v2`
- 冻结时间：2026-08-06 09:43（UTC+8）
- 机器真身：`config/m5_dynamic_fundamental_data_gate_recovery_v2.yaml`
- 架构裁决：`docs/ADR_0003_M5_GLOBAL_DATA_FAILURE_EVIDENCE.md`
- 当前阶段：`RECOVERY_PROTOCOL_ONLY_NO_REAL_READ`

## 1. 本目标只回答什么

本节点只冻结 release v3 真实失败后的恢复合同：未来实现怎样把财报来源身份冲突封存为脱敏、确定、
可独立审计的全局 DATA NO-GO，并通过新 protocol scope 建立新 case。它不读取真实财务行，不诊断本次
具体冲突证券/日期/值，不选择普通/VIP 来源，不运行 runner/auditor/registry，不改变任何研究结果。

## 2. 保留与作废边界

- 旧 case/event 1—10、v1/v2/v3 release、输入束、ledger 和零输出事实永久保留；v3 不得重跑。
- v3 的 `STOPPED` 不是 DATA NO-GO；不得补造旧报告、矩阵或 audit。
- 原 `m5-dynamic-fundamental-cross-pool-data-preexecution-v1` 的八式、三池、24 单元、PIT、覆盖、
  staleness、方向、未来窗和尝试 `N=14/20` 原样继承。
- 恢复不增加候选、不翻向、不调门槛、不缩池、不读取标签/效果，也不产生新的研究尝试。

## 3. 冲突分类与失败关闭

对 income、balancesheet、cashflow 的普通/VIP 来源分别保留来源标签，以五字段冻结身份分组。业务值
按 NULL 与精确有限数值规范化；不使用容差或结果导向修复。每张表必须输出以下互斥类别：

1. `EXACT_DUPLICATE_WITHIN_STANDARD`；
2. `EXACT_DUPLICATE_WITHIN_VIP`；
3. `CONSISTENT_OVERLAP_STANDARD_VIP`；
4. `CONFLICT_WITHIN_STANDARD`；
5. `CONFLICT_WITHIN_VIP`；
6. `CONFLICT_STANDARD_VIP`。

前三类不改变业务值；完全重复只允许确定性无损折叠。后三类任一计数大于 0 即触发
`GLOBAL_SOURCE_IDENTITY_CONFLICT`，冲突组不进入 PIT 或公式计算，全批失败关闭。不能将 VIP/普通
优先级、最新批次、update flag 大小、字段非空率或“更合理的数值”用作冲突选边规则。

## 4. 脱敏证据

`source_conflict_report.json` 只允许：schema/outcome、表名、六类聚合计数、冲突字段计数、输入身份、
每表与全局 canonical conflict-set SHA、零泄漏声明。不得包含证券代码、公告日、报告期、report type、
update flag、财务值、候选值、绝对路径或批次原文。

canonical conflict-set SHA 的本地重算输入可含规范化身份和逐字段值 SHA，但只输出最终哈希。它用于证明
runner 与 auditor 看见同一冲突集合，不授权对外导出或把哈希当作数据修复依据。

## 5. 输出、矩阵和退出码

正常模式沿用原三个产物。全局失败模式必须 write-once 生成：

- `source_conflict_report.json`；
- `data_gate_report.json`；
- `run_manifest.json`。

全局失败时 feature panel 明确不存在；报告保存 8×3 共 24 个协议顺序单元，全部
`status=FAIL / reason_code=GLOBAL_SOURCE_IDENTITY_CONFLICT / computation_status=NOT_COMPUTED_GLOBAL_FAILURE`。
eligible 为空、rejected 为原八候选顺序，批裁决固定 `NO_GO_M5_2_DATA_PREEXECUTION`。覆盖、相关性、
候选值均未计算，不能写成零值。

runner：GO=0，封存 NO-GO=3，未封存的控制/运行故障=2。auditor PASS 后 registrar 才能把简化的 24
单元状态、run manifest SHA 和 audit report SHA 追加为 `DATA_GATE_RECORDED`；全局 NO-GO 正常进入
`BLOCKED_DATA`。runner 自报或 exit 3 均不能单独改状态。

## 6. 独立审计与幂等

auditor 必须使用独立冲突分类实现，不导入 runner 的分类/计算入口。它重读相同输入并复算六类计数、
冲突字段计数、conflict-set SHA、文件集合、矩阵和裁决；同时验证报告没有受禁字段。runner/auditor
各完整双跑必须复用相同 run ID 并保持每个产物逐字节一致；registry command 和 outbox 各重放一次，
新增事件/ledger 行均为 0。

## 7. 新 case 与批准边界

恢复 protocol scope 必须绑定旧 STOPPED 证据、原研究配置、proposal export、ADR、本协议和机器恢复
配置。新 case ID 仍由 `proposal_id + 新 protocol_scope_sha256` 派生，与旧 case 不同。registry v1
schema 零迁移，可在相同数据库追加新 case，但旧 case 不得变化。

本节点只允许后续施工恢复实现与 release。新实现/镜像/输入束全部内容寻址并先行推送后，另生成完整
release scope；只有用户明确批准该新 SHA，且 proposal 当时仍为 `REVIEW_REQUIRED`、未到期，才允许
一次断网真实 DATA_GATE。批准不迁移、不预签名、不自动续期。

## 8. 停止线

以下任一发生立即停止：真实数据读取、冲突证券/日期/值输出、普通/VIP 选边、原始数据改写、公式或
门槛变化、旧 case 变化、label/effect/model/backtest/DeepSeek/Web/scheduler/生产触碰、外部网络或
凭据使用。本恢复 DATA NO-GO 即使未来完成，也不表示因子无效；DATA GO 才可另立 M5-2C synthetic
工程 release，仍不授权效果研究。

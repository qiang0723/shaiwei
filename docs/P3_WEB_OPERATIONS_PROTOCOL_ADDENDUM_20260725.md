# P3-2A 结果前冻结补遗：哨兵证据绑定现状

> 日期：2026-07-25（Asia/Shanghai）
>
> 适用协议：`p3-web-operations-v1`
>
> 状态：`FROZEN_BEFORE_IMPLEMENTATION`

## 发现

实现审计在读取真实 `data/shadow/signals/20260724-*.json` 后确认：当前不可变信号只保存
`data_complete_at/data_snapshot_sha256/code_snapshot_sha256`，没有保存 `sentinel_results`、哨兵报告
文件 SHA-256 或哨兵内容 SHA-256。`ledger/shadow_runs.csv` 保存 `sentinel_report_path`，但没有对应
哈希列。

因此原协议第 2.1 节要求“报告结果与不可变信号中的 `sentinel_results` 完全一致”在当前 schema 下
不可执行。不得伪造该字段，也不得以当前读取到的日志文件 SHA-256 冒充历史时点已经绑定的哈希。

## 权威修正

P3-2A 保持不修改 scheduler、信号 schema 或生产账本的授权边界，哨兵验证改为：

1. 报告路径必须来自同日终态 PASS 的 `shadow_runs` 且位于 `logs/sentinels/`；
2. 报告 `generated_at` 必须精确等于信号 `data_complete_at`；
3. 报告与影子运行、信号三方的代码快照和数据快照必须一致；
4. S1—S10 必须恰好各一项，`required_failures` 必须与明细一致；
5. 查询时计算并返回当前报告文件 SHA-256，但标签固定为
   `sentinel_binding_status=IDENTITY_MATCH_UNHASHED`；
6. 即使十项状态均通过，`sentinel_evidence_status=WARN`，不得显示为哈希完整 PASS；
7. 报告换包、时点不等、身份不等、缺项或重项仍为 `EVIDENCE_MISMATCH`。

`data_quality_summary.status` 表示当前可读数据质量结论，可在全部门通过时为 `PASS`；
`evidence_status` 必须独立为 `WARN` 并携带 `SENTINEL_REPORT_NOT_HASH_BOUND`。Web 页面必须同时展示，
不得合并成全绿。

## 后续边界

若要将哨兵证据升级为 `HASH_BOUND`，须另立生产目标，在哨兵完成时生成内容哈希并写入信号或新的
追加式引用账本，同时处理旧历史记录兼容和发布隔离；不得在 P3-2A 查询层回写生产证据。


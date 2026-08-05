# M5-2B 数据门 release registry 挂载恢复单（2026-08-05）

## 1. 触发事实

用户在 `2026-08-05` 对 release scope
`f53085d3cc428e17f014a3d1b0ab7f2f2f0f4ddf6eb64b2db7042fd26ccefe70` 表示继续执行。执行前复核在
任何真实财务语义值读取之前发现：该 scope 的容器计划绑定了 `/inputs:ro`、`/outputs:rw` 和
`/audit:rw`，但没有绑定 ADR 要求的正式 registry 窄写目录 `/registry:rw`。

正式链必须先追加 `IMPORT → PROTOCOL_FROZEN → DATA_GATE_RELEASE_READY → DATA_GATE_APPROVED`，再由
同一 registry 记录 `DATA_GATE_STARTED/RECORDED` 并通过 outbox 发布脱敏 ledger。缺少 `/registry`
绑定时，继续执行只有两种非法方式：临时增加未获批挂载，或绕过 registry 直接构造 approval envelope。
两者均违反结果前 release 身份和 ADR，故旧 scope 在真实数据读取前失败关闭。

## 2. 旧 scope 处置

- 旧 scope、验收文档和用户回复永久保留，不改写、不删除；
- 状态标记为 `SUPERSEDED_BEFORE_REAL_DATA_READ`，不是数据门 NO-GO，也不是策略 REJECT；
- `real_financial_rows_read=false`、`real_candidate_values_computed=false`；
- `data_gate_approval_recorded=false`、`data_gate_execution_count=0`；
- 正式 registry、approval envelope、input bundle、runner/auditor 产物均未创建；
- 标签、效果、DeepSeek、模型、回测、Web、scheduler 与生产仍未授权。

## 3. 唯一允许修复

release 合同新增且只新增一个项目内内容寻址挂载：

```text
data/control/m5_2/runtime/<release-identity>:/registry:rw
```

`DataReleaseScope` 必须强制恰好四个 target：`/inputs:ro`、`/outputs:rw`、`/audit:rw`、
`/registry:rw`；缺失、重复、绝对路径、越界路径、错误 mode 或额外挂载均失败关闭。runner、auditor、
registry 的网络、用户、只读根、capability、资源和命令不变。

修复不得改变 protocol scope、8 个候选、3 个池、24 单元、输入 manifest、PIT/覆盖门、尝试 N、
提案有效期或任何未授权边界。

## 4. 重新发布与批准

修复必须先测试、提交并推送，再重建最终镜像并生成新的精确 release scope；旧 SHA 不能沿用。新 scope
须保留同一 metadata-only 输入 manifest，并绑定新的实现提交、镜像、四挂载和 registry runtime。

即使用户已对旧 scope 表示继续执行，也必须在新 scope 推送后重新报告完整 SHA、镜像和到期时间，并
取得针对新 SHA 的明确批准。新批准前不得初始化正式 registry、生成 approval envelope/input bundle，
更不得读取真实财务值或运行数据门。

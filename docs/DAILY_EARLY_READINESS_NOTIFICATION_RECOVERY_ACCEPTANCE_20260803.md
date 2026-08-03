# 日增量早探测下游静默等待补正工程验收

> 日期：2026-08-03（Asia/Shanghai）
>
> 协议：`p0-daily-early-readiness-notification-recovery-v1`
>
> 裁决：`GO_EARLY_READINESS_NOTIFICATION_RECOVERY_ENGINEERING_ONLY`
>
> 生产状态：`BUILT_NOT_PROMOTED_NOT_ACTIVE`

## 1. 权威结论

已修复早探测的编排缺口：当日五类来源尚未齐全、日增量返回 `WAITING_SOURCE` 时，scheduler 只记录
脱敏健康状态和目标日期，本轮不再运行影子、Top30/Top20 模拟仓、重放或前瞻验收，也不发失败通知、
不进入 degraded。

该补正只获得工程 GO。新的不可变 scheduler 候选已经构建和断网验证，但没有 promote、没有改
`shaiwei:scheduler-current`、没有启动或重启生产。真实 16:00 探测仍须在后续另一新交易日以独立发布
协议受控切换后验收。

## 2. 结果已知与协议先行

- 2026-08-03 发布切换期已经观察到 7 次跨快照告警，旧告警和
  `PASS_WITH_NOTIFICATION_WARN` 裁决永久保留，不以本补正回写历史。
- 恢复协议明确标记 `FROZEN_AFTER_INCIDENT_BEFORE_IMPLEMENTATION`，只冻结 `WAITING_SOURCE` 下游
  短路，不把已知问题包装为盲预注册。
- 协议提交 `f21701bc...` 先行推送；实现提交 `fa6c67ab...` 随后推送。协议、实现与候选身份可独立
  追溯。

## 3. 实现与不变项

`src/shaiwei/pipeline/scheduler.py` 仅在顶层编排增加一个窄分支：

1. `WAITING_SOURCE`：写 `waiting_source` health 后结束本轮下游；
2. 其他状态：保持原 shadow → paper → 最终状态的顺序；
3. 任一真正异常仍进入原异常分支，写 degraded 并发送
   `daily_scheduler_cycle_failed`。

没有修改日增量来源、字段、完整性门、19:30硬兜底、历史补采、`NOOP`、`.BJ`排除、S1—S10、信号、
模型、Top30/Top20策略、账户、模拟成交、账本、通知重试、Compose或生产挂载。

## 4. 测试证据

- 新增 scheduler 顶层 fixture 证明：
  - `WAITING_SOURCE` 时 shadow/paper 调用均为 0、飞书调用 0、退出码 0；
  - health 状态序列包含 `waiting_source/20260804` 且不含 degraded；
  - `PASS` 时 shadow 与 paper 仍各执行一次，防止补正误伤正常链路。
- 宿主 scheduler + daily 专项：16 PASS。
- 宿主全仓：539 PASS，只有既有 Starlette 弃用 warning。
- Ruff、`compileall`、`pip check`、三套 Compose 解析、`git diff --check` 和凭据模式扫描全部 PASS。
- 新候选在 `--network none`、只读根、`cap-drop ALL`、`no-new-privileges`、无项目挂载和无凭据条件下，
  scheduler + daily 专项 16 PASS；唯一 warning 是只读根阻止 pytest 写缓存，不影响测试结果。

## 5. 不可变候选与发布审计

| 字段 | 值 |
|---|---|
| 候选镜像 | `shaiwei:scheduler-0640574ba7353c3e` |
| image ID | `sha256:85711ae0b4c3b19de1554f778cb0ff2ee10f5b1e962e2ef79e1d0953a6a5e79f` |
| 代码快照 | `0640574ba7353c3eef888eac2f706a29606db728319d3717b7ecdfc25de40c40` |
| Git | `fa6c67ab541c19b056221303756d81ad98ee122e` |
| `BUILD_PASS` 审计 | `aa64d960d64be6d403b53b9018a8a1cb00f25be2a8c46bc9f35e9dd9b48ee05f` |

发布审计链由 23 行增至 24 行，tip 等于本次 `BUILD_PASS`，`docker-release-status=PASS`。本次只发起
一个构建会话并持续轮询至完成，没有重复构建。

## 6. 生产隔离证据

构建和断网测试结束后，实际生产 scheduler 仍为：

- 容器：`183b8c6c5eddac951d9d9b3cfa58c0d38e351d5b94ee1b1d52b9b8059c23dd3b`；
- 镜像 ID：`sha256:722f63de15932cb2698e82db7c0140f02921f27f126e1c0235ca62e0a1213b76`；
- 创建时间：`2026-08-03T09:39:34.800579793Z`；
- 只读根：`true`；健康状态：`healthy`；
- current 发布状态仍绑定代码快照
  `4e5244b6b02739dd209a9b01ea715c43ed9a874a7014156e20cf364f06a82708`。

因此本目标没有把开发施工与生产切换合并为同一个变量，也没有影响已完成的 2026-08-03 自然跑批。

## 7. 下一步硬门

1. 不在 2026-08-03 晚间 promote 或启动候选。
2. 后续须另立日期绑定的 P0-E 发布协议/守护，冻结候选、当前运行身份、最新 Top30/Top20
   `FORWARD`、唯一新交易日、窗口、失败回滚和只执行一次语义；不能直接复用已经绑定 Top20 与
   2026-08-03 的旧 guard 配置。
3. 在新交易日窗口受控提升后，记录首次探测、首次就绪、正式完成时点、整日 PASS、`.BJ=0`、
   S1—S10、信号、Top30/Top20、飞书、重放、幂等及零人工修数。
4. 单个真实交易日仍不能证明 16:00—17:00 稳定完成率；需要自然积累多个交易日后再评价 SLA。

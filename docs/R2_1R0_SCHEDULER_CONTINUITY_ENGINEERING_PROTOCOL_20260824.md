# R2-1R0 Scheduler 运行连续性工程协议

- 协议：`r2-1r0-scheduler-continuity-engineering-v1`
- 冻结日期：2026-08-24（UTC+8）
- 状态：`FROZEN_ENGINEERING_ONLY`
- ADR：`docs/ADR_004_SCHEDULER_PHASE_TIMELINE_20260824.md`
- 机器真身：`config/r2_1r0_scheduler_timeline_v1.yaml`
- 策略效果读取：0
- 生产发布授权：无

## 1. 结果目标

为 R2-1 后继连续区段提供可审计的 scheduler phase 时间线，使下一次同日缺口可以定位到数据源探测、
日增量、shadow 或具体模拟账户子阶段，而不是只得到一个被覆盖的 health 快照。

本节点只回答工程可行性；不改变 Top30/Top20、20日/2次调仓门、R2-1 v1 阻断终态或任何收益结论。

## 2. 冻结阶段

固定 phase 集合：

1. `CYCLE`
2. `DAILY`
3. `READINESS_PROBE`
4. `DAILY_COLLECTION`
5. `SHADOW`
6. `PAPER`
7. `PAPER_EXECUTE`
8. `PAPER_VERIFY`
9. `PAPER_ACCEPTANCE`

`PAPER_*` 必须带冻结账户 ID；其他 phase 禁止带账户。未知 phase 或未知账户失败关闭。

## 3. 慢阶段预算

预算只产生 WARN，不是性能调参目标，也不改变核心裁决：

| phase | WARN 秒数 | 依据 |
|---|---:|---|
| `READINESS_PROBE` | 1,200 | 覆盖五个源请求的有界重试长尾 |
| `DAILY_COLLECTION` | 1,800 | 覆盖参考表与五类正式批次 |
| `DAILY` | 2,700 | 包含 readiness 或正式 collection 的外层预算 |
| `SHADOW` | 3,600 | 约为异常前 14 次最大 19.9 分钟的 3 倍 |
| `PAPER_EXECUTE` | 300 | 单账户执行通常远低于五分钟 |
| `PAPER_VERIFY` | 300 | 单账户独立重放预算 |
| `PAPER_ACCEPTANCE` | 300 | 单账户机器验收预算 |
| `PAPER` | 1,800 | 两账户及重放/验收的外层预算 |
| `CYCLE` | 7,200 | 整轮诊断预算；R0 不硬终止 |

任何预算以后若变更必须升协议版本；不得根据某次结果临时上调。

## 4. 事件与失败语义

- phase 事件只有 `STARTED`、`COMPLETED`、`COMPLETED_WITH_WARN`、`FAILED`；
- `event_kind` 固定为 `PHASE` 或 `DURATION_WARNING_NOTIFICATION`；后者状态只允许
  `PASS`、`FAIL`、`DISABLED`，并沿用触发 WARN 的 phase、账户、耗时和预算；
- readiness outcome 只允许 `READY` / `NOT_READY`；其他阶段可用 `PASS`、`NOOP`、
  `WAITING_SOURCE`，禁止自由文本 outcome；
- cycle 还允许业务 outcome：`PASS`、`NOOP`、`WAITING_SOURCE`、`WAITING_LOCK`、`FAILED`、`STOPPED`；
- 每个完成/失败事件记录 wall-clock elapsed、预算和安全 `error_type`；不保存错误 message；
- 每个文件的事件形成 SHA-256 链，写入加排他文件锁并 `fsync`；
- 跨午夜 cycle 的所有事件留在 cycle 启动日文件，避免一轮证据被拆开；
- 慢阶段 callback 先在时间线固化 WARN，再尝试飞书；投递结果追加为同 cycle 事件，投递失败不改核心；
- 时间线写失败阻止后续 phase 并进入现有 scheduler 异常路径。

## 5. 验收矩阵

- 正常 PASS、NOOP、WAITING_SOURCE、daily lock、子阶段异常各一条完整 chain；
- 账户顺序固定 Top30 后 Top20，execute → verify → acceptance 不变；
- readiness false 不进入 collection/shadow/paper；
- 慢 shadow 和慢 paper 子阶段产生 WARN，未超时阶段保持 COMPLETED；
- 通知 callback 失败、文件不可写、历史行被改、尾行截断、未知 phase、未知账户均有对抗测试；
- 两个 writer 并发追加后仍为单链；相同运行不会改写旧事件；
- current scheduler 身份与服务状态施工前后完全一致。

## 6. 禁止事项

本节点禁止：真实补跑、历史 phase 回填、硬超时/kill、修改 macOS 电源设置、启动 `caffeinate`、资源
限额调整、模型/信号/账户/门槛修改、Web 接入、生产镜像 build/promote/restart、外网或 secret 读取。

## 7. 完成与后继

工程门通过时只裁 `GO_ENGINEERING_ONLY`。下一步先由用户裁定宿主防休眠方案，再另立不可变 scheduler
release；只有新发布稳定后，才冻结 R2-1R1 连续区段协议。R2-1 v1 始终保留
`BLOCKED_EVIDENCE`。

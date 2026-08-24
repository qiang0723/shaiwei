# R2-1R0 Scheduler 运行连续性工程验收

- 验收日期：2026-08-24（UTC+8）
- 协议：`r2-1r0-scheduler-continuity-engineering-v1`
- 协议冻结提交：`76be85e`
- Schema 闭合提交：`994fd41`
- 裁决：`GO_ENGINEERING_ONLY`
- 生产发布授权：无

## 1. 结论

已在不改变业务账本、策略、模型、门禁和生产容器的前提下完成 scheduler phase 时间线工程。新能力以
独立适配器记录按 cycle 启动日分区的 JSONL；逐事件加排他文件锁、`fsync` 和 SHA-256 前向链。异常、
慢阶段和通知结果均使用封闭枚举及安全错误类型，不保存命令、环境、绝对路径、证券、持仓、收益或凭据。

R2-1 v1 的 `BLOCKED_EVIDENCE` 不变。本验收只证明后继版本可以生成更细的运行连续性证据，不证明生产
已经启用该能力，也不构成策略有效、模拟账户达标或 R2-1R1 通过。

## 2. 实现边界

新增职责拆分为三个小模块：

1. `scheduler_timeline_contract.py`：冻结合同加载及预算、账户、阶段、状态枚举的严格校验；
2. `scheduler_timeline_events.py`：事件 Schema、独立 SHA 链复核和共享读锁；
3. `scheduler_timeline.py`：cycle/phase 上下文、排他锁追加、`fsync` 及慢阶段通知回执。

最终文件分别为 176、170、354 行，均低于 400 行常态线。既有 `daily.py` 仅增加 readiness/collection
薄编排，最终 540 行；未把新职责写入既有 670 行以上的 `paper_cycle.py`。`scheduler.py` 最终 233 行，
按固定账户顺序记录 execute → verify → acceptance。

## 3. 运行语义

- 正常启动先持久化 `CYCLE/STARTED`；phase 的 `STARTED` 写失败时绝不进入 phase body。
- readiness false 固化为 `NOT_READY`，返回 `WAITING_SOURCE`，不进入 collection/shadow/paper。
- phase 异常只保存 `error_type` 并失败关闭；业务异常仍进入原 scheduler degraded/飞书路径。
- 超预算先固化 `COMPLETED_WITH_WARN`，再调用飞书；投递 `PASS/FAIL/DISABLED` 作为同 cycle 后继事件。
- 飞书失败不把核心完成状态改成失败；时间线自身无法可靠追加则阻止后续 phase。
- 跨午夜 cycle 始终写入启动日文件；并发 writer 在同一文件上形成一条可独立复核的全局哈希链。
- business ledger 继续是业务状态权威；时间线没有回填、改账或改判权限。

## 4. 对抗与回归证据

- 专项：30 PASS；覆盖严格合同、跨午夜、慢阶段、通知失败/禁用、篡改、截断、未知 phase、未知账户、
  phase body 前写失败、真实不可写目录、phase异常去详情、自由文本 outcome、八个并发 cycle、daily
  readiness 短路、daily锁竞争和 scheduler 外层顺序。
- 架构门：13 PASS。
- 全仓：1,865 PASS；仅 1 条既有 Starlette 弃用提示和 16 条既有 pandas FutureWarning。
- Ruff：PASS；`compileall`：PASS；`pip check`：PASS；`git diff --check`：PASS。

关键冻结/实现身份：

| 对象 | SHA-256 |
|---|---|
| timeline 合同 | `e6949be7c21b37ee872f80e9ba9b8330138c15416ff59f5e0c2ee445fd62e287` |
| writer/context | `d9acc6410f6a1556e846c3c86da172b9b110f4b3124542e5d15c030e3a21e39c` |
| contract loader | `a17a7d4f14f0a72398c44099f904957ddad29dffff8eba97f75b4a374ad599fa` |
| event verifier | `00edca1f2d97d0b608d52932be535bd454b2e7873eb3c99b07c25fc8822060a9` |
| 对抗测试 | `dc1f86c115ae9cae324f7bfc933d7eb91e3037313d0dfb3526fc15ed41e58905` |

## 5. 生产隔离

本节点没有执行 Docker build/promote/restart，也没有运行真实 daily、shadow、paper 或历史回填。核验时
scheduler 仍为容器 `183b8c6c5edd`、镜像标签 `shaiwei:scheduler-current`、镜像内容
`sha256:722f63de15932cb2698e82db7c0140f02921f27f126e1c0235ca62e0a1213b76`，创建时间仍为
`2026-08-03 17:39:34 +0800`，状态 healthy。测试时间线只写 pytest 临时目录，项目运行日志未被回填。

## 6. 后继边界

下一步不能直接把开发工作树切进生产。应先裁定宿主防休眠/可用性方案，再另立不可变 scheduler release，
构建新镜像并以 fixture 验证 timeline 挂载和写权限；发布获批并稳定后，才能结果前冻结 R2-1R1 的
“缺口后连续区段自动重置”协议。20 个 live-dual 日和 2 次自然调仓门不得降低。

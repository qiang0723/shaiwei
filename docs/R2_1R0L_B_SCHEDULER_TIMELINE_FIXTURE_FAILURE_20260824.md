# R2-1R0L-B Scheduler timeline 候选构建与 fixture 失败验收

- 执行日期：2026-08-24（UTC+8）
- 协议：`r2-1r0l-scheduler-timeline-release-v1`
- 授权节点：`R2-1R0L-B`
- 终态：`BUILD_PASS / FIXTURE_FAIL / NO_GO_PROMOTION`
- 生产授权：无

## 1. 裁决

绑定提交的候选镜像已恰好构建一次并通过镜像 label、运行时 manifest 与 Git 身份核对；同一镜像随后
恰好运行一次断网、只读 synthetic timeline fixture。fixture 共 12 项，11 项通过、1 项失败。失败项在
Docker Desktop bind mount 上并发写入同一个 timeline 文件时形成两个都指向零哈希的首记录，独立校验
正确拒绝第二条记录。因此候选不得提升、不得重启生产 scheduler，也不得在同 scope 下重跑。

这不是策略、模型、业务跑批或前瞻结果失败；它只否决当前 scheduler timeline 候选的并发持久化能力。

## 2. 绑定身份与构建

- 授权 Git HEAD：`0018224c4eb803191e2ac07edad3857868aab21f`
- 构建时 `HEAD == origin/main`：是
- 授权及实测代码快照：
  `ccf4aa05bc3e07ffc2f62fcf09f79a7cd9aa339e7a80999d3e0c7f049a823d34`
- 候选标签：`shaiwei:scheduler-ccf4aa05bc3e07ff`
- 候选镜像 ID：
  `sha256:56a97f020603e91eca897bfe034b27a76aa143f64b3e1c381b8a2a71d470064f`
- 构建次数：恰好 1
- 构建审计记录 SHA-256：
  `3045ab97e3aaa9547b36cd32592642f2d9bbb395058e0485d312edaba6eeb832`

构建来源为项目内 Git 忽略的受控 archive 上下文；候选标签在构建前不存在。构建未挂载 secret 或
`.env`，自然业务账本、项目日志、data 和三份既有用户草稿均未进入上下文。

## 3. 唯一 fixture

fixture 只运行一次，边界如下：

- 使用上述同一候选镜像；
- `network=none`；
- 根文件系统只读；
- drop all capabilities，并启用 `no-new-privileges`；
- 只挂载 Git 忽略的 `.release/scheduler-timeline-fixture/logs`；
- 未挂载项目 data、ledger、logs、Docker socket或 `.env`；
- 只执行 `tests/test_scheduler_timeline.py` 的 synthetic 测试，不运行真实业务入口。

结果为 `11 passed, 1 failed`。跨午夜文件绑定、单写者哈希链、篡改/截断 fail closed、慢阶段通知隔离、
未知 phase/account 拒绝等均通过；失败项为
`test_two_writers_produce_one_valid_chain`。

失败文件中仅形成两行：

1. cycle `...0002` 的首记录以前驱零哈希写入，事件哈希为
   `a3f2f1af652d90d9e8cc3b197ca81ed4611dda14bb7a10cf8a9cc4d8ad70b774`；
2. cycle `...0003` 的首记录仍以前驱零哈希写入，而不是引用上一条事件哈希。

随后读取方以第一条事件哈希作为预期前驱，正确报出
`TimelineError: timeline SHA-256 predecessor mismatch`。这证明当前 `fcntl.flock` 单独使用时，至少在本机
Docker bind mount 的同进程多线程并发场景下，没有提供冻结合同要求的串行追加保证。现有证据不能再
细分为 Docker Desktop 文件系统锁语义或实现缺少进程内互斥；在修复前必须按能力缺口处理。

## 4. 不可变证据

- JUnit SHA-256：
  `e3a8ce0f49ed3a9102d65b456d7d513659bdefc483c907a15e3ac7ff90048d7e`
- 失败 timeline SHA-256：
  `582c7f0d3b3ab0e5aa99251ddcfb64ede7cabb52e25ce5d137acdb8f131888d9`
- fixture 输出树规范文件清单摘要 SHA-256：
  `f4d3382ca95dfbeedbc72673246441e11173a80ceb8a9c57ecc3238f98694a9e`

原始 fixture 产物保存在 Git 忽略的 `.release/scheduler-timeline-fixture/logs`。同 scope 不重跑，不覆盖
失败产物，不以宿主测试或删除并发项替代真实 bind mount 结果。

## 5. 生产隔离

执行后生产 scheduler 仍为：

- 容器：`183b8c6c5eddac951d9d9b3cfa58c0d38e351d5b94ee1b1d52b9b8059c23dd3b`
- 镜像：`sha256:722f63de15932cb2698e82db7c0140f02921f27f126e1c0235ca62e0a1213b76`
- 创建时间：`2026-08-03T09:39:34.800579793Z`
- 状态：`running/healthy`
- restart policy：`unless-stopped`

候选没有运行中的容器；未 promote、未改 current/previous 标签、未重启 scheduler、未运行真实业务、
未回填历史 timeline，也未写生产账本。

## 6. 后继边界

下一合法节点应另立 `R2-1R0L-B-R1`，至少分为两段：

1. 结果盲工程：为同一路径增加进程内互斥，同时保留跨进程文件锁；新增同进程多线程和独立进程并发
   合成门，证明任何失败都不会留下可误读为有效的分叉链；该段不构建、不运行 daemon fixture。
2. 新授权执行：绑定新的 HEAD、代码快照和候选标签，恰好构建一个新镜像，并在同类 bind mount 上
   恰好运行一次断网只读 fixture；旧候选与本次失败证据永久保留。

在新候选完整通过前，`R2-1R0L-C` 不可申请，`R2-1R1` 也不从本候选开始计数。

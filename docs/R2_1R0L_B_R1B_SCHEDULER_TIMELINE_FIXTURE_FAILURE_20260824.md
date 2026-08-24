# R2-1R0L-B-R1B Scheduler timeline 新候选 fixture 失败验收

- 执行日期：2026-08-24（UTC+8）
- 授权节点：`R2-1R0L-B-R1B`
- 绑定合同：`r2-1r0l-b-r1-timeline-lock-recovery-v1`
- 终态：`BUILD_PASS / FIXTURE_FAIL / NO_GO_PROMOTION`
- 生产授权：无

## 1. 裁决

绑定 R1 修复的 scheduler 候选已恰好构建一次，并通过镜像 label、运行时 manifest、Git 与代码快照
核对。同一镜像随后恰好运行一次断网、只读的 15 项 timeline fixture，结果为 14 PASS、1 FAIL。

R1 新增的进程内路径互斥及“`flock` 无效时 8 线程并发”测试在真实 Docker bind mount 中通过，说明
L-B 的同进程线程分叉已被修复。唯一失败收敛为 4 个独立 Python 进程：Docker Desktop bind mount 上
的 `flock` 没有为同一 timeline 文件提供冻结合同要求的跨进程串行保证。

因此新候选仍不得提升；不得把 14/15、宿主 1,879 PASS 或同进程修复成功表述为发布通过。同 scope
不重跑、不删测试、不降低并发门。

## 2. 候选身份

- 授权及实际 Git HEAD：`76ec0bc538f571cdcf1524e51ca9bb44433ba36c`
- 授权及实际代码快照：
  `6be617e41ab6f88c12e27c920c4b6af66c481f6f2e7964f8978c3149693c1e2c`
- 候选标签：`shaiwei:scheduler-6be617e41ab6f88c`
- 候选镜像 ID：
  `sha256:b6c4e18a8447bbe5d8b257bac5de10f67344bb186c5ab93eca16b67eee6d6b83`
- 构建次数：恰好 1
- 构建审计记录 SHA-256：
  `740bd1852c33d47f867f79b6ef797f2ac32ba97eaf8920a849f12abdf6f36eb5`

构建前候选标签不存在；来源仍为已推送 HEAD 的受控 Git archive。未挂载 `.env`、secret、data、
ledger、项目日志或用户草稿。旧失败候选 `sha256:56a97f02...0064f` 未改标、未删除。

## 3. 唯一断网 fixture

fixture 仅运行一次，并使用新的 Git 忽略输出根
`.release/scheduler-timeline-fixture-r1b/logs`：

- `network=none`；
- 根文件系统只读；
- drop all capabilities，启用 `no-new-privileges`；
- 只挂载上述专用 fixture 日志根；
- 无 data、ledger、项目 logs、Docker socket、`.env` 或 secret 挂载；
- 只运行 `tests/test_scheduler_timeline.py`，不调用真实业务入口。

结果为 `14 passed, 1 failed`。失败项
`test_independent_processes_produce_one_valid_chain` 使用 4 个独立 Python worker，经 ready/start gate 同时
写入同一文件。落盘文件只有两行：

1. cycle `...0003` 首记录以前驱零哈希写入，事件哈希为
   `7954ff62d54f4f414e274cf4b5564640db660ecdce3d8efbc966bb1217d5baea`；
2. cycle `...0004` 首记录仍以前驱零哈希写入，而不是引用第一条事件哈希。

四个 worker 均以 `TimelineError: timeline SHA-256 predecessor mismatch` 失败关闭，没有把分叉链误判为
有效。失败 timeline 为 2 行，不是截断或测试超时。

## 4. 不可变证据

- R1B JUnit SHA-256：
  `2729c195622bd272d525b06b0e21d9fefed939aabfa66182ad4ab7c37a4c8e1b`
- R1B 失败 timeline SHA-256：
  `b6686cf564a8c6c301df80470c757b00f39e3d4b3a3dc5c5496568bfbf630cfd`
- R1B fixture 输出树规范文件清单摘要 SHA-256：
  `945dd02c1b92d3ca7f6d8f5668d6690fed4bfda8484b56613033ec99d398fe9a`

旧 L-B 失败证据复核仍为：

- JUnit：`e3a8ce0f49ed3a9102d65b456d7d513659bdefc483c907a15e3ac7ff90048d7e`
- timeline：`582c7f0d3b3ab0e5aa99251ddcfb64ede7cabb52e25ce5d137acdb8f131888d9`
- 输出树摘要：`f4d3382ca95dfbeedbc72673246441e11173a80ceb8a9c57ecc3238f98694a9e`

两次失败输出根彼此独立；新 fixture 未覆盖旧产物。

## 5. 影响边界

本次证据只直接证明 timeline writer 在当前 Docker Desktop bind mount 上不能仅依赖 `flock` 完成
跨进程串行。只读代码清单同时发现生产或共享持久化路径还在以下位置使用同类锁：

- `ledger.py` 的追加式账本写入；
- `daily.py` 的 scheduler 单实例锁；
- `paper_cycle.py` 与 `shadow_cycle.py` 的周期锁；
- timeline 的共享读取锁；
- 若干研究账本与 outbox。

这不等于这些路径已经发生数据损坏：当前生产 scheduler 是单容器、主编排单进程，现有账本仍须由
各自校验器判定。它意味着“Docker bind mount 上 `flock` 可作为跨进程权威锁”这一公共假设已被真实
fixture 否证，继续只修 timeline 会留下同类系统风险。

## 6. 生产隔离

执行后生产 scheduler 仍为：

- 容器：`183b8c6c5eddac951d9d9b3cfa58c0d38e351d5b94ee1b1d52b9b8059c23dd3b`
- 镜像：`sha256:722f63de15932cb2698e82db7c0140f02921f27f126e1c0235ca62e0a1213b76`
- 状态：`running/healthy`
- restart policy：`unless-stopped`

新旧候选均无运行中容器；未 promote、未改 current/previous、未 restart、未运行真实业务或历史回填，
也未写生产账本。项目真实日志只有授权构建产生的追加式 `BUILD_PASS` 发布审计；fixture 只写专用忽略
根。

## 7. 下一合法节点

下一步应先立 `R2-1R0L-B-R2A` 只读锁语义审计与 ADR，而不是直接申请第三个候选：

1. 确认 scheduler、ledger、paper、shadow 与研究写路径的真实进程/容器并发拓扑；
2. 比较专用 Docker named lock volume、bind mount 原子目录锁、单写者编排三种以内方案；
3. 明确崩溃释放、跨容器提升、锁顺序、超时、观测、迁移与回滚；
4. 冻结一个统一的生产锁后端和最小迁移范围；
5. ADR 通过后再分工程与唯一 Docker fixture 两段授权。

在统一锁后端及真实 bind/named-volume fixture 通过前，不申请 L-C，不启动 R2-1R1 计数。

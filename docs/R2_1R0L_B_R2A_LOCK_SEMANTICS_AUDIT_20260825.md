# R2-1R0L-B-R2A 锁语义与并发拓扑只读审计

- 审计日期：2026-08-25（UTC+8）
- 终态：`GO_ARCHITECTURE_ONLY / IMPLEMENTATION_NOT_STARTED`
- 生产授权：无

## 1. 结论

R1B 的失败不是 timeline 私有问题，而是共享基础设施边界问题。当前生产关键写路径有五类直接使用
`fcntl.flock`，其中 timeline 已在与生产相同类型的 Docker Desktop bind mount 上证明跨进程互斥不
成立。正常 scheduler 串行拓扑降低了已发生损坏的概率，但不能满足重复 scheduler、手工 `--once`、
恢复任务或跨容器发布时原锁的设计职责。

本审计接受 ADR-0009：保留业务 `data/ledger/logs` 在项目目录，只将逻辑锁文件迁到 Docker 管理的
专用 named volume，并由一个统一后端同时提供线程与跨进程/跨容器互斥。该结论只允许进入 R2B 工程
协议，不等于 named volume 已通过本机锁验收。

## 2. 生产关键锁清单

| 写路径 | 当前锁对象 | 当前挂载 | 真实/潜在并发 | 审计结论 |
|---|---|---|---|---|
| scheduler timeline writer/verifier | timeline 数据文件本身，EX/SH；writer 另有进程内 mutex | `logs/` bind | scheduler 主进程、独立 verifier、恢复/fixture | 线程层已修；跨进程已被 R1B 否证 |
| daily cycle | `logs/scheduler/daily.lock`，EX/NB | `logs/` bind | 长期 scheduler、手工或恢复 `--once` | 单实例门不能继续以 bind `flock` 为权威 |
| shadow cycle | `logs/shadow/cycle.lock`，EX/NB | `logs/` bind | scheduler 子进程、手工 shadow | 同上 |
| paper cycle | `logs/paper/cycle.lock`，EX/blocking | `logs/` bind | 两账户顺序子进程、手工/恢复 paper | 当前正常串行，但锁职责要求跨进程有效 |
| canonical CSV ledger | 每个 CSV 文件本身，EX | `ledger/` bind | daily 主进程、shadow/paper 子进程、研究/恢复入口 | 影响面最大；没有损坏证据，但权威假设已不可信 |

另有 `research/g1.py`、`research/star50_residual_effect/evidence.py` 与
`research_gates/gate_registry/outbox.py` 使用 `flock`。它们不是当前 scheduler 首批生产路径；R2B 必须
登记其状态，但不得借机重开已关闭研究或扩大迁移范围。

## 3. 实际运行拓扑证据

审计时只读观察：

- scheduler 容器 ID：`183b8c6c5eddac951d9d9b3cfa58c0d38e351d5b94ee1b1d52b9b8059c23dd3b`
- scheduler 镜像 ID：`sha256:722f63de15932cb2698e82db7c0140f02921f27f126e1c0235ca62e0a1213b76`
- 状态：运行 3 周且 healthy；根文件系统只读。
- 观察瞬间只有 `docker-init` 与一个长期 `python -m shaiwei.pipeline.scheduler`；这只是瞬时证据，
  不否定 scheduler 在 shadow/paper 阶段启动子进程的源码事实。
- 三个持久化挂载均为 bind：宿主项目 `data/ledger/logs` 分别映射到 `/workspace` 下同名目录。
- 容器内 `/proc/mounts` 将三者报告为 `/run/host_mark/Users` 来源、`fakeowner` 文件系统；`stat -f`
  类型为 `UNKNOWN (0x6a656a63)`。这些结果只描述本机当前 Docker Desktop 后端，不外推到其他宿主。

源码拓扑为：主循环先在本进程运行 daily，然后以 `subprocess.run` 串行启动 shadow，再按账户顺序启动
paper execute/verify/acceptance。normal path 没有主动并行两个 cycle；保护重复入口仍是各 lock 的明确
职责。发布使用 `docker compose up --force-recreate`，当前契约只允许 `data/ledger/logs` 三个 bind
mount，尚无共享锁 volume。

## 4. 风险分级

- **P0 发布阻断**：当前新候选不得 promote，R2-1R1 不得计数；timeline 的真实跨进程合同已失败。
- **P1 潜在完整性风险**：canonical ledger、daily、paper、shadow 尚无已证实损坏，但不能继续声称
  bind `flock` 能防重复 writer；任何新的并发入口必须停止扩张。
- **P2 研究路径债务**：三个研究锁入口进入 inventory；只有重新变为共享 writer 时才迁移。
- **非结论**：本审计不推翻既有 ledger 哈希、前瞻结果、模型、策略或研究裁决，也不证明 named
  volume 必然正确。

## 5. 方案裁决与最小迁移面

三案比较为：继续线程补丁拒绝；bind 原子目录锁保留为灾难恢复候选但不作默认；named volume 的统一
逻辑锁被接受进入工程。最小生产迁移必须一次覆盖 timeline EX/SH、daily、shadow、paper 与 canonical
ledger，不能在同一个生产版本中让这些 writer 一半使用旧 bind 锁、一半使用新锁。

统一后端必须以逻辑资源 ID 定位锁，包含进程内层与 named-volume `flock`，缺失/错误 mount 时失败
关闭。宿主直接运行或未挂同一 volume 的开发容器，在 scheduler 运行时不得写生产持久化路径。

## 6. 本节点验证与边界

本节点完成了：源码锁点与调用关系清点、当前容器挂载/进程只读核验、Docker 官方存储边界复核、三案
比较、迁移/回滚/fixture 设计及 ADR 冻结。

本节点没有：修改源码、配置、Compose、模型、门禁或 ledger；没有构建镜像、运行并发 fixture、读取
`.env`、访问业务结果、调用外网数据源、重启/提升生产或补写 timeline。生产身份与运行状态未改变。

下一合法节点为 R2B 结果盲工程协议与实现；完成并推送后，才可申请 R2C 的唯一候选构建和一次真实
named-volume fixture。R2C 通过前不得进入 R2D 或 R2-1R1。

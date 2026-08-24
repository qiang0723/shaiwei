# ADR-004：Scheduler 运行连续性使用独立哈希链阶段时间线

- 日期：2026-08-24（UTC+8）
- 状态：`ACCEPTED_FOR_ENGINEERING`
- 关联节点：`R2-1R0`

## 1. 问题与结果目标

R2-1 在 2026-08-13—14 形成两个不可回补的自然前瞻缺口。现有 daily/shadow/paper 账本能证明最终
结果，却不能还原 `WAITING_SOURCE` 尝试、阶段停顿和 scheduler 异常；`health.json` 又会被下一轮覆盖。

本 ADR 的结果目标是：未来再出现休眠、资源争用、数据源迟到或子进程异常时，只依靠筛微项目目录内
证据即可定位到 readiness、daily、shadow 或具体 paper 子阶段，同时不复制研究口径、不改变策略结果。

## 2. 候选方案

### A. 扩大 `health.json`

优点是改动小；缺点是仍会覆盖历史，无法证明缺口、恢复和重复事件，拒绝。

### B. 增加 canonical CSV ledger

审计能力强，但会把运行诊断混入研究/账户业务账本，增加提交快照和追加门负担；时间线是运行日志而非
研究事实，拒绝。

### C. 独立按日 JSONL，逐事件哈希链接（选择）

写入 `logs/scheduler/timeline_YYYYMMDD.jsonl`，每个事件绑定前一事件 SHA-256；按 cycle 与 phase 分层，
记录开始、完成、失败、耗时和安全错误类型。文件继续位于现有 `logs/` 生产挂载内，不新增挂载、服务、
依赖、secret 或 Git 跟踪运行数据。

代价是运行日志会增长，且哈希链只能证明项目内文件的连续性，不等同于外部时间戳公证。按日分区限制
单文件大小；保留/归档策略待常开服务器与备份方案就绪后另立目标。

## 3. 合同与依赖边界

- 新 Schema：`shaiwei-scheduler-phase-event-v1`；机器配置见
  `config/r2_1r0_scheduler_timeline_v1.yaml`。
- 新适配层只负责序列化、文件锁、`fsync`、哈希链验证和阶段计时；不得导入模型、账户、Web 或通知。
- pipeline 编排可以把安全字段交给时间线，并以窄 callback 发送慢阶段 WARN；通知失败不得把已完成核心
  阶段改成失败。
- 事件禁止保存异常 message、命令行、环境变量、绝对路径、证券、持仓、收益、token 或 webhook。
- daily/shadow/paper 原账本仍是业务权威；时间线只证明运行过程，不得用于改写其状态。

## 4. 失败关闭

- phase `STARTED` 事件未持久化时，不允许进入该阶段，避免形成无运行证据的副作用；
- 完成/失败事件写入失败时 scheduler 进入现有异常路径并保持坏消息；
- 旧文件最后一行无效、哈希链断裂、同 cycle sequence 倒退或配置出现未知 phase 时拒绝追加；
- 慢阶段只记 `COMPLETED_WITH_WARN` 并发送 WARN，不改变业务 PASS，不自动 kill 或重跑；
- 同一个自然运行 scope 不因时间线失败绕过现有 daily/shadow/paper 幂等门。

## 5. 迁移、发布与回滚

R2-1R0 先在开发镜像通过合成 cycle、并发追加、篡改、跨午夜、写失败和慢阶段通知测试。当前生产
scheduler 不重建、不重启。真实发布必须另立 release，遵守
`docs/SCHEDULER_RELEASE_ISOLATION.md`，从干净且已推送提交构建不可变镜像。

回滚只切回 previous scheduler 镜像；既有时间线文件保留，不删除、不截断。旧镜像不会读取新文件，
所以回滚不需要数据迁移。禁止追溯补造 2026-08-13—14 的 phase 事件。

## 6. 验收指标

- 合成 cycle 的 cycle/phase 开始、完成、失败、业务 outcome 和耗时均可独立验证；
- 同文件逐事件 `previous_event_sha256` 与 `event_sha256` 完整；任意历史字节篡改 fail closed；
- readiness、daily collection、shadow、paper execute/verify/acceptance 均有直接测试；
- 慢阶段通知失败不改核心结果，时间线写失败则阻断后续阶段；
- 新模块不超过 400 行，scheduler 保持薄编排；架构、全仓、Ruff、diff 与脱敏门通过；
- current scheduler 容器、镜像、挂载、创建时间和健康状态均不变化。

## 7. 复审触发器

新增外部可观测平台、远程日志、保留删除策略、硬超时/自动 kill、资源采样、Web 查询或把时间线升级为
生产裁决权威时，必须复审本 ADR；不能在 R2-1R0 中顺手扩大。

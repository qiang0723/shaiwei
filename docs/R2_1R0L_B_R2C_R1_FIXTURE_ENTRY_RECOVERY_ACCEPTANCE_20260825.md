# R2-1R0L-B-R2C-R1 Fixture 入口恢复工程验收

- 日期：2026-08-25（UTC+8）
- 合同：`r2-1r0l-b-r2c-r1-fixture-entry-recovery-v1`
- 终态：`GO_RELEASE_READY_NOT_EXECUTION_APPROVAL`
- 生产授权：无

## 1. 结果

R2C 第 2 项入口契约不匹配已按冻结边界完成结果盲恢复。新入口不再在候选容器中调用宿主 pytest，
而是执行固定的候选原生 Python payload：继承 Docker authority 和 named-volume mount，不传显式
`lock_root`，在候选进程内把 `fcntl.flock` 替换为 no-op，并让 8 个线程同时争用同一逻辑资源。只有
进程内互斥把临界区最大并发保持为 1 时 payload 才成功。

真实执行动作已独立标识为 `R2C_R1_RUNTIME_LOCK_FIXTURE_ENTRY_RECOVERY_ONCE`。原 R2C scope、候选、
失败证据和 `LOCK_BEHAVIOR_NOT_EVALUATED` 均未修改；原 scope 仍永久不得重跑。

## 2. 单变量与命令边界

本次只改变 `eight_threads_with_noop_flock` 的适配入口：

- `runtime_lock_fixture.py` 的第 2 项从候选内 pytest 改为 `python -c <固定 payload>`；
- payload 明确使用 `logical_lock(DAILY_CYCLE)`，源码不含 `lock_root`；
- 命令形状测试证明仍带 `SHAIWEI_LOCK_AUTHORITY=docker-named-volume-v1`、稳定卷
  `shaiwei_runtime_locks_v1:/run/shaiwei-locks`、断网、只读根和降权参数；
- 其余 9 项、顺序、claim-first、失败即停、证据报告、输出根唯一性和同 scope 禁止重跑均未改变。

生产锁实现、Compose、release、scheduler、业务 schema、模型、策略、Web 和真实账本均未修改。

## 3. 独立工程证据

同一个固定 payload 已在独立本地子进程中执行，通过临时本地锁根验证：8 个线程结束后活跃数为 0，
最大同时临界区数为 1。该测试不使用 Docker，不模拟生产 mount 成功；真实 named-volume 权威仍必须由
下一次唯一 daemon fixture 验证。

身份与 SHA-256：

- 工程代码快照：`88e3f471565ba461fb660f41a97a2dd4ac633585c4f74efadd9a3b264e2abec0`；
- fixture controller：`e791a674727c45af6d0a1c452cffa972493f8f5868f69f2c72f06a0f0cb98769`；
- 固定 payload：`90de34b538c9be640e1d6b0a86a453e4cd2bfc00c1b52fef5c2e15b22b4909f6`；
- fixture tests：`d230dfdce1e0919815119c86351a294c47358cd7d81da0dd86f0c506561aec39`；
- 冻结 recovery config：`b3e5ae9ef8705f15dd0f6ddb315f51771856db2ea8aa35d7f102fb93e26a0723`；
- 结果前协议：`d295a758a7270d42ad9b383f4598d45f907ef0e32426a497d4ccee9a88440b78`。

## 4. 验证

- R2C-R1 专项：14 PASS；
- 锁、timeline、release、隔离构建和构建身份联合专项：95 PASS；
- 架构门：13 PASS；
- 全仓：1,907 PASS，17 条均为既有第三方/兼容性 warning；
- Ruff、compileall、pip check、diff-check 与任务文件脱敏检查通过；
- controller 400 行、payload 95 行，均未突破冻结预算。

## 5. 当前权限与下一停止点

本节点未调用 Docker daemon；build、fixture suite、volume 创建/删除、promote、restart、真实业务、
真实 ledger、网络和密钥读取均为 0。生产 scheduler 未被本施工触碰。

实现提交推送后，须用最终 `HEAD == origin/main`、上述代码快照、内容寻址候选标签和新 scope 形成精确
授权句。用户批准前不得构建候选或运行 suite；新 scope 无论 build 或 fixture 失败均不得重跑。只有
完整 10 项真实 suite 全绿后，才可另立 R2D，R2-1R1 仍不得提前启动。

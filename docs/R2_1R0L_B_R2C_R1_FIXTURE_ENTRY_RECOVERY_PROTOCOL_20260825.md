# R2-1R0L-B-R2C-R1 Fixture 入口恢复协议

- 日期：2026-08-25（UTC+8）
- 合同：`r2-1r0l-b-r2c-r1-fixture-entry-recovery-v1`
- 当前状态：`FROZEN_ENGINEERING_NOT_EXECUTION_APPROVAL`
- 生产授权：无

## 1. 问题与结果目标

R2C 原 scope 已唯一构建候选并调用一次真实 suite。候选身份门通过，但第 2 项错误复用了显式传入
`lock_root=tmp_path` 的宿主单元测试；真实 `docker-named-volume-v1` 权威正确拒绝该入口，锁行为尚未
被评价。R2C-R1 只修复 fixture 入口，使同一项在候选镜像内继承真实 authority 和 named-volume mount，
不传显式锁根，并把候选内 `flock` 替换为 no-op 后验证 8 线程临界区仍严格串行。

本节点不修改生产锁实现、不放宽锁根校验，也不重解释旧失败。通过工程门只表示可以形成新的精确
release scope，不代表真实 fixture、生产发布或 R2-1R1 已获授权。

## 2. 永久保留的前驱证据

以下前驱身份永久保留且不得重跑或改写：

- scope：`2da6de12e3c4ab2d7b301a9e279ffc5091b458672672f4b9ca81a3adf8ed5afa`；
- HEAD / snapshot：`a909cdd1...b91d02e7` / `8009eeb5...7b70`；
- candidate / image ID：`shaiwei:scheduler-8009eeb50c7d35f5` /
  `sha256:da267602...5cea4d7`；
- claim / report / tree file / tree content：`52d956ea...64f7f` / `7bb5e6c1...54e7` /
  `b5fcf8a1...fe5e` / `03f564da...c4e4`；
- 终态：`BUILD_PASS / FIXTURE_FAIL / NO_GO_PROMOTION`；锁行为权威：
  `LOCK_BEHAVIOR_NOT_EVALUATED`。

稳定卷 `shaiwei_runtime_locks_v1` 已由前驱 suite 创建并保留。R2C-R1 不删除该卷，不清除旧候选或旧
证据，也不复用旧输出根。

## 3. 唯一允许的实现变化

只允许替换 `eight_threads_with_noop_flock` 的执行适配器：

1. 候选内固定 payload 导入真实 `logical_lock` 和 `runtime:daily-cycle`；
2. 在候选进程内把底层 `fcntl.flock` 替换为 no-op；
3. 启动恰好 8 个线程，并用 barrier 使其同时争用；
4. 调用 `logical_lock` 时不得出现显式 `lock_root`；
5. 断言临界区最大同时活跃数恰好为 1，结束时活跃数为 0；
6. Docker 命令形状必须继续携带真实 authority 环境、稳定卷挂载、只读根、断网和降权参数。

其余 9 个用例、执行顺序、安全挂载、claim-first、命令计数、证据写入、失败即停和同 scope 禁止重跑
全部保持不变。不得借本恢复修改生产锁、Compose、release、scheduler、业务 schema 或门槛。

## 4. 工程验收与停止点

工程阶段须有两层证明：一是零 Docker 的本地子进程运行同一固定 payload，验证 no-op `flock` 下 8
线程串行；二是命令形状测试证明真实 daemon 调用将执行 `python -c <固定 payload>`，且不再引用宿主
pytest 或显式锁根。全仓、架构、Ruff、diff-check 和脱敏门仍须通过。

工程提交推送后，重新绑定最终 `HEAD == origin/main`、代码快照、候选标签和新 scope。只有用户再次
逐字批准动作 `R2C_R1_RUNTIME_LOCK_FIXTURE_ENTRY_RECOVERY_ONCE` 后，才允许恰好构建一个新候选并
调用一次完整 suite；build 或 suite 失败仍消费新 scope，不得重跑。

## 5. 当前不授权

当前不授权 Docker build、Docker fixture、volume 创建/删除、promote、restart、真实业务、历史回填、
生产 ledger、网络、密钥、Web、模型、策略、DeepSeek、模拟仓或生产。R2C-R1 未全绿前不得进入 R2D
或启动 R2-1R1。

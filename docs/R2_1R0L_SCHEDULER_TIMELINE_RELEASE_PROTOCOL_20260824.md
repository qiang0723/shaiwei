# R2-1R0L Scheduler Timeline 不可变发布协议

- 冻结时间：2026-08-24T17:02:00+08:00
- 合同：`r2-1r0l-scheduler-timeline-release-v1`
- 机器真身：`config/r2_1r0_scheduler_timeline_release_v1.yaml`
- 状态：`FROZEN_ENGINEERING_ONLY_BUILD_AND_PROMOTE_NOT_AUTHORIZED`
- 生产授权：无

## 1. 前置门

R2-1R0 phase timeline 工程已 `GO_ENGINEERING_ONLY`；R2-1H0 已完成接电 `sleep=0`，用户同时人工确认
Docker Desktop“登录时启动”已开启，因此宿主门关闭为 `GO_HOST_AVAILABILITY_COMPLETE`。

旧生产 scheduler 必须在施工期间保持：容器 `183b8c6c5edd...23dd3b`、镜像
`sha256:722f63de...13b76`、原启动时间、`running/healthy` 和 `unless-stopped`。

## 2. 新发现的发布边界

当前 `release.build_image()` 要求整个 live worktree 绝对干净；但生产 scheduler 正常追加六份受控业务
账本，且 live worktree 中还有三份不属于本节点的既有平台校准草稿。为了构建镜像而暂存、提交、stash、
checkout、reset、删除或覆盖这些文件，会把发布动作与运行证据/用户工作混在一起，禁止采用。

基础 Dockerfile 只复制冻结 `CONTROLLED_FILES` 和四个受控根；ledger/logs/data 已被 `.dockerignore` 排除，
普通 docs 也默认排除。因此应把“整棵活工作树干净”收敛为更强的“镜像来源恰好等于已推送提交”：

1. `HEAD == origin/main`；
2. live worktree 中任何受控输入的 tracked/staged/untracked 变化都失败关闭；
3. 使用 `git archive HEAD` 在项目内 Git 忽略的 `.release/scheduler-build-contexts/` 创建临时上下文；
4. 只从该上下文计算 snapshot、构建镜像和验证 manifest；
5. 非受控自然账本和用户草稿保留在 live worktree，不进入上下文，也不影响镜像；
6. 构建审计仍写入 live 项目的 `logs/releases`，临时上下文结束后删除。

这不是放宽身份门：镜像从“可能混有 live 内容的工作树”升级为“只能来自已推送 Git 树”。

## 3. 分阶段权限

### R2-1R0L-A：构建上下文工程

只允许修改 release/provenance 的窄构建适配器、测试、机器合同和文档。须证明：

- 自然账本和非受控草稿存在时仍选择 Git archive；
- 任一受控文件 dirty/untracked 时失败关闭；
- HEAD 未推送时失败关闭；
- archive snapshot 与镜像 label/runtime manifest 三者相等；
- 不读取 `.env`，不把 data/ledger/logs/用户草稿复制进上下文；
- 不 build、不启动 fixture、不 promote、不重启 scheduler。

### R2-1R0L-B：候选构建与断网 fixture

必须在 A 代码推送后另获授权，且避开 16:00—19:30：

1. 从已推送提交恰好构建一个内容寻址候选；
2. 构建网络只用于冻结依赖安装，不挂 secret 或 `.env`；
3. 同一候选以 `network=none`、只读根、无 data/ledger 挂载运行一次 synthetic timeline fixture；
4. fixture 只写 `.release/scheduler-timeline-fixture/logs`，验证哈希链和跨午夜绑定；
5. 项目真实 logs、业务账本、scheduler 容器均不变；
6. 输出候选镜像 ID、snapshot、Git、fixture 哈希后停止。

### R2-1R0L-C：生产提升

候选通过后仍须用户绑定精确镜像/快照再次批准。提升前必须：

- 不在 16:00—19:30；
- `release_start_readiness` 证明存在晚于旧 paper snapshot 的合法新交易日；
- current/previous、发布哈希链和回滚目标完整；
- promote 失败自动恢复旧 current；
- 不输出完整 Docker 环境。

提升后只验证容器身份、只读根、data/ledger/logs 唯一挂载、health 和 timeline 新文件；不手工触发真实
业务周期，不回填历史 phase。

## 4. 验收与后继

生产发布成功不等于 R2-1R1 通过。候选必须先经历首个自然交易日完整 cycle；确认 phase chain、业务
账本、影子、双账户、飞书与幂等均正常后，再结果前冻结 R2-1R1 新连续区段。门槛仍为 20 个
live-dual 交易日和至少 2 次自然调仓。

## 5. 当前停止点

当前仅冻结协议。由于冻结时处于 16:00—19:30 数据窗口，不运行测试洪峰、Docker build、fixture、
promote、restart 或真实业务。下一合法节点是 R2-1R0L-A 轻量工程，须在数据窗口结束后施工。

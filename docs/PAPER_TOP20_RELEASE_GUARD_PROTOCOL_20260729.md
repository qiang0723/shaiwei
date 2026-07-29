# Top20 单次生产切换守护协议

协议 ID：`paper-top20-release-guard-20260730`

冻结日期：2026-07-29（UTC+8）

目标日期：2026-07-30（本地官方交易日历已确认开市）

## 1. 目的

连续两个交易日均在原 scheduler 完成 Top30 后才收到人工通知，跨快照启动门因此正确 fail closed。
本协议只补齐一次性发布时点守护：在新交易日已进入本地可用资格、原 scheduler 尚未完成当日
Top30 时，启动已提升的 Top20 候选。它不修改模型、信号、交易规则、数据门、调仓周期或账户资金。

## 2. 唯一候选与当前生产真身

唯一允许启动的候选固定为：

- 内容标签：`shaiwei:scheduler-4e5244b6b02739dd`
- image ID：`sha256:722f63de15932cb2698e82db7c0140f02921f27f126e1c0235ca62e0a1213b76`
- 代码快照：`4e5244b6b02739dd209a9b01ea715c43ed9a874a7014156e20cf364f06a82708`
- Git：`210af4dab33c85b38c05b28f56c176b7970c41db`

守护启动前唯一允许存在的生产真身固定为：

- image ID：`sha256:de87ec740981166b032b394fb256a978acdc8d35e999a369f1debc3466aa0261`
- 代码快照：`eb8e752132ac1fbe6a9557d26b4c7a65df36f6169d617b6e1e10db88d46b7fbd`
- 最新 Top30 FORWARD 执行日：`20260729`

候选、发布指针、运行中镜像或最新 FORWARD 身份任一不符即停止，不自动修复、不改指针、不换候选。

## 3. 时间窗

- 时区固定 `Asia/Shanghai`。
- 只允许在 2026-07-30 16:05:00（含）至 19:00:00（不含）执行。
- 本地日历计划必须返回唯一新日期 `20260730`，且它必须晚于最新 Top30 执行日。
- 过早、过期、休市、计划多日积压、当日已被旧快照完成或时间/日历不明确均 fail closed。

19:00 截止给原 19:30 正式批次保留至少 30 分钟边界；守护不等待到临界时点强切。

## 4. 前置门

守护在任何 Docker 变更前必须逐项通过：

1. 工作树干净，`HEAD == origin/main`；不隐式 fetch、pull、build、commit 或 push。
2. 发布审计哈希链 PASS，current 指针与本协议候选四项身份逐字一致。
3. 候选标签和镜像运行时身份复核 PASS；不得读取或输出容器环境变量。
4. 当前 scheduler healthy，定向读取的 image ID/代码快照与本协议旧真身一致。
5. 最新 `model_baseline` PASS 行恰为 `20260729` 和旧代码快照。
6. 既有 `release_start_readiness()` 返回 `CROSS_SNAPSHOT_WITH_NEW_DATA`，且唯一新日期为
   `20260730`。

任一门失败时只返回结构化 `BLOCKED`，不调用 `start_current()`，不写 release 审计，不发送飞书，
不改生产文件。

## 5. 唯一获准动作

全部前置门 PASS 后只调用一次既有 `start_current()`：

- 不 build、不 promote、不 rollback、不运行 `daily --once`；
- 由既有发布层完成 current 标签复核、scheduler 单服务 force-recreate、只读根/挂载白名单、
  运行时代码与 Git 身份及健康检查；
- 成功后只产生既有 `START_PASS` 发布审计记录；守护自身不另造生产账本。

如果候选已经按精确身份运行，守护返回 `ALREADY_ACTIVE`，不得重启第二次。

## 6. 后置验收与停止边界

启动成功只证明发布切换完成，不证明当日数据、Top20 前瞻或策略有效：

- 候选按其冻结的 19:30 口径自然串行运行 Top30、Top20；守护不手工触发。
- 当日晚间另核验日增量、`.BJ=0`、S1—S9、S10、信号、Top30、Top20、飞书与幂等。
- Top20 首个自然 FORWARD 独立 PASS 后，才允许在后续另一交易日处理 16:00 早探测候选。
- 若启动后容器契约失败，沿用既有发布失败语义并人工裁决；守护不得自行扩大为回滚流程。

## 7. 验收要求

- fixture 覆盖过早、过期、错误日期、多日积压、脏工作树、远端不同步、候选漂移、当前容器漂移、
  最新 FORWARD 漂移、安全门阻断、已激活幂等和唯一一次启动。
- 测试必须证明所有阻断发生在 `start_current()` 前，且阻断路径零发布写入。
- 全仓测试、Ruff、compileall、`git diff --check`、追加式账本与脱敏检查 PASS。
- 施工和自动化安排不得重启或改变今晚运行中的生产 scheduler。

## 8. 结论边界

本协议只授权 `GO_ONE_SHOT_RELEASE_GUARD_ENGINEERING`。当前
`strategy_effective=NOT_EVALUATED`、`production_authorization` 仍仅限已批准的 Top20 模拟账户日更；
不授权实盘、策略比较结论、16:00 早探测切换或其他研究施工。

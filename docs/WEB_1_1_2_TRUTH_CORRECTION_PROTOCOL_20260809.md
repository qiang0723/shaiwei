# Web 1.1.2 前瞻分层与路线事实投影修正协议

- 协议 ID：`web-1.1.2-truth-correction-v1`
- 冻结日期：2026-08-09（UTC+8）
- 状态：`FROZEN_IMPLEMENTATION_ONLY`
- 权限：本机只读 Web 查询、投影和展示修正
- 不授权：模型、信号、模拟成交规则、scheduler、生产账本、研究重跑、外网或写 API

## 1. 结果目标

Web 必须让用户区分三件不同的事实：单账户产物的协议 `FORWARD`、Top20 的受控追赶，以及 Top30 / Top20
同日自然运行证据。当前页面把 Top20 的 10 个协议 `FORWARD` 全部称作“自然前瞻”，并据此绘制趋势图；
这与 `r2-1-forward-checkpoint-v1` 已冻结的 5 日受控追赶、5 日 live-dual 分层冲突。

同时，策略工厂仍停留在 2026-08-06 的路线投影，未显示 2026-08-09 的
`COURSE_CORRECTION_AND_OBSERVE`、M7 数据门终止和 R2-1 当前主目标。本次只修事实投影和页面语义，
不重新设计 Web 1.1.1，也不增加研究或交易控制能力。

## 2. 权威输入与不变量

权威输入固定为：

1. `config/r2_1_forward_checkpoint_v1.yaml`；
2. `docs/R2_1_FORWARD_CHECKPOINT_PROTOCOL_20260809.md`；
3. `docs/PLATFORM_ROUTE_REVIEW_20260809.md`；
4. `docs/M7_MONEYFLOW_EVIDENCE_RECOVERY_NETWORK_EXECUTION_ACCEPTANCE_20260809.md`；
5. 两个模拟账户身份、`ledger/paper_runs.csv`、对应不可变账户日产物、影子信号和冻结 SSE 开市日历身份；
6. 既有 `strategy_factory_v3` 内容寻址快照。

以下事实不得改变：两个账户初始资金均为 500,000 RMB、基准为 `000906.SH`、Top30 / Top20 策略身份、
2026-07-31 共同状态锚点、2026-08-03 live-dual 起点、20 日 / 2 次自然调仓门、现有工作包和因子准入计数。
旧账本、产物、`mode=FORWARD`、旧策略工厂快照及其哈希永久保留，不覆盖、不改写。

## 3. 后端职责与输出合同

新增独立、窄职责的 Web 前瞻检查点投影模块；`query.py` 只负责组装。权威分类必须在后端完成，前端不得
根据日期、订单数或文案复制业务公式。

`paper/forward` 和原子总览新增 `paired_checkpoint`：

- `protocol_forward_count`：两账户在同一执行日均有唯一 PASS、产物均为 `FORWARD`；
- `controlled_catchup_count`：协议 FORWARD 中至少一账户的 Asia/Shanghai 启动日期晚于执行日；
- `live_dual_count`：两账户均在执行日由 `docker-scheduler` 启动，并通过冻结身份、同日证据、官方开市日、
  重放、会计、新鲜度和 `.BJ=0` 门；
- `live_dual_rebalance_count`：匹配影子信号 `rebalance_due=true` 的完整双账户自然周期；订单为 0 也计周期；
- 共同锚点、20 / 2 门槛、计划日期、覆盖状态、终态和 live-dual 精确序列；
- 当前允许终态只有 `NOT_DUE / BLOCKED_EVIDENCE / OBSERVED_WITH_EXECUTION_WARN / CHECKPOINT_OBSERVED`。

单账户 `forward_observation_count` 保持“协议 FORWARD”含义以兼容现有 API，但每个账户日新增证据分层。
Top20 的受控追赶不得再标为自然，也不得与 live-dual 拼成一条自然效果曲线。

缺少冻结配置、日历覆盖、任一账户日、策略身份、同日证据、重放、会计、新鲜度或 `.BJ` 门时，检查点
返回 `BLOCKED_EVIDENCE` 并列出受控原因；不得静默取交集、改用订单数推断调仓或回退旧口径。

## 4. 页面修正

### 总览

保留 Top30 单账户的协议 FORWARD 结果，另增紧凑的“双账户自然检查点”：当前 live-dual 日 / 20、自然
调仓 / 2、共同锚点、下一预计证据日和最早检查点。预计日期明确标注为计划，不替代账本。

### 模拟组合

- Top20 首屏分别显示“协议 FORWARD”“受控追赶”“同日自然”，禁止把 10 日统称自然前瞻；
- 账户日表增加“证据分层”；
- 当前 live-dual 仅 5 日，按 Web 1.1 既有门槛只展示精确表，不绘制自然趋势；
- 共同锚点固定为 2026-07-31，Top20 锚点来源必须常驻说明；
- 不输出优胜、失败、策略 GO/REJECT、生产切换、年化、Sharpe、信息比率或显著性。

### 策略工厂

在既有 v3 证据之上增加内容寻址的路线 overlay，首屏显示：

- 当前路线 `COURSE_CORRECTION_AND_OBSERVE`；
- 暂停新增股票池、因子、LLM 批次、通用控制面和无目标重构；
- M7 终态为数据证据恢复仍不完整，候选和效果均未进入；
- 当前主目标为 R2-1 自然前瞻检查点；
- “可研究股票池”只表示底层能力，不表示当前获准开工。

## 5. 架构、迁移与回滚

- 新业务计算放在独立 Web 投影模块，不增长既有热点 `types.ts`；前瞻类型进入独立 TypeScript 文件。
- Web 镜像仅复制白名单配置和权威文档，不挂载原始行情、`.env`、Docker socket 或项目根目录。
- 既有端点向后兼容；新增字段由新前端消费，旧字段不改名、不改数值。
- 回滚恢复旧 Web 镜像即可；旧 v3 策略工厂快照和全部自然证据保持原样。
- 不新增常驻服务、依赖、数据库、缓存、外网、secret 或写接口。

## 6. 验收门

1. 固定真实截止日必须复算为：协议 FORWARD 10 日 / 1 次、受控追赶 5 日 / 1 次、live-dual 5 日 / 0 次；
2. 受控追赶、身份错配、缺开市日、订单为 0 的调仓周期、`.BJ`、会计错配和日历越界均有失败路径测试；
3. 前端运行时校验拒绝未知分层、错误计数、错误共同锚点和被隐藏的路线坏消息；
4. 1440 / 1024 / 768 / 390 / 320 px 无页面级横向溢出，当前 5 日不画自然趋势；
5. 全仓相称测试、`make architecture-check`、Ruff、compileall、前端构建、`git diff --check` 与脱敏检查通过；
6. 只重建隔离 Web，scheduler 容器、镜像和创建时间前后不变；
7. `STATE.md` 与验收文档区分 Web 工程完成、R2 未到期、策略未评价和生产授权无。

## 7. 停止条件

页面、API 和真实本机部署一致后停止。本任务不借机运行 R2 检查点、不提前读取未来结果、不恢复 M7、
不新增研究任务，也不因页面施工改变 2026-08-14 / 2026-08-28 的计划边界。

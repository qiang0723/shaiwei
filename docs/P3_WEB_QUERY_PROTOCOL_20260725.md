# P3-0 Web 1.0 只读查询协议（结果前冻结）

> 冻结日期：2026-07-25（Asia/Shanghai）
>
> 协议：`p3-web-query-v1`
>
> 状态：`FROZEN_BEFORE_IMPLEMENTATION`

## 1. 本阶段目标

P3-0 只施工 Web 1.0 的可信查询底座：

1. 原子 `overview_snapshot`；
2. 独立 FastAPI 只读适配层；
3. 默认不启动的隔离 `web-query/web-ui` Docker profile；
4. 模拟仓、FORWARD 专属业绩、最新信号与次日对账的确定性投影；
5. 契约、脱敏、错误状态、幂等和生产隔离验收。

本阶段不是完整 Web 页面，不授权下单、在线改参、导出、任意文件访问、SQL、因子工厂接口、
远程访问或生产发布；不修改模型、策略、研究门禁、生产数据、生产账本或运行中的 scheduler
镜像。

## 2. 权威输入与固定边界

固定账户只有 `model_baseline`。只读输入白名单为：

- `ledger/shadow_runs.csv`
- `ledger/shadow_reconciliations.csv`
- `ledger/paper_accounts.csv`
- `ledger/paper_events.csv`
- `ledger/paper_runs.csv`
- 上述账本登记且位于 `data/shadow/signals/`、`data/shadow/reconciliations/`、
  `data/paper/` 的不可变产物
- `logs/notifications/feishu_YYYYMMDD.jsonl` 的脱敏投递证据

不得读取 `.env`、原始行情、Parquet、模型文件、Docker socket、Git 元数据或白名单外路径。
账本中的绝对路径、`..`、符号链接越界或不在批准前缀内的产物一律
`EVIDENCE_MISMATCH`。任何返回对象出现 `.BJ` 一律失败，不得静默过滤后继续。

## 3. 原子快照与幂等

`overview_snapshot(as_of)` 按以下顺序形成证据切片：

1. 在固定白名单内列出输入；
2. 读取账本与通知文件的字节快照并记录大小、修改时间和 SHA-256；
3. 按账本选择不晚于 `as_of` 的最新 PASS 信号、模拟账户日和已到期对账；
4. 读取被选中的不可变产物，逐项核对账本身份、文件 SHA-256 和内容哈希；
5. 独立重放所选账户日的事件链、状态链和会计恒等；
6. 再次核对输入集合、大小和修改时间；期间变化则最多重试两次，仍变化返回 `CONFLICT`；
7. 对规范化证据身份计算稳定 `snapshot_id`。相同证据与参数必须产生相同
   `snapshot_id`、ETag 和业务数据。

`generated_at` 固定为本切片内最新权威证据时间，不用查询时钟制造伪变化。HTTP
`request_id` 不进入 `snapshot_id`。

## 4. 总览状态

总览固定返回：

- 身份：`schema_version/snapshot_id/as_of/generated_at/timezone`
- 分列状态：`operational_status/evidence_status/performance_observation_status/notification_status`
- 综合：`overall_status/status_reason/required_evidence_complete`
- 信号：信号日期与哈希、调仓判定、目标数、计划交易腿、下一执行日、执行证据状态
- 组合：最新账户日、净资产、现金、市值、实际持仓数、重放状态
- FORWARD：锚点、观察数、专属组合/基准净值、净值差、回撤、费用、换手、现金比例与成熟度
- 证据：代码/数据/模型/信号/产物哈希、`.BJ=0`

综合状态优先级固定为：
`FAIL > STALE > WARN > NOT_READY > PASS`。通知投递和核心任务分列；通知重试后恢复为
`WARN`，不得覆盖早先失败尝试，也不得把核心任务改成 FAIL。

## 5. 信号与执行时钟

最新信号只返回生成时已成立的事实：信号/代码/数据/模型身份、目标排名与权重、相对上一
目标的新增/保留/移除，以及信号生成前最后一个完成模拟账户日的实际权重参照。

- `rebalance_due=false` 时 `planned_trade_leg_count=0`；
- `rebalance_due=true` 时计划腿按目标权重与信号生成前实际权重的确定性差异计算；
- 计划腿不是订单或成交；
- 只有已登记 PASS 对账才返回真实执行日、实际交易腿、可成交统计、开盘偏差、换手与成本；
- 尚无已登记对账时 `execution_evidence_status=NOT_DUE`，`next_execution_date=null`，不得
  用周末规则或本地时钟猜测官方开市日。

## 6. 模拟组合与 FORWARD 口径

逐仓查询投影固定为：

- `actual_weight = market_value / net_asset`
- `unrealized_pnl = market_value - cost_basis`
- `realized_pnl` 与 `stale_trade_days` 原样保留

净资产必须等于现金加市值，字段缺失或净资产非正时失败。

FORWARD 序列以首个 FORWARD 前最后一个 BACKFILL 账户日为唯一锚点：

- `forward_portfolio_nav = normalized_nav_t / anchor_portfolio_nav`
- `forward_benchmark_nav = benchmark_nav_t / anchor_benchmark_nav`
- `forward_net_excess = forward_portfolio_nav - forward_benchmark_nav`

P3-0 不挂载官方交易日历，因此覆盖率明确为 `NOT_EVALUATED`。在补齐官方日历证据前，即使
观察日达到 252/504，也不得展示年化、Sharpe 或信息比率；当前只允许
`NOT_READY/OBSERVING`。这是一项 fail-closed 约束，不改写 R5 的长期门槛。

## 7. HTTP 与错误契约

允许端点与资源限制以 `config/p3_web_query_v1.yaml` 为准。只允许 `GET/HEAD`，关闭
OpenAPI/Swagger/ReDoc，不启用宽泛 CORS。成功响应使用 `web-v1` 包络，失败响应只返回稳定
错误码和脱敏文案，不返回异常栈、本地绝对路径、密钥或原始日志。

固定错误码：

- `INVALID_ARGUMENT`
- `NO_DATA`
- `NOT_READY`
- `STALE`
- `EVIDENCE_MISMATCH`
- `FORBIDDEN_UNIVERSE`
- `CONFLICT`
- `INTERNAL_ERROR`

单次 NAV 最多 1,000 个账户日；单响应最大 1 MiB；当前日响应 `Cache-Control: no-store`。

## 8. Docker 隔离

新增独立 `compose.web.yaml`，不修改或继承生产 `compose.yaml` 的 scheduler 服务：

- 两个服务都属于显式 `web` profile，启动时必须点名
  `web-query web-ui`；
- 不加载 `.env`，不挂项目根目录；
- `web-query` 仅挂载第 2 节白名单目录，全部只读，不映射宿主端口；
- `web-ui` 不挂生产证据，只通过内部网络反向代理 `/api`；
- 宿主只开放 `127.0.0.1:8080`；
- 根文件系统只读、非 root、`cap_drop: ALL`、`no-new-privileges`、有界 tmpfs、
  CPU/内存/PID/并发/超时限制；
- 不挂 Docker socket，不自动启动或重建 scheduler。

## 9. 通过条件

必须全部满足：

1. 协议冻结提交早于实现提交；
2. 原子快照、内容哈希、事件重放、会计恒等和 `.BJ` fail-closed 测试通过；
3. BACKFILL/FORWARD 分段与锚点公式测试通过；
4. 信号时钟、`NOT_DUE`、计划腿/成交腿分离测试通过；
5. API allowlist、错误脱敏、文档关闭、方法拒绝、响应上限与稳定 ETag 测试通过；
6. Docker profile 默认不启动、无 `.env`、无整仓挂载、无 query 宿主端口、UI 仅回环；
7. 重复查询业务响应与证据身份一致；
8. 全仓测试、Ruff、compileall、依赖、Compose、Git 脱敏检查通过；
9. scheduler 容器身份、挂载、健康状态不变。


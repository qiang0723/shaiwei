# Web 1.0 主控架构裁决

> 裁决日期：2026-07-23（Asia/Shanghai）
>
> 状态：`ACCEPT_WITH_GUARDRAILS`
>
> 边界：本裁决冻结 Web 查询、部署和展示边界，不授权立即修改后台、启动 Web 服务或影响 P0.5 首个自然 `FORWARD` 验收。代码施工须另立目标。

## 总结

Web 1.0 的七页结构、指标分层、只读原则和证据优先方向通过主控复核。七项未决提案均得到明确裁决，其中 `latest_signal`、逐仓字段和前瞻业绩口径按本文件收紧。实现顺序保持：总览 → 模拟组合 → 股票池/信号；因子工厂先保留专业页面与契约设计，待后台形成可审计只读查询后再接真实数据。

## R1 — 原子 `overview_snapshot`：接受

首页必须由后台生成一个原子快照，前端不得把多个“最新”响应拼成同一结论。最小要求：

- 固化 `schema_version/snapshot_id/as_of/generated_at/timezone`；
- 分列 `operational_status/evidence_status/performance_observation_status/notification_status`，综合状态只由后台聚合；
- 每个组成对象携带业务日期、证据身份和哈希，全部属于同一 `snapshot_id`；
- 明确最近完整交易日、信号身份、下一执行日、模拟仓账户日、重放状态和 `.BJ=0`；
- 前瞻业绩引用 R5 的 FORWARD 锚点与专属序列，不引用混合 BACKFILL 的累计结果冒充前瞻表现。

任一必需组成对象跨快照、哈希断链或返回 `.BJ` 时，快照失败，不允许降级成 PASS。

## R2 — FastAPI 只读适配层与 Web Docker profile：接受

选择 FastAPI 是因为现有权威查询均为 Python 函数，适配层只做校验、包络、脱敏和访问控制，不重新计算研究口径。施工时必须满足：

- `web-query` 与 `web-ui` 进入显式 `web` profile；启动命令必须显式点名两个 Web 服务，禁止用裸 `docker compose --profile web up` 意外带起无 profile 的服务；
- Web 服务不得继承当前 `x-shaiwei-common`，不得加载 `env_file: .env`，不得挂载整个项目根目录；
- 查询服务只挂载经批准的 `ledger/`、`data/paper/`、信号/报告和脱敏通知证据子路径，全部 `read_only`；
- 容器根文件系统 `read_only: true`，临时空间只用有界 `tmpfs`；使用非 root 用户、`cap_drop: [ALL]`、`no-new-privileges`，不挂 Docker socket；
- `web-query` 不发布宿主机端口；`web-ui` 在内部网络反向代理 `/api`，宿主机只绑定 `127.0.0.1`；首版不需要宽泛 CORS；
- 只开放 allowlist 中的 `GET/HEAD` 查询，关闭任意路径、SQL、文件浏览和生产改写；API 文档端点默认关闭；
- 配置 CPU、内存、并发、超时、响应上限和脱敏结构化日志；健康检查不得写生产目录；
- 局域网或公网暴露、认证、多用户和远程部署必须另立安全目标。

FastAPI 官方容器方案和 Docker Compose profile/read-only 语义仅支持这一选型的工程可行性，不替代上述项目级隔离要求。

## R3 — `latest_signal` 原子字段与可成交性边界：部分接受并改名

`latest_signal(as_of)` 只陈述信号生成时已经成立的事实：

- 信号日期、生成时间、模型/代码/数据/信号哈希、调仓判定和下一官方执行日；
- 目标排名、证券、目标权重、相对上一目标的新增/保留/移除；
- 最近已完成模拟仓账户日及其实际权重，必须附 `actual_weight_as_of` 和账户证据哈希；
- `planned_trade_leg_count` 和逐证券 `planned_weight_delta`，明确只是信号时点计划，不是成交事实；
- `.BJ=0` 证据，返回 `.BJ` 立即失败。

次日停牌、方向性涨跌停、真实开盘、实际成交腿、开盘偏差、换手和成本只有执行日证据形成后，才能由 `shadow_reconciliation(signal_sha256)` 返回。执行日前只允许 `execution_evidence_status=NOT_DUE`；禁止在 `latest_signal` 中预测或伪报“可成交”。

## R4 — 逐仓实际权重、未实现盈亏与估值陈旧度：接受查询投影

不可变账户日产物已经包含 `market_value/cost_basis/realized_pnl/price_date/stale_trade_days`。因此：

- `stale_trade_days` 直接按原字段展示，不新增第二套定义；
- 查询层可确定性输出 `actual_weight = market_value / net_asset`；
- 查询层可输出 `unrealized_pnl = market_value - cost_basis`；
- 同时保留 `realized_pnl`，不得把两者相加冒充账户总收益；
- 净资产无效、字段缺失或账户恒等失败时不得计算；
- 这些字段只作为查询投影新增，不回写或重做历史事件/运行产物。

目标权重仍来自不可变信号，并与 `actual_weight_as_of` 对齐后才允许计算权重偏差。

## R5 — FORWARD 业绩锚点与样本门槛：接受分层门槛

### R5.1 前瞻专属锚点

当前账户先有四个 `BACKFILL` 账户日，现有 `net_excess = normalized_nav - benchmark_nav` 是全账户累计净值差。首页不得把它直接称为 FORWARD 业绩。

后台须固化最后一个 BACKFILL 账户日为前瞻锚点，并返回：

- `forward_anchor_trade_date`；
- `forward_anchor_portfolio_nav` 与 `forward_anchor_benchmark_nav`；
- `forward_portfolio_nav_t = normalized_nav_t / forward_anchor_portfolio_nav`；
- `forward_benchmark_nav_t = benchmark_nav_t / forward_anchor_benchmark_nav`；
- `forward_net_excess_t = forward_portfolio_nav_t - forward_benchmark_nav_t`，展示单位为百分点；
- 锚点账户日、策略版本、代码和产物哈希。

BACKFILL 与 FORWARD 可在审计图中分段展示，但主结果卡只使用上述 FORWARD 专属序列。

### R5.2 展示成熟度

| 成熟度 | 最小证据 | 允许展示 | 禁止结论 |
|---|---|---|---|
| `OBSERVING` | 1–251 个完整 FORWARD 账户日 | 前瞻累计收益、累计净超额、回撤、费用、换手、现金比例、样本数 | 年化、Sharpe、信息比率、策略有效性 |
| `ANNUALIZED_READY` | ≥252 个账户日、覆盖率 ≥95%、跨度 ≥12 个月 | 后台产出的前瞻年化收益与年化波动；仍标“早期描述” | Sharpe/信息比率、G8 判决 |
| `RISK_ADJUSTED_READY` | ≥504 个账户日、覆盖率 ≥95%、跨度 ≥24 个月、≥40 个完成调仓周期 | 后台公式冻结后可展示 Sharpe/信息比率，并标 `PROVISIONAL` | 把风险调整指标当作准入或长期有效性判决 |
| `EVALUATION_READY` | 满足 G8 的 720 个共同观察及其余冻结条件 | 可进入 G8 三年裁决 | 自动判 PASS |

Sharpe 必须冻结无风险收益来源，信息比率必须冻结主动收益定义；二者都必须记录序列相关修正方法，禁止简单套用 `sqrt(252)`。达到天数但公式未冻结时仍隐藏。以上门槛是 Web 展示门槛，不替代 G8、G1 或任何研究门禁。

## R6 — 脱敏只读导出：原则接受，首期后置

首期三个页面稳定后才能启用导出。只允许导出当前已显示、后端 allowlist 批准的派生视图：

- 禁止原始行情、Parquet、账本全量、任意路径、SQL、完整日志、秘密和通知签名材料；
- 默认排除完整本地路径，证据哈希是否导出由字段 allowlist 决定；
- 固定账户、日期范围和最大行数，返回 `.BJ` 立即失败；
- CSV 必须防公式注入，JSON 必须使用稳定 schema；
- 导出动作写入脱敏的 Web 容器结构化日志，不写生产账本；
- 仅限本机回环地址。任何共享、上传或公网下载另行授权。

## R7 — 因子工厂四组查询：接受设计，延后施工

接受 `factor_catalog/factor_detail/factor_compare/factor_admission_history` 四组只读提案，但不在正式因子库为 0 时虚构真实页面数据。附加约束：

- `factor_catalog` 后端分页，排序字段 allowlist，默认不按收益排序；
- `factor_detail` 按 `identity/gates/quality/ic/monotonicity/stability/tradability/correlation/incremental/evidence` 分节或按需加载，避免单次返回无限时序；
- 每节固定 `factor_version/metric_schema_version/as_of` 和完整可比身份；
- `factor_compare` 最多 3 个版本，由后端验证宇宙、窗口、horizon、中性化、成本和规则版本；不一致返回 `CONFLICT`；
- `factor_admission_history` 只追加展示，保留所有 REJECT、失败门和实验总账 N；
- 前端不扫描实验账本、不重算 IC/DSR/Newey-West、不改变方向或门槛。

## 施工顺序

1. 先完成 P0.5 首个自然 FORWARD 验收并保持 scheduler 稳定；
2. 用脱敏示例数据完成本地可点击原型与浏览器 QA；
3. 单独实现只读查询投影、`overview_snapshot` 和 FORWARD 专属序列；
4. 实现隔离的 `web-query/web-ui` Docker profile；
5. 首期只接总览、模拟组合、股票池/信号；
6. 真实使用复盘后再决定因子工厂查询与导出施工。

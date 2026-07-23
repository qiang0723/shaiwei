# Web 1.0 查询契约映射（v1.0）

> 本文区分“已实现 Python 只读查询”和“Web 需求提案”。名字出现在提案区不代表 API 已存在。

## 1. 已实现契约

权威实现：`src/shaiwei/paper/query.py`。当前无 HTTP 路由。

### 1.1 `paper_portfolio_snapshot(account_id="model_baseline", as_of=None)`

- 选择不晚于 `as_of` 的最近一个 PASS 运行；无完成快照则抛 `PaperQueryError`。
- 公共身份：`as_of/generated_at/account_id/execution_policy_version/source_refs/evidence_hashes`。
- 结果字段：`freshness_status/mode/cash/market_value/net_asset/normalized_nav/benchmark_nav/net_excess/drawdown/cumulative_fees/cumulative_dividends/positions`。
- 页面：模拟组合身份、会计卡、当前持仓、证据抽屉。
- 限制：没有 `forward_status`；`positions` 的精确子字段以运行产物为准；没有目标权重或现金拖累。

### 1.2 `paper_orders_fills(signal_sha256, account_id="model_baseline")`

- `signal_sha256` 必须恰好匹配一个完成运行，否则错误。
- 公共身份同上；结果字段：`freshness_status/mode/orders/fills/corporate_actions`。
- 页面：账户日执行区、订单/成交/公司行为抽屉。
- 限制：成交率、原因分布只能在同一响应内做显示聚合；字段级 schema 尚未作为 Web 契约冻结。

### 1.3 `paper_nav_series(account_id="model_baseline", start=None, end=None)`

- 范围内必须至少一个完成观察，且不能跨多个 `execution_policy_version`。
- 身份：`as_of/generated_at/account_id/execution_policy_version/freshness_status/source_refs/evidence_hashes`。
- 状态：`forward_status/forward_observation_count`。
- series：`trade_date/mode/normalized_nav/benchmark_nav/net_excess/drawdown/turnover/cash_ratio/daily_fees/freshness_status`。
- 页面：组合净值、净超额、回撤、换手、现金和费用。
- 限制：当前 `forward_status=PASS` 仅表示存在 FORWARD 观察，不代表长期策略有效。

### 1.4 `verify_paper_replay(account_id="model_baseline")`

- 从账户、事件、运行账本独立重放并核对不可变产物。
- 返回：`status/account_id/as_of/run_count/event_count/order_count/fill_count/mode_counts/ledger_hashes`。
- 页面：组合证据身份、系统运行审计摘要。
- 限制：没有通用 `generated_at/source_refs/freshness_status` 包络；Web 适配层不得伪造其业务含义。

### 1.5 `paper_forward_acceptance(account_id="model_baseline")`

- 无自然 FORWARD 时：`status=NOT_READY/forward_observation_count=0/replay_status`。
- 有 FORWARD 后按当前受控代码、冻结策略、Docker operator、新鲜度、`.BJ=0`、账本重放和飞书开始/完成证据 fail closed。
- 页面：总览验收状态、组合身份；不是收益有效性判决。

## 2. 页面到契约映射

| 页面模块 | 已实现查询 | 可否真实接入 | 缺口 |
|---|---|---|---|
| 总览组合摘要 | snapshot + nav + acceptance | 否，须原子总览契约 | 多请求可能跨快照；缺信号/运行/门禁/FORWARD 专属锚点 |
| 模拟组合净值 | nav | 是，代码目标获批后 | HTTP 适配、字段 schema、错误码 |
| 模拟组合当前账户 | snapshot | 是，代码目标获批后 | HTTP 适配、持仓字段说明 |
| 账户日执行 | orders | 是，需 signal hash | 页面需先从受控来源取得 signal hash |
| 组合重放 | verify | 是，代码目标获批后 | 统一包络和新鲜度说明 |
| 股票池/信号 | 无 | 否 | `latest_signal` |
| 因子目录与 tear sheet | 无 | 否 | `factor_catalog/factor_detail/factor_compare/factor_admission_history` |
| 模型/回测 | 无 | 否 | `experiment_summary` |
| 数据质量 | 无 | 否 | `data_quality_summary` |
| 系统运行/通知 | 无 | 否 | `system_run_summary`、`notification_delivery_summary` |

## 3. 需求提案（不得视为已存在）

### P-WEB-01 `overview_snapshot(as_of)`

目的：由后台原子地产生首页一致性快照，绑定 `snapshot_id`、受控代码、数据快照和验收范围。

最小字段：

- 包络：`schema_version/snapshot_id/as_of/generated_at/timezone/freshness_status/source_refs/evidence_hashes`；
- 结论：`overall_status/status_reason/required_evidence_complete`，并分列 `operational_status/evidence_status/performance_observation_status/notification_status`；
- 行动：`signal_sha256/signal_date/rebalance_due/next_execution_date/target_count/planned_trade_leg_count/execution_evidence_status`；
- 组合：仅引用同一 snapshot 下的 paper 摘要、`forward_status`、FORWARD 锚点、专属净值序列摘要和表现成熟度；
- 运行：`task_status/notification_status/first_failed_step`；
- 证据：`controlled_code_snapshot/acceptance_scope/replay_status/bse_count`。

禁止：前端把多个端点响应按“最新”拼起来；BACKFILL 回报进入主结果卡。

### P-WEB-02 `latest_signal(as_of)`

目的：一次返回不可变信号身份、目标明细和信号生成时已经存在的实际账户参照；不得提前陈述执行日可成交性。

最小字段：信号/模型/代码/数据哈希，是否调仓，上一/下一调仓日和下一官方执行日，目标排名、证券、目标权重、相对上一目标变化；最近已完成模拟仓账户日、`actual_weight_as_of`、账户证据哈希、逐仓实际权重、`planned_weight_delta` 和 `planned_trade_leg_count`；必须有 `.BJ=0` 证据。因子贡献作为可选能力，不在首版必需字段。

执行日前只返回 `execution_evidence_status=NOT_DUE`。停牌、方向性涨跌停、真实开盘、实际交易腿和成本不属于本契约。

### P-WEB-03 `shadow_reconciliation(signal_sha256)`

目的：返回信号后次日开盘对账，不与模拟成交混为一谈。

最小字段：`executed_trade_leg_count/tradable_numerator/tradable_denominator/metric_status/open_gap/turnover/estimated_cost/reasons`，并绑定信号、执行日、行情批次和代码快照。执行证据未到时返回 `NOT_DUE`，不得预测。

### P-WEB-03A FORWARD 业绩投影

目的：从连续账户日中固化最后一个 BACKFILL 锚点，返回 FORWARD 专属组合/基准净值、累计净值差、覆盖率、调仓周期和表现成熟度。现有 `paper_nav_series.net_excess` 保持全账户审计语义，不得在前端重新命名成 FORWARD 结果。

后端门槛和公式见 `WEB_ARCHITECTURE_RULINGS_20260723.md` R5。任何跨策略版本、缺锚点、缺账户日或哈希断链均失败。

### P-WEB-04 `experiment_summary(experiment_id)`

目的：返回实验身份、窗口、参数、指标、判决、失败原因和产物引用；失败实验必须可查。

### P-WEB-05 `data_quality_summary(as_of)`

目的：返回批次、覆盖、S1-S10、异常、重哈希和 `.BJ` 排除；合法空、未适用和缺失分开。

### P-WEB-06 `system_run_summary(as_of)` 与 `notification_delivery_summary(message_id)`

目的：核心任务和通知分离。通知保留每次 attempt、错误类型、retryable、recovered、重复消息风险，不能覆盖失败尝试。

### P-WEB-07 因子工厂四组契约

- `factor_catalog(status, family, data_category, as_of)`：返回因子身份、生命周期、经济假设摘要、实现版本、实验尝试 N、最新判决与证据完整性；正式库 0 插入必须如实返回空列表与状态说明。
- `factor_detail(factor_id, version)`：返回冻结定义、方向、输入字段与 PIT 时点、覆盖、RankIC/ICIR、分位收益、换手、自相关、中性化、分组、六窗口、压力期、成本、相关性、增量结果、G1 全门和证据引用。
- `factor_compare(factor_versions[])`：最多 3 个；后端验证宇宙、窗口、horizon、中性化和成本可比，任何不一致返回 `CONFLICT`。
- `factor_admission_history(factor_id)`：按时间返回所有提交、判决、失败门、规则版本、实验总账 N 和不可变证据，不覆盖旧 REJECT。

共同要求：返回 `factor_id/factor_version/research_family/benchmark_id/horizon/universe_id/neutralization/decision_rule_version/code_snapshot_sha256/data_snapshot_sha256`；所有统计量由后台冻结实现计算，前端只展示。

## 4. HTTP 适配层候选包络

主控已原则批准只读 HTTP 层；只有另立代码目标并完成隔离验收后才能采用：

```json
{
  "schema_version": "web-v1",
  "request_id": "opaque-id",
  "data": {},
  "meta": {
    "as_of": "2026-07-22",
    "generated_at": "2026-07-22T12:00:00Z",
    "timezone": "Asia/Shanghai",
    "freshness_status": "PASS",
    "source_refs": [],
    "evidence_hashes": {}
  }
}
```

错误包络：

```json
{
  "schema_version": "web-v1",
  "request_id": "opaque-id",
  "error": {
    "code": "EVIDENCE_MISMATCH",
    "message": "证据校验失败",
    "retryable": false
  }
}
```

候选错误码：`INVALID_ARGUMENT/NO_DATA/NOT_READY/STALE/EVIDENCE_MISMATCH/FORBIDDEN_UNIVERSE/CONFLICT/INTERNAL_ERROR`。HTTP 状态与业务状态分离；例如 `NOT_READY` 可为成功响应中的领域状态，而证据哈希不一致必须是失败响应。

## 5. 缓存与一致性

- `as_of` 和不可变证据身份进入缓存键；
- 当前日查询默认 `no-store` 或短 TTL，历史不可变账户日可使用 ETag=证据哈希；
- 切换页面必须保留 `as_of`，不保留不相容的局部筛选；
- 任何跨策略版本范围查询由后端拒绝；
- 浏览器缓存命中也必须显示原始 `generated_at` 和 freshness；
- 返回 `.BJ`、未知状态枚举或缺少必需证据字段时，UI 显示 FAIL，不静默丢行后继续。

## 6. 已批准的运行隔离

- FastAPI 查询服务不得继承生产 `x-shaiwei-common`，不得加载 `.env` 或挂载项目根目录；
- 只读挂载采用 allowlist，根文件系统只读，非 root、无 Docker socket、无任意路径/SQL；
- `web-query` 不映射宿主端口，由 `web-ui` 在内部网络反向代理；宿主只开放 `127.0.0.1` 的 UI 端口；
- `web` profile 启动时必须显式点名 `web-query web-ui`，避免 Compose 同时纳入未设置 profile 的生产服务；
- 详细裁决见 `WEB_ARCHITECTURE_RULINGS_20260723.md` R2。

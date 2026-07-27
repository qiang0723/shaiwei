# Web 1.0 查询契约映射（v1.0）

> 本文区分“已实现只读查询”和“Web 需求提案”。P3-0 已将 P-WEB-01/02/03/03A 落地为 HTTP
> 只读契约，P3-2A 已落地 P-WEB-05/06；P3-3B 已落地 P-WEB-04/07 的类型化 HTTP 与安全投影，
> P3-3C 已完成 P-WEB-07 四层页面；P3-4A 已落地 `experiment_catalog`，P3-4B 已完成模型/回测
> 目录、类型化详情与严格 UI 代理。七类页面均保持本机只读。

## 1. 已实现契约

原 Python 权威实现：`src/shaiwei/paper/query.py`。P3-0 原子投影与 HTTP 适配分别位于
`src/shaiwei/web/query.py`、`src/shaiwei/web/api.py`；部署边界见 `compose.web.yaml`。

2026-07-27 起，四个 HTTP 模拟组合端点支持严格枚举 `account_id=model_baseline|model_top20`，默认
仍为 `model_baseline`；未知账户 HTTP 422。四响应的 snapshot 必须绑定同一账户。Top20 当前0个自然
FORWARD，返回 NOT_READY、空序列和空锚点，不允许前端补0或跨观察类型比较。

同日起，`paper/portfolio` 的逐仓结果增加 `security_name/security_name_source/
security_name_status`，并返回 `security_name_coverage`。名称主源为账户日时点的 `namechange`，当前
`stock_basic` 只作 WARN 兜底；投影指针与 bundle 哈希进入原子 snapshot。常驻查询不挂 raw 数据，
缺失名称不得丢弃持仓或伪造名称。

### 1.1 `paper_portfolio_snapshot(account_id="model_baseline", as_of=None)`

- 选择不晚于 `as_of` 的最近一个 PASS 运行；无完成快照则抛 `PaperQueryError`。
- 公共身份：`as_of/generated_at/account_id/execution_policy_version/source_refs/evidence_hashes`。
- 结果字段：`freshness_status/mode/cash/market_value/net_asset/normalized_nav/benchmark_nav/net_excess/drawdown/cumulative_fees/cumulative_dividends/positions/security_name_coverage`；逐仓含PIT简称、来源和状态。
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
| 总览组合摘要 | `GET /api/v1/overview` | 是 | P3-0 原子快照；完整页面待 P3-1 |
| 模拟组合净值 | `GET /api/v1/paper/nav`、`paper/forward` + 严格 `account_id` | 是 | 官方日历覆盖率暂为 NOT_EVALUATED；Top20 当前0 FORWARD |
| 模拟组合当前账户 | `GET /api/v1/paper/portfolio` + 严格 `account_id` | 是 | Top30默认、Top20只读比较；已含PIT中文简称、实际权重、未实现盈亏与陈旧度 |
| 账户日执行 | orders | 是，需 signal hash | 页面需先从受控来源取得 signal hash |
| 组合重放 | `GET /api/v1/paper/replay` + 严格 `account_id` | 是 | 两账户分别独立事件/状态链重放 |
| 股票池/信号 | `GET /api/v1/signals/latest`、`signals/reconciliation` | 是 | 正式页面与原因展示待 P3-1 |
| 因子目录与 tear sheet | `GET /api/v1/factors`、详情、比较、准入历史 | 是，P3-3C 页面已完成 | 四类历史未统一登记指标固定 `NOT_EVALUATED` |
| 模型/回测 | `GET /api/v1/experiments`、已知 ID 详情 | 是，P3-4B 页面已完成 | 无逐日 NAV，不画净值；不提供搜索、表现排序或比较 |
| 数据质量 | `GET /api/v1/data-quality` | 是，P3-2B 页面已完成 | 哨兵报告尚未历史哈希绑定，证据状态固定 WARN；原始 Parquet 重哈希 NOT_EVALUATED |
| 系统运行/通知 | `GET /api/v1/system/runs`、`GET /api/v1/notifications/{message_id}` | 是，P3-2B 页面已完成 | 实时 Docker 身份 NOT_EVALUATED；旧通知 schema 只计数、不可按消息寻址 |

## 3. P3-0 已实现契约与后续提案

### P-WEB-01 `overview_snapshot(as_of)`（已实现）

目的：由后台原子地产生首页一致性快照，绑定 `snapshot_id`、受控代码、数据快照和验收范围。

最小字段：

- 包络：`schema_version/snapshot_id/as_of/generated_at/timezone/freshness_status/source_refs/evidence_hashes`；
- 结论：`overall_status/status_reason/required_evidence_complete`，并分列 `operational_status/evidence_status/performance_observation_status/notification_status`；
- 行动：`signal_sha256/signal_date/rebalance_due/next_execution_date/target_count/planned_trade_leg_count/execution_evidence_status`；
- 组合：仅引用同一 snapshot 下的 paper 摘要、`forward_status`、FORWARD 锚点、专属净值序列摘要和表现成熟度；
- 运行：`task_status/notification_status/first_failed_step`；
- 证据：`controlled_code_snapshot/acceptance_scope/replay_status/bse_count`。

禁止：前端把多个端点响应按“最新”拼起来；BACKFILL 回报进入主结果卡。

### P-WEB-02 `latest_signal(as_of)`（已实现）

目的：一次返回不可变信号身份、目标明细和信号生成时已经存在的实际账户参照；不得提前陈述执行日可成交性。

最小字段：信号/模型/代码/数据哈希，是否调仓，上一/下一调仓日和下一官方执行日，目标排名、证券、目标权重、相对上一目标变化；最近已完成模拟仓账户日、`actual_weight_as_of`、账户证据哈希、逐仓实际权重、`planned_weight_delta` 和 `planned_trade_leg_count`；必须有 `.BJ=0` 证据。因子贡献作为可选能力，不在首版必需字段。

执行日前只返回 `execution_evidence_status=NOT_DUE`。停牌、方向性涨跌停、真实开盘、实际交易腿和成本不属于本契约。

### P-WEB-03 `shadow_reconciliation(signal_sha256)`（已实现）

目的：返回信号后次日开盘对账，不与模拟成交混为一谈。

最小字段：`executed_trade_leg_count/tradable_numerator/tradable_denominator/metric_status/open_gap/turnover/estimated_cost/reasons`，并绑定信号、执行日、行情批次和代码快照。执行证据未到时返回 `NOT_DUE`，不得预测。

### P-WEB-03A FORWARD 业绩投影（已实现，覆盖率 fail closed）

目的：从连续账户日中固化最后一个 BACKFILL 锚点，返回 FORWARD 专属组合/基准净值、累计净值差、覆盖率、调仓周期和表现成熟度。现有 `paper_nav_series.net_excess` 保持全账户审计语义，不得在前端重新命名成 FORWARD 结果。

后端门槛和公式见 `WEB_ARCHITECTURE_RULINGS_20260723.md` R5。任何跨策略版本、缺锚点、缺账户日或哈希断链均失败。

### P-WEB-04 `experiment_summary(experiment_kind, experiment_id)`（P3-3B 已实现详情）

目的：返回类型化实验身份、证据层级、窗口、受控参数摘要、指标、判决、失败原因和产物引用；失败、
provisional、被替代和失效实验必须可查。

`experiment_kind` 必填，只允许 `research_experiment/p2_engineering_run/p2_effect_original/
p2_effect_correction`。不同实验源必须走独立 adapter，不返回原始 `params_json/result_json`。D1 原机器
GO 必须应用语义纠错后展示权威 STOP；原 P2-2 必须标 `INVALIDATED_METHOD`，P2-2C 才是当前权威历史
效果结论。

本端点只支持已知 ID 的详情；发现与翻页由下述 P-WEB-04A 提供。前端仍不得扫描账本补齐。

### P-WEB-04A `experiment_catalog(...)`（P3-4A 后端、P3-4B 页面已实现）

端点：`GET/HEAD /api/v1/experiments`，由本机 UI 同源精确代理开放。

目的：在不读取原始账本、研究目录或 raw JSON 的前提下，对 P3-3B 不可变投影中的 783 条实验记录
提供类型化发现、精确筛选和有界分页。每行只返回身份、证据层级、authority/lifecycle、适配器级
`outcome_status`、模型/引擎与失败原因数量；不返回数值业绩、逐日序列、参数 JSON 或结果 JSON。

支持 `experiment_kind/research_family/evidence_tier/authority_status/lifecycle_status/outcome_status/
evidence_status/as_of` 精确筛选，limit 1—100，固定按 UTC 时间降序、kind 与 ID 升序。未知组合
fail closed，禁止表现排序。P3-4B 目录固定每页 25 条，详情按 evidence tier 白名单展示；无逐日
NAV 时明确不画净值，原 P2-2 必须链接权威 P2-2C。

### P-WEB-05 `data_quality_summary(as_of)`（P3-2A 已实现）

端点：`GET/HEAD /api/v1/data-quality`。

目的：返回日增量终态、截止运行完成时刻的采集账本身份链、当日批次、S1-S10、异常计数和
`.BJ` 排除。合法空、未适用和缺失分开。

当前边界：查询会以 69,000+ 批次登记身份重算 `data_snapshot_sha256`，但不挂载 `data/raw`，因此
`raw_parquet_rehash_status=NOT_EVALUATED`。现有信号/影子账本未保存哨兵报告哈希，故十项均通过时
`status=PASS` 但 `evidence_status=WARN / binding_status=IDENTITY_MATCH_UNHASHED`；不得合成全绿。
异常逐行证券、`params_json` 和 Parquet 路径不返回。

### P-WEB-06 `system_run_summary(as_of)` 与 `notification_delivery_summary(message_id)`（P3-2A 已实现）

端点：`GET/HEAD /api/v1/system/runs`、
`GET/HEAD /api/v1/notifications/{message_id}`。

目的：核心任务和通知分离。固定步骤为日增量、哨兵、次日对账、影子信号、模拟仓和账本重放；
保留每个步骤的失败尝试与恢复。通知按稳定消息 ID 保留每次 attempt、错误类型、retryable、
recovered 和重复投递风险，不能覆盖失败尝试。

release 审计链会逐条验哈希并返回运行前最后一个已登记 `START_PASS` 身份；查询不挂 Docker socket，
因此实时容器身份保持 `NOT_EVALUATED`。2026-07-23 前无 message ID 的 legacy 通知只计数，不合成
ID，也不进入当前重试统计。

### P-WEB-07 因子工厂四组契约（P3-3B 后端、P3-3C 页面已实现）

- `factor_catalog(status, family, data_category, as_of)`：只收录曾进入 G1 的因子；稳定
  `factor_id` 与实验版 `factor_version` 分离，返回生命周期、权威状态、实验尝试 N、最新记录判决与证据
  完整性。正式库 0 插入必须如实返回空列表与计数，不把全部实验或历史版本重复计成因子。
- `factor_detail(factor_id, version)`：返回冻结定义、方向、PIT/shift、复杂度、RankIC/ICIR、换手、
  六窗口、压力期、成本、库相关、增量结果、G1 全门和证据引用。当前无统一证据的覆盖率、分位收益/
  单调性、自相关和候选池相关性固定 `NOT_EVALUATED`，不由 Web 重算。
- `factor_compare(factor_versions[])`：只接受 2—3 个当前权威版本；后端验证家族、宇宙、窗口、
  horizon、中性化、组合、成本、代码、数据和比较策略 fingerprint。缺字段返回 `NOT_EVALUATED`，
  任何不一致返回 `CONFLICT`，v1 不跨家族比较。
- `factor_admission_history(factor_id)`：按时间返回所有提交、判决、失败门、规则版本、实验总账 N 和不可变证据，不覆盖旧 REJECT。

共同要求：返回 `factor_id/factor_version/research_family/benchmark_id/horizon/universe_id/neutralization/decision_rule_version/code_snapshot_sha256/data_snapshot_sha256`；所有统计量只读取已冻结后台证据，
本查询不重新计算。旧 P1/Stage-1 版本必须保留并标非当前权威。

安全边界：P3-3B 先由一次性 Docker 构建器将受控账本、G1 JSON 和纠错覆盖投影为 write-once、限字段、
哈希绑定的 `data/web/research_snapshots/`；web-query 只读挂载该投影，禁止直接挂整个
`data/research`。完整协议见 `P3_FACTOR_EXPERIMENT_QUERY_PROTOCOL_20260725.md`。

## 4. HTTP 适配层包络（已实现）

P3-0 已实现只读 HTTP 层，P3-2A 与 P3-3B 在同一包络下扩展运维和研究投影：

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
- P3-2A 只新增 `logs/sentinels`、`logs/releases`、`logs/scheduler` 三个只读挂载；仍不挂
  `data/raw` 或 Docker socket；
- 详细裁决见 `WEB_ARCHITECTURE_RULINGS_20260723.md` R2。

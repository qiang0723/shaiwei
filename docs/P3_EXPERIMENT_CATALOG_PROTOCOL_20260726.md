# P3-4A 模型/回测实验目录协议（结果前冻结）

> 冻结日期：2026-07-26（Asia/Shanghai）
>
> 协议：`p3-experiment-catalog-v1`
>
> 状态：`FROZEN_BEFORE_IMPLEMENTATION`

## 1. 目标与边界

P3-4A 只补齐 `experiment_summary` 之前缺失的列表发现能力，新增内部只读
`GET/HEAD /api/v1/experiments`。它为后续模型/回测页面提供类型化目录，不在本目标施工页面、扩展 UI
代理、运行模型/回测/G1/LLM、重新计算效果、改变权威覆盖或授权生产。

目录只读 P3-3B 不可变投影中的 `experiments`，不直接读取账本、研究目录、原始 JSON、模型、预测、
NAV、交易或持仓。详情仍由 `(experiment_kind, experiment_id)` 唯一定位的 `experiment_summary` 提供。

## 2. 结构审计结论

结果前只审计身份与分类字段，未查看或重算数值效果。当前投影共有 783 条记录：

| kind | 数量 | 语义 |
|---|---:|---|
| `research_experiment` | 778 | 基线、影子、GP、G1、P1 与 D1 研究实验 |
| `p2_engineering_run` | 3 | 科创50工程运行；仅一条当前权威，另外两条为 provisional 历史 |
| `p2_effect_original` | 1 | 原 P2-2，方法已失效但证据保留 |
| `p2_effect_correction` | 1 | P2-2C 当前权威历史效果结论 |

783 条的 `experiment_id/recorded_at/research_family/evidence_tier/authority_status/lifecycle_status/
evidence_status` 均完整。`recorded_at` 跨时区但都有时区信息，排序必须先规范到 UTC，不允许直接按字符串
排序。P2 三条工程记录时间相同，因此固定追加 kind 和 ID 作为稳定并列键。

这些记录不是 783 个“有效模型”：其中包含发现尝试、运行记录、失败、G1 判决、工程 GO、失效方法和
历史效果拒绝。目录必须保持证据层级，不能以统一成功率、收益排行或模型榜单压平语义。

## 3. 列表项与 outcome 语义

每行只返回：kind、ID、记录时间、研究家族、证据层级、authority、lifecycle、`outcome_status`、
模型/引擎、引擎版本、失败原因数量和证据状态。列表不返回 `decision` 对象、窗口收益、IC、回撤、
预测、持仓、逐日序列、原始 `params_json/result_json`、证据路径或哈希全集；用户进入详情后再读取。

`outcome_status` 是适配器级展示语义，不是新裁判，固定为：

- `RECORDED`：基线、影子或前瞻运行已有记录，但目录不推断策略有效；
- `FAILED`：已登记执行失败；
- `DISCOVERY_ONLY`：GP/D1 仍是发现或评估记录，未进入 G1；
- `DISCOVERY_REJECTED`：D1 发现层拒绝，不得称为 G1 或策略 REJECT；
- `G1_REJECTED/G1_ADMITTED`：只由已有 G1 判决映射；
- `REVIEW_STOPPED`：D1 语义合同纠错后的权威 STOP；
- `ENGINEERING_GO_ONLY`：只证明工程通路，不含策略效果；
- `HISTORICAL_EFFECT_REJECTED`：P2-2C 当前权威历史效果 REJECT；
- `INVALIDATED_METHOD`：原 P2-2 方法失效，数值可复算但不再权威。

映射只看 kind、adapter、lifecycle 和 authority；不读取数值结果决定标签。出现未冻结组合必须
`NOT_EVALUATED`，不能回退为 `RECORDED`。

## 4. 筛选、分页与排序

允许精确筛选 `experiment_kind/research_family/evidence_tier/authority_status/lifecycle_status/
outcome_status/evidence_status/as_of`。过滤值必须来自当前投影已登记枚举；未知值和未知查询参数返回
`INVALID_ARGUMENT`，不做模糊搜索、自由 SQL、正则或路径匹配。

分页采用不可变快照上的有界 offset：默认 25、最小 1、最大 100，offset 从 0 开始。固定排序为：

1. `recorded_at` 规范为 UTC 后降序；
2. `experiment_kind` 升序；
3. `experiment_id` 升序。

响应返回投影总数、`as_of` 后数量、筛选后数量、当前返回数、可用过滤值、上一页/下一页边界和固定
排序声明。客户端翻页时必须保持相同 `snapshot_id`；快照变化必须清空旧页后重查，不跨快照合并。
不提供客户端排序、结果排序、收益/IC/回撤筛选。

## 5. 时间与权威覆盖

`as_of` 只按 Asia/Shanghai 日期裁剪 `recorded_at`，同时继续应用当前已知 authority overlay，并返回
`CURRENT_AUTHORITY_APPLIED_TO_HISTORICAL_RECORDS`。这是按当前知识回看旧记录，不是重演当时的权威
状态。查询时钟不能创建、升级或隐藏业务状态。

`available_filters` 从 `as_of` 后、其他筛选前的真实记录生成；`counters.kind_counts` 必须与
`as_of_count` 相加一致。合法空筛选返回空 items 与计数 0，不生成占位实验。

## 6. 不可变投影绑定

P3-4A 协议文件必须作为新来源加入一次性投影构建，manifest 同时绑定
`p3-factor-experiment-query-v1` 和 `p3-experiment-catalog-v1`。保留原 `protocol_id` 兼容已有因子和
详情响应，同时新增 `protocol_ids`；旧投影不改写，新构建产生新 snapshot。

相同源证据、两份协议和构建器代码必须双跑得到相同 bundle/manifest/snapshot。web-query 继续只读
挂载 `data/web/research_snapshots`；projector 仅新增本协议文件的只读挂载，其他源与唯一写目录不变。

## 7. HTTP 与安全边界

- 只允许 GET/HEAD；limit 由 FastAPI 和查询函数双层限制；响应仍受 1 MiB 上限；
- 本目标不把 `/api/v1/experiments` 或详情路径加入 UI 代理，外部仍只能经无宿主端口的 web-query
  内部服务读取；
- query 不加载 `.env`、不挂 Docker socket、不挂原始研究目录，容器继续非 root、只读根；
- 任一 `.BJ`、非法路径、哈希/manifest 不一致、重复身份、未知 adapter/outcome 或投影期间变化均
  fail closed；
- 不返回数值业绩、原始 JSON、绝对路径、密钥、Webhook、token 或生产控制能力。

## 8. 通过条件

1. 本协议与机器配置提交、推送早于实现；
2. 783 条记录恰好各列一次，目录 ID 与详情逐项一致；
3. 十类 outcome 映射穷尽当前 adapter 组合，未知组合 fail closed；
4. 精确筛选、历史切片、合法空、固定排序、offset/limit 边界和跨页无重复通过；
5. kind 计数相加等于 `as_of_count`，筛选/返回/分页计数自洽；
6. 目录响应不含数值效果、raw JSON、逐日序列、绝对路径或 `.BJ`；
7. 新协议进入投影 source hash，双跑 snapshot/bundle/manifest 一致；
8. API 方法、未知参数、响应大小、Compose 只读挂载和写拒绝探针通过；
9. 全仓测试、Ruff、compileall、依赖、Compose、脱敏和 `git diff --check` 通过；
10. scheduler 容器、镜像、创建时间和 healthy 状态施工前后不变。

## 9. 后续边界

P3-4A GO 只解除模型/回测页面的“缺目录后端”阻断，不自动授权页面。P3-4B 若继续，必须另立页面
协议，明确首页问题、分组、详情下钻、数值展示和历史失效表达；不得把 783 条记录做成表现排行榜。

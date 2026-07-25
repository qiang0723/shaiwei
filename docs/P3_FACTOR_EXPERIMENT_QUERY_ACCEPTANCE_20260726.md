# P3-3B 因子与实验只读查询验收

> 验收日期：2026-07-26（Asia/Shanghai）
>
> 冻结协议：`p3-factor-experiment-query-v1`
>
> 结论：`GO_TYPED_READ_ONLY_BACKEND`

## 1. 结论边界

P3-3B 已完成一次性 Docker 研究投影构建器、五组类型化查询和内部 HTTP 契约：
`factor_catalog`、`factor_detail`、`factor_compare`、`factor_admission_history`、
`experiment_summary`。

本结论只证明后端能以冻结口径、安全地发布现有研究证据，不证明任何因子或策略有效，不授权因子工厂
页面、实验目录、导出、远程访问、模型/回测/G1/LLM 执行或生产接入。正式因子库仍为 0。

## 2. 数据质量与权威语义

投影构建前对各来源按预期粒度做 fail-closed 校验：

| 来源 | 预期粒度 | 关键校验 | 终态 |
|---|---|---|---|
| `experiments.csv` | 每实验一行 | `experiment_id` 唯一；已知 adapter；代码/数据哈希合法 | 778/778 |
| `factor_admissions.csv` | 每 G1 判决一行 | `decision_id` 唯一；候选实验外键；报告/证据/测试三层哈希 | 18/18 |
| Stage-1/P1 G1 | 每候选版本一组 | 公式、家族、候选 ID、代码、数据、测试报告一致；15 门完整 | 18/18 |
| D1 尝试/复核 | 每尝试、每角色一行 | 尝试到实验一一对应；复核集合严格为冻结 Top2；每候选四角色 | 40 尝试、8 复核 |
| P2 工程 | 每工程运行一行 | 3 个运行身份唯一；仅 `a4cfad...` 为 current | 1 current、2 provisional |
| P2 效果 | 每效果运行一行 | 原方法与纠错方法分别绑定报告、准入和协议哈希 | 原方法失效、P2-2C current |

真实投影包含 10 个精确因子身份、18 个 G1 版本、8 个当前权威版本、8 个当前权威 REJECT、
2 个仅历史因子、0 个正式入库因子、778 个类型化研究实验详情，以及 3 个 P2 工程运行、1 个原
P2-2、1 个 P2-2C 纠错运行。

权威覆盖按冻结规则生效：旧 Stage-1/P1 版本不被覆盖；D1 STOP 只施加于
`6ade2d0f6d103613` 和 `3bf9d418202afc20`，其余 38 个尝试没有复核 overlay；原 P2-2 固定为
`INVALIDATED_METHOD / REPRODUCIBLE_NOT_AUTHORITATIVE`；P2-2C 固定为
`AUTHORITATIVE_CURRENT / NO_GO / REJECT / production_authorization=none`。

## 3. 不可变投影

构建入口为 `make docker-web-research-project`。构建器仅在一次性、断网、非 root、只读根文件系统
容器内运行。账本、G1 和 P2 来源只读；唯一可写挂载为 `data/web/research_snapshots`。Web 查询容器
只读挂载该投影目录，不挂 `data/research`，不加载 `.env`，不挂 Docker socket，也没有宿主端口。

终版真实投影：

| 项目 | 值 |
|---|---|
| snapshot ID | `9afe4d11e3a6a3b36db47c31568b3eb6d4e3a5a7f81d516ed70a075369180f13` |
| bundle SHA-256 | `4acb8e597909cc4b5901286f54dc271788dcea87458377771c4979aee42e5cf0` |
| manifest SHA-256 | `389c8ddfa496cc8c8269a232aba796398a09d0de0042237c194e659c396d0d94` |
| source/build identities | 72 |
| bundle 字节数 | 925,683 |
| evidence generated_at | `2026-07-25T12:25:00+00:00` |

snapshot 由协议 ID、全部来源哈希和构建器代码哈希共同决定；相同来源与构建器双跑得到相同 snapshot、
bundle 和 manifest。已存在同名目录但内容不同会立即失败，不设置可变 `latest` 指针，不覆盖旧投影。

## 4. 查询行为

目录默认按 `research_family,factor_id` 排序，不按 IC、收益、DSR 或综合分排序。`ADMITTED` 过滤合法
返回空列表和 `formal_library_count=0`，不生成明星因子或占位值。

详情默认选择当前权威版本；若 as-of 截断后不存在 current，则显式
`fallback_to_latest_historical=true`。已有 G1 的公式、方向、PIT/shift、复杂度、15 门、六窗口 RankIC、
压力期回撤、换手、增量组合、成本/滑点和库相关可以读取。coverage ratio、quantile returns /
monotonicity、factor autocorrelation、candidate-pool correlation 始终为
`NOT_EVALUATED / recomputed=false`。

投影和响应均不含 `daily_oos`、`daily_net_excess_returns`、原始 `params_json/result_json` 或原始路径。
比较只接受 2—3 个当前权威版本；非权威版本、跨家族、缺 fingerprint 或任一冻结 fingerprint 不同均
fail closed，且不按表现重排。

实验详情强制 `(experiment_kind, experiment_id)`。四个 kind 均有独立 adapter；未知 kind 不猜测，且
没有实验列表端点。`as_of` 按 Asia/Shanghai 截断登记事件，但始终应用当前权威 overlay，并返回
`CURRENT_AUTHORITY_APPLIED_TO_HISTORICAL_RECORDS`。

## 5. 安全与验证

已通过：

- 宿主全仓 `282 passed`；
- Docker 全仓 `282 passed`；
- P3 专项 13 项；
- Ruff、compileall、pip check、Compose config、`git diff --check`；
- 非法路径、符号链接、哈希篡改、重复主键/外键、`.BJ`、非权威比较、不可比 fingerprint、未知 kind、
  GET/HEAD 方法和 1 MiB 响应上限对抗；
- 真实 Docker 投影双跑幂等；
- Web 容器对投影写探针以 `Read-only file system` 拒绝；
- 投影全文不含 `/Users/`、`/workspace`、`params_json`、`result_json`、逐日序列字段或已知密钥片段；
- Docker Python 3.11 与宿主 Python 3.12 的 JavaScript MIME 差异已以固定映射消除。

终版独立 Web 镜像内容 ID 为
`sha256:fde536a2012b0e59dae3f44ca8e0ff6e7fb78ddc201d49bba7f9d702c8f1e1c6`。

施工前 scheduler 为原容器 `fd8e96152b53`、镜像内容 ID
`sha256:de87ec740981166b032b394fb256a978acdc8d35e999a369f1debc3466aa0261`、代码快照
`eb8e752132ac1fbe6a9557d26b4c7a65df36f6169d617b6e1e10db88d46b7fbd`，状态 healthy。施工只构建独立
`shaiwei:web-v1` 和一次性投影容器；未重建、重启或修改 scheduler。

## 6. 限制与下一闸

- G1 四类 tear-sheet 指标仍缺；本目标按未评估发布，没有补算。
- `experiment_summary` 是已知 ID 详情，不是 `experiment_catalog`；模型/回测完整页面仍为 `NOT_READY`。
- 因子页面、实验目录、导出和 UI 代理 allowlist 均未开放。
- 研究源更新后必须显式重跑一次性投影；没有常驻监听器。
- P3-3C 若继续，应先冻结因子工厂页面任务与交互契约；模型/回测页面须先另立
  `experiment_catalog` 协议。

# P3-3A 因子与实验只读查询协议（结果前冻结）

> 冻结日期：2026-07-25（Asia/Shanghai）
>
> 协议：`p3-factor-experiment-query-v1`
>
> 状态：`FROZEN_BEFORE_BACKEND_IMPLEMENTATION`

## 1. 目标与授权

本协议冻结五组查询：`factor_catalog`、`factor_detail`、`factor_compare`、
`factor_admission_history`、`experiment_summary`。下一目标仅可实现只读后端及安全投影，不授权页面、
任意实验列表、导出、模型/回测/G1/LLM 执行、策略裁决、生产接入或远程访问。

机器真身为 `config/p3_factor_experiment_queries_v1.yaml`；现状与缺口证据见
`P3_FACTOR_EXPERIMENT_EVIDENCE_AUDIT_20260725.md`。机器配置与本文冲突时必须停止并回到协议评审，
不得在代码中自行选择更宽解释。

## 2. 安全发布边界

现有 G1 证据分布在 `logs/g1` 和 `data/research`，后者同时含 Parquet、模型、预测、NAV、交易、持仓
及 provisional 产物。Web 服务禁止直接挂载整个研究目录。

P3-3B 必须由一次性 Docker 构建器完成：

1. 仅只读打开机器配置列出的账本、G1 JSON 和权威覆盖；
2. 验证路径为项目相对路径、前缀受控、无 `..`、无绝对路径、无符号链接越界；
3. 验证账本主键、外键、报告/证据 SHA-256 及覆盖文件 SHA-256；
4. 只投影本协议列出的字段，不返回原始 `params_json/result_json` 或逐日序列；
5. 写入 `data/web/research_snapshots/<snapshot_id>/` 的不可变 JSON 和 manifest；
6. 相同源证据产生相同 snapshot、字节与哈希，已存在不同内容立即失败；
7. web-query 只读挂载投影目录，不读取 `.env`、原始研究目录、模型文件或 Docker socket。

投影构建是证据格式化，不得计算新的 RankIC、收益、DSR、HAC、门禁或因子排名。

## 3. 身份与权威语义

### 3.1 因子

`factor_id` 为：

```text
sha256(UTF8("factor-exact-v1\0" + research_family + "\0" + feature_or_formula))
```

`factor_version` 固定为 G1 判决中的 `candidate_experiment_id`。不做公式等价归一化；文本不同即不同
身份，同一公式在不同研究家族也不合并。

当前权威版本：

- Stage-1：`trial_count=166` 且候选代码快照为 `e03da3ac…`；
- P1：`trial_count=18` 且候选代码快照为 `8f8f7a09…`。

不匹配的旧判决继续按追加历史返回，但 authority 分别标为
`HISTORICAL_NON_AUTHORITATIVE` 或 `SUPERSEDED_ENGINEERING_GENERATION`。生命周期不得只看
`experiments.admitted`；没有 G1 判决的发现尝试不是 G1 REJECT。

### 3.2 实验

`experiment_summary` 必须同时接收 `experiment_kind` 和 `experiment_id`。允许的 kind 只有：

- `research_experiment`；
- `p2_engineering_run`；
- `p2_effect_original`；
- `p2_effect_correction`。

省略 kind 或适配器未知返回 `INVALID_ARGUMENT/NOT_EVALUATED`，不得猜测。原 P2-2 固定
`INVALIDATED_METHOD / REPRODUCIBLE_NOT_AUTHORITATIVE` 并指向 P2-2C；D1 原机器 GO 必须与语义纠错
合并后对两条受复核候选返回权威 STOP，未进入该复核的另外 38 次尝试不套用此 overlay；P2-1 只有
`a4cfad…` 终版报告是 current，前两份为 provisional 历史。

## 4. 五组查询

### 4.1 `factor_catalog(status, family, data_category, as_of)`

只收录曾进入 G1 的因子，不把全部 778 次实验伪装成因子。返回因子身份、家族、数据类别、生命周期、
权威状态、版本数、当前版本、家族尝试 N、最新记录判决和证据状态；同时返回正式库、已研究、当前权威
REJECT 和仅历史因子计数。

默认排序按家族和身份，不按收益、IC、DSR 或任何“综合分”。当前正式库计数必须为 0；过滤
`ADMITTED` 时返回合法空列表，不生成明星因子或占位数据。

### 4.2 `factor_detail(factor_id, version)`

默认选当前权威版本；没有当前版本时选最近历史版本并显著标记。允许展示已有 G1 证据：公式与方向、
PIT/shift、复杂度、六窗口 RankIC、三压力期最大回撤、基线/候选 ICIR与净超额、换手、成本/滑点、
库相关、DSR、HAC、15 个门和哈希引用。

覆盖率、分位收益/单调性、因子自相关和候选池相关性当前统一为 `NOT_EVALUATED`。响应不返回逐日 IC/
收益序列，前端不得补算。

### 4.3 `factor_compare(factor_versions[])`

只接受 2—3 个当前权威版本。家族、宇宙、基准、标签、horizon、中性化、六窗、压力期、组合、成本、
G1、代码、数据和比较策略必须全部具有相同 fingerprint；任一缺失返回 `NOT_EVALUATED`，任一不同返回
`CONFLICT`。v1 禁止跨家族比较，也不默认按结果排序。

### 4.4 `factor_admission_history(factor_id)`

按时间返回全部版本：记录判决、当前 authority、尝试 N、失败门、规则、证据与报告哈希。旧 REJECT、
provisional、失效和被替代版本均不可覆盖或隐藏。

### 4.5 `experiment_summary(experiment_kind, experiment_id)`

返回类型化的实验身份、证据层级、authority、生命周期、模型/引擎、seed、train/valid、代码/数据、
判决、失败原因和证据引用。不同 `candidate_source` 必须使用机器配置中的独立 adapter；不返回原始 JSON。

本端点只解决已知 ID 的详情，不提供列表发现能力。因此模型/回测完整页面在另行冻结
`experiment_catalog` 之前保持 `NOT_READY`。

## 5. 时间、错误与状态

- `as_of` 只截断已登记事件；仓库最新权威纠错永远覆盖旧记录，并显示
  `CURRENT_AUTHORITY_APPLIED_TO_HISTORICAL_RECORDS`；
- 证据缺失、哈希不符、重复主键、外键断裂、非法路径、未知状态或投影期间变化均
  `EVIDENCE_MISMATCH`；
- 不可比较为 `CONFLICT`，未评估指标为 `NOT_EVALUATED`，合法空为 `NO_DATA` 或带计数的空列表；
- 任一证券代码出现 `.BJ` 立即 `FORBIDDEN_UNIVERSE`，不静默过滤；
- 查询时钟不产生业务状态；相同参数和证据必须产生相同业务响应、snapshot 和 ETag。

## 6. P3-3B 通过条件

1. 本协议和机器配置的提交、推送早于实现提交；
2. 10 个因子身份、18 个版本、8 个当前权威版本、0 个正式入库因子被正确投影；
3. P1/Stage-1 历史版本、D1 STOP、原 P2-2 失效和 P2-2C 权威结论全部有 fixture 锁定；
4. 未提交 G1 的实验不会显示为 REJECT，未知适配器不会猜测字段；
5. 四类缺失 tear-sheet 指标固定 `NOT_EVALUATED`，前后端均不重算；
6. 跨家族、缺 fingerprint 或非权威版本比较 fail closed；
7. 投影构建器与 API 均通过路径、符号链接、哈希、大小、方法、脱敏和 `.BJ` 对抗测试；
8. Compose 不挂整个研究目录，不加载 `.env`，无 Docker socket，查询仍无宿主端口；
9. 全仓测试、Ruff、compileall、依赖、Compose 和 Git 脱敏检查通过；
10. scheduler 容器、镜像、代码快照与健康状态施工前后不变。

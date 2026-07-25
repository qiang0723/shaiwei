# P3-3A 因子工厂与模型/回测证据只读审计

> 审计日期：2026-07-25（Asia/Shanghai）
>
> 审计范围：只读盘点现有因子、实验、准入、纠错与失效证据；不运行模型、回测、G1 或 LLM，
> 不生成候选，不读取新策略效果，不修改生产策略、信号、门禁、scheduler、数据或追加式账本。
>
> 裁决：**PASS_WITH_FINDINGS / GO_P3_3B_TYPED_READ_ONLY_BACKEND_ONLY**。

## 1. 结论先行

现有证据足以施工 `factor_catalog`、`factor_detail`、`factor_compare`、
`factor_admission_history` 和带类型命名空间的 `experiment_summary`，但不能把账本或研究 JSON
直接透传给 Web。后端必须先做三件事：

1. 用稳定因子身份合并同一公式的多个实验版本，同时保留每一条旧判决；
2. 在展示前应用 P1/Stage-1 的终版选择规则、D1 语义纠错和 P2 方法失效/纠错覆盖；
3. 由一次性 Docker 构建器生成限字段、哈希绑定、write-once 的研究投影包，Web 只读挂载该投影，
   不直接挂载整个 `data/research` 或返回原始 `params_json/result_json`。

因此下一目标可以进入 P3-3B **只读后端**，但尚不授权因子页、模型/回测页或生产部署。尤其是
`experiment_summary` 只有详情查询，没有列表/分页契约；完整模型/回测页面仍为 `NOT_READY`，后续若
确有页面需要，应另行冻结 `experiment_catalog`，不能让前端扫描账本代替。

## 2. 用途、粒度与权威来源

本审计只回答：现有历史证据是否足以安全地投影为 Web 查询，以及哪些结论是当前权威结论。它不评价
候选是否值得继续研究，也不复算任何收益、IC 或准入门。

| 对象 | 业务粒度 | 权威来源 | 当前规模 |
|---|---|---|---:|
| 通用实验 | 一次登记尝试 | `ledger/experiments.csv` | 778 |
| G1 判决 | 一次候选版本准入裁决 | `ledger/factor_admissions.csv` + 哈希绑定报告/证据 | 18 |
| 因子身份 | 同研究家族内精确公式文本 | 由实验公式确定性派生 | 10 |
| D1 发现尝试 | 一次 LLM 生成/沙箱/发现期尝试 | `llm_factor_attempts_v2.csv` | 40 |
| D1 对抗复核 | 候选 × 角色 | `llm_factor_reviews.csv` + 语义纠错 JSON | 8 |
| P2 工程历史 | 一次工程报告版本 | P2 engineering 两账本 | 3 |
| P2 原效果 | 一次原方法效果运行/裁决 | P2 effect 两账本 | 1 |
| P2 纠错效果 | 一次权威纠错运行/裁决 | P2 correction 两账本 | 1 |

正式因子库当前仍是 **0 插入**。`experiments.csv` 的 778 行全部 `admitted=false`，但该字段不能单独
解释为“778 个因子均被 G1 拒绝”：绝大多数只是发现、基线、影子或未进入 G1 的尝试。只有
`factor_admissions.csv` 能证明 G1 判决。

## 3. 数据质量核验

### 3.1 完整性、唯一性与引用完整性

- 实验 778 行、778 个唯一 `experiment_id`，父实验引用缺失 0，`params_json/result_json` 解析失败 0，
  train/valid 区间缺失 0。
- G1 判决 18 行、18 个唯一 `decision_id`、18 个唯一候选实验引用，缺失实验外键 0。
- 18 份 G1 报告、18 份候选证据和 18 份 factor-test 报告均存在；报告 SHA-256 与账本不一致 0，
  报告中的候选、规则、实验总账、代码/数据和证据绑定不一致 0。
- D1 40 个尝试与 40 个通用实验逐个 attempt ID 一一对应；8 个复核 ID 唯一且只覆盖两个 Top2
  候选。语义纠错引用的 3 个违规复核全部存在，response/raw artifact SHA-256 与复核账本不一致 0；
  STOP overlay 只作用于这两条候选，不扩散到其余 38 次尝试。
- P2 工程、原效果和纠错效果的 run/decision ID 均唯一；纠错账本明确记录原模型与执行均无效，
  权威纠错结论为 `NO_GO/REJECT`、生产授权 none。

### 3.2 粒度与版本

18 次 G1 判决只对应 10 个精确公式身份：8 个公式各有两个实验版本，另 2 个只有历史版本。分层如下：

- P1：12 次判决对应 6 个公式；`trial_count=6` 是首次可复算但后来发现字节漂移的历史代，
  `trial_count=18` 是最终绑定代。两代均保留，但只有后者是当前权威版本。
- Stage-1：6 次判决对应 4 个公式；只有代码快照 `e03da3ac…`、`trial_count=166` 的正确 Top2
  是当前权威版本，其余是错误回溯/排序/汇总路径下的历史记录。

因此 `candidate_experiment_id` 只能作为 `factor_version`，不能作为长期 `factor_id`。v1 冻结为
“研究家族 + 原样公式文本”的 SHA-256；不做语义归一化，避免把不同数据语境或文本变体错误合并。

### 3.3 一致性与权威覆盖

账本内部一致不代表其每一行都具有当前裁决权威。必须应用下列覆盖：

| 范围 | 原记录 | 当前权威解释 |
|---|---|---|
| P1 第一代 | 普通 REJECT、N=6 | 历史可查；被最终 N=18 绑定代取代 |
| Stage-1 早期两批 | 普通 REJECT、N=82/124 | 历史可查；非正确 Top2 的当前裁决 |
| D1-3A 原报告 | `GO_INDEPENDENT_HUMAN_GATE` | 仅证明传输/schema/费用；语义纠错后权威 STOP |
| P2-1 前两份工程报告 | GO | provisional 历史；终版为 `a4cfad…` 报告 |
| 原 P2-2 | `NO_GO/REJECT` | 数值可复算，但模型/执行方法无效，不能作权威效果决策 |
| P2-2C | `NO_GO/REJECT` | 当前权威历史效果结论；生产授权 none |

若查询不应用这些覆盖，会分别产生“D1 已通过人工闸”“原 P2-2 是权威结论”“三个 P2-1 工程 GO
同等有效”等错误展示，严重度为 P0。

### 3.4 指标可用性

18 个 G1 版本都具备同一核心证据结构：冻结方向、PIT/shift、复杂度、六窗口 RankIC、逐日 OOS
RankIC、三压力期最大回撤、基线/候选净 ICIR与净超额、换手、双倍成本/滑点、DSR、HAC t、15 个门和
证据哈希。因此这些字段可以只读展示。

但 factor-test 有两种家族 schema，当前没有统一、已登记的以下证据：

- 覆盖率的分子、分母和范围；
- 分位收益与单调性；
- 因子自相关与分位换手；
- 候选池内部相关性矩阵；
- 可跨家族使用的统一 neutralization/comparison fingerprint。

这些部分必须返回 `NOT_EVALUATED`，不得由 Web 临时扫描 Parquet 或重算后填绿。现有
`library_max_abs_correlation`、组合换手和增量结果不受影响，仍按 G1 报告展示。

### 3.5 时效与历史视图

`as_of` 只筛选当时已登记的事件；纠错和失效覆盖始终采用仓库当前最新权威解释。历史响应必须显示
`CURRENT_AUTHORITY_APPLIED_TO_HISTORICAL_RECORDS`，防止用户把“当时记录的结论”误认为“今天仍有效的
结论”。查询时间本身不能生成新的业务状态。

## 4. Findings 与处置

| 级别 | Finding | 影响 | 冻结处置 |
|---|---|---|---|
| P0 | 纠错/失效信息分散在不同账本和文档 | 可展示错误的当前结论 | 强制 authority overlay；缺失或哈希不符即 `EVIDENCE_MISMATCH` |
| P0 | `experiments.admitted=false` 无法区分未提交与 G1 REJECT | 会把 778 次尝试伪装成 778 个被拒因子 | 因子生命周期只从 G1 判决与权威覆盖派生 |
| P1 | 18 个准入版本与 10 个因子身份混在一起 | 因子数量、尝试 N 和历史版本会被重复计算 | 分离 `factor_id` 与 `factor_version` |
| P1 | 研究结果 JSON 按来源高度异构 | 通用字段可能空填或错义 | `experiment_kind + adapter` 必填；未知适配器返回 `NOT_EVALUATED` |
| P1 | 研究目录包含 Parquet、模型和 provisional 产物 | 直接挂载扩大泄露与误读面 | 先建 write-once 研究投影包，Web 禁挂整个研究目录 |
| P1 | 完整模型页没有 experiment 列表/分页契约 | 单个详情端点无法支持页面导航 | P3-3B 只做详情；页面保持 NOT_READY |
| P2 | tear sheet 四类指标没有统一证据 | 页面可能诱导前端现场计算 | 明确 `NOT_EVALUATED`，后续另立研究协议补证据 |

## 5. 证据快照

本次审计读取的关键账本快照：

| 文件 | 数据行 | SHA-256 |
|---|---:|---|
| `ledger/experiments.csv` | 778 | `cfb08c500b7519d579b9814cf2dd037f23089c7effe5bd71064e9dde35478129` |
| `ledger/factor_admissions.csv` | 18 | `566dd5bdd14d2bd447e69197b8c116b59db492e6771772cbf204b609cf8c4cde` |
| `ledger/llm_factor_attempts_v2.csv` | 40 | `80bf00a8f415b818877a3d91993eecd474cb1bb5d39ccddd8e29db5f2b47c1b3` |
| `ledger/llm_factor_reviews.csv` | 8 | `9029ea65490711dbd6bddc592d2f3116ad1b7e811059cad926caca283d13e280` |
| P2 engineering runs/admissions | 3 / 3 | `ed6a5e56…` / `9e79231f…` |
| P2 original effect runs/admissions | 1 / 1 | `13492b89…` / `454aeacf…` |
| P2 correction runs/admissions | 1 / 1 | `953fd315…` / `a298bb99…` |

权威覆盖文件：D1 机器纠错 `de8b331c…`、P2 原方法失效附录 `fddc25b6…`、P2-2C 验收
`3fd8c768…`。完整值已冻结在 `config/p3_factor_experiment_queries_v1.yaml`。

## 6. 下一目标边界

允许另立 P3-3B，只施工：一次性只读投影构建器、五组类型化查询、错误/脱敏/哈希/原子切片测试，
以及现有 web-query 的精确只读投影挂载。禁止在该目标中施工页面、补算缺失指标、运行研究、改动模型/
门禁/信号/scheduler，或把查询结果用于新的策略裁决。

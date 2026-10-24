# G1 正控工程说明（g1-positive-control-v1 §10 第 2 步）

- 日期：2026-10-24；上位：`docs/G1_POSITIVE_CONTROL_PROTOCOL_20261024.md`（冻结于 e08881c）、`config/g1_positive_control_v1.yaml`
- 性质：**结果前**的实现选择与解释记录。不改协议、不改 `g1-v1` 任何判据；本步只有合成测试，未读取任何真实数据或标定结果
- 代码：`src/shaiwei/research/g1_calibration/`（protocol / controls / signals / evidence / judge / writer / summary / runner / pilot）

## 1. 复用而不复制冻结逻辑

- 判定原样调用 `g1.py` 的 `_evaluate_gates`、`_verify_integrity_binding`、`family_trials`、`deflated_sharpe_probability`；
  `g1.py`（693 行）与 `g1_pipeline.py`（643 行）均在热点上限，**一行未改**。
- 组合证据（方向冻结、90/10 混合、正常/双倍成本/双倍滑点三次回测、换手、压力期独立因子腿、六窗与日频 OOS）逐项沿用
  `g1_pipeline.evaluate_candidate`；等价性测试在同一合成输入上运行真实 `evaluate_candidate` 并要求全部数值逐位相等。
- 中性化沿用 `neutralized_factor_values` 与 `daily_rank_ic`；等价性测试要求与真实 `evaluate_factor_panel` 输出逐位相等。
- 载入时校验：配置冻结状态、协议文档存在、三层恰好划分 15 个 `g1-v1` 门、`g1-v1` 规格 SHA 与冻结值一致、发现期与标签与基线一致，
  任一不符拒绝执行。

## 2. 结果前的解释（协议未逐字规定处）

| 问题 | 采用的解释 | 理由 |
|---|---|---|
| `a` 按强度一个还是按种子一个 | **每个种子各自标定**，使每次评估的发现期 RankIC 都落在目标 ±0.002 | 让“容差”对每次评估都成立；噪声种子不同则同一 `a` 实现的 RankIC 不同 |
| 诊断 DSR（N=166/196）的试验方差 | **只替换 N**，试验 Sharpe 离散度仍取本格 | 协议 §5 只指定 N；仅报告，不影响终态 |
| N1 的截面支撑 | 当日有收盘价的股票（PIT），**不借用未来标签是否存在** | 阴性对照的支撑本身不得含未来信息 |
| N2 打乱对象 | R3 的**原始**因子值（中性化之前），每日截面内打乱 | 与“保留分布与时间结构、切断对应关系”一致，随后走标准中性化 |
| R5 的 250 日回看 | 以五层 `Ref(·,50)` 叠出 250 日，原样通过真实候选的白名单与 shift 哨兵；单独建回看 260 日的数据集 | 单节点窗口上限 50、主数据只预热 100 日；qlib 日历始于 2016-01，故 R5 约自 2017-01 起有值，方向冻结只用 2017–2018 |
| R1/R2 的 PIT/shift | 如实记 `false` 并标注豁免 | 含未来信息；该门在 §2 中只报告 |
| 非表达式路线的复杂度 | 按描述式公式计 token | 复杂度门只报告 |
| Top30 Jaccard | 策略调仓步（`is_rebalance_step`）上**按分数排名**的 Top30，不是经 dropout 后的实际持仓 | 协议原文“候选 Top30 与基线 Top30” |
| 传递链 | 方向化因子 OOS RankIC → 分数 RankIC 增量（候选−基线）→ 组合净超额增量；报告两段比值 | §6 只要求报告，不作门 |

## 3. 记账与隔离（协议 §8）

- 每次评估（含证据失败）在 `ledger/experiments.csv` 记一行，家族为格子名（如 `g1-calibration-v1/R1/0.04`），
  `params_json.admission_scope=NOT_FOR_ADMISSION`；**DSR 的 N 与方差由 `g1-v1` 从这些行机械统计，失败尝试同样计入 N**。
  同绑定复跑只复用、不追加第二行。`ledger.append_experiment` 为此增加可选 `path` 参数（向后兼容）；未用 `append_experiment_once`，
  因其敏感词过滤会误拒 `g1-v1` 复杂度绑定必需的 `expression_tokens` 字段。
- 判定写 `ledger/g1_calibration_runs.csv`（本步新建，仅表头），报告写 `logs/g1-calibration/<执行 ID>/`，面板与证据写
  `data/research/g1-calibration-v1/<执行 ID>/`；写入口拒绝 `factor_admissions.csv`、`logs/g1/`、因子库与正式 G1 研究目录。
- 每份证据带顶层 `admission_scope`：正式裁判的证据模型 `extra="forbid"`，读到即校验失败（有测试）；面板 parquet 元数据同样带标记。
- 判定绑定本格试验集合的哈希（ID+选择期 Sharpe），复跑逐字节复用；整份实验总账哈希记在标定账本行中。

## 4. 计时试跑（第 3 步，待单独授权）

`python -m shaiwei.research.g1_calibration.pilot --pilot --output data/research/g1-calibration-v1/pilot-…/timing.json`：
只用**协议外种子 0**（R1@0.04、N1），构造信号与组合证据后即丢弃；不写任何账本、不判定、不输出任何指标值，只记录耗时与
30/20/10 三档噪声种子的预计总时长。正式执行入口（读取 release scope）在第 4 步实现。

## 5. 结果前观察（不改动，留给正式结果解释）

`g1-v1` 共享的中性化残差只保留**未来标签非空**的行（`_neutralized_residual` 对 label 做 dropna），因而真实候选与本标定的
所有混合信号都天然排除了 t+1 或 t+11 开盘缺失（停牌、退市）的股票，而基线信号不排除。这是对候选有利的支撑层前视，
同样作用于历史 29 次真实裁决。本标定按“测量门本身”原则**不修正**；若终态为 `G1_PERMISSIVE`，此处是第一嫌疑，
修正须另立 `g1-v2`。

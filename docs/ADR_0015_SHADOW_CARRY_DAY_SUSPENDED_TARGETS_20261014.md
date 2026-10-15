# ADR 0015 · 沿用日 manifest 对停牌沿用目标的处理

- 日期：2026-10-14
- 状态：**ACCEPTED 2026-10-15**（用户对 §10 三问回复“按建议”：方案 B；`max_carried_without_score=3`；只随新候选
  （ADR 0016）进入生产。本提交即结果前冻结：PROTOCOL 与实现随后另行提交，实现不得先于协议。）
- 关联：docs/DATA_SPEC.md 第 20 条数据时钟契约；docs/PAPER_EXECUTION_POLICY_V1.md；STATE.md 2026-10-14 事件登记；
  src/shaiwei/shadow/manifest.py:72-86；src/shaiwei/shadow/generation.py:187-192、231

## 1. 问题与结果目标

**问题。** 影子信号在非调仓日（`rebalance_due=False`）沿用上一 manifest 的 30 个目标，`write_signal_manifest` 把当日评分
reindex 到这 30 只，任何一只没有当日评分即抛 `DataClockError("carried targets missing current scores")`，整日信号失败
（manifest.py:82-84）。成分股停牌当日没有 OHLCV bar，qlib 无特征、模型无评分，于是**一只停牌 = 当日前瞻信号消失**。
20260929 即如此：600363.SH 因实施风险警示停牌一日，调度器每 15 分钟重试、累计 89 次 FAIL，次日数据推进后该日永久缺失，
约 180 条飞书告警无人处置。Top30 内每年出现若干次单日停牌是常态，缺口会复发。

**结果目标。** 沿用日在存在**可解释**的无评分目标时仍按"持仓不变"合同产出信号；不可解释的缺口继续失败关闭；调仓日逻辑、
G0/G1 判据、paper-v1 执行策略一律不变。

## 2. 现状证据

- 沿用语义：生成端只在 `rebalance_due=False` 时传 `target_instruments`（generation.py:191-192）；manifest 要求恰好 topk 个唯一
  名字且全部有评分（manifest.py:75-86）。
- 20260929：`daily` 无 600363.SH 行、`suspend_d` 记 `S`（无 timing=全天）、`adj_factor` 有行；0930 以 `R` 复牌。首个失败
  发生在日增量 PASS 后 11 秒；shadow_runs 89 行 FAIL，error_type 全为 DataClockError。
- 对账端：`reconcile_next_open` 按 instrument 左连接，权重不变的目标 `executable=True`（reconciliation.py:157-160），
  对无评分沿用目标无额外要求。
- 模拟仓端：paper-v1 已有停牌持仓处理（开盘停牌不成交并保留拒绝原因；估值沿用最后官方收盘，超 20 个交易日标 `STALE`），
  即两侧对"停牌的既有持仓"口径本就是"保留"，只有 manifest 把它当成致命错误。

## 3. 候选方案

| 方案 | 内容 | 判断 |
|---|---|---|
| A 保持现状 | 接受停牌日无信号；次日自动推进 | 每年若干个前瞻信号日凭空消失，模拟仓少执行日，且每次 ~180 条告警；与"沿用=持仓不变"的语义自相矛盾（持仓明明不变，却说不出信号） |
| **B 可解释缺口沿用** | 沿用日里"当日无 bar"的目标以 `score=null`、`score_status="CARRIED_NO_SCORE"` 沿用原权重；有 bar 却无评分仍失败；缺口只数超上限仍失败 | 保住合同语义，只放行能用数据解释的缺口；schema 需升版，下游要容忍 null |
| C 剔除并摊权 | 沿用日把缺评分目标剔除、权重摊给其余 29 只 | 改变了组合=隐性调仓，违背"10 个交易日才改变目标组合"的冻结口径，否决 |

**选择 B。** 代价：manifest `schema_version` 2→3；`write_signal_manifest` 新增可解释缺口输入；下游三处（Top20 投影、
Web 信号页、报告）需容忍 `score: null`；新增配置项与测试。

## 4. 影响边界

- 只影响 `rebalance_due=False` 分支；调仓日仍由当日评分 Top30 决定，无任何变化。
- 不改 G0–G9/C0/g1-v1/g8-v1；不改 paper-v1；不改股票池、标签、模型、调仓周期。
- 不改任何已有 manifest；`verify_signal_manifest` 算法不变（null 字段参与规范化 JSON 哈希）。
- 生产生效条件：生产 scheduler 运行 07-27 代码（210af4d），本变更**只能随新候选镜像进入生产**（见 ADR 0016）。在此之前生产
  行为不变，缺口仍可能发生；巡检 `SHADOW_SIGNAL_MISSING/REPEATED_FAIL` 会报出。

## 5. 合同与数据迁移

**manifest v3**（新增，向后兼容读取）：
- 每个 order 增加 `score_status: "LIVE" | "CARRIED_NO_SCORE"`；`CARRIED_NO_SCORE` 时 `score: null`，`target_weight` 不变，
  `rank` 沿用上一 manifest 的 rank。
- 顶层增加 `carried_without_score: [instrument, ...]`（可为空数组）与 `carry_explanation: "NO_SIGNAL_DATE_BAR"`。
- `schema_version: 3`。读取方按 `schema_version` 分支：v2 无新字段即全部 `LIVE`。

**生成端输入**：`write_signal_manifest(..., explained_missing: frozenset[str])`，由 `shadow_cycle` 用当日 `tushare.daily`
（信号日 PASS 后必然存在）计算"沿用目标中无 bar 者"传入；generation.py 只做转发，不做判断（依赖向内）。

**配置**：`shadow_pipeline.max_carried_without_score`（建议 3，即 Top30 的 10%）；超出即 DataClockError——同日 4 只以上
成分股停牌意味着系统性事件或数据缺陷，宁可当日不出单。

**下游兼容清单（实现时逐项加测试）**：
1. `shadow/reconciliation.py`：左连接按 instrument，不读 score → 无改动，加回归测试。
2. `paper/projection.py` `project_top20_signal`：按 `rank` 截取前 20、等权 5%；须确认不以 score 排序或求和（null 会崩）。
3. `web/query_signal.py`：当前/上一信号 orders 对比与展示；null score 的渲染与"持平/新增/退出"分类不得报错。
4. `shadow/report.py`、`web/query_evidence.py:442`：读取 orders 的地方容忍 null。
5. `tests/test_shadow_manifest*`：新增 v3 哈希稳定性、v2 旧文件仍可验证。

## 6. 失败关闭

- 缺评分目标**不在**"信号日无 bar"集合内（有 bar 却无评分）→ DataClockError 不变：这是模型/特征层异常，不能用停牌解释。
- 缺口只数 > `max_carried_without_score` → DataClockError。
- `target_instruments` 数量/唯一性检查不变；调仓日 `len(selected) < topk` 检查不变。
- `signal_daily` 不可读 → 不做任何解释、按旧合同处理（即失败），不猜。

## 7. 回滚

纯代码回滚（revert 提交）即可恢复旧合同；已生成的 v3 manifest 保留不改，读取方对 v3 的兼容代码保留。无数据迁移。

## 8. 验收指标

- 单元测试：①沿用日 1–3 只无 bar 目标 → 产出 v3 manifest，权重/rank 沿用，`carried_without_score` 正确；②有 bar 无评分 →
  DataClockError；③4 只无 bar → DataClockError；④调仓日行为与 v2 字节级一致（除 schema_version）；⑤v2 旧 manifest 校验通过；
  ⑥下游三处对 null 的容忍。
- 离线重放 fixture：用 20260928 manifest 的目标列表 + 20260929 真实 `daily`/`suspend_d`（只读）+ 合成评分，证明新合同对该日产出
  信号且 `carried_without_score == ["SH600363"]`；不读模型、不写生产目录（`.test-tmp`）。
- 全仓测试、Ruff、`make architecture-check`、`git diff --check`、脱敏检查通过；manifest.py 仍 ≤400 行。
- 不得以本变更为由修改 20260929 的历史账本或补造该日信号。

## 9. 退出 / 复审触发器

- 若出现"有 bar 却无评分"的真实案例，另立 ADR，不扩大本合同。
- 若日后股票池规则在调仓日即排除停牌/ST，复审 `max_carried_without_score` 是否仍需要。
- ADR 0016 落地、本合同随候选进入生产并经首个自然沿用日验证后，状态改为 IMPLEMENTED。

## 10. 需要用户裁决

1. 接受方案 B（沿用可解释缺口）并授权按本 ADR 写 PROTOCOL 冻结后实现？
2. `max_carried_without_score` 取 3 是否可接受？
3. 是否同意"只随新候选进入生产"，不为此单独做发布？

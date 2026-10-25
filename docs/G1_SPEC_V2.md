# G1 因子准入执行规格 — g1-v2

- 冻结：2026-10-25（实现之前）；机器配置：`config/g1_v2_spec.yaml`
- 依据：`g1-positive-control-v1` 终态 `G1_UNDERPOWERED` 的机制证据（`docs/G1_POSITIVE_CONTROL_ACCEPTANCE_20261025.md` §4）与用户对
  `docs/G1_V2_RECALIBRATION_PROTOCOL_DRAFT_20261025.md` D1–D4 的裁决（均选建议项）
- `g1-v1`（`docs/G1_SPEC.md`、`config/settings.yaml:g1_admission`、`src/shaiwei/research/g1.py`）**原样保留**，其 29 份历史裁决不重算、不覆盖
- **g1-v2 只有在 `g1-positive-control-v2` 终态为 `G1_CALIBRATED` 之后才可用于任何真实候选**；在此之前不得裁决任何真实因子
- `docs/GATES.md` 的 G1 执行解释段只在 g1-v2 标定为 `G1_CALIBRATED` 且用户确认启用后才追加；在此之前 GATES.md 不改

## 1. 与 G1 冻结文字的对应

GATES.md G1 的条目与阈值数字不变（DSR≥0.95、NW(10) t≥3.0、N 按同研究家族实验总账全部尝试计、压力期回撤≤20%、换手≤1.10、成本+100%、
滑点加倍、|ρ|<0.5、复杂度、经济含义）。g1-v2 只重新解释两处原文未规定的执行方式，并修正一个已知偏差：

| 原文 | g1-v1 | g1-v2 |
|---|---|---|
| ④ 入库后组合**净 ICIR** 有增量 | 候选混合分数 ICIR > 基线 ICIR（点比较） | 逐日配对差 d_t = RankIC(候选混合分数)_t − RankIC(基线分数)_t，NW(10) t(d) ≥ 3.0 |
| ④ 入库后组合**净超额** 有增量 | 候选复利净超额 > 基线（点比较；已证明由选股噪声决定） | 逐日配对差 e_t = 候选日净超额_t − 基线日净超额_t，NW(10) t(e) > −2.0（非劣） |
| DSR≥0.95 | 作用在候选组合日净超额 | 作用在 d_t（增量信息比），试验方差取同家族各尝试的 `selection_increment_ir` |
| 中性化 | 残差只保留未来标签非空的行（支撑前视） | 残差只用当日 PIT 支撑（因子、行业、市值非空），标签只用于计算 IC |

“不放宽”的检验：`g1-positive-control-v2` 在新种子阴性对照上必须零通过，并新增 N3“基线复制”对照（见该协议）。

## 2. 全部准入门（全部通过才 PASS）

1. `pit_and_shift`、2. `complexity`、3. `economic_rationale`、4. `library_correlation`：同 g1-v1；
5. `rolling_window_sign`（W1–W6 方向校正后 ≥4 个为正）、6. `rank_ic_retention`（≥0.5）、15. `hac_t`（因子自身方向化日频 OOS RankIC 的
   NW(10) t≥3.0）：同 g1-v1，但因子残差按 PIT 支撑中性化；
7. `stress_drawdown`（三段压力期独立因子腿 ≤20%）、8. `turnover`（≤1.10）、11. `cost_2x`、12. `slippage_2x`：同 g1-v1；
9. **`incremental_icir_t`**：d_t 在 W1–W6 全部 OOS 交易日（同日配对、两侧均有效才计入）的 NW(10) t ≥ 3.0，且观测 ≥252；
10. **`excess_noninferiority`**：e_t 在 W1–W6 全部 OOS 交易日的 NW(10) t > −2.0，且观测 ≥252；
13. **`valid_trial_increment_irs`**：同家族具有有限 `result_json.selection_increment_ir` 的尝试 ≥2；
14. **`deflated_increment_ir`**：对 d_t 按 Bailey & López de Prado 公式计算 DSR（d 的偏度、峰度、样本长度；期望最大值用同家族试验
    `selection_increment_ir` 的样本方差与家族尝试数 N）≥0.95。N 不接受自报，机械统计实验总账同家族全部尝试（含失败与 g1-v1 时期的尝试）。

任何缺字段、非有限值、窗口/压力期集合不符、d_t 或 e_t 无法由证据复算账本 `selection_increment_ir`，均为证据错误；普通不达标为 REJECT。

## 3. 证据契约（相对 g1-v1 的增量）

证据 `schema_version: 2`，在 g1-v1 字段之外增加：逐日 `candidate_score_rank_ic`、`baseline_score_rank_ic`、`candidate_daily_net_excess`、
`baseline_daily_net_excess`（均带日期，按日期配对）、`neutralization: pit_support`。实验总账 `result_json` 增加 `selection_increment_ir`。
裁决写 `logs/g1-v2/` 与独立账本；**是否沿用 `ledger/factor_admissions.csv` 另行决定**（须在历史候选重判协议中裁决，本规格不授权写入）。

## 4. 方法依据与边界

- Newey & West（1987）HAC，Bartlett 权重、10 阶，与 10 日重叠标签一致；配对差消除两侧共同的市场与基线噪声。
- Bailey & López de Prado，*The Deflated Sharpe Ratio*：原定义针对策略收益；g1-v2 将其用于增量信息比序列，是本项目的方法选择，
  其行为由 `g1-positive-control-v2` 的阳性/阴性对照实证检验，而非由文献背书。
- 2017、2024-01~02、2026H1 已用于规则设计，只作已知压力复核；真正前瞻样本外仍从 2026-07-09 起累计。

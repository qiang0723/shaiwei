# G1 因子准入执行规格 — g1-v1

冻结时间：2026-07-16，早于首次阶段 1 因子准入。该规格只建设裁判，不授权或启动因子挖掘。

## 1. 目的与不可变性

G1 回答的不是“候选看起来是否不错”，而是“在已经尝试过的全部同家族研究之后，这个候选是否仍为
现有组合提供扣费后的可重复增量”。阈值来自 `config/settings.yaml:g1_admission`，连同六窗口名称和
三段压力期共同计算 `spec_sha256`。每次判定绑定：

- 候选实验 ID、代码快照和数据快照；
- 原始证据 JSON 的 SHA-256；
- 实验总账整文件 SHA-256；
- `g1-v1` 规则 SHA-256；
- 判定报告 SHA-256。

报告写入 `logs/g1/`，决策追加到 `ledger/factor_admissions.csv`。相同四重绑定复跑只复用原结果，
不追加第二条决策；旧报告不覆盖。因子准入账本与实验总账分离，裁判行为本身不增加试验次数 N。

## 2. 对原 G1 歧义的冻结解释

原文 `DSR/t≥3.0` 量纲不成立：DSR 是概率，t 是无量纲统计量。`g1-v1` 将其解释为两个独立且
必须同时通过的门：

1. `DSR ≥ 0.95`；
2. 方向冻结后的日频样本外 RankIC，`Newey-West(10) t ≥ 3.0`。

DSR 使用 Bailey 与 López de Prado 的定义：在原始日频上计算候选扣费后超额收益 Sharpe，使用收益
偏度、原始峰度、样本长度，以及同研究家族试验 Sharpe 的样本方差。拒绝阈值为 N 次独立试验下的
期望最大 Sharpe。N 不接受证据文件自报，而是机械统计 `ledger/experiments.csv` 中
`params_json.g1_research_family` 相同的全部尝试；失败尝试也增加 N。试验方差只使用总账中存在有限
`result_json.selection_sharpe` 的尝试，少于 2 个有效值直接 REJECT，不用默认方差补齐。

这是一项保守执行选择：相关试验不折算“有效 N”，因为在尚无稳定相关结构估计前，折减 N 会给研究者
留下事后放宽空间。

Newey-West 使用 Bartlett 权重和固定 10 阶滞后，与项目 10 交易日重叠标签和调仓周期一致。候选方向
只由样本内 RankIC 的符号冻结，样本外数据不得翻转方向以制造正 t 值。两项统计均至少需要 252 个
日频观测。

原始方法依据：

- Bailey & López de Prado, *The Deflated Sharpe Ratio*：
  https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf
- Harvey, Liu & Zhu, *… and the Cross-Section of Expected Returns*：
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2513152
- Newey & West, *A Simple, Positive Semi-Definite, Heteroskedasticity and Autocorrelation
  Consistent Covariance Matrix*：https://ssrn.com/abstract=225071

## 3. 全部准入门

以下门全部通过才 `PASS/admitted=true`：

1. PIT 与 shift 哨兵均 PASS。
2. 表达式非空；token ≤20、AST 节点 ≤80，且复杂度与候选实验总账一致。
3. 人工撰写的经济含义不少于 20 个字符；模型自评不代替人工陈述。
4. 对既有因子库最大绝对 Spearman 相关性严格 `<0.5`，等于 0.5 也拒绝。
5. 固定 W1-W6 中，按样本内方向校正后至少 4 个窗口 RankIC 为正。
6. 六窗口平均方向校正 RankIC / `|样本内 RankIC| ≥0.5`。
7. 三个冻结压力期的组合最大回撤分别 `≤20%`。
8. 候选单边换手 / 同配置基线单边换手 `≤1.10`。
9. 候选扣费后 ICIR 严格高于同预算基线。
10. 候选扣费后净超额严格高于同预算基线。
11. 成本 +100% 后净超额 `≥0`。
12. 滑点加倍后净超额 `≥0`。
13. 同家族至少两个试验具有有效的日频 `selection_sharpe`。
14. DSR `≥0.95`。
15. Newey-West(10) 日频样本外 RankIC t `≥3.0`。

任何缺字段、非有限数值、窗口/压力期集合不完全匹配、候选日收益不能复算实验总账
`selection_sharpe`，均为证据错误并停止判定；普通门槛不达标则形成可审计 `REJECT` 报告。

## 4. 证据输入契约

候选生成器必须先向 `ledger/experiments.csv` 追加一行，并在 `params_json` 写入：

```json
{
  "g1_research_family": "stage1-gp-v1",
  "expression_tokens": 9,
  "ast_nodes": 14
}
```

凡成功得到选择期收益的尝试，都在 `result_json.selection_sharpe` 写入未年化日频 Sharpe
（日频扣费后超额收益均值 / 样本标准差）；失败尝试保留失败原因且同样计入 N。

裁判证据 JSON 的权威机器 schema 可执行：

```bash
make g1-schema
```

核心字段包括候选实验 ID、研究家族、候选代码/数据快照、人工经济含义、PIT/shift 测试报告路径与
哈希、复杂度、对库相关性、六窗口
RankIC、逐日样本外 RankIC、三压力期最大回撤、基线/候选换手与净 ICIR/净超额、双倍成本/滑点
净超额，以及逐日扣费后超额收益。所有序列必须来自与候选实验行相同的代码和数据快照。

执行方式：

```bash
make g1-admit G1_EVIDENCE=data/research/<candidate>.json
make docker-g1-admit G1_EVIDENCE=data/research/<candidate>.json
```

CLI 对统计上的不准入返回结构化 `REJECT`，而不是伪装成系统故障；证据损坏或绑定不一致则非零退出。

## 5. 当前边界

- 2017、2024-01~02、2026H1 已被用于规则设计，只是已知压力复核，不宣称未知样本外。
- 真正前瞻样本外仍从 2026-07-09 起累计。
- `g1-v1` 不实现候选生成、模型选择或自动入库；它只裁决已经完整记账的候选。
- 更改任何规则须创建 `g1-v2`，保留 `g1-v1` 代码、配置、旧账本与旧报告，禁止重写历史结论。

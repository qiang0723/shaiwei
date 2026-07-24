# P1 主力资金流六候选正式效果验收（2026-07-24，UTC+8）

## 1. 最终结论

P1 正式效果比较完成，机器结论为 **REJECT**：六个预注册资金流候选均未通过冻结的 `g1-v1`
十五门，因此正式因子库插入 0 个，不授权进入生产模型、信号、scheduler 或模拟仓。

这不是数据或运行失败。六候选均通过 PIT/shift、复杂度、经济含义、因子库相关性、六窗口符号、
压力回撤、换手、双倍成本、额外双边 10bp 滑点和有效试验数门；共同未通过：

1. RankIC 保留率；
2. 相对 Alpha158 基线的净 ICIR 增量；
3. 相对 Alpha158 基线的净超额增量；
4. Deflated Sharpe；
5. Newey-West(10) HAC t。

结论应表述为：**首批六个简单资金流候选自身存在部分正 IC 和正净超额，但没有在同预算 Alpha158
之外形成足够稳定、显著且可准入的增量。** 不得把“成本压力后仍为正”或个别窗口较强改写成成功。

## 2. 冻结比较与结果

比较保持中证800、次一开盘、Top30、10 交易日调仓、同一账户规模和费用不变。候选组合为
`90% Alpha158 横截面排名 + 10% 方向冻结后的资金流增量残差排名`；每个候选执行 W1—W6 ×
正常费用/双倍成本/额外双边 10bp，共 108 个预注册证据单元。

| 候选 | 发现期 RankIC | 正向 OOS 窗 | 候选净超额 | 基线净超额 | 候选净 ICIR | 基线净 ICIR | 结论 |
|---|---:|---:|---:|---:|---:|---:|---|
| `mf_net_intensity_1d` | 0.01679 | 4/6 | 0.27110 | 0.51824 | 0.38311 | 0.38924 | REJECT |
| `mf_large_intensity_1d` | 0.01694 | 4/6 | 0.29465 | 0.51824 | 0.38201 | 0.38924 | REJECT |
| `mf_net_intensity_5d` | 0.02492 | 4/6 | 0.21789 | 0.51824 | 0.38231 | 0.38924 | REJECT |
| `mf_net_intensity_20d` | 0.01333 | 4/6 | 0.20116 | 0.51824 | 0.37843 | 0.38924 | REJECT |
| `mf_net_innovation_5_20` | 0.01741 | 4/6 | 0.47575 | 0.51824 | 0.38024 | 0.38924 | REJECT |
| `mf_net_persistence_10d` | 0.02382 | 4/6 | 0.39620 | 0.51824 | 0.38885 | 0.38924 | REJECT |

所有候选的三段压力期最大回撤均低于 20% 门槛，双倍成本和额外滑点后的累计净超额均非负；但没有
候选同时超过基线净 ICIR 和基线净超额。最接近基线的是 `mf_net_innovation_5_20`，其净超额
0.47575 仍低于 0.51824，且 HAC/DSR 不通过，因此也不能作为“候补赢家”接入生产。

## 3. 警告日稳定性诊断

全量质量报告的 37 个 `NET_FLOW_EXCEEDS_DAILY_SCALE_TAIL` 警告源日只用于 `NOT_FOR_VERDICT`
诊断。按候选覆盖，剔除警告源日对应的特征日后移除 31—35 个日度 IC 观察，平均 RankIC 变化范围约
-0.00019 至 +0.00030；方向混合且量级小。该结果不改变正式主判，也不证明警告无风险。

## 4. 不可变证据与哈希

| 证据 | 行数 | SHA-256 |
|---|---:|---|
| canonical 核心残差 | 3,169,528 | `efbc8eca00cf528c8895a49a16a9824be1e755ab41429d9e95bcc17487e55993` |
| canonical 正式残差 | 2,335,871 | `e2e456653c72aebcfc173402b76cfa422f0a020506bd26241c349d94423ebfcf` |
| Alpha158 预测缓存 | 1,164,697 | `46a24aad0c21e2df054b2f4ba9d58ffebbadaf8bf9a811318fedd836663cc38a` |
| 逐日 IC | 21,415 | `ff1d7274b61c3ed10c6f4c45c6eef310aa6e13a3c803a5b9ba05fac5cef8d82a` |
| 量化后逐日收益 | 26,208 | `6dbe01ce4abc5d8aeb55d386b73bd4351e910c7d19c112f4938a6c2caa04cd4d` |
| 最终汇总 | — | `9d6e8580f03748d42d9a81195f6a5b2146d111b9400afe175e02ba9789bbde24` |

绑定：

- 生产代码快照：`261f58b858dbc46d49ffb9f623e8868dcb10891cc2dadd2292728da6de7eb4fa`；
- canonical 残差数据快照：`9f9e72bc0e4de0c0d231455b278d6cb536eb5da59124e03eaaea29066929477e`；
- 最终 P1 工具快照：`8f8f7a09c21f3c097d1487cb719370854bd785c81096f9f96fc737c3a37cc045`；
- 最终比较规则：`27d14240cfcefef5dec912fbdeb95a9a351888d3765043af168f61bfa77c6daf`。

本地机器报告：

- `logs/moneyflow/p1_residual_build_ordered_idempotent_20260724.json`；
- `logs/moneyflow/p1_experiment_run_bound_20260724.json`；
- `logs/moneyflow/p1_experiment_run_bound_idempotent_20260724.json`；
- `data/research/moneyflow/experiments/p1-moneyflow-v1/summary-27d14240cfce-8f8f7a09c21f-9f9e72bc0e4d.json`。

## 5. 失败尝试、试验 N 与幂等

整个家族最终保留 18 条实验记录：

- 第一代 6 条完成计算与 G1，随后端到端复跑发现 qlib 日收益 `10^-15` 级字节漂移；
- 第二代 6 条将逐日收益量化到 10 位，但把 Sharpe 二次量化，G1 在裁决前按证据绑定失败；
- 第三代 6 条保留量化逐日收益，并从该序列精确重算 Sharpe，完成 G1。

没有删除、覆盖或把失败尝试排除出 N。最终六项 G1 决策均使用 `trial_count=18`；
`ledger/experiments.csv` 中本家族 18 行，`ledger/factor_admissions.csv` 中 12 行（第一代 6 个普通
REJECT + 第三代 6 个最终 REJECT；第二代在裁决前绑定失败）。

第三代完全相同复跑结果：逐日 IC、逐日收益、候选不可变 JSON、实验记录、G1 决策和汇总六类
`reuse` 全部为 `true`；实验仍为 18 行、准入仍为 12 行、汇总哈希不变。两次修复后运行峰值 RSS
分别约 6.23 GB 和 7.27 GB，均在现有 Docker 资源限制内。

交付前质量门：P1 隔离测试 41 项、全仓测试 184 项、Ruff、compileall、`pip check`、账本唯一性与
追加约束、差异格式和凭据脱敏检查全部 PASS；Docker scheduler 保持 healthy。

## 6. 授权边界与下一步

- P1 至此完整结束，结论为 `REJECT`；正式因子库 0 插入。
- 不在本家族追加窗口、组合、阈值或候选变体；若未来有新的独立经济假设，必须另建预注册家族并把
  既有 18 次尝试纳入多重检验背景。
- 生产代码快照从头到尾未漂移，P1 工具仅位于 `tools/p1_moneyflow/`。
- 后台下一工作包可转向 P2 科创50独立策略臂，但在修改 `src/config/tests/compose` 前，必须先通过
  生产 scheduler 与开发工作树的发布快照隔离门禁。
- Web 视觉设计可旁路继续；真实 API、Web Docker profile 与生产代码施工同样等待隔离门禁。

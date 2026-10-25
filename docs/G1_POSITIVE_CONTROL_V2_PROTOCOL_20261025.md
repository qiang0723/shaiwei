# g1-v2 正控重标定 · 结果前协议

- 协议 ID：`g1-positive-control-v2`；家族：`g1-calibration-v2`；机器配置：`config/g1_positive_control_v2.yaml`
- 状态：`FROZEN_BEFORE_RESULTS`；冻结：2026-10-25（实现之前）
- 被测对象：`g1-v2`（`docs/G1_SPEC_V2.md`、`config/g1_v2_spec.yaml`，配置 SHA-256 `8ecce43f…`）
- 上位：`docs/G1_V2_RECALIBRATION_PROTOCOL_DRAFT_20261025.md`（用户 D1–D4 均选建议项）、`g1-positive-control-v1` 验收；设计沿用 v1，
  只列差异。本协议提交推送前不写任何实现

## 0. 要回答的问题

`g1-v2` 是否同时做到：对现实可得效应量（发现期 RankIC ≤0.04）有 ≥80% 的检出率，且不放行纯噪声、不把“基线已有的信息”当增量。

## 1. 结果盲证明（冻结时复核）

```
冻结前 HEAD                    5f064c141ae28cd8356d26fd8c15f04d6ce4d399
ledger/experiments.csv         1009 行（g1-calibration-v1 家族 93 行，g1-calibration-v2 家族 0 行）
ledger/factor_admissions.csv   29 条决策，admitted=true 0 条
ledger/g1_calibration_runs.csv 93 行（全部 g1-positive-control-v1）
g1-v2                           从未计算于任何真实或标定数据
```

## 2. 与 v1 相同

两层划分原则、R1–R5 构造与强度阶梯（0.02/0.04/0.06，容差 ±0.002，每种子各自标定 `a`）、六窗与发现期、DSR 家族按“路线×强度”格子
（诊断 N=166/196，只替换 N）、Top30 Jaccard 与传递链必报、Clopper–Pearson 上界与依赖性说明、NOT_FOR_ADMISSION 硬隔离、预算削减
顺序（只削 N1/N2，从不削 R1）、单次执行与独立审计流程。

## 3. 与 v1 不同

| 项 | v2 |
|---|---|
| 被测门 | `g1-v2`：B 层的 `incremental_icir_t`、`excess_noninferiority`、`valid_trial_increment_irs`、`deflated_increment_ir` 取代 v1 的四个对应门 |
| 中性化 | PIT 支撑（`pit_support`）；R1 的 `a` 也在 PIT 中性化下标定 |
| 种子 | 全部更新且与 v1 不相交：R1/R2 201–205、N1 6001–6030、N2 7001–7030、N3 8001–8030 |
| 新阴性对照 N3 | “基线复制”：各窗口内 f_t = (z(基线分数)_t + z(噪声)_t)/√2，方向固定为 +1（基线只有 OOS 分数，无发现期）。只按三个增量门判定：`incremental_icir_t`、`valid_trial_increment_irs`、`deflated_increment_ir` 全部通过即算“放行” |
| 报告目录 | `logs/g1-calibration-v2/` |

## 4. 预注册判读

| 条件 | 终态 | 后果 |
|---|---|---|
| N1、N2 主判零通过，N3 增量零放行，且 R1 在 **≤0.04** 某档 5 种子中 ≥4 个主判通过 | `G1_CALIBRATED` | g1-v2 可用；另立协议决定历史候选重判与因子线恢复 |
| 同上但 R1 仅在 0.06 档检出 | `G1_BORDERLINE` | g1-v2 不启用；须另立 g1-v3 |
| 阴性对照零通过且 R1 三档均未检出 | `G1_UNDERPOWERED` | g1-v2 不启用；因子线继续暂停 |
| N1、N2 主判或 N3 增量有任何一次通过 | `G1_PERMISSIVE` | g1-v2 作废 |

误放率：N1+N2 主判（60）与 N3 增量（30）分别报告 Clopper–Pearson 95% 单侧上界。**不得在读取任何 v2 标定结果之后修改本表。**

## 5. 开发集（D4）

v1 正式执行 `g1cal-17f5ae756cdb-20261024T153149Z` 的 93 份落盘面板可作开发集：只用于检查 g1-v2 新统计量能否计算、报告其分布；
**不得据此调整任何阈值、选项、构造或判读**。开发集检查本身另需授权（读取真实数据），输出写 `logs/g1-calibration-v2/dev-set/`，不进任何账本。

## 6. 执行序列（每步单独授权）

1. 本协议、`docs/G1_SPEC_V2.md`、两份配置提交推送（冻结）；
2. 工程：g1-v2 裁判新模块（`g1.py` 一行不改）、PIT 中性化、配对增量与证据 schema v2、N3、复用 v1 标定框架；合成测试；
3. 开发集可行性检查（只读，只出分布）；
4. 计时试跑（协议外种子）→ 断网镜像 → scope → 用户逐字批准 → 单次执行 → 独立审计 → 验收。

## 7. 变更规则

同 v1：冻结后修改须显式作废并保留原文；若冻结与首次结果读取之间 §1 任一事实变化，须重新起草。

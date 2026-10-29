# TP-F-1 趋势回踩联合状态正式小批 · 协议（2026-10-29 冻结，实现前）

- 协议 ID：`tp-f-1-trend-pullback-joint-state-001`；机器真身：`config/tp_f_1_formal_small_batch_v1.yaml`（SHA-256 见 STATE）
- 状态：`RESULT_BLIND_FORMAL_PROTOCOL_FROZEN_PENDING_R2_1R1_LATCH_USER_BATCH_AUTHORIZATION_AND_RELEASE`；本协议推送前不写实现
- 草案与裁决：`docs/TP_F_1_FORMAL_SMALL_BATCH_PROTOCOL_DRAFT_20261029.md`；用户 2026-10-29 对 D1–D4 均选建议项
- 上位：
  - TP-F-0A：`GO_PREP_ONLY`；
  - TP-F-0B：`GO_FORMAL_PROTOCOL`，审计 PASS；
  - 形态：RF-1（`357975f2…`）；
  - 裁判：g1-v2（`8ecce43f…`）。
- 结果盲：TP-F 公式 0 个。TS 收益、g1-v2 重判结果、TP-F-0B 计数都不作为参数来源；TP-F-0B 计数只用于写明缺失值如何处理。

## 1. 研究问题

中证800 PIT 成员，标签 t+1 开盘进、t+11 开盘出：趋势质量 × 回踩质量的联合状态，能否在 Alpha158 与行业/市值暴露之外，提供稳定、非重复、扣成本后的增量信息？裁决权全在 g1-v2。

## 2. 执行三门（冻结 ≠ 执行授权）

1. R2-1R1 检查点锁存（`CHECKPOINT_OBSERVED` 或 `OBSERVED_WITH_EXECUTION_WARN`），且用户已看过描述报告；
2. 用户对本批精确 scope 的逐字授权；
3. 任何 LLM 调用前已冻结执行 release。

任一不满足，一分钱都不花。

## 3. 已裁决口径

| 裁决 | 冻结内容 |
|---|---|
| D1 机制约束 | 候选必须满足 TP-F-0B 联合状态签名（同一规范表达式内，趋势分量与回踩分量位于不相交子树），不满足即拒并计入预算。签名实现以哈希绑定；均线交叉类不算分量，属于已知局限 |
| D2 选择 | 全部合格候选（≤3）在发现期 2016–2018 计算 g1-v2 `selection_increment_ir`，机械取 Top1/Top2；方向取发现期 RankIC 的符号，只冻结一次；无参数网格 |
| D3 家族 N | DSR 的 N 计入全部完成响应（≤8，含失败与重复）；逐尝试方差来自全部合格候选的发现期增量 IR；有效 IR 少于 2 个时，相应门如实失败 |
| D4 预算 | `deepseek-v4-pro`（不可用即 `BLOCKED`，不换模型）；至多 8 个响应、至多 3 个合格候选；单批 $1、总 $2；第二批只用于 `BLOCKED` 后另立的恢复协议 |

## 4. 候选合同与去重

- **语法**：AlphaGen 安全 AST（`5bc20c3b…`），特征 `$open/$close/$high/$low/$volume/$vwap`；单算子 ≤50 日，总回看 ≤100 交易日，≤20 token，≤80 节点。
- **规范表达式**与 ≥20 字的非占位经济陈述，缺一不可。
- **拒绝条件**（计入预算）：
  - 规范 AST 等于 RF-0B 封存注册表、Alpha158、D1-v2/M1/M3 账本或 R3/R4/R5 中任一身份；
  - 语义等价于 TS v5 语义签名，或 TP-F-0B 普查中 D1-v2 已有的联合状态式。
- **五层去重**：

  | 层 | 执行点 |
  |---|---|
  | ① 规范 AST | 候选合同 |
  | ② 语义盲评 | 沿用 RF-1 |
  | ③ 暴露 | g1-v2 `library_correlation` |
  | ④ 增量 IC | `incremental_icir_t` |
  | ⑤ 组合增量 | `excess_noninferiority` / `cost_2x` / `slippage_2x` |

## 5. 效果阶段

- **判定**：Top1、Top2 依次进入 g1-v2 全部 15 门。
- **读取区间**：与 TP-F-0B 画像一致，即发现期、W1–W6、三个压力期；不读其外。
- **缺失值**：沿用 g1-v2 既有管线，不填充。
  - 2016 年前 99 个交易日预热不足 → NaN，由 PIT 支撑剔除；
  - t+11 出场缺开盘 → 标签 NaN；
  - 申万缺失 → 不在 PIT 支撑内。
- **记账**：只写 `factor_admissions_v2` 与 `experiments`；不入因子库，不写 v1 准入账本。

## 6. 裁决

- **`GO_SEPARATE_ADMISSION_OR_PAPER_PROTOCOL_PROPOSAL_ONLY`**：Top1 或 Top2 通过 g1-v2。只授权起草入库或模拟仓提案。
- **`REJECT_TP_F_AND_CLOSE`**：两者均 REJECT，或合格候选不足，或预算耗尽。按 TP-F-0A §4 关闭机制，不改口径追结果。
- **`BLOCKED_TP_F_1`**：合同或执行失败。另立恢复协议。

生产授权 `none`。

## 7. 执行边界与序列

- **网络与密钥**：只开 DeepSeek HTTPS 通道；密钥只由 LLM 容器读取。其余容器断网、只读根、write-once。
- **单次执行**：同 scope 不重跑，每批独立审计；不碰模拟仓、scheduler、Web 或生产。
- **每步单独授权**：
  1. 推送冻结；
  2. 工程：复用 `rf_1` 骨架与 `tp_f_0b` 签名/注册表，不复制；合成测试；
  3. 镜像内 fixture；
  4. 等 R2-1R1 锁存，并经用户看过报告；
  5. 精确 scope → 逐字批准 → 单批生成 → 发现期选择 → g1-v2 判定 → 独立审计 → 验收。
- **变更规则**：冻结后修改须显式作废并保留原文；任何候选生成之后，不得修改合同、选择、N 或裁决规则。

# M6-5C-A 生产 Head30 退市风险退出方法工程协议

- 协议 ID：`m6-csi800-production-head30-delisting-risk-method-v1`
- 状态：`FROZEN_BEFORE_IMPLEMENTATION`
- 日期：2026-08-23（UTC+8）
- 前序：M6-5B-R1 `BLOCKED_BY_UNMODELED_DELISTING`；A1-5A `GO_ENGINEERING_ONLY`
- ADR：`docs/ADR_002_DELISTING_RISK_EXIT_OVERLAY_20260823.md`

## 1. 结果目标

建设一个不读取封存效果的纯退市风险状态机，为未来 M6-5C-B 执行适配提供唯一方法真身。本节点只
回答“指令是否能按 PIT、确定、失败关闭地产生”，不回答 50 万元账户是否可行、策略是否有效或是否
应进入生产。

## 2. 固定输入和状态

- 输入仅含 `ts_code / trade_date / close` 的未复权 A 股日线、信号日、当前持仓代码和目标代码；
- `.BJ`、重复证券日、无效日期、非正价格、同一证券日期倒序或冲突立即失败关闭；
- `trigger_price_cny=1.00`，`trigger_consecutive_trading_closes=10`，比较为严格 `<1.00`；
- 缺失交易行既不计数也不伪造收盘；本状态机只沿实际有效交易收盘序列计算；
- 状态为 `CLEAR / BUY_BLOCKED / EXIT_LATCHED / DISPOSED`。已有持仓触发后进入 `EXIT_LATCHED`，不能
  因后来价格恢复而自动清除；非持仓风险股只阻止当次买入，后续重新达到 CLEAR 才可在新信号中进入。

## 3. 固定输出

- `blocked_buy_codes`：当次目标中风险已激活且当前未持有的证券；
- `forced_exit_codes`：当前持仓中首次或继续处于锁存退出的证券；
- `eligible_target_codes`：原有序目标去除 blocked/forced 后的稳定子序列；
- `cash_reserve_weight`：按原目标权重计算被移除权重，不向其他证券再分配；
- 每个触发必须给出最后 10 个有效收盘日、价格、as-of 和原因码，不含收益或未来价格；
- 任何实际成交、费用、NAV 或裁决均不属于本节点输出。

## 4. 继承与变化

- 继承封存 Head30 排名、目标权重、10 日普通调仓、50 万元、费用、整手、开盘合法性、容量和全部
  效果门；本节点不得读取这些效果；
- 唯一新变量为 `delisting_price_risk_exit_overlay_v1`；不加替代股、不重排、不提高其余权重；
- `paper-v1` 和 `src/shaiwei/paper/engine.py` 均不修改。新策略身份预留为
  `paper-v2-delisting-risk-exit`，只有未来 M6-5C-B 工程通过后才能使用；
- 旧两次 `m6_head30_capital_feasibility` 尝试不重算。未来新家族为
  `m6_head30_capital_feasibility_delisting_risk_v1`，历史结果只能是事后方法恢复诊断。

## 5. A1-5A 接入要求

M6-5C-A 真实读取和账本追加均为 0。未来 M6-5C-B/C 若要读取封存目标、价格或效果，必须在 reader
调用前：

1. 以新 family、ordinal 和精确 release scope 构造 canonical claim；
2. 把最小 `ledger/experiments.csv` 写挂载与 receipt 输出根加入不可变 release；
3. claim/receipt 双 fsync 成功后才开放 reader；失败仍消费尝试，同 scope 不得重跑；
4. terminal report 和独立 audit 必须引用并复核 claim receipt，不更新 claim 行。

## 6. 实现与验收范围

新增独立 `capital_feasibility/delisting_risk.py`，不依赖 Web、Docker、Qlib、模型、账本或 `.env`；新增
配置合同和 synthetic fixture，覆盖 9/10 日边界、等于 1 元、序列重置、持仓锁存、买入阻止、目标
顺序、现金权重、重复/.BJ/无效价格、确定性双跑和未来行不可见。

专项、架构、全仓、账本、Ruff、compileall、pip check 和 diff-check 全绿后，只可裁为
`GO_METHOD_ENGINEERING_ONLY`。不构建镜像、不生成 scope、不运行真实回放、不写真实账本、不改变 Web、
scheduler、模拟仓或生产。

## 7. 下一步与停止条件

完成后停在 M6-5C-B 前。下一节点须另立执行适配协议，优先从冻结热点 `paper/engine.py` 抽出可复用
卖出执行职责，证明 `paper-v1` 默认路径完全不变，再接入每日锁存退出；不得把执行适配、真实效果和
生产发布合并成一个节点。

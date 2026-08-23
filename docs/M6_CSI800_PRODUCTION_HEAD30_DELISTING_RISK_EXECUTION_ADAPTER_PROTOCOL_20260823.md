# M6-5C-B 生产 Head30 退市风险执行适配工程协议

- 协议 ID：`m6-csi800-production-head30-delisting-risk-execution-adapter-v1`
- 状态：`FROZEN_BEFORE_IMPLEMENTATION`
- 日期：2026-08-23（UTC+8）
- 前序：M6-5C-A `GO_METHOD_ENGINEERING_ONLY`
- ADR：`docs/ADR_002_DELISTING_RISK_EXIT_OVERLAY_20260823.md`

## 1. 结果目标

在不读取真实目标、行情或效果的前提下，为 M6-5C-A 的 `EXIT_LATCHED` 指令建设研究专用执行端口；
同时把 `paper/engine.py` 中已有的卖出计算抽到独立、可直接测试的领域模块。成功只表示合成执行适配
可用且 `paper-v1` 兼容，不表示 50 万元回放完成、策略有效或获得生产授权。

## 2. 旧语义冻结

- 施工前 `src/shaiwei/paper/engine.py` SHA-256 为
  `44e64d1a776973b0eb5b9ba5ce6d8a7d103a7e8a20aaeb172929c7ca4b1d6b94`，860 行；
- 固定两日合成场景覆盖初始双股买入、次日完整卖出、再买入、订单/成交 ID、费用、成本、现金、持仓、
  NAV、换手和基准；其完整 canonical 结果 SHA-256 为
  `dd7b40b33b75f7e5b261bebaf64b8d1e748d6e42f62225da0b4d490f6e9d1faa`；
- 实现后无风险指令的默认调用和显式空指令调用都必须重算到同一 SHA；现有 `paper-v1` 全量测试必须
  保持通过，订单及成交字段不得增加、删除或改值。

## 3. 新策略身份与唯一变化

- 新增研究专用 `PaperDelistingRiskPortfolio`，账户固定
  `m6_head30_delisting_risk`，执行策略固定 `paper-v2-delisting-risk-exit`；
- 该策略继承 `paper-v1` 的资金、费用、整手、涨跌停、停牌、公司行为、估值和会计语义；
- 只有新策略允许目标股票权重合计小于 1，差额是风险层明确保留的现金；权重仍不得非正或超过 1；
- 新增可选 `forced_exit_codes` 指令，默认空。非空指令只允许新策略使用，必须唯一、已持仓、非 `.BJ`，
  且不得仍出现在当次目标中；
- 风险退出在 `rebalance_due=false` 时仍执行，按代码稳定排序，目标数量固定为 0，可完整卖出零股尾差；
  若缺开盘、停牌或跌停则生成拒绝订单并保留持仓，后续是否重试由 M6-5C-A 的锁存状态驱动；
- 风险订单增加 `execution_reason=DELISTING_PRICE_RISK_EXIT`；`paper-v1` 订单不增加该字段。

## 4. 模块边界

新增 `paper/sell_execution.py`，负责 `PaperEngineError`、费用、订单/成交构造、卖出数量和纯卖出状态
转换；`paper/engine.py` 只保留行情状态裁决、日级编排和持仓对象归位。已有从 `paper.engine` 导入
`PaperEngineError/calculate_fees` 的调用继续兼容。

新增 `paper/risk_exit_policy.py` 保存研究专用策略类型，不修改生产 settings 或模拟账户注册。不得把
M6 专属状态机反向导入通用 paper 层；未来 runner 负责把 M6-5C-A 输出转换成窄指令。

## 5. 失败关闭与测试

合成 fixture 必须覆盖：旧黄金哈希、空指令等价、非调仓风险卖出、跌停/停牌/缺价拒绝、现金和费用、
完整零股卖出、重复/未持仓/仍在目标/.BJ 指令、`paper-v1` 越权、低于 100% 权重仅 v2 合法，以及
退市生效日仍持仓继续沿用原 fail-closed。

`paper/engine.py` 行数必须下降，新增模块各不超过 400 行，不得新增依赖、服务、网络、secret 或写
接口。专项、架构、全仓、账本、Ruff、compileall、pip check 和 diff-check 全绿。

## 6. 权限和下一步

M6-5C-B 真实目标/价格/效果读取均为 0，canonical ledger 写入 0，不运行回测、不构建真实 release、
不生成 scope、不改 Web、scheduler、模拟仓或生产。

工程 GO 后下一步只能另立 M6-5C-C 结果封存 runner/replay/auditor/release 工程：它必须先接 A1-5A
claim gate，再读取任何封存目标、价格或效果；工程完成并推送后，真实历史恢复诊断仍须用户绑定精确
scope 单独授权。

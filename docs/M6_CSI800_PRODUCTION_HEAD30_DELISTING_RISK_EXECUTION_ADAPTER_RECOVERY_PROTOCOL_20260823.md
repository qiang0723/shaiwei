# M6-5C-B-R1 生产 Head30 退市风险执行适配兼容恢复协议

- 协议 ID：`m6-csi800-production-head30-delisting-risk-execution-adapter-recovery-v1`
- 状态：`FROZEN_AFTER_COMPATIBILITY_FAILURE_BEFORE_RECOVERY_IMPLEMENTATION`
- 日期：2026-08-23（UTC+8）
- 前序：M6-5C-B 结果前冻结提交 `c6da400`

## 1. 失败事实与原协议处置

M6-5C-B 的合成功能门一度通过，但全仓回归有 23 项失败。失败均来自已关闭的 M6 release 合同对
`src/shaiwei/paper/engine.py` 旧字节身份的直接绑定；把其从 860 行抽薄会使历史 release 无法再按原
前序复核。真实目标、价格、收益和效果读取均为 0，canonical ledger 写入 0，未生成真实 release、
scope 或生产变更。

因此原协议中“旧 engine 行数必须下降、由旧 engine 导入新卖出模块”两项标记为
`NO_GO_DUE_TO_ARCHIVED_PREDECESSOR_IDENTITY`，其余已冻结的 paper-v1 金标、v2 策略语义和权限边界
不改写。本恢复协议是显式 successor，不把失败施工伪装成原协议通过。

## 2. 唯一恢复变量

- `paper/engine.py` 必须恢复并永久保持旧 SHA-256
  `44e64d1a776973b0eb5b9ba5ce6d8a7d103a7e8a20aaeb172929c7ca4b1d6b94`、860 行；
- 新增不超过 400 行的 `paper/risk_exit_engine.py` 作为 paper-v2 薄编排，只复用旧 engine 已存在的
  行情状态、公司行为、估值、买入和数据对象边界；
- 新增 `paper/sell_execution.py` 保存 v2 可独立测试的卖出原子，旧 engine 不反向导入它；
- `execute_paper_day` 对 paper-v1 且空风险指令必须原样委托旧 `execute_day`，非空指令失败关闭；
  paper-v2 才进入风险适配器；
- 旧 engine 私有符号的复用是本恢复节点的明确兼容接缝，后续不得静默改名；若要公共化，必须另立
  版本化 engine API 和所有历史 release 的迁移方案，不能再次直接改旧文件。

## 3. 不变语义与机器门

M6-5C-B 已冻结的 v2 账户、低于 100% 目标权重、非调仓日风险退出、失败保留持仓、风险原因字段及
全部越权门保持不变。paper-v1 默认调用与显式空指令必须继续得到完整两日 canonical SHA-256
`dd7b40b33b75f7e5b261bebaf64b8d1e748d6e42f62225da0b4d490f6e9d1faa`。

专项测试之外，必须重跑所有旧 M6 release/恢复合同以及全仓测试，证明旧 engine 身份与历史验证链
全部恢复。任何旧合同漂移都使 R1 失败关闭。

## 4. 权限与下一步

本节点只授权合成适配和兼容恢复；不读取真实目标、价格或效果，不写 canonical ledger，不运行真实
回测，不构建 release/scope，不改 Web、scheduler、模拟仓或生产。工程 GO 后下一步仍只能另立
M6-5C-C 结果封存 runner/replay/auditor/release 工程，并在未来任何效果 reader 之前接入 A1-5A
claim gate；真实执行须用户对精确 scope 另行授权。

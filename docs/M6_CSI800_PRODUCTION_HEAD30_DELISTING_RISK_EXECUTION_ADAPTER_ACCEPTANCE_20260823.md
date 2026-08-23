# M6-5C-B-R1 生产 Head30 退市风险执行适配工程验收

- 日期：2026-08-23（UTC+8）
- 最终裁决：`GO_EXECUTION_ADAPTER_ENGINEERING_ONLY`
- 生产授权：`none`
- 真实目标/价格/效果读取：`0 / 0 / 0`
- canonical ledger 新增：`0`

## 1. 裁决链

首次 M6-5C-B 合成功能门通过，但直接修改冻结的 `paper/engine.py` 使 23 项已关闭 M6 release 合同
无法验证其旧前序身份，因此按 `NO_GO_DUE_TO_ARCHIVED_PREDECESSOR_IDENTITY` 停止。失败未触及真实
数据、效果或账本；原协议与失败事实均保留。

恢复协议提交 `19b9882` 先行推送后，R1 只改变兼容架构：旧 engine 恢复到 860 行且 SHA-256 精确为
`44e64d1a776973b0eb5b9ba5ce6d8a7d103a7e8a20aaeb172929c7ca4b1d6b94`。历史 M6 release 合同因而
全部恢复，不以新功能覆盖旧证据。

## 2. 工程结果

- `PaperDelistingRiskPortfolio` 固定研究账户和 `paper-v2-delisting-risk-exit` 身份；
- `execute_paper_day` 对 paper-v1 的空风险指令精确委托旧 engine，非空风险指令失败关闭；
- paper-v2 允许风险退出后显式留现金，非调仓日也可按稳定代码序完整卖出锁存持仓；
- 缺价、开盘停牌或跌停只生成拒绝订单，不删除持仓、不增加现金；
- 风险卖出订单唯一增加 `execution_reason=DELISTING_PRICE_RISK_EXIT`，普通 paper-v1 Schema 不变；
- 重复、未持仓、仍在目标、`.BJ`、错误策略身份均失败关闭；退市生效日仍持仓继续使用既有
  `explicit disposal rule` 硬停，不猜测处置价。

完整两日 paper-v1 默认调用与显式空风险指令均重算为冻结 canonical SHA-256
`dd7b40b33b75f7e5b261bebaf64b8d1e748d6e42f62225da0b4d490f6e9d1faa`。

## 3. 架构与身份

| 文件 | 行数 | SHA-256 |
|---|---:|---|
| `paper/engine.py` | 860 | `44e64d1...1d6b94` |
| `paper/risk_exit_engine.py` | 362 | `634b4bb3...c9fd31` |
| `paper/sell_execution.py` | 193 | `8d076ee9...be99a` |
| `paper/risk_exit_policy.py` | 16 | `f5a7b8b7...92ead` |
| adapter contract | 157 | `8a1a13c3...ea7a9` |

新模块均低于 400 行；领域层未依赖研究 runner、Web、pipeline、Docker、Qlib、DeepSeek 或 ledger。
R1 显式登记了对旧 engine 私有计算接缝的只读复用，避免复制整套 860 行会计引擎。该接缝若未来
公共化，必须另立迁移协议，不能再改写冻结文件。

## 4. 验证

- M6-5C-B/R1 与 paper 专项：25 PASS；
- 旧 M6 关键 release/恢复合同联合门：51 PASS（包含上述专项）；
- 架构门：13 PASS；
- 全仓：1,808 PASS，17 条均为既有第三方/ pandas warning；
- 账本追加门：86 PASS；
- Ruff、compileall、pip check、diff-check：PASS；
- scheduler：原 `shaiwei:scheduler-current` 容器持续运行两周且 healthy，本节点未重启。

## 5. 权限边界与下一步

本节点没有真实回放、模型、预测、效果读取、尝试消费、release/scope、模拟仓写入、Web 或生产变更。
`GO_EXECUTION_ADAPTER_ENGINEERING_ONLY` 只说明纯合成执行适配和历史兼容性完成，不说明该恢复变量
有效，也不授权生产。

下一合法节点是 M6-5C-C：结果封存地建设 runner、内部 replay、独立 auditor 和 release scope；必须
在任何真实 effect reader 前接入 A1-5A claim gate，并继续保持结果盲。工程完成且推送后，真实历史
诊断仍须用户绑定精确 scope 单独授权。

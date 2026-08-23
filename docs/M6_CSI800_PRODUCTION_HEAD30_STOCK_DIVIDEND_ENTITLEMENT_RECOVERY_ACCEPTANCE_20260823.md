# M6-5C-C-R3 红股权益恢复工程验收

- 日期：2026-08-23（UTC+8）
- 裁决：`GO_ENGINEERING_ONLY`
- 策略效果：`NOT_EVALUATED`
- 生产授权：`none`

## 1. 交付边界

本节点只修复 paper-v2 的一个公司行为状态：证券在股权登记日取得红股权益后，即使原持仓在红股
上市日前已经卖空，权益仍然有效。上市日先建立数量为零、总成本基础为 `0.00` 的 detached
position，再复用冻结 paper-v1 的到期动作加入精确整数股。

`cost_basis` 继续表示模拟引擎累计现金买入支出，不是税法成本。新入口不增加现金、费用、订单或
成交，不改变公司行为事件结构，也不改变已有持仓、现金股利、分数股、应收权益估值、退市风险
触发和退出参数。

## 2. 兼容架构

初次本地实现曾直接替换 `risk_exit_engine.py` 的到期动作调用，专项功能通过，但全量测试的 3 个
历史 release 身份门正确失败。该中间实现未提交、未发布、未读取真实结果。

终版改为独立入口 `execute_entitlement_recovery_day`：先补齐 detached position，再调用原封不动的
paper-v2 风险引擎。由此同时保留：

- `paper/engine.py`：860 行，SHA-256
  `44e64d1a776973b0eb5b9ba5ce6d8a7d103a7e8a20aaeb172929c7ca4b1d6b94`；
- `paper/risk_exit_engine.py`：SHA-256
  `634b4bb32428f3646e2805ab745dfb600544f0802517c3d8a5df767b53c9fd31`；
- paper-v1 两日金标：
  `dd7b40b33b75f7e5b261bebaf64b8d1e748d6e42f62225da0b4d490f6e9d1faa`。

新增模块均小于 400 行：适配器 89 行，冻结合同 139 行。终版文件身份：

- 协议：`f40047b9bb0ddc2512efba248b5dd66d272bf97cd7456f7c29e8aaaad6fd6462`；
- 适配器：`0500e097f490a5499952e0de4f732913b8a8a6fbf3612639b3c775666214055f`；
- 合同：`a43591d5b375c4bccd3eef1363ed802a2f9d974f424dbf62524f4a4288b2af52`；
- 测试：`e4be88ae4bf8022f5d6c05f2f4925378104143a5a6ef6e0daeb0daaad8fce377`。

## 3. 验证

- 红股专项、旧退市执行与历史 release 联合：42 PASS；
- 架构宪法：13 PASS；
- 全仓：1,826 PASS，17 条既有第三方/数据类型 warning；
- Ruff、compileall、pip check、diff-check：PASS；
- 卖空后到账并可卖、已有仓位总成本不变、重复调用幂等、分数股失败不留幽灵仓、纯现金不造仓、
  同代码多笔权益确定性、到账后估值恒等式均有 synthetic 覆盖。

未读取真实目标、行情或效果，未写 canonical ledger，未生成 release/scope，未调用外网，未改模型、
预测、Web、scheduler、模拟仓或生产。自然跑批产生的工作树账本未被纳入本节点提交。

## 4. 结论与下一门

R3 工程门通过，但这不代表退市风险策略有效，也不授权真实回放。若继续，必须另立结果盲 release：
同一尝试家族 `m6_head30_500k_delisting_risk_overlay_v1` 使用 ordinal 2、历史尝试数 1，并让 runner
显式调用本节点的新入口；新镜像、新 scope 和用户精确授权缺一不可。R2 scope 永久不得重跑。

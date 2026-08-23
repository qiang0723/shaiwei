# M6-5C-C-R4 successor release 工程验收

- 日期：2026-08-23（UTC+8）
- 裁决：`GO_SUCCESSOR_BUILD_READY_NOT_EXECUTION_APPROVAL`
- 策略效果：`NOT_EVALUATED`
- 生产授权：`none`

## 实现

新增独立组件 `m6-head30-delisting-entitlement-release`，旧 R2 Dockerfile、Compose、scope、镜像和
runner 均未改动。旧模拟器只增加默认仍为 `execute_paper_day` 的 keyword-only executor；successor
显式注入 `execute_entitlement_recovery_day`。旧默认调用与显式旧入口逐内容相同。

successor 合同绑定 R3 协议/适配器/验收、R2 失败 scope 和 experiment、ordinal 2、parent
`6797875cf3c0`、运行前 1 次/claim 后 2 次、当前组件注册表、源码 bundle、镜像标签与 scope 自哈希。
runner 继续 claim-first；auditor 只读 artifact，并只把冻结尝试计数从默认 0→1 参数化为 1→2。

新增 6 个职责模块共 1,126 行，最大合同模块 323 行，全部不超过 400 行。没有复制风险、费用、容量、
效果门或独立统计实现。

## synthetic 证据

fixture 在 6 个窗口中构造同一合法链：先持仓并在登记日取得红股权益，随后风险退出清仓，上市日以
detached position 到账，下一交易日再次按锁存风险退出。每窗都要求两次 `held→absent` 和一次
`absent→held`，防止只验证最初买卖而误报成功。

同时验证 ordinal 2、parent、claim/receipt 先于 reader、同 scope 拒绝重开、first/replay 相等、独立
重建相等、真实目标/价格/效果读取 0、canonical ledger 写入 0。

## 验证

- successor、R3、旧 R2、claim 注册表和构建注册表联合：54 PASS；
- 架构宪法：13 PASS；
- 全仓：1,834 PASS，17 条既有 warning；
- Ruff、compileall、pip check、Compose config、diff-check：PASS；
- 当前构建资产 97/97 恰好登记一次，effect runner 10/10 自发现且逐 SHA 绑定。

本文件只表示实现可构建。尚未构建 successor 镜像、运行 daemon fixture 或生成 release scope；真实
approval、claim、效果和 audit 均不存在。下一步必须先推送本实现，再各执行一次构建与 daemon fixture。

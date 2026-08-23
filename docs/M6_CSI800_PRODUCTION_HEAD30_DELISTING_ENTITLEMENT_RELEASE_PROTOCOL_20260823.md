# M6-5C-C-R4 红股权益 successor release 协议

- 协议 ID：`m6-csi800-production-head30-delisting-entitlement-release-v1`
- 状态：`FROZEN_BEFORE_RELEASE_IMPLEMENTATION`
- 日期：2026-08-23（UTC+8）
- 策略效果：`NOT_EVALUATED`
- 生产授权：`none`

## 1. 结果目标与单变量

R2 在 claim 后因合法红股权益缺少无现持仓到账语义而失败，已消费本研究家族 ordinal 1。R3 已仅用
synthetic 证明新的 `execute_entitlement_recovery_day` 能在保留 paper-v1 和封存风险引擎字节身份的
前提下完成 detached 红股到账。

R4 只把这个已验收入口接入一次新的 claim-first release。生产 Head30 目标、六窗口、调仓、50 万元
本金、连续 10 个有效收盘严格低于 1 元的锁存退出、不补位留现金、开盘执行、费用、容量、效果门和
独立统计全部不变；不拟合模型、不生成预测、不搜索参数。

## 2. 尝试与谱系

- 家族：`m6_head30_500k_delisting_risk_overlay_v1`；
- 新尝试：ordinal 2，父 experiment `6797875cf3c0`，运行前 1 次，claim 后 2 次；
- runner 必须先 durable append canonical `ledger/experiments.csv`，再 durable 写 receipt，之后才可读取
  sealed target、raw price 或任何效果；
- claim 后任何错误都消费 ordinal 2 并永久关闭该 scope，同 scope 不得重跑；
- R2 scope `94a45605...9829` 永久关闭，不得通过本节点重开或覆盖其失败证据。

## 3. release 架构

建立独立组件 `m6-head30-delisting-entitlement-release`，不修改封存 R2 Dockerfile、Compose、镜像或
scope。当前构建注册表登记 successor 的新资产；旧 R2 按 ADR-002 继续使用自身历史注册表身份。

领域模拟应在旧 `delisting_release_simulation` 增加默认仍为旧入口的窄 executor 注入点；旧调用不传
executor 时行为和结果必须不变。successor runner 显式传入 R3 新入口。禁止复制整份模拟器形成第二套
风险、费用或指标计算。

runner 断网、只读根、非 root，只精确挂载 R2/raw 只读输入和 claim/effect/canonical ledger 写路径；
auditor 不挂 raw 或 R2，只读 effect、receipt、ledger并写独立 audit。不得挂 `.env`、Docker socket、
整个项目、Web、模拟仓或生产目录。

## 4. 工程和 fixture 门

新合同必须绑定 R3 协议/适配器/验收、R2 失败 scope/experiment、输入身份、ordinal 2、父尝试、当前
构建注册表、源码 bundle、镜像内容 ID 和 scope 自哈希。

断网 synthetic fixture 必须真实穿过 successor CLI，并证明：红股登记后卖空、上市日 detached 到账、
first/replay 逐内容一致、独立重建一致、claim 先于 reader、parent/ordinal/累计次数正确、同 scope
拒绝重开，以及 fixture 不写 canonical ledger、不读取真实目标/价格/效果。

## 5. 当前权限和停止点

本节点只允许协议、实现、测试、一次新镜像构建、一次 daemon fixture 和 metadata-only scope。真实
目标、行情、效果、canonical ledger、approval、runner、auditor和生产授权均为 0。

release scope 推送后必须停止。真实执行只有用户逐字绑定最终 scope SHA 与动作
`M6_HEAD30_500K_DELISTING_ENTITLEMENT_RECOVERY_ONCE_WITH_CLAIM_REPLAY_AND_INDEPENDENT_AUDIT`
才可进行。

# M6-5C-C 生产 Head30 退市风险恢复结果盲 release 协议

- 协议 ID：`m6-csi800-production-head30-delisting-risk-release-v1`
- 状态：`FROZEN_BEFORE_RELEASE_IMPLEMENTATION`
- 日期：2026-08-23（UTC+8）
- 研究权限：`POST_HOC_METHOD_RECOVERY_DIAGNOSTIC_ONLY`
- 生产授权：`none`

## 1. 唯一问题与单变量

M6-5B-R1 因 `002505.SZ` 在退市生效日仍持仓且无合法处置规则而
`BLOCKED_BY_UNMODELED_DELISTING`，未形成完整 50 万元效果。M6-5C-A/B-R1 已结果封存地建立唯一
新变量：连续 10 个有效交易收盘严格低于 1 元后，未持有目标禁买，已持仓目标锁存退出，卖出失败
继续持有并在后续交易日重试；剔除权重留现金，不补位、不重分配、不猜退市价。

本节点只建设该变量的 runner、内部 replay、独立 auditor、不可变镜像及 release scope。生产
Head30 目标、排序、调仓日、500,000 元初始资金、paper-v1 费用/整手/公司行为/开盘成交、20 日成交额
容量和原 M6-5B 六窗口效果门全部不变。不拟合模型、不生成预测、不搜索参数、不增加第三臂。

## 2. PIT 风险时钟

- 每个执行日的风险 `as_of` 必须是该执行日前一个官方开市日；
- 风险输入只允许 `trade_date <= as_of` 的日收盘，执行日开盘、收盘、成交量和未来记录不得参与触发；
- 连续 10 个“有效交易收盘”按该证券实际存在且价格有效的收盘序列计数，停牌无收盘不伪造观察；
- 每窗口状态独立重置，但首日允许使用 scope 内已冻结的向前 90 日原始批次形成合法历史；
- runner 必须在结果中保存去重后的风险观察、每日 `as_of`、执行前持仓、目标、状态裁决、风险订单与
  执行后持仓，使无 raw/R2 挂载的 auditor 可以独立重建；`.BJ`、未来观察、重复键或时钟错位均阻断。

## 3. 执行和结果合同

- 唯一账户：`m6_head30_delisting_risk`；唯一入口：`paper.risk_exit_engine.execute_paper_day`；
- 原目标每只权重仍为 `1/30`，被风险层剔除的权重成为现金；其余目标不重新归一；
- 风险退出可在非调仓日执行，卖出仍走原开盘、停牌、涨跌停、费用与零股尾差规则；
- first pass 与 replay 必须逐内容相同；独立 auditor 不导入主 simulation、主指标 evaluator 或
  `evaluate_risk_overlay`，数值容差固定 `1e-12`；
- 原 M6-5B `release_metrics.evaluate` 与独立统计门原样复用。完整运行只能得到：
  `RECOVERY_DIAGNOSTIC_PASSES_FROZEN_CAPITAL_GATES`、
  `RECOVERY_DIAGNOSTIC_FAILS_FROZEN_CAPITAL_GATES` 或 `BLOCKED`；三者均
  `NOT_FOR_PRODUCTION_VERDICT`、生产授权 `none`。

## 4. claim-first 尝试合同

新尝试家族与原 M6-5B 两次已消费尝试分离：

- `attempt_family=m6_head30_500k_delisting_risk_overlay_v1`；
- future exact scope 的 `attempt_ordinal=1`，运行前家族次数 0，claim 后为 1；
- claim spec 固定候选源为封存 M6 R2 Head30、engine 为
  `paper-v2-delisting-risk-exit`、公式为 `10 valid closes < 1 CNY; latch exit; no replacement`；
- runner 在读取 sealed target、raw price 或任何效果前，必须依次完成 canonical
  `ledger/experiments.csv` append+fsync 和内容寻址 receipt+fsync；
- claim/receipt 后任何错误均消费该次尝试并永久关闭 scope；同 scope 不得重跑；
- report 和 audit 必须绑定 receipt、唯一 ledger row、scope、镜像和代码身份，不回写 claim 行。

## 5. release 与容器

- 新组件只使用独立 Dockerfile/Compose，登记进中央 build-asset registry；不得修改全局
  `CONTROLLED_FILES`、基础 Dockerfile 或 scheduler 镜像；
- runner：断网、只读根、非 root；R2/raw 只读，effect/claim receipt/canonical experiment ledger
  为精确最小写挂载；不得挂 `.env`、Docker socket、整个项目或生产目录；
- auditor：断网、只读 effect、只读 claim receipt/ledger、独立 audit 根可写；不得挂 raw、R2、模型、
  预测或生产目录；
- 合成 daemon fixture 必须用临时账本与临时输入穿过真实 CLI，证明 claim 先于 reader、first/replay、
  独立重建、拒绝重试和失败后尝试保守消费；不得触碰 canonical ledger。

## 6. 前序身份

- M6-5C-A method config：`e38b5a59...fb2df4b`；方法模块：`cce48800...7fa1de`；
- M6-5C-B-R1 adapter recovery config：`bb6a75ab...34221a`；验收：`3256493f...e7216`；
- risk engine / policy / sell atom：`634b4bb3...c9fd31` / `f5a7b8b7...92ead` /
  `8d076ee9...be99a`；
- A1-5A claim module：`f437a576...47399`；验收：`04f9bf76...c44d6`；
- M6-5B-R1失败机器证据：`5cc68507...118f9`；原 scope：`c73b4afb...c74757`，永久关闭。

## 7. 当前权限与停止点

协议与工程期真实目标/价格/效果读取均为 0，canonical ledger 写入 0；只允许读取跟踪配置和输入
manifest 的元数据身份，不允许读取 raw Parquet、sealed target 内容或旧 effect 内容。

实现、测试、镜像合成 fixture 和 metadata-only scope 完成并推送后必须停止。真实运行必须由用户
逐字绑定最终 scope SHA 与动作
`M6_HEAD30_500K_DELISTING_RISK_RECOVERY_ONCE_WITH_CLAIM_REPLAY_AND_INDEPENDENT_AUDIT`
另行授权；未授权不得创建 approval、claim 尝试或读取真实语义。

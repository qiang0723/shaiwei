# M6-5C-C-R4 红股权益恢复真实执行验收

- 日期：2026-08-24（UTC+8）
- scope：`117e69a8c29f48d2434c84363d4766d48af4f2010aeddae1610128fb9614c51d`
- 裁决：`RECOVERY_DIAGNOSTIC_FAILS_FROZEN_CAPITAL_GATES`
- 策略有效性权限：`NOT_FOR_PRODUCTION_VERDICT`
- 生产授权：`none`

## 唯一执行与尝试谱系

用户逐字绑定 scope 与动作后，runner 在 `network_mode=none` 下只启动一次。它先向 canonical
`ledger/experiments.csv` 追加 ordinal 2，再 fsync claim receipt，之后才读取封存输入：

- experiment：`362b5b223108`，parent：`6797875cf3c0`；
- 家族：`m6_head30_500k_delisting_risk_overlay_v1`，累计尝试 2；
- ledger row SHA-256：`1a71a40ad32fe4c0404b5a820b9dc31d46a281f983076add8907bde366c6979c`；
- receipt 内部 SHA-256：`c24785f381d945be3705160b3a2c45b56b4b6112f7cc347a0a53784a7d10c65b`；
- claim 文件 SHA-256：`de36991cedd50111781c03e28180b2374082e14c163baf8abe6fa685bd16ea67`；
- approval SHA-256：`82adef1efe3f877ac688a8ae95a3d6d07271d8076081e763be7bc9a795b3289e`。

first pass 与 replay 文件 SHA-256 均为
`4e91436fba1bda15445f01898461baa841a7d5d142019d32b87ca746d8c9d2ef`，逐字节一致。report SHA-256
为 `10086f6fbd949c505611c0464c28c9a22dad606da3ba6fcaebc20f704f6e9fab`，result SHA-256 为
`0cb67d20e0e9b20a79fd88bc9ee97fac8562c3c21cef54f236292dc9f1c2aca9`。同 scope 永久关闭，不得重跑。

## 冻结门结果

六窗口、会计、非负现金、整数股、普通容量、持仓数量中位数/最小值、现金中位数、目标误差中位数、
最小手数拒绝比例、正窗口数、1.5 倍成本、可执行/理想 NAV 比和退市风险卖出容量均 PASS。退市风险
退出产生 1 笔订单并成交 1 笔，容量违规为 0；R2 暴露的无现持仓红股到账阻断已消除。

两个冻结的极值门 FAIL：

- 最大调仓后现金比例 `42.9416%`，高于冻结上限 `35%`；
- 最大目标 L1 偏差 `85.9510%`，高于冻结上限 `50%`。

其余重要诊断为：持仓中位数 29、最少 21，现金比例中位数 `10.5283%`，目标 L1 偏差中位数
`21.4676%`，最小手数拒绝比例 `5.7407%`；基础成本正超额窗口 5/6，六窗合并 1.5 倍成本净超额
`45.2679%`，可执行/理想 pooled NAV 比 `1.07798`。W1 基础净超额为 `-13.5090%`，W2—W6 为正。

这些数字说明收益保留门大多通过，但少数再平衡时点的现金滞留与目标偏离过大，因此 50 万元资本
可行性按预冻结规则必须判 FAIL。不得用中位数良好或收益为正覆盖极值门，也不得事后放宽阈值。

## 独立审计与边界

auditor 只启动一次，只读 effect、claim 和 ledger，不挂 raw 或 R2。14 项检查全部 PASS，包括文件集、
claim/尝试身份、first/replay 物理与语义一致、两遍独立重建、结果/report/runtime/目标身份以及
post-hoc 非生产权限。audit SHA-256 为
`14b35de8281aca5b9a8dfa5bdc9607456a71fb90d5902242acf4a7a27eaf4686`，独立 result SHA 与主结果完全一致。

没有外网、模型拟合、新预测、前瞻、模拟仓、Web、scheduler 或生产变更。scheduler 仍为原容器
`183b8c6c5edd`、镜像 `shaiwei:scheduler-current` 且 healthy，未重启。

## 结论与后继边界

本次闭合的是已知执行语义缺口，不是新的盲策略发现。红股权益恢复工程有效，但该退市风险 overlay 在
当前冻结 50 万元资本门下仍为 `CAPITAL_INFEASIBLE`，不授权生产，也不推翻此前生产 Head30 的独立
研究尺度裁决。M6-5C-C 到此关闭：不调门槛、不追加同家族变体、不重跑同 scope。若未来研究现金滞留
或目标偏差机制，必须作为新的结果已知研究问题另立协议和尝试家族，不能回写本次裁决。

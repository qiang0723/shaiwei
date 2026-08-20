# M6-5B-R1 50万元历史回放入口恢复执行失败留痕

## 权威状态

R1 scope `c73b4afb452c55dce0149ef1fd8770c28538be03ec16de6c6de00881f3c74757` 已按用户精确
授权调用唯一 runner。runner 开始真实读取并消费 1 个新账户可行性尝试，但首遍在估值一个已经到达
退市生效日、仍未卖出的 `002505.SZ` 持仓时失败关闭：

`PaperEngineError: delisted position requires an explicit disposal rule: 002505.SZ`

本 scope 永久关闭，不得重跑。首遍未完成，内部 replay 未开始，独立 auditor 未调用；因此没有
完整效果报告，策略有效性仍为 `NOT_EVALUATED`，生产授权为 `none`。本次消费 1 次新尝试，家族累计
2 次。没有拟合模型、生成预测、写实验账本、写模拟仓、访问外网、修改 Web、重启 scheduler 或改变
生产。

## 为什么这是方法边界，不是普通代码缺陷

- 封存 Head30 目标显示，`002505.SZ` 在 W6 的 2024-06-20 调仓中排名第1；从 2024-07-04 起已
  不再属于目标。
- 哈希核验后的日线只到 2024-07-02，此后到退市生效日没有可成交记录；`stock_basic` 的退市生效日
  为 2024-08-30。
- paper-v1 要求缺开盘或不可成交的卖单拒绝，且持仓进入退市日而没有明确处置证据时必须失败；它
  明确禁止擅自按最后价、零价或假设成交价结算。
- 因此引擎的 fail closed 行为正确。补一个默认价格继续计算会改变经济含义，并可能把真实无法退出
  的风险伪装成普通滑点，不得作为 R1 的入口修复。

“失败日为 2024-08-30”是根据引擎唯一退市守卫、官方字段和日序列作出的诊断推断；原 failure
artifact 只记录证券和错误，不伪称它直接记录了该日期。

## 不可变证据

- approval SHA-256：`ffa8bb1d6cc59351d52e6017fd800b0319c425a18c1192e058f3129adec963ee`
- authorization SHA-256：`0479cbf65388c91393f2acb4b0beaed2535ea68f0e3e031b3ab614b46a223b10`
- effect-started SHA-256：`a95b5ac326918dbe57170a48c5fad71875f0f120af3bb147b7624719bdc3ff51`
- failure SHA-256：`0ad522dff8d0bd0864208363f7bc5ac248c00d5ab13085547bc8bb1288499e40`
- effect 根恰好3个失败留痕文件，audit 根0文件。
- R2五文件树在失败后仍为1,191,570 bytes，SHA-256
  `d3d84d104968bf01f88312bd665060f2e57727145e4064697b4753bd6fc545c1`。
- 机器留痕：`config/m6_csi800_production_head30_500k_entrypoint_recovery_execution_failure_v1.json`。
  SHA-256为`5cc68507e18ec75b6bcb7194b00e7241337d5751dcf3423d3713880b957118f9`。
- scheduler 仍为原容器 `183b8c6c5edd`，状态 healthy，未重启。

## 裁决与下一合法节点

本次权威裁决为 `BLOCKED_BY_UNMODELED_DELISTING`，不是 `CAPITAL_INFEASIBLE`，也不是策略收益
`REJECT`；完整50万元效果尚未形成。

不再追加 R2 技术重跑。若继续，应另立 M6-5C 方法节点，先在不读取额外效果的前提下裁定并验证：

1. 是否存在当时可知、可审计的风险警示或退市处置证据；
2. 若采用事前风险退出/禁入，它应作为新的策略执行变量和新尝试家族，不能回写本次单变量协议；
3. 若采用退市后现金或股份处置，必须有明确权威证据与时间口径，禁止最后价或零价猜测；
4. 若上述证据无法闭合，则 M6-5B 保持 BLOCKED，不能为了拿到回测结果而绕过 paper-v1。

任何新真实回放仍须新协议、新镜像、新输出根、新 scope 与用户再次精确授权。

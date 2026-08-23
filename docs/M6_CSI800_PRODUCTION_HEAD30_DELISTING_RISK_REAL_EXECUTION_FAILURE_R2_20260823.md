# M6-5C-C-R2 真实诊断失败闭环

- 日期：2026-08-23（UTC+8）
- 裁决：`BLOCKED_AFTER_CLAIM_BY_UNMODELED_STOCK_DIVIDEND_ENTITLEMENT_WITHOUT_POSITION`
- 策略有效性：`NOT_EVALUATED`
- 生产授权：`none`

## 唯一运行事实

用户精确批准 scope `94a4560553cd67899988276f336cc103de052b2088a2d4adbb63e5ff2d2e9829`
后，R2 runner 在 `network_mode=none` 下唯一启动一次。它先向 canonical
`ledger/experiments.csv` 追加 experiment `6797875cf3c0`，随后 fsync claim receipt，才进入封存目标
与行情读取。claim/receipt 独立核验 PASS：

- ledger row SHA-256：`b73c33ae39f15fc99858c4620043d05d27147c6af714aae79b921ba1343d4518`；
- receipt 内部 SHA-256：`cb555a8ccde9a4bcc875207bbd99bb142be3e5cc98863174f3020bbe4fc7f510`；
- claim 文件 SHA-256：`d25853c9abd0d8cdea16b3bc8dded57d2121ae9d4acb4b40239d9b7b85ac5c21`。

该 claim 保守消费 1 次家族尝试；相同 scope 永久不得重跑。

## 阻断点

首遍历史回放在 corporate-action 应用阶段抛出
`PaperEngineError: stock dividend entitlement has no position`。引擎已经在股权登记日按当时持仓捕获
红股权益，但当红股上市日到来时，原股票持仓已被卖空；现有 paper-v2 仍复用 paper-v1 的到期动作，
它只允许把红股数量加到一个仍存在的持仓，未定义“权益仍有效但当前持仓为零”时的新持仓、成本基础
和后续处置语义。

这是合法市场状态所暴露的执行语义缺口。忽略红股会少记资产，直接以零成本或任意成本新建持仓会
扭曲收益，因此按 fail-closed 停止是正确行为。该问题与本次退市风险触发规则是否有效无关，不能用
本次失败推断策略好坏。

## 产物与权限边界

- effect 目录只有 `failure.json`，SHA-256
  `b06bd93eb1bedf5da91fb36c30dd16c77585bbf9affcd0616e25862df8df7fc7`；
- first pass 未完成，内部 replay 未开始，正式 report 不存在；
- auditor 未启动，audit 产物为 0；
- 没有模型拟合、新预测、外网、前瞻、模拟仓、Web、scheduler 或生产变更；
- scheduler 保持原 `shaiwei:scheduler-current` 容器 healthy。

## 后继边界

本 scope 到此永久关闭，不得补跑 auditor 或再次调用 runner。若继续，只能另立结果盲恢复协议，先在
paper-v2 独立适配层明确并测试：登记日权益随卖出继续保留、红股上市日建立可审计持仓、数量取整、
成本基础、与现金股利并存、退市风险退出及不补位的交互；paper-v1 冻结实现和历史身份不得修改。

后继真实效果读取至少是同一尝试家族 ordinal 2，`family_attempts_before_run=1`，仍须新的镜像、scope
和用户精确授权。不得因本次阻断修改收益门槛或退市风险参数。

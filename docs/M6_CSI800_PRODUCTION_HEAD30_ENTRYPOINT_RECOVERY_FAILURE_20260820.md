# M6-4B-R1 生产 Head30 真实效果入口恢复失败留痕

## 权威状态

R1 scope `ea648bda49b185cb698f11f78f01d8ce16df217e50c4d12542dfac4318783d2c` 已于
2026-08-20 15:11:48（UTC+8）调用唯一 runner。容器成功创建并开始读取真实处理臂效果；运行在
2026-08-20 15:13:40 失败关闭。因此本 scope 的 1 个组合转换尝试已经消费，永久不得重跑。

- `treatment_effect_started.json` 明确记录 `portfolio_attempts_consumed=1`、
  `same_release_retry_authorized=false`。
- 首遍在 2024-07-04 处理 `SZ002505` 时，Qlib 的成交价接口返回空值；生产 Head30 全目标适配器
  在到达既有持仓价格回退逻辑前执行 `float(None)`，触发 `TypeError`。
- 这是执行/估值缺失值合同不完整，不是 Head30 策略效果结论。当前无完整首遍、无 replay、无
  正式 effect report，独立 auditor 未启动；`strategy_effective=NOT_EVALUATED`。
- 不得在已读效果之后自行选择或改变收盘价、前收盘价、停牌冻结价、跳过证券或剔除交易日。必须
  另立 R2 结果隔离协议，先冻结“空成交价应返回空并进入原有持仓价格回退；回退价仍为空或非有限
  时失败关闭”的语义和对抗测试，形成新输出根和新 scope，再由用户精确批准。
- scheduler 保持原容器 healthy，未重启；未修改生产、模拟仓、Web、模型、预测或实验账本。

## 不可变证据

- authorization SHA-256：`e6f445e76b53f122aa7bf50c790ff4fd4ecb3521af5a9f3fd5a48ff2f531c96f`
- treatment-started SHA-256：`1423f719df1159c499997927801fc86293251a8f485e8a4c18dc623dfcd0672b`
- failure SHA-256：`20554456f2bb114c200a1df9ea2bd33a469bab69de3a72af1d714b20a71eea79`
- 机器留痕：`config/m6_csi800_production_head30_entrypoint_recovery_failure_v1.json`

## 下一合法节点

只允许先做零效果读取的 M6-4B-R2 方法与工程恢复：冻结双空价格的业务语义、失败关闭边界、原 R1
证据身份、新输出根、一次新尝试与独立审计。R1 runner 和 auditor 均不得再次调用；R2 真实运行须
新的不可变镜像、release scope SHA 和用户精确授权。

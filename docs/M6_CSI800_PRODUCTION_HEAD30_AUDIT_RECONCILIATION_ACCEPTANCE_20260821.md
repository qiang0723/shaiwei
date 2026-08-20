# M6 生产 Head30 审查校准与账本对账验收

## 裁决

本节点 `PASS`。C-1 的权威状态继续为 `VALIDATED_RESEARCH_SCALE`，生产授权继续为 `none`；M6-5B
仍暂停，未启动 M6-5C，也未读取新效果、重跑模型/预测/回测或修改模拟仓、Web、scheduler。

本次解决了两类审查问题：

1. 用封存的精确处理臂与合法控制臂纠正比较数字和风险措辞；
2. 将 R1、R2 两次真实效果读取各消费的一次 `m6_portfolio_converter` 尝试补入原协议指定的
   `ledger/experiments.csv`，并建立确定性、幂等、失败关闭的机器入口。

## C-1 校准

处理臂 1 / 1.5 / 2 倍成本六窗口复合净超额为 41.6224% / 25.0290% / 10.3673%，基础成本正窗口
5/6，冻结 G0 继续通过。合法 `Top30/n_drop=3` 控制臂同口径为 68.7790% / 65.9315% / 63.1317%。
处理臂平均窗口累计换手 38.1256、累计记录成本 4.1461%，控制臂对应 5.6070、0.5673%；W4 处理臂
最大回撤 21.5427%。

因此准确结论是“处理臂绝对门通过，但相对控制臂明显变弱且换手/成本显著增加”。市场状态差异暂列
研究假设，不再把“涨市跑输、跌市跑赢”写成已验证事实。详见
`docs/M6_CSI800_PRODUCTION_HEAD30_AUDIT_ADDENDUM_20260821.md`。

## 两次尝试的历史对账

原 R1/R2 release 均显式设置 `experiment_ledger_write_authorized=false` 且未挂载生产账本，所以缺口
不是 runner 擅自漏写后可静默补丁，而是权限设计与原协议“一次效果读取对应一次 canonical ledger
尝试”的冲突。本次另立结果已知的历史对账协议：

- R1 `ea648bda...83d2c`：真实效果已读，空成交价后失败，消费第 1 次；补记 ID `e97f4e185e33`。
- R2 `9b78ef69...f9b4a`：runner/replay 完成，后续 R7 独立审计闭合，消费第 2 次；补记 ID
  `3ce8e73c0733`，父记录指向 R1。
- 两行只登记尝试与证据身份，均 `admitted=false`，明确“不是因子准入实验”；R1 的失败不等于策略
  REJECT，R2 才承接后续权威 `VALIDATED_RESEARCH_SCALE`。
- 目标两行 canonical SHA-256 为
  `939c9c1ef0a4df77bb242a0aff4018d20c2afcf6420ff9b798af0b0c49434d79`。
- 对账入口连续执行两次，第二次新增 0 行；相同 ID 不同内容会失败关闭。

协议与机器收据：

- `config/m6_csi800_production_head30_attempt_ledger_reconciliation_v1.yaml`
- `config/m6_csi800_production_head30_attempt_ledger_reconciliation_receipt_v1.json`

## 门禁与回归

- 新增窄账本接口 `append_reconciled_experiment`：必须显式提供确定性 ID 和时间，只允许幂等追加，
  同 ID 不同内容失败关闭，并拒绝敏感参数字段。
- 新增专项测试覆盖：两个效果读取与两个账本行一一对应、来源哈希漂移失败、重复对账零新增、目标行
  被篡改失败、同 ID 内容冲突失败。
- 为 paper-v1 增加退市生效日持仓且无处置证据的精确回归测试，锁定现有 fail-closed 行为；没有设计
  或实现 paper-v2 退市处置规则。
- R2 report 与 first-pass bundle 在对账前后哈希仍为
  `79c67444...24d3a`、`389c1770...92ec2`，历史结果未改。
- 最终验证：专项 14 PASS、架构门 13 PASS、全仓 1,633 PASS；Ruff、`git diff --check`、脱敏检查
  PASS。仅保留 1 条既有 Starlette 弃用提示和 16 条既有 pandas FutureWarning。
- 生产 scheduler 仍为原 `shaiwei:scheduler-current` 容器，运行两周且 `healthy`；本次未重启或改镜像。

## 后续边界

M6-5B/M6-5C 继续暂停。若未来恢复，先单独冻结当时可知的退市风险退出或权威实际处置证据，再决定
50 万元历史可行性；不得把本次账本补记当成继续运行授权。任何新的真实效果入口在执行前都必须把
“效果读取成功消费尝试”和“canonical ledger 可写、可验、失败关闭”作为同一个发布门，不能再依赖
事后人工补账。

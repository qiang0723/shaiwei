# M6-4B-R2 生产 Head30 空成交价恢复独立审计失败留痕

## 权威状态

R2 scope `9b78ef69ec11c180bbc1adc46b95c3f8023bf729480d4fd647e2eab1085f9b4a` 已于
2026-08-20 16:41:34（UTC+8）调用唯一 runner。runner 完成首遍和内部重放，随后于 16:45:33
调用唯一独立 auditor；auditor 因 `reported_result_identity` 失败关闭。因此本 scope 已永久关闭，
不得重跑 runner 或 auditor。

- R2 首次处理效果读取已消费 1 个新组合转换尝试；连同 R1，家族累计消费 2 次。模型拟合和新预测
  均为 0。
- 空成交价恢复按冻结语义工作，R1 的 `SZ002505` 空值路径被安全越过。首遍与重放 bundle 的物理
  SHA-256 均为 `389c1770...92ec2`，内部重放一致。
- 主计算报告和 bundle 内结果的 SHA-256 均为 `42a60f59...de7a1`；主计算与独立重建均给出
  `VALIDATED_RESEARCH_SCALE`。G0 诊断为六窗中 5 个基础成本净超额为正，合并 1.5 倍成本净超额
  25.03%。这些数值是已封存研究证据，但在独立审计恢复通过前不是权威策略有效性结论。
- 独立重建与主结果通过冻结的 `rel_tol=abs_tol=1e-12` 语义等价检查；50 个浮点值不逐字节相等，
  最大绝对差 `3.725290298461914e-09`，主要来自独立求和/复利重算的浮点累积顺序。独立结果哈希
  `daac6d2a...5abf` 因而不等于主结果哈希。
- 冻结 auditor 同时要求“独立重建语义等价”和“独立重建 canonical SHA 与主结果完全一致”。后者
  把独立数值实现的机器级浮点差异误当成结果身份漂移，是审计合同缺陷；不得通过修改封存结果、
  放宽 G0、改变收益或重跑回测来修复。
- `effect-r2-audit` 保持 0 文件，策略状态为
  `NOT_AUTHORIZED_PENDING_INDEPENDENT_AUDIT_RECOVERY`，生产授权仍为 `none`。scheduler 保持原容器
  healthy，未重启。

## 不可变证据

- approval SHA-256：`0fe053c832897632d8cd8fbbb165252580b4134a44b62e27e9f416ebe4f47336`
- authorization SHA-256：`6899740f95422b49166a35caa7ec7eeca780a4a067b06876e50c6bbaa9a63bb9`
- treatment-started SHA-256：`a83d15a727fcb3d29ff1230bcba7150576af0cb83cc5de3cd24d28e368440916`
- first/replay bundle SHA-256：`389c1770811a77d043b0ab2914740ac1e9c7a8c7f2e6694641a8ed28b8492ec2`
- report SHA-256：`79c674444dce99c8dd4e51933feac8f55360ea2c87c16950c2ef4c422c224d3a`
- 机器留痕：`config/m6_csi800_production_head30_price_recovery_audit_failure_v1.json`

## 下一合法节点

只能另立 auditor-only 恢复协议：只读上述五份封存 R2 产物，不挂载 Qlib，不调用 runner，不训练、
不预测、不回测且新增组合尝试为 0。恢复审计必须分别验证：报告结果哈希精确绑定主 bundle；独立
重建在冻结容差内等价；双方 decision 精确一致。不得要求两个独立浮点实现产生相同 canonical
SHA，也不得改写原报告或原 bundle。新恢复 scope 仍须单独冻结、构建和用户精确批准。

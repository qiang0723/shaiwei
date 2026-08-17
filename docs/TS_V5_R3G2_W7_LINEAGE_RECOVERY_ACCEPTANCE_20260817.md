# TS-v5 R3G-2 W7分数谱系入口恢复验收

日期：2026-08-17（UTC+8）

权威裁决：`GO_W7_SCORE_LINEAGE_DATA_ONLY`

策略有效性：`NOT_EVALUATED`

生产授权：`none`

## 执行事实

用户逐字批准recovery scope `f61a2365...44b5`后，唯一runner于2026-08-17 10:31（UTC+8）创建，
在断网、只读根、非root、无`.env`、无生产ledger的恢复镜像内运行。内部只执行固定W7的first pass和
replay；随后唯一auditor在不挂Qlib的独立容器内复核。原scope `5d238942...38ad`没有重跑。

自动权限审查曾在创建runner进程前超时一次；没有容器、授权标记或lineage开始标记，因此不计runner
调用。系统允许的同命令一次重试才是scope内唯一真实调用。

## 谱系结果

- first/replay bundle SHA-256均为`5842f87d...2f93`，模型、预测和summary逐内容一致。
- 预测谱系为194,329行，日期覆盖2025-01-02—2025-12-31；只包含
  `datetime/instrument/score`允许域。W7标签成熟度锚仍为2025-12-16，仅供未来指标口径使用。
- 模型SHA-256：`999e9839...c0b2`；预测SHA-256：`0c8befa9...8321`；两遍manifest SHA-256：
  `67fa92dc...cb8b`。
- runner报告SHA-256：`d3c51f89...274d`；独立audit SHA-256：`d5cd43c3...276d`。
- audit全部通过：窗口、协议、行数、日期边界、模型非空、无效果字段、策略未评价、生产授权none。

## 权限与结论边界

- 真实Qlib只由runner读取；auditor没有Qlib挂载。
- 没有读取或计算测试标签、RankIC、收益、H00906、组合、回撤或策略效果；效果尝试仍为0。
- 没有外网、secret、实验账本、模拟仓、Web或生产变更。
- `GO_W7_SCORE_LINEAGE_DATA_ONLY`只解除R3G-2效果运行前的W7谱系数据阻断，不等于TS策略有效，且
  不自动授权后续效果读取。下一步必须另立效果release scope并重新取得用户精确批准。

脱敏追踪真身为`config/ts_v5_r3g2_w7_recovery_manifest_v1.json`。原入口失败回执、原空输出证据和本次
忽略区模型/预测/report/audit均永久保留；本recovery scope不得重跑。

## 终版验证

- 脱敏manifest对scope、approval、runner report、audit、两遍pass manifest、模型、预测、summary、
  文件数和覆盖元数据逐项复算PASS；manifest SHA-256为`fe7b7aee...579f`。
- 全仓1,356项PASS、架构13项PASS；Ruff、Compose、`git diff --check`和定向凭据扫描PASS。17条warning
  均为既有第三方弃用或pandas未来行为提示。
- runner/auditor一次性容器均已按`--rm`清理；生产scheduler保持原容器`183b8c6c5edd`、原镜像且
  healthy，未重启。

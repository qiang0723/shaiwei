# M7-0R3-P2 请求计划独立审计挂载恢复

## 裁决

首次真实请求计划独立审计已按失败关闭停止。请求计划未改、输入未改、代码未改，网络、provider、
secret 和资金流数值读取均为 0。当前只冻结一次性挂载恢复 scope，状态为
`READY_NOT_EXECUTION_AUTHORIZED`，尚未运行恢复审计。

## 首次失败与根因

- 首次 auditor 容器把内容寻址计划目录挂载到 `/plans`，命令也以 `/plans` 为 plan root。
- 独立审计器会从冻结输入重新计算 plan ID，并要求 plan root 的 basename 等于该 ID；实际 basename
  为 `plans`，因此在写审计产物前返回 `RecoveryError`。
- 首次路径下没有生成 `request_plan_audit.json`，该 FAIL 不得删除、覆盖或改称 PASS。
- 只读分段诊断确认：manifest、官方日期、plan ID 算术、两轨目标身份、三份计划文件物理/逻辑身份、
  527 个状态键覆盖和 541 个双形态资金流键覆盖均通过。该诊断没有写产物、读取数值或访问网络。

## 恢复边界

恢复只修正 plan mount target：保留内容寻址 basename，挂载为
`/plans/406f083f09cc8e41517ff9b38a4e109606a44b3da923710e4f745e34932b0470`。其余 Git、镜像、输入、
审计算法、阈值和资源边界逐项不变；输出进入新的忽略目录
`data/control/m7-recovery/request-plan-audit-recoveries/v1`，不复用首次输出路径。

恢复 scope 的机器真身为
`config/m7_moneyflow_request_plan_audit_mount_recovery_scope_v1.yaml`，物理 SHA-256 为
`3a5d201bf3972198cd98d74e6c40cb1fb15a63180fe0e660054ca37286b9592f`。必须在该文件提交并推送后，由
用户同时绑定完整 SHA 和动作
`M7_REQUEST_PLAN_INDEPENDENT_AUDIT_MOUNT_RECOVERY_ONCE` 明确批准。恢复仅允许 auditor 调用一次；若再
失败，本 scope 永久关闭。

## 权限声明

该恢复使用 `network=none`、只读根、非 root、`cap_drop=ALL`、`no-new-privileges`；只挂载封存 targets、
封存 request plan 和新的审计输出目录。不挂载 `.env`、token、项目根、Docker socket、生产
`data/raw`、ledger 或 logs。恢复 PASS 也只证明请求计划审计闭环，不授权后续真实网络恢复。

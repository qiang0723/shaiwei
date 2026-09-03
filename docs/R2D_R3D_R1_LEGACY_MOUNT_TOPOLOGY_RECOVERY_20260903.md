# R2D-R3D-R1 旧生产挂载拓扑恢复协议

## 前序失败

2026-09-03 20:46 UTC+8，R3D Phase A scope
`553e8bcb1bda778328dc45d4866cce884a306a50f76cb81ed599d7cb74adce35` 的唯一只读预检在生产
mutation 前因 `legacy scheduler pre-prepare mounts differ from the contract` 阻断。current/previous、
运行容器、release state/audit 和业务账本均未被该预检改变；该 scope 永久关闭，不得重试或授权。

## 根因与唯一变量

R3D config 继承 R3B 时点的旧生产三 bind 挂载预期；当前旧生产实际为三个受控 bind 加
`/run/shaiwei-locks`。底层 `release._container_contract` 已严格验证第四项必须为 writable volume、名称
`shaiwei_runtime_locks_v1`，并继续按旧镜像身份把其 lock authority 解释为
`legacy-bind-flock-v0`。失败来自上层协议集合滞后，不是未验证挂载、候选漂移或业务失败。

R1 只允许 R2D 协议模型显式接受两种既有合法旧生产拓扑：三 bind，或三 bind 加上述固定 named
volume；每份 config 仍必须选定精确集合，prepare 时实际集合必须逐项相等。底层类型、卷名、RW、
只读根、镜像、健康、重启、candidate authority 和发布动作全部不变。

## 恢复与授权边界

先单独提交并推送守卫源码，再把 R3D config 绑定新控制器 HEAD/六组件 SHA 和四挂载，完成专项、架构、
Ruff 与差异检查后提交推送。随后只能生成新的 metadata-only scope；它必须显式引用并作废上述失败
scope。新 scope 获得用户逐字批准前不得运行 `--execute`。

本协议不授权 promote/start/restart、业务跑批、回填、密钥、外网、候选重建、fixture 重跑或效果读取。
若新预检仍失败、窗口过期或任何身份漂移，停止并保留证据，不得继续扩张恢复变量。

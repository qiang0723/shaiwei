# M6-4B-R5 生产 Head30 独立审计谱系入口恢复协议

## 冻结结论

R5 只修复 R4 最终镜像未提供 R3 协议 YAML 的入口缺陷。R4 已唯一调用并永久关闭；失败发生在
R2 effect 读取前，R2 封存产物、审计语义和家族累计 2 次组合转换尝试均不变。

## 唯一变量

R5 将仓库中已跟踪、哈希冻结的 R3 协议
`config/m6_csi800_production_head30_audit_identity_recovery_v1.yaml` 只读挂载到
`/inputs/r3-protocol.yaml`，并把该显式路径交给原 R3 协议 loader。loader、allowlist、R3 Python
审计代码和 R2 原协议路径均不修改。

## 完整 daemon 预检

R4 的 fixture 只验证旧 R2 协议，未覆盖真实入口的 R3 谱系依赖。R5 发布前必须由 Docker daemon
使用最终镜像和 Compose fixture 服务，调用与真实入口完全相同的谱系/authority 预检函数，并按
真实容器路径挂载以下文件：R5 协议、R3 协议、R3 scope、R4 失败证据、R2 release 和 R2 approval。

fixture 明确禁止挂载 R2 effect，因此只能证明入口和授权谱系可达，不能读取结果或执行审计。只有该
完整预检 PASS，才允许生成待授权 scope。

## 执行边界

R5 仍为断网 auditor-only：不挂载 Qlib、项目根、`.env`、Docker socket、生产账本、模型、预测或
其他项目。R2 effect 只读，新 R5 audit 目录可写。生成 scope 后停止；真实审计必须再次取得用户对
新 scope SHA-256 的精确授权，R2/R3/R4/R5 均不得重跑。

机器真身：
`config/m6_csi800_production_head30_audit_lineage_entry_recovery_v1.yaml`。

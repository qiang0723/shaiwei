# M6-4B-R3 生产 Head30 独立审计身份恢复执行失败留痕

## 权威状态

R3 scope `b38628defcfee83087f0c0d982d0c1145b3f6d642c28508055cba2bddb9614d3` 已于
2026-08-20 18:05:18（UTC+8）调用唯一 auditor-only 容器。容器成功创建，但在读取 R2 effect
之前失败关闭；本 scope 永久不得重跑。

- 入口把容器内只读挂载路径 `/inputs/original-protocol.yaml` 传给冻结的
  `ReleaseProtocol.load`。该 loader 只允许项目内三个固定协议路径，因而抛出
  `ProtocolError: production-converter release protocol path is not allowed`。
- 这是恢复入口的路径绑定缺陷，不是主结果、独立重建、G0 或策略缺陷。独立审计计算尚未开始，
  `effect_semantics_read=false`。
- 新恢复 audit 目录保持 0 文件；R2 effect 仍为 5 文件、1,191,570 bytes、tree SHA-256
  `d3d84d10...45c1`，前后完全一致。
- runner 调用 0、训练/预测/回测 0、新增组合尝试 0；家族累计仍为 2。生产授权仍为 `none`，策略
  状态为 `NOT_AUTHORIZED_PENDING_AUDIT_ENTRYPOINT_RECOVERY`。
- scheduler 保持原容器 healthy，未重启或替换。

## 不可变证据

- R3 approval SHA-256：`a2251c9a70afb5fc35da04b9c25824d3a0ae5daa1e22716e572d7bc6b4bd15d0`
- R3 recovery scope SHA-256：`b38628defcfee83087f0c0d982d0c1145b3f6d642c28508055cba2bddb9614d3`
- R2 effect tree SHA-256：`d3d84d104968bf01f88312bd665060f2e57727145e4064697b4753bd6fc545c1`
- 机器留痕：`config/m6_csi800_production_head30_audit_identity_recovery_execution_failure_v1.json`

## 下一合法节点

只能另立 M6-4B-R4 入口路径恢复：保持 R3 的三层审计语义、R2 五文件、镜像基础和零新增尝试不变，
仅把旧协议验证改为使用基础镜像内允许的固定项目路径，或在不调用路径白名单 loader 的情况下对挂载
文件做精确哈希与 Schema 验证。必须先用 daemon 级合成 fixture 覆盖“容器内协议路径可加载”，形成
新镜像、新输出根和新 scope，再由用户精确批准一次 auditor-only 执行。不得复用 R3 approval、scope
或输出目录，也不得借恢复修改统计合同或结果。

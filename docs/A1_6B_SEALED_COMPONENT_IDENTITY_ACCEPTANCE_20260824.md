# A1-6B 封存组件身份权威验收

- 日期：2026-08-24（UTC+8）
- 协议：`docs/ADR_003_SEALED_COMPONENT_IDENTITY_AUTHORITY_20260824.md`
- 裁决：`GO_ENGINEERING_COMPLETE`
- 效果读取 / 新研究尝试 / 生产授权：`0 / 0 / none`

## 结果

A1-6B 已完成。当前构建资产注册表与历史 release 身份被拆成两个明确权威：注册表描述当前所有权和
生命周期；封存 release 由其版本化合同中的历史 registry SHA、逐资产 SHA 和组件快照永久复核。

R4 组件 `m6-head30-delisting-entitlement-release` 已从 `ACTIVE_LOCAL_READ_ONLY` 如实关闭为
`CLOSED_FROZEN`。当前注册表规范 SHA 已变为
`659cef181514b041d608a294b6c1f58363c78e4947cc7822e15a346055e7d9c6`，但以下历史 scope 均继续通过：

- R2 scope `94a4560553cd67899988276f336cc103de052b2088a2d4adbb63e5ff2d2e9829`，历史 registry
  `e0251d3cd9f38da055d533f8fb2f059ef5213f7ed13ef9caab7a653e64155035`；
- R4 scope `117e69a8c29f48d2434c84363d4766d48af4f2010aeddae1610128fb9614c51d`，历史 registry
  `160159dc2c735ad4239a5bb60f1c209a4baf65ef9326d643077f3400f0be69a3`。

## 实现边界

1. `build_identity.release` 新增纯校验 `verify_sealed_component_identity`。它不读当前注册表和文件系统，
   只接受调用方显式冻结的历史权威，并严格验证 registry、规范资产记录和组件快照。
2. R2/R4 删除各自不完整的资产解析逻辑，共用同一校验器；两者都固定发布时的三条路径、逐资产 SHA
   和组件快照。
3. R2/R4 合成 fixture 改用冻结身份，证明历史复核不依赖当前 registry；当前 active release 校验仍
   使用当前注册表和工作树。
4. 两个已关闭 builder 增加状态门，不能再为 closed 组件形成新 scope。
5. 没有修改历史 scope、协议、approval、claim、effect、audit、账本、镜像或结果裁决；删除文件 0。

## 失败关闭与测试

- 通用单元门分别篡改历史 registry、资产路径、资产 SHA（同时重算假快照）和组件快照，全部拒绝；
- R4 真实 scope 重复上述四类对抗，全部拒绝；
- R2/R4 两份真实 scope 正向通过，closed builder 拒绝签发；
- 当前 97/97 个 tracked Dockerfile/Compose 资产仍恰好登记一次；Web active attestation 仍通过；
- 专项测试：`59 passed`；
- 架构门：`13 passed`；
- 全仓测试：`1851 passed`，仅 17 条既有第三方/未来弃用 warning；
- Ruff、`git diff --check` 与凭据/生成数据门通过。

## 生产隔离

scheduler 仍为容器 `183b8c6c5edd`、镜像 `shaiwei:scheduler-current`，创建时间
`2026-08-03 17:39:34 +0800`，状态 `healthy`；本节点未重启、重建或修改生产服务。

## 下一步

A1-6B 结束，M6 继续保持关闭。恢复 R2-1 自然前瞻证据检查，不新增代码、不继续 M6 变体。历史 M6
文件的归档或清理仍等待异机恢复条件和用户逐文件复核，本节点不产生删除授权。

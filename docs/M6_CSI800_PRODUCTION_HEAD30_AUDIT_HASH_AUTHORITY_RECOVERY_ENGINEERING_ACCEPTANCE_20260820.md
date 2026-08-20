# M6-4B-R6 生产 Head30 独立审计哈希权威恢复工程验收

## 裁决

`GO_RELEASE_READY_NOT_EXECUTION_APPROVAL`

R6 已完成协议、实现、最终镜像、断网 daemon fixture 和精确 scope。真实 R2 effect 未挂载到
fixture，独立审计未调用，新增组合转换尝试为 0，生产授权为 `none`。

精确 release scope：

`349859a6794c3c50e377fdaf016e54fb854e1ab06be86b56aff40522799a90fa`

该 scope 不是执行授权。只有用户以完整 scope SHA 和冻结动作
`M6_PRODUCTION_HEAD30_AUDIT_HASH_AUTHORITY_RECOVERY_ONCE` 明确批准后，才允许启动一次
auditor-only 容器。

## 唯一修正

R6 删除了协议之外的“本次独立重算 canonical SHA 必须等于 R3 历史独立 SHA”裁决门。以下约束
全部保留：

- 当前独立重算 SHA 必须写入审计证据；历史 SHA 也保留为诊断字段。
- R2 主结果必须与封存主身份逐字节一致。
- 首遍和 replay 的物理身份必须一致。
- 独立重算与主结果继续使用相对/绝对 `1e-12` 容差。
- 主计算与独立重算的 decision 必须完全一致。
- R2 effect 树在审计前后必须完全一致；Qlib、runner、训练、预测和回测均禁止。

没有修改研究问题、G0、组合转换器、效果结果、统计公式或生产策略。

## 对抗 fixture

最终镜像由 Docker daemon 在 `network_mode=none`、只读根、非 root、capabilities 全丢弃的容器中
运行。fixture 使用与真实入口相同的 R5→R4→R3→R2 谱系预检，但不挂载 `/outputs` 或 `/audit`。

机器结果：

- 完整 R5/R4/R3/R2 谱系：`PASS`。
- 当前独立 SHA 与历史 SHA 不同、数值在 `1e-12` 内且 decision 一致：`PASS`。
- 数值差异超过容差：正确 fail closed。
- decision 漂移：正确 fail closed。
- `effect_mounted=false`、`effect_semantics_read=false`、`audit_invoked=false`。

fixture 证据 SHA-256：
`c3b020b9ec3832de74da17170b38cc164d27fe67b3198422e904f5139b5210ce`。

## 身份与验证

- 协议先行提交：`0f8522b`。
- 实现提交并已推送：`754036458fcdf1d429f2c6dda53357b80f34f61b`。
- 最终镜像：`shaiwei:m6-production-head30-audit-hash-authority-recovery-v1`。
- 镜像 ID：`sha256:cdd7a9606f214bca669283d91fa5cb9457c6d4392161bd7638dcf62629dac9af`。
- 基座镜像 ID：`sha256:73f3b0a570b32fdb8c331b306f0f1ddc141224bce5ce422bb385ffbc4cd5fba0`。
- 平台：`linux/arm64`；镜像内提交身份与 `origin/main` 均为 `7540364...4f61b`。
- scope 文档 SHA-256：`88e13c6474acfdccfd334748bc0cf4e5cf59042159748969db9126b86a79096f`。
- 专项测试：14 PASS；架构门：13 PASS；全仓：1589 PASS。
- Ruff、compileall、pip check、Compose 解析、diff-check 与敏感模式扫描：PASS。
- 三个新增生产模块分别为 321、339、230 行，均低于 400 行上限。
- scheduler 保持原容器 `183b8c6c5edd`、原镜像并为 `healthy`，未重启。

## 执行边界

R2/R3/R4/R5 scope 均不得重跑。R6 获精确批准后也只允许一次 auditor-only 运行：只读 R2 五份
封存 effect，写入新的 R6 audit 根；新增组合尝试 0。不得挂载 Qlib、调用 runner、训练、预测、回测、
写实验账本、访问外网或凭据，也不得进入前瞻、模拟仓、Web 或生产。

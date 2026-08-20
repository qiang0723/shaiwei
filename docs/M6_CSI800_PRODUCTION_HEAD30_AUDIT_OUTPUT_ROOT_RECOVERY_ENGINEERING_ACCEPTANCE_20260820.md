# M6-4B-R7 生产 Head30 独立审计输出根恢复工程验收

## 裁决

`GO_RELEASE_READY_NOT_EXECUTION_APPROVAL`

R7 已完成协议、实现、最终镜像、同根目录 daemon fixture 和精确 scope。真实 R2 effect 未挂载到
fixture，独立审计未调用，新增组合转换尝试为 0，生产授权为 `none`。

精确 release scope：

`c08605ca15ab480efaac4077db514b65a86ea40cf3872fd059029e932747b717`

该 scope 不是执行授权。只有用户以完整 scope SHA 和冻结动作
`M6_PRODUCTION_HEAD30_AUDIT_OUTPUT_ROOT_RECOVERY_ONCE` 明确批准后，才允许启动一次 auditor-only
容器。

## 唯一修正

R7 显式创建新的宿主 audit 根：

`data/research/m6_csi800_production_head30_v1/effect-r2-audit-output-root-recovery`

`create_host_path=false` 保持不变。fixture 与未来真实服务绑定同一宿主目录；fixture 对该目录完成固定
哨兵的写入、读回、SHA-256 核验和删除，并确认目录在运行前后都为空。

R6 的哈希权威语义、主结果精确身份、首遍/replay 物理一致、相对/绝对 `1e-12` 容差和 decision
精确一致全部原样继承。没有修改研究问题、G0、组合转换器、效果结果或生产策略。

## Daemon fixture

最终镜像在 `network_mode=none`、只读容器根、非 root、capabilities 全丢弃的环境中运行。fixture
没有 `/outputs` 或 `/audit`，但把未来真实 audit 宿主根挂载到 `/fixture-output`：

- R6/R5/R4/R3/R2 完整谱系：`PASS`。
- audit 根写入—读取—哈希—删除：`PASS`。
- audit 根运行前为空、运行后为空：`true/true`。
- 哨兵 SHA-256：`8577c02d1043a054e368d46b937541be12ba69bba43e0678e9854d7c0f2f15e8`。
- 历史独立 SHA 不同但容差/裁决一致：`PASS`；超容差和 decision 漂移正确 fail closed。
- `effect_mounted=false`、`effect_semantics_read=false`、`audit_invoked=false`。

fixture 证据 SHA-256：
`54c77ac08084da4ec773b178cbf6bec78fde8ec40a355ee4efb0e89ff4333408`。

## 身份与验证

- 协议先行提交：`a3e2e01`。
- 实现提交并已推送：`7732fb2ee8a9079ab96744e3e266cddaab649666`。
- 最终镜像：`shaiwei:m6-production-head30-audit-output-root-recovery-v1`。
- 镜像 ID：`sha256:8611728ac7d4b60cd7d87741a51834c23120c7eb56eb09c151f2c0383578528d`。
- 基座镜像 ID：`sha256:cdd7a9606f214bca669283d91fa5cb9457c6d4392161bd7638dcf62629dac9af`。
- 平台：`linux/arm64`；镜像内提交身份与 `origin/main` 均为 `7732fb2...649666`。
- scope 文档 SHA-256：`cbd5840532e7733916b60270e66d4dca7d60b1a41fc3f53dd985d70f290082cf`。
- 专项测试：14 PASS；架构门：13 PASS；全仓：1603 PASS。
- Ruff、compileall、pip check、Compose 解析、diff-check 与敏感模式扫描：PASS。
- 三个新增生产模块分别为 317、295、213 行，均低于 400 行上限。
- scheduler 保持原容器 `183b8c6c5edd` 且 `healthy`，未重启。

## 执行边界

R2/R3/R4/R5/R6 scope 均不得重跑。R7 获精确批准后也只允许一次 auditor-only 运行：只读 R2
五份封存 effect，写入新的已验证 R7 audit 根；新增组合尝试 0。不得挂载 Qlib、调用 runner、训练、
预测、回测、写实验账本、访问外网或凭据，也不得进入前瞻、模拟仓、Web 或生产。

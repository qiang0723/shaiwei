# M6-5C-C-R1 退市风险恢复 release 终版验收

- 日期：2026-08-23（UTC+8）
- 裁决：`GO_RELEASE_READY_NOT_EXECUTION_APPROVAL`
- release scope：`2afe815fbded79e221d23b431a09648c92cef64766ad47e68503425ecffec85c`
- 策略权限：`POST_HOC_METHOD_RECOVERY_DIAGNOSTIC_ONLY`
- 生产授权：`none`

## 1. release 身份

- base协议提交：`1775fbc`；claim-first实现提交：`aac357d`；R1协议提交：`0c15976`；R1实现提交：
  `5a142da7144b16abedbe9facdf64dd36d8c64d1b`；
- successor 镜像：`shaiwei:m6-head30-delisting-risk-release-r1-v1`，内容 ID
  `sha256:be1e9b47ad6e069c6e4d44e2f3cc14176529a55d060996a003eed26e50192fd9`；
- source bundle：`360db13e8cdef29572f70101b5f44f0b9ec7380a88f715f820784097bb23bc0a`，
  946 个文件；component build snapshot：`8bfd9b6b...581444`；
- scope 文件 SHA-256：`845f623f...ecc70`；scope 自身份：`2afe815f...ec85c`；
- metadata scope 同时绑定 base protocol、R1 protocol、原封存 R2/raw/R7 输入身份、镜像标签、三项构建
  资产、claim spec、容器最小权限和 daemon fixture。

## 2. 首次失败与恢复留痕

首次镜像 `faf2ac66...c963cbf` 由于 Docker context 缺三份前序文档，在 synthetic domain 进入前失败，
永久关闭且未重跑。R1 仅增加专用 dockerignore 和三份显式只读 COPY；全局 `.dockerignore`、领域代码、
claim、门槛与挂载集合不变。successor 独立构建一次，原失败镜像未被覆盖。

## 3. daemon fixture

successor 在 `network_mode=none`、只读根、非 root、drop-all/no-new-privileges 下唯一运行一次：

- claim 在 reader 前完成，第二次同 scope 调用被拒绝；
- 合成 30 只、六窗口中每窗恰好一次锁存退出，共 6 个风险退出订单；
- 风险时钟严格使用执行日前一官方开市日；first/replay 逐内容相同；
- artifact-only 独立实现复算一致，auditor CLI 不挂 raw/R2；
- fixture SHA-256：`c3b3c7fa...9a05e4`；canonical ledger 写入 0、真实输入读取 0、网络 0。

## 4. 验证与运行隔离

- R1/M6-5C/build/claim 专项：35 PASS；全仓：1,815 PASS；architecture-check：13 PASS；
- Ruff、compileall、pip check、Compose、diff-check、脱敏检查：PASS；
- 构建资产 94/94，效果入口 9/9；所有新增生产模块不超过 400 行；
- scheduler 保持原容器 `183b8c6c5edd`、原镜像 `shaiwei:scheduler-current`、创建时间
  `2026-08-03 17:39:34 +0800`，持续 healthy，未重启。

## 5. 当前停止点

当前 scope 只有 `release_ready=true`；真实目标、价格、效果、claim receipt、canonical ledger、正式
effect/audit 均未授权。没有 approval 文件，没有新真实尝试。若继续，用户须逐字绑定上述 scope SHA
并授权动作
`M6_HEAD30_500K_DELISTING_RISK_RECOVERY_ONCE_WITH_CLAIM_REPLAY_AND_INDEPENDENT_AUDIT`；同 scope 只准
运行一次，claim 后任何失败均消费 ordinal 1，且不授权外网、模型拟合、新预测、前瞻、模拟仓、Web、
scheduler 或生产。

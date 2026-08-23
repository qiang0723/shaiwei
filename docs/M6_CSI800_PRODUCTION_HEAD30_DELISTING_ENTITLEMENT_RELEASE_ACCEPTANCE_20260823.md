# M6-5C-C-R4 红股权益 successor release 验收

- 日期：2026-08-23（UTC+8）
- 裁决：`GO_RELEASE_READY_NOT_EXECUTION_APPROVAL`
- 策略效果：`NOT_EVALUATED`
- 生产授权：`none`

## 发布身份

- 冻结协议 SHA-256：`9d0be9e3a2f6ee2daeaf6f27863e11611bca9bcdd128fffecb0844b81f04bc7b`；
- 实现提交 / `origin/main`：`923137289e091c71daa05afec6f38c1436808004`；
- source manifest 文件 SHA-256：`49ac7e78ebd16f3edd807c1e27a20b25bfc8790e8aa96099017efa75722288f4`，
  绑定 962 个 `src/config/pyproject` 文件；
- source bundle SHA-256：`b98c848678edabbaef4b9efd81acaf922334823587e38b03b9f5107e74e774cc`；
- 当前构建注册表 SHA-256：`160159dc2c735ad4239a5bb60f1c209a4baf65ef9326d643077f3400f0be69a3`；
- successor 三项构建资产的组件快照 SHA-256：
  `64ca5bd0605c4b285400f93229ef106e0c489459f983f2b72428c75554e748e5`；
- 镜像 `shaiwei:m6-head30-delisting-entitlement-release-v1` 内容 ID：
  `sha256:dd29fe1442e95c88d0ee8d5f9e69a58d4f5a92592eb78c98dbb6b5cd0186435b`；
- metadata-only scope：
  `config/m6_csi800_production_head30_delisting_entitlement_release_scope_v1.json`，文件 SHA-256
  `4a8c59e17eb252a1285befa622e96b038c6d7319fc7df3c431d8453d976cff9f`，scope SHA-256
  `117e69a8c29f48d2434c84363d4766d48af4f2010aeddae1610128fb9614c51d`。

镜像只构建一次。revision、source bundle、组件构建快照三项标签均与 scope 一致；scope 还逐项绑定
当前注册表中的 Compose/Dockerfile 路径与文件 SHA、fixture 镜像身份和四个 write-once 输出根。
ADR-002 继续保证旧 R2 使用自身封存注册表身份，不因当前 successor 登记而失效。

## 唯一 daemon fixture

在新的 Git 忽略目录执行恰好一次断网 synthetic fixture；证据 SHA-256 为
`4043df751a99d4d2be12ca9055d9adc426d6726eb3ea61934b0b4413744ab71b`，`reused=false`。机器结果：

- 真实穿过 successor `ReleaseScope.load()`，runner/auditor CLI 映射 PASS；
- ordinal 2、parent `6797875cf3c0`、claim 先于 effect reader，同 scope 重开被拒绝；
- 六个窗口均完成登记日持仓、风险退出、detached 红股到账和再次风险退出；
- first/replay 逐内容一致，独立重建与主裁决一致；
- `network_used=false`，真实目标/行情/效果读取为 0，canonical ledger 写入为 0；
- fixture 未创建真实 approval、claim、effect 或 audit 产物。

## 验证与隔离

scope loader 独立重算值与文件自哈希均为 `117e69a8...c51d`；镜像、组件、源码和 fixture 身份一致。
身份篡改门覆盖镜像标签、Compose/Dockerfile 哈希、fixture image ID 和输出根。专项 11 PASS，
architecture-check 13 PASS，全仓 1,838 PASS；Ruff、compileall、pip check、Compose config 和
diff-check 均 PASS。

canonical experiment ledger 只保留已消费的 ordinal 1 `6797875cf3c0`；没有 ordinal 2 真执行行。
R4 approval、claim、effect、audit 四类真实路径均不存在。没有读取 `.env`，没有外网、模型拟合、新
预测、前瞻、模拟仓、Web 或生产写入。scheduler 仍为原容器 `183b8c6c5edd`、原镜像
`shaiwei:scheduler-current`，持续 healthy，未重启、未换镜像。

## 停止条件

本节点到此停止，不创建 approval，不启动真实 runner 或 auditor。唯一真实恢复必须由用户逐字绑定
scope `117e69a8c29f48d2434c84363d4766d48af4f2010aeddae1610128fb9614c51d` 与动作
`M6_HEAD30_500K_DELISTING_ENTITLEMENT_RECOVERY_ONCE_WITH_CLAIM_REPLAY_AND_INDEPENDENT_AUDIT`。
一旦 claim 写入，ordinal 2 即被消费；无论后续成功或失败，同 scope 均不得重跑。

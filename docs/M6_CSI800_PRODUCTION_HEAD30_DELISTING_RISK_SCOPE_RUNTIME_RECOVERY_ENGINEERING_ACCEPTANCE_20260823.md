# M6-5C-C-R2 scope 运行时恢复工程验收

- 日期：2026-08-23（UTC+8）
- 裁决：`GO_SUCCESSOR_BUILD_READY_NOT_EXECUTION_APPROVAL`
- 生产授权：`none`

## 结果与单一改动

R2 只修复组件镜像在 `ReleaseScope.load()` 中被要求携带全仓无关构建资产的问题。中央构建注册表新增
显式 `validate_filesystem=false` 元数据模式；默认值仍为 `true`，因此宿主构建、全仓资产清点和既有
调用继续执行严格文件存在、非符号链接与根目录约束。元数据模式仍严格验证 Schema、重复键、枚举、
排序、唯一归属和安全相对路径，不能绕过注册表结构门。

release scope 不再从组件镜像文件系统重算无关资产，而是要求注册表中
`m6-head30-delisting-risk-release` 的三条资产路径与 scope 内封存记录逐项相等，并从三条 scope 哈希
重算组件快照；Compose 与 Dockerfile 身份也必须来自同一组封存记录。R1、R2 恢复协议哈希均进入
scope 身份。领域计算、attempt claim、冻结输入、指标、门槛和挂载角色没有变化。

## 失败隔离与 fixture

- 原 scope `2afe815f...ec85c`、原 approval 和 R1 镜像永久关闭，不得重跑或复用；
- successor 使用新镜像 `shaiwei:m6-head30-delisting-risk-release-r2-v1` 和新 scope 文件；
- approval、claim、effect、audit 全部改用带 `-r2` 的隔离路径，避免读取或覆盖失败 R1 状态；
- daemon fixture 现在构造完整合成 scope，并真实穿过 `ReleaseScope.load()`；篡改任一 scoped 构建
  哈希会在组件快照门失败关闭；
- fixture 仍只使用合成数据，真实目标、行情、效果、canonical ledger、approval 和生产写入均为 0。

## 验证

- build identity + M6-5C release 专项：34 PASS；
- architecture-check：13 PASS；
- 全仓：1,817 PASS，17 条既有第三方/未来弃用提示；
- Ruff、compileall、pip check、Compose config、`git diff --check`：PASS；
- 新增生产模块均不超过 400 行；构建资产仍为 94/94，默认严格文件门未放宽。

## 下一步

本实现推送后，才可按 R2 冻结协议生成同一远端 revision 的 source manifest、执行恰好一次断网
successor 镜像构建和恰好一次 daemon fixture。两者通过后生成并推送新的 metadata-only scope，然后
停止；不得创建真实 approval、运行真实 runner/auditor，或读取真实目标、行情、效果。真实运行必须
由用户对新 scope 与冻结动作重新精确授权。

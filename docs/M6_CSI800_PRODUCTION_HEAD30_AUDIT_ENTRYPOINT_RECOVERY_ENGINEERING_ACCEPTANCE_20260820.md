# M6-4B-R4 生产 Head30 独立审计入口恢复工程验收

## 裁决

`GO_AUDIT_ENTRYPOINT_RECOVERY_RELEASE_READY_NOT_EXECUTION_APPROVAL`。

R4 已修复 R3 的容器协议路径入口错误，且只改变这一项。真实 R2 effect 未由 R4 读取，独立审计未
执行，新增组合转换尝试为 0，家族累计仍为 2，生产授权为 `none`。

## 冻结与实现身份

- 结果前协议提交：`da89e70`，早于实现提交并已推送。
- 实现提交：`ace34dbb93b9759df4e5c3e7d1373b24d42a6c51`，构建前已推送；该提交包含
  daemon fixture 与最终镜像身份的双向绑定补强。
- R4 协议 SHA-256：`5f82479c1a799cea1c451a23e0a2ea948c8abdd916a2501e28b604af9892cd0e`。
- 最终镜像：`shaiwei:m6-production-head30-audit-entrypoint-recovery-v1`。
- 镜像 ID：`sha256:27dadcefa5f445ced646ef9bca013c1487715ed6947213aab991bc05e3d49fb4`，
  `linux/arm64`。
- 基础 R3 镜像 ID：`sha256:91cca66537e0ba058116f79c20897728d9913aa850af6e9f4efb8f50f61c9d3c`。

## 唯一改动与 daemon 证据

R3 使用的 `/inputs/original-protocol.yaml` 已从 R4 的真实服务命令和挂载中移除。冻结 loader 未修改；
R4 使用基础镜像内合法路径：

`/workspace/config/m6_csi800_production_head30_price_recovery_v1.yaml`

Docker daemon 使用最终镜像真实创建了断网、只读、非 root、无数据挂载的 fixture 容器。fixture
成功由冻结 `ReleaseProtocol.load` 加载上述路径，物理 SHA-256 为
`6e4fc89c5c02db862681866e96d1e8063e6b6bc2a6bb58c3cfc08819ba327a6e`；继承的 R3 审计语义
合成门 PASS，`real_effect_read=false`、`audit_invoked=false`、生产 `none`。

## 工程与边界验证

- R4 专项：12 PASS。
- 架构宪法：13 PASS。
- 全仓：1562 PASS，17 条均为既有第三方/数据类型 warning。
- Ruff、compileall、pip check、Compose config、diff-check、敏感模式扫描：PASS。
- 三个新增生产模块分别为 300、274、206 行，均低于 400 行上限。
- 镜像内 R4 contract/entrypoint 与宿主实现哈希一致；继承的 R3 contract/entrypoint 哈希也精确一致。
- scheduler 保持原容器 `183b8c6c5edd`、原镜像 `sha256:722f63de...3b76`、healthy，未重启。

## 待授权 scope

- scope SHA-256：`d07daefb27918286f8efa712e60dd6d21482c75b71f7677bd634b85b61c3bd71`。
- scope 文件 SHA-256：`b51abde30b00222600c621e5b4a83dd77695e53008be29de3748083fe739bef1`。
- scope 生成只核对路径、文件集合、大小和 SHA-256；`effect_semantics_read=false`。
- 新 R4 audit 输出根仍不存在；真实 auditor 调用数为 0。

精确批准句：

> 批准 M6-4B-R4 release scope
> `d07daefb27918286f8efa712e60dd6d21482c75b71f7677bd634b85b61c3bd71` 按动作
> `M6_PRODUCTION_HEAD30_AUDIT_ENTRYPOINT_RECOVERY_ONCE` 运行一次断网 auditor-only 入口恢复审计；
> 只读 R2 五份封存 effect，新增组合尝试 0，不授权 Qlib、runner、训练、预测、回测、实验账本、
> 外网、前瞻、模拟仓、Web 或生产，R2/R3/R4 scope 均不得重跑。

没有该精确批准，不创建 approval、不读取效果语义、不运行真实恢复。

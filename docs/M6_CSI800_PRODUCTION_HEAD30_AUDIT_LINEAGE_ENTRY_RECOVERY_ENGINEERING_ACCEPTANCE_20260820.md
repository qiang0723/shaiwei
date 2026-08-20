# M6-4B-R5 生产 Head30 独立审计谱系入口恢复工程验收

## 裁决

`GO_AUDIT_LINEAGE_ENTRY_RECOVERY_RELEASE_READY_NOT_EXECUTION_APPROVAL`。

R5 只补充 R3 协议的显式只读交付，并把发布 fixture 升级为真实入口同函数的完整谱系/authority
预检。R2 effect 未由 R5 读取，独立审计未执行，新增组合转换尝试为 0，家族累计仍为 2，生产授权
为 `none`。

## 冻结与实现身份

- 协议提交：`fef88da`，早于实现并已推送。
- 终版实现提交：`51ca37a848686f6c371d26a676a636477bc9b66c`，构建前已推送。
- 协议 SHA-256：`1cdc2672deca349a8cae2902046ef39b2c017b0c8b109eec10e1fda025e144e2`。
- 最终镜像：`shaiwei:m6-production-head30-audit-lineage-recovery-v1`。
- 镜像 ID：`sha256:73f3b0a570b32fdb8c331b306f0f1ddc141224bce5ce422bb385ffbc4cd5fba0`，
  `linux/arm64`。
- 基础 R4 镜像：`sha256:27dadcefa5f445ced646ef9bca013c1487715ed6947213aab991bc05e3d49fb4`。

## 唯一改动

R3 协议由仓库跟踪真身只读挂载到 `/inputs/r3-protocol.yaml`。R3 loader、R3 审计算法、R2 原协议
路径、结果、组合、成本、G0 和容差均未修改。

新增 R5 代码只承担版本化合同、谱系预检、发布 scope 和一次性编排；统计重算继续复用冻结的 R3
实现。新增三个生产模块为 305、252、226 行，没有引入超大单文件。

## daemon 完整预检

最终镜像由 Docker daemon 以断网、只读、非 root、无 effect 挂载的 fixture 服务实际创建。
fixture 调用与真实 R5 入口完全相同的 `lineage_preflight`，并闭合：

- R5 协议；
- R4 scope 与 R4 执行失败证据；
- R3 协议与 R3 scope；
- R2 原 release、approval 与镜像内合法协议路径。

结果：`PASS`；`effect_mounted=false`、`effect_semantics_read=false`、`audit_invoked=false`。
preflight 文件 SHA-256：`68c78010fec4f88b325159f0f363fe2d993004751a89eb444097ae1930471947`。

首次工程 fixture 曾在导入阶段因薄镜像包路径差异失败；当时无 effect 挂载、无 scope、无审计调用。
修复采用包内/薄镜像双导入路径，并新增对应回归测试；终版镜像重新构建后完整预检 PASS。

## 验证

- R5 专项：13 PASS。
- 架构宪法：13 PASS。
- 全仓：1575 PASS，17 条均为既有 warning。
- Ruff、compileall、pip check、Compose config、diff-check、敏感模式扫描：PASS。
- 镜像内 R5/R4/R3 六个模块与宿主冻结文件哈希一致。
- scheduler 保持原容器 `183b8c6c5edd`、原镜像、healthy，未重启。

## 待授权 scope

- scope SHA-256：`baa43d73ab0310c039d1c4794e74ebd3eda4a51578204224778ddaca0d724789`。
- scope 文件 SHA-256：`ef2e1b603d9395c85de4ef931122f45d272f513bc95ef6e155bdddbc49423fd7`。
- scope 生成仅核对文件身份、集合、大小和 SHA-256；`effect_semantics_read=false`。
- 新 R5 audit 输出根不存在；真实 R5 auditor 调用数为 0。

精确批准句：

> 批准 M6-4B-R5 release scope
> `baa43d73ab0310c039d1c4794e74ebd3eda4a51578204224778ddaca0d724789` 按动作
> `M6_PRODUCTION_HEAD30_AUDIT_LINEAGE_ENTRY_RECOVERY_ONCE` 运行一次断网 auditor-only 谱系入口恢复审计；
> 只读 R2 五份封存 effect，新增组合尝试 0，不授权 Qlib、runner、训练、预测、回测、实验账本、
> 外网、前瞻、模拟仓、Web 或生产，R2/R3/R4/R5 scope 均不得重跑。

没有该精确批准，不创建 R5 approval、不读取效果语义、不运行真实恢复。

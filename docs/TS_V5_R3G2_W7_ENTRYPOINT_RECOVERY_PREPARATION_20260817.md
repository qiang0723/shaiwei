# TS-v5 R3G-2 W7入口恢复发布准备

日期：2026-08-17（UTC+8）

当前裁决：`RECOVERY_RELEASE_PREPARATION_ONLY_NOT_EXECUTED`

## 结果目标

原scope `5d238942...38ad`在进入真实`run()`前因CLI参数名错配失败并已消费。本恢复包只允许在一个新的、
精确批准的scope下重新尝试W7分数谱系，目标仍是生成2025年W7模型与
`datetime/instrument/score`谱系并完成内部双跑和无Qlib独立审计。它不读取RankIC、标签效果、收益、
H00906、组合或策略效果，也不授权模拟仓、Web和生产。

## 权威事实与冻结边界

- 原scope文档SHA-256：`f8155b51...cb79`；scope SHA-256：`5d238942...38ad`。
- 原批准SHA-256：`9f513150...0f28`；入口失败回执SHA-256：`cdfe44d1...99bb`。
- 原runner调用1次、容器已创建；lineage读取、真实Qlib读取、auditor、策略效果尝试均为0；原lineage
  与audit目录文件数均为0。
- 唯一修复是runner/auditor两个CLI将外部参数`release/approval`映射到内部
  `release_path/approval_path`，并由直接调用两个`main()`的测试锁定。W7窗口、训练器、provider、
  输入哈希、输出合同和效果协议均未修改。
- 原scope永久禁止重跑；恢复必须使用新镜像、新scope、新批准schema和新的输出目录。

## 实现边界

恢复协议为`config/ts_v5_r3g2_w7_entrypoint_recovery_release_v1.yaml`。一次性Docker仍使用断网、只读根、
非root、无`.env`、无Docker socket、无生产ledger、无整仓挂载：runner只读冻结Qlib与scope/approval，
写新的recovery输出；auditor不挂Qlib，只读lineage并写独立audit。生产scheduler及其镜像不受影响。

实现继续复用原`w7_run`、`w7_audit_run`、`w7_lineage`和`w7_audit`，只新增恢复发布适配器；没有复制模型、
分数或审计计算。新生产文件均低于400行，既有热点未增长。该编排不是常驻服务，不新增外部依赖、写API、
公共账本或生产权限边界，因此不另立ADR；若未来把恢复能力推广为通用运行平台，须单独评审。

## 执行纪律

1. 先完成本地合同、失败路径、架构和全仓回归。
2. 只提交并推送恢复准备，不读取真实W7。
3. 以已推送commit构建不可变恢复镜像，运行断网synthetic fixture，逐项核对host/image受控文件。
4. 生成并推送唯一recovery scope；此时`execution_authorized=false`。
5. 用户逐字批准新scope与动作前，不创建recovery approval，不运行runner或auditor。

原失败证据及原空输出目录必须永久保留。恢复若再次失败，同一新scope仍不得重跑。

## 准备提交验证

- W7发布/runner/lineage/recovery专项：23项PASS。
- 全仓：1,356项PASS；17条均为既有第三方弃用或pandas未来行为warning。
- 架构门：13项PASS；Ruff、Compose解析、`git diff --check`和定向凭据扫描PASS。
- 原失败回执、原批准、原scope和两个空输出目录已由恢复发布器逐项复核一致。

以上仅证明恢复发布准备可构建，不是恢复执行或W7数据GO。

## 不可变恢复scope

- 准备提交：`8c228342205223f1e6820a136b61bc76671b3296`，已先推送`origin/main`。
- 镜像：`shaiwei:ts-v5-r3g2-w7-lineage-recovery-v1`；内容ID
  `sha256:39a5fa13...1398`；平台`linux/arm64`；嵌入commit`8c22834`。
- 镜像manifest：911个受控文件；manifest SHA-256 `bb569dad...a2f`；代码快照
  `a6102897...cda0`。host/image逐文件一致。
- recovery scope：`f61a236518282018c3525864eff5cd5fa0ed6fe01e3c26c04ff10224087144b5`；文档
  SHA-256 `235bfac2...b395`。
- scope生成后没有创建approval或recovery输出目录，runner/auditor均未调用；scheduler仍为原容器
  `183b8c6c5edd`且healthy。

下一动作只可为用户逐字批准：
`TS_R3G2_W7_SCORE_LINEAGE_ENTRYPOINT_RECOVERY_ONCE_WITH_REPLAY_AND_INDEPENDENT_AUDIT`。批准仍只允许
一个runner（内部first/replay）和一个无Qlib auditor；同scope不得重跑。

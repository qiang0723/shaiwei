# M1-1 科创50价量因子发现批终版验收

日期：2026-08-01（UTC+8）  
裁决：`GO_DISCOVERY_TOP2_LOCKED`  
策略有效性：`NOT_EVALUATED`  
生产授权：`none`

## 结论

本批按结果前冻结协议完成恰好 40 个 `deepseek-v4-pro` 响应，并只在 2020-08-03 至
2022-12-15 的科创50发现期执行受限 DSL 评价。14 条候选完成发现评价，6 条因严格 JSON schema 拒绝，
20 条因正文与唯一公式的语义合同不一致而拒绝；所有 40 次都计入研究家族 N，没有递补或调门槛。

机械 Top2 已按“绝对发现 RankIC、覆盖、复杂度、全局序号”的预注册顺序锁定：

1. `5c3c30d8b3a01f76`，序号 28，`liquidity_volume`；
2. `47f690ef14487a25`，序号 11，`reversal_mean_reversion`。

Git 摘要只保存 attempt、主题、序号和表达式/发现证据哈希，不披露公式或发现期指标。Top2 只是下一阶段
审查对象，不表示因子有效，更不表示旧 P2 科创50策略被修复。

## 费用与模型合同

- 完成响应：40/40；传输完成 40/40；无重试、无重复请求、无计费不确定性。
- 实际估算费用：`0.071831434 USD`，通过 `1 USD` 单批硬熔断；未使用余额不构成新批授权。
- 模型与价格在调用前依据 DeepSeek 官方
  [价格页](https://api-docs.deepseek.com/quick_start/pricing/)、
  [Chat Completion](https://api-docs.deepseek.com/api/create-chat-completion/) 与
  [Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode/) 重新核对并冻结。

## 终态组装修复

第 40 个响应及全部静态证据写入成功后，终态报告因通用 verifier 把全局实验账本中的旧 D1 行也计入
本批而 fail closed。修复前冻结 `m1-star50-price-volume-v1-terminal-recovery-001`，绑定故障时账本与
旧 D1 哈希，只允许按精确 `protocol_id` 过滤共享实验账本。

修复提交 `eff0bea78d81a4c9272b01d45a4501f4ba5d7626` 通过混合协议和同协议孤儿行 fixture；恢复镜像只从
既有 40 份证据组装报告，新增 provider 调用 0，候选/指标/账本/产物均未改变。诊断时曾意外显示部分
公式文本，但修复提交推送前未查看 RankIC、覆盖或排序，留痕见冻结附录。

## 完整性与幂等

- attempt 40 行与全局 experiments 中本 protocol 40 行严格一一对应；同 protocol 孤儿行继续 fail closed。
- transport 80 行，严格为 40 个 STARTED + 40 个 COMPLETED；静态证据含 40 份原始响应和 14 份发现产物。
- 134 个证据文件、1,258,619 bytes，证据束 SHA-256
  `f931a9b219172a2d5236d8c96a557bc5c9317f150b0738a0391f2712bda4305a`。
- 终态报告 SHA-256
  `5cdf09ca316eeb58a9613cf2c4596c0a1fdc2e0c6fd5af49d8974a10f68c45cb`。
- 无密钥复跑返回 `idempotent_reuse=true / external_api_calls_this_run=0`；attempt、transport、
  experiments 和报告四哈希前后不变。

## 数据、秘密与生产边界

- 数据快照 `f6ad4566...4c5`，577 个发现交易日、28,850 成员日、每日严格 50 只；`.BJ=0`。
- `sealed_validation_read=false`、`stress_periods_read=false`、`g1_run=false`、
  `model_or_portfolio_run=false`。
- DeepSeek 密钥只从项目内 Git 忽略的 `.env` 注入首次临时容器；没有写入镜像、Git、账本、报告或日志；
  终态恢复和幂等复跑均未注入密钥。
- scheduler 始终保持容器 `fd8e96152b53`、镜像 `sha256:de87ec74...0261`、原创建时间和 healthy，未重启。

## 验证

- 修复前宿主全仓 424 PASS；Ruff、compileall、pip check、Compose 与 diff-check PASS。
- 执行前最终镜像 M1 专项 18 PASS、release manifest 与依赖 PASS；发现输入断网零调用预检 PASS。
- 结果账本满足 append-only；旧 D1 尝试/传输与因子准入账本哈希保持不变。

## 下一阶段

如继续，应另立 M1-2：仅对已锁定 Top2 做独立的经济解释、数据泄漏与表达式稳定性审查。审查通过后
才允许另立结果前协议解封 2023-2025 验证窗并运行既有 G1；不通过即停止，不递补第 3 名、不改式、
不追加候选。当前不得接模拟仓、Web 结果页、前瞻或生产。

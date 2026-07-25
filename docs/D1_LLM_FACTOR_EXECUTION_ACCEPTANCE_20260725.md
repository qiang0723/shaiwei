# D1-2B 首批真实 LLM 因子提案生成验收（2026-07-25）

## 结论

`d1-llm-dsl-v1-batch-001` 已完成恰好 40 份 DeepSeek 完成响应和冻结发现期
评价，机器终态为：

- `completed_response_exact_gate=true`
- `cost_gate_pass=true`
- `d1_2b_verdict=GO_D1_3_REVIEW`
- `strategy_effective=NOT_EVALUATED`
- `production_authorization=none`

这表示 D1-2B 的生成、发现期筛选和证据工程通过，可以另立 D1-3 人工经济
解释闸；不表示因子有效，不授权 W1–W6、G1、前瞻或生产。

机器可读摘要为 `config/d1_llm_factor_execution_manifest_v1.json`。原始请求、
完整响应和发现期证据保存在项目 `data/` 忽略区；Git 只提交脱敏摘要和追加式
审计账本。

## 数量与费用

- 完成响应：40/40，全局序号 1–40 连续；
- 发现期完成：36；协议内拒绝：4，其中重复 AST 2、DSL 沙箱拒绝 2；
- 原始响应产物：40；transport 完成事件：40/40；
- 实际估算费用：`0.076626207 USD`；
- 单批硬熔断：`1 USD`，通过；D1 总授权：`10 USD`；
- 未用余额不授权追加批次。

机械 Top2 均来自 `volatility_range` 主题，attempt 分别为
`6ade2d0f6d103613`（全局序号 18）和 `3bf9d418202afc20`（全局序号 23）。
本验收不披露公式或发现期 RankIC，也不把机械排序解释为经济有效性。

## 控制流恢复

首次运行在第 1 份响应完成后暴露两条工程缺陷：独立提案错误拒绝已有同主题
历史，以及部分批次恢复会从序号 1 重走。程序在第 2 个请求前 fail closed；
不存在重复调用或计费不确定性。

恢复前新增并推送
`config/d1_llm_factor_execution_recovery_v1.yaml`，锁定首份响应、三份账本字节
前缀和四类首份产物，仅允许修复上述两条控制流。恢复镜像
`shaiwei:d1-live-v1-r1` 从序号 2 完成剩余 39 份；首份响应继续计数且未重发。
完整说明见 `docs/D1_LLM_FACTOR_EXECUTION_RECOVERY_20260725.md`。

## 完整性与幂等

- attempt 账本 40 行，与 experiments 总账的本 release 行 40:40 一一对应；
- transport 账本 80 行，严格为每个 attempt 一条 STARTED 和一条 COMPLETED；
- 静态证据：40 份 raw、40 份 provider response、40 份 manifest、36 份
  discovery，共同纳入 160 文件证据束；
- 证据束 SHA-256：
  `f769fa1aae90bfc9f8f49b070a22e37a078fdab7754a585f9a4f674fc9cee07c`；
- run report SHA-256：
  `70cd8160c956513537a885a4a5f2e65b72d55c0d3371a46b3e208f370e8949e6`；
- 完成后以无密钥、`network none`、只读文件系统重放，得到
  `idempotent_reuse=true`、`external_api_calls_this_run=0`；重放前后证据束哈希
  完全相同。

## 数据与研究边界

- 只使用结果前冻结的 2016-06-01—2018-12-31 发现期；
- `W1_W6_read=false`、`stress_periods_read=false`、`g1_run=false`；
- 没有读取前瞻结果，没有生成生产信号，没有修改模型门槛；
- 40 次中的格式、重复或沙箱失败均计 N，不递补；
- D1-3 尚未授权，不得查看 W1–W6 或运行 G1。

## 密钥与生产隔离

- DeepSeek 密钥仅存项目 `.env`，文件权限 `0600`，并受 `.gitignore` 排除；
- 密钥未写入镜像、源代码、账本、报告、日志或 Git，只注入一次性 live 容器；
- 因密钥曾由用户在对话中明文提供，建议本次任务完成后在 DeepSeek 控制台
  轮换，项目 `.env` 只保存轮换后的新密钥；
- 生产 scheduler 容器 ID、镜像 ID 和创建时间前后完全相同，最终
  `running/healthy`；未修改或重启生产 scheduler。

## 验收前验证

控制流恢复提交前：全仓 `260 passed`，专项 `57 passed`，随后 staged 脱敏、
append-only 与 live 恢复专项 `26 passed`；Ruff、compileall、pip check、Compose
和 diff-check 全部通过。终版账本和验收文档仍需在提交前重跑同等级门禁。

## 下一步

如继续，必须另立 D1-3 目标：只对机械 Top2 做人工经济解释与数据泄漏审查，
冻结后才允许执行既有 `g1-v1`。D1-3 不通过即停止，不递补第 3 名、不调门槛、
不追加候选；无论结果如何都不自动进入生产。

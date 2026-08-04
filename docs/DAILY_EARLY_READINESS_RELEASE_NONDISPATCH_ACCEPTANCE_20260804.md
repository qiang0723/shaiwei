# 日增量自然运行与早探测发布未派发验收

> 日期：2026-08-04（Asia/Shanghai）
>
> 自然运行裁决：`PASS_WITH_NOTIFICATION_WARN`
>
> 发布守护裁决：`AUTOMATION_DISPATCH_NOT_OBSERVED`
>
> 生产状态：`OLD_RELEASE_HEALTHY_CANDIDATE_NOT_PROMOTED`

## 1. 权威结论

2026-08-04 的日增量、影子信号、次日开盘对账、Top30/Top20 模拟仓、独立重放和机器验收均已完成。
核心任务没有失败；Top20 开始通知首次遇到 `NETWORK_SSLEOFError`，同一逻辑消息第二次投递恢复，故整链
只能表述为 `PASS_WITH_NOTIFICATION_WARN`，不能写成无告警全绿。

日期绑定的 `daily-early-readiness-release-guard-20260804` 没有产生 START/PROMOTE/ROLLBACK 审计，
生产仍运行旧 release，候选没有提升。项目内没有可证明 Codex 应用侧派发原因的证据，因此只分类为
`AUTOMATION_DISPATCH_NOT_OBSERVED`，不推断为守护代码失败或日跑批失败。20260804 协议已经过期，禁止
改日期后补执行或静默重写。

## 2. 日增量与数据证据

- `daily_runs`：run `79ab7807ff33`，交易日 `20260804`，状态 PASS；数据快照
  `572099a7dc2473cbf23035d9b29429310974d8d376a08ed74258a00a98d6f58e`。
- 实际新增 8 个不可变原始批次，共 21,158 行；逐文件 SHA-256 与 `ingest_batches` 账本完全一致，
  实际读取 `ts_code` 复核 `.BJ=0`。`ingest_batches.csv` 终验哈希为
  `418aa1d6d271c421df9c9b71b9b4e37085953de33790ca26172e5df83f31c9e9`。
- 哨兵 `logs/sentinels/20260804T114118.843549Z.json`：S1—S9 PASS，S10
  NOT_APPLICABLE；无人工修数。
- 影子 run `acbca97d68f2` PASS，信号按时、非调仓日；其代码快照仍为旧生产
  `4e5244b6...82708`，这同时证明候选没有参与本次自然运行。
- `20260803 → 20260804` 开盘对账 PASS：30 个目标、0 订单、0 成交、换手与预计成本均为 0，平均
  绝对开盘偏差 `1.6931%`；产物 SHA-256
  `4564f16ecd1690c80c4b22b9b9c2827a7aec05500c9ca8e4bb7b0a56d3d6960a`。

## 3. 双模拟账户与通知

| 账户 | 当日产物 | FORWARD 观察日 | 净资产 | 独立重放/机器验收 |
|---|---|---:|---:|---|
| Top30 `model_baseline` | `691987e0...e89f` | 9 | 472,591.75 RMB | PASS / PASS |
| Top20 `model_top20` | `26de5b7f...afec` | 7 | 465,895.64 RMB | PASS / PASS |

两账户当日均为非调仓日，订单和成交为 0；全量账本重放中 `.BJ` 事件为 0。飞书文件共 10 行：9 行首次
PASS；Top20 `paper_top20_cycle_started` 首次为可重试网络失败，第二次 PASS 且 `recovered=true`，完成
通知首次 PASS。通知文件终验哈希为
`534817dc58109b698c643bd87dd33bb73bef47019966981a361e36c3a6759b2d`。

## 4. 幂等与不可变性

自然整链完成后，在同一受控生产容器中执行一次 `scheduler --once`：影子返回 NOOP、Top30 返回 NOOP、
Top20 返回 NOOP；两个账户的独立重放和机器验收仍 PASS。执行前后 7 个追加式账本、当日通知、两账户
当日产物和当日信号文件的物理 SHA-256 全部不变，证明零重复追加、零覆盖和零重复通知。

## 5. 发布未派发证据与下一步

- release 审计仍为 24 行，tip 仍为候选 BUILD_PASS 的
  `aa64d960d64be6d403b53b9018a8a1cb00f25be2a8c46bc9f35e9dd9b48ee05f`。
- current 仍是 `shaiwei:scheduler-4e5244b6b02739dd`，image ID
  `sha256:722f63de15932cb2698e82db7c0140f02921f27f126e1c0235ca62e0a1213b76`，代码快照
  `4e5244b6b02739dd209a9b01ea715c43ed9a874a7014156e20cf364f06a82708`；scheduler healthy。
- 候选 `shaiwei:scheduler-0640574ba7353c3e` 保持未提升状态。

下一步只能另立绑定 20260805 的恢复协议，以本次 Top30/Top20 产物作为新的最新 FORWARD 边界；协议
须先行提交推送，再将守护默认配置切到新版本。不得覆盖 v1、补造 20260804 执行证据或手工补跑数据。

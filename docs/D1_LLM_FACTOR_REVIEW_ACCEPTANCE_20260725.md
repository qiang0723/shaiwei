# D1-3A Top2 盲态对抗复核验收

## 1. 结论

D1-3A 按结果前提交 `12b3101a21a6695828703a8962639c4a17e4e4c9` 完成恰好 8 份
DeepSeek 对抗复核：8/8 JSON 与 schema PASS，8 个 HTTP 请求均一次完成，无重试、无计费不确定性，
实际估算费用 `$0.01472214`，低于专项硬上限 `$0.25`；连同 D1-2B，D1 累计估算费用为
`$0.091348347`，仍不把未用额度解释为新调用授权。

机器终态为：

- `review_execution_gate=GO_INDEPENDENT_HUMAN_GATE`；
- `human_adjudication_complete=false`；
- `strategy_effective=NOT_EVALUATED`；
- `production_authorization=none`。

这只证明对抗复核证据完整，不能解释为候选通过，更不授权读取 W1—W6、运行 G1 或接入生产。

## 2. 八份建议的审计摘要

四份返回 `BLOCKER_FOUND`，四份返回 `NO_BLOCKER_FOUND`：

- 候选 `6ade2d0f6d103613`：构造有效性与结构冗余角色报阻断；经济符号与 PIT/次日开盘时钟未报阻断。
- 候选 `3bf9d418202afc20`：构造有效性与经济符号角色报阻断；PIT/次日开盘时钟与其自身冗余角色未报阻断。

主要对抗意见与结果前审查点一致：两个表达式外层均计算“日内区间代理的 20 日时间序列离散度”，不能
把它们表述成区间波动率水平或 Parkinson 估计量；候选 23 的原始草稿用“更高风险补偿”解释冻结的
负向方向，逻辑相反。两份冗余复核互相冲突：一份认为两式属于近似同一暴露，另一份认为 close
归一化带来不同构造。因此它们只是待独立人工闸复核的证据，不是主窗口裁决。

主窗口在协议冻结前已误见候选 18 的发现期 RankIC 与覆盖率，故按
`docs/D1_LLM_FACTOR_REVIEW_PROTOCOL_20260725.md` 永久退出最终人工闸。已见数值没有进入任何请求、
本文或可提交账本；候选 23 的发现期数值以及两者的 W1—W6、压力期、G1、前瞻和生产结果仍未查看。

## 3. 调用、费用和不可变证据

- 协议 SHA-256：`ad5ab9720198a2bab41912391a25cb09c5ca38c7accb37bef3904824c943f6da`；
- 执行 release SHA-256：`fd5eb02c288256e86ad0df85d90ee3411106a40a7dd6038eea7b017acc61fcdb`；
- prompt SHA-256：`0ac012fecc596624bc3e2617f2e41f7d7d012d7f9edeab4f6edd88432546cc4a`；
- 镜像：`shaiwei:d1-review-live-v1`，ID
  `sha256:a2d192004a451ad66768a5cda303fbaa91c73e8b81bb8aadbe7d52c1dc4c3458`；
- 镜像内嵌 Git：`12b3101a21a6695828703a8962639c4a17e4e4c9`；
- 受控代码快照：`0a6f1f305db8c8943c6c27f27a7d5a0500b231c876ca79f1b895841f1632c101`；
- 运行报告 SHA-256：`2e08e2b3909a25ceba36616a538f16437b402d838d01e5ff8efc9850a119f8b0`；
- review ledger：9 行，SHA-256
  `9029ea65490711dbd6bddc592d2f3116ad1b7e811059cad926caca283d13e280`；
- transport ledger：17 行，SHA-256
  `df7b39a7dd47fe5f6afc01e8217187d477a71c9a0827fd1b24b442fe1eafba58`；
- 忽略区共 33 个文件、约 264 KiB；规范化整束 SHA-256
  `ea5213086dd981943c11c859e5cdb05554c7c972ecaa248852066a4747ca38e6`。

静态重哈希确认 8 份 request、8 份 provider response、8 份脱敏 raw envelope、8 份 review manifest 和
8 条 review 记录一一对应；transport 为 8 组 `STARTED → COMPLETED`，没有 retry/error 事件。

## 4. 幂等、安全与生产隔离

同一镜像随后在 `network=none`、无 `DEEPSEEK_API_KEY`、只读根、仅 D1-3 专属路径可写的条件下复跑：

- `idempotent_reuse=true`；
- `external_api_calls_this_run=0`；
- 两份 ledger、运行报告和 33 文件证据束的行数与 SHA-256 全部不变。

镜像环境中不存在 DeepSeek key；项目 `.env` 继续为 Git 忽略、权限 0600，容器只接收唯一
`DEEPSEEK_API_KEY` 变量，不加载 Tushare 或飞书凭据。请求禁词门和终版报告同时证明未发送发现期数值、
W1—W6、压力期、G1、收益、持仓或生产结果。

生产 scheduler 在施工前后均为原容器 `fd8e96152b53`、原镜像
`sha256:de87ec740981166b032b394fb256a978acdc8d35e999a369f1debc3466aa0261`、原创建时间
`2026-07-24T12:25:27.362813588Z`，状态 running/healthy；未重建、未重启、未改生产挂载或配置。

结果前全仓测试 272 PASS；D1-3 专项、append-only 与 secret hygiene 27 PASS；Ruff、compileall、
`pip check`、Compose 解析与 `git diff --check` 均 PASS。

真实追加完成后，预执行测试中“新账本必须只有表头”的一次性断言按预期失效。后置修正只把该断言改为
“允许 0/0 的预执行态或 8/16 的完整终态，拒绝任意中间态、重复 ID、非连续序号和非
`STARTED → COMPLETED` 序列”；未修改 runner、协议、prompt、release、候选、响应、账本或忽略区
产物，未再次联网。原执行镜像、代码快照和所有运行证据继续作为 D1-3A 唯一真身。

## 5. 下一道闸

D1-3A 到此完成并停止。若继续，用户须明确授权一个独立且结果盲态的审查子任务；它只能读取两条公式、
冻结方向、非权威解释草稿、结构冗余规则和上述无业绩对抗意见，不能接触发现期或后续效果数字。它需先
形成可审计的人工解释/拒绝记录；只有通过者才允许另行冻结 D1-3B G1 输入并运行不变 `g1-v1`。

未获该授权前，不读取 W1—W6、不运行 G1、不递补第三名、不改公式/方向/窗口、不生成新候选。

# Top20 模拟账户生产切换启动验收（2026-08-03，UTC+8）

协议：`paper-top20-release-guard-20260803`

## 1. 权威结论

机器裁决为 **START_PASS**：已批准的 Top20 scheduler 候选在冻结的 2026-08-03 16:05—19:00
窗口内完成一次受控启动，实际 scheduler 已切换到候选镜像并保持 healthy。

本结论只证明生产发布切换完成，不等于 20260803 日增量、Top30、Top20 或飞书链路已经通过，也不
构成 Top20 优于 Top30、策略有效、实盘交易或真实委托授权。首个 Top20 自然 `FORWARD` 必须等待
19:30 冻结调度自然产生后另行验收，禁止手工补跑冒充自然证据。

## 2. 触发事实

- 16:05 计划任务未留下守护输出或发布审计；17:38 复核时发布审计仍为 22 行，最后一条生产
  `START_PASS` 仍是 2026-07-24，scheduler 仍为旧容器 `fd8e96152b53...a5adbb`。因此只能继续分类为
  `AUTOMATION_DISPATCH_NOT_OBSERVED`，不猜测 Codex 应用侧未派发的具体原因。
- 用户在本主任务明确要求继续可执行下一步后，17:39 仍处于冻结窗口内；主控只执行一次既定入口
  `make docker-release-guard`，没有改协议、代码、候选、日期、门槛或数据，也没有重试。
- 守护在 Docker 变更前重新验证工作树干净、`HEAD=origin/main`、发布审计链、候选身份、旧容器健康、
  最新 Top30 `FORWARD` 和跨快照唯一新交易日，全部 PASS 后才调用一次 `start_current()`。

## 3. 启动前门禁

| 门 | 实际证据 | 结论 |
|---|---|---|
| 时间窗口 | `2026-08-03T17:39:31+08:00` | PASS |
| 最新 Top30 执行日 | `20260731` | PASS |
| 唯一新增交易日 | `20260803` | PASS |
| readiness | `CROSS_SNAPSHOT_WITH_NEW_DATA` | PASS |
| 旧镜像 | `sha256:de87ec740981166b032b394fb256a978acdc8d35e999a369f1debc3466aa0261` | PASS |
| 旧代码快照 | `eb8e752132ac1fbe6a9557d26b4c7a65df36f6169d617b6e1e10db88d46b7fbd` | PASS |
| 旧容器健康 | `fd8e96152b53...a5adbb / healthy` | PASS |

## 4. 实际启动身份

- 容器：`183b8c6c5eddac951d9d9b3cfa58c0d38e351d5b94ee1b1d52b9b8059c23dd3b`；
- 镜像：`sha256:722f63de15932cb2698e82db7c0140f02921f27f126e1c0235ca62e0a1213b76`；
- 镜像 Git：`210af4dab33c85b38c05b28f56c176b7970c41db`；
- 代码快照：`4e5244b6b02739dd209a9b01ea715c43ed9a874a7014156e20cf364f06a82708`；
- 只读根文件系统：`true`；挂载目标仅 `/workspace/data`、`/workspace/ledger`、`/workspace/logs`；
- 创建时间：`2026-08-03 17:39:34 +0800`；定向复核状态：`healthy`。

发布审计新增且只新增一条 `START_PASS`，记录 SHA-256 为
`6d227e7f2b7f689b5228ed5576a4ac3682f0b4ce6f2c4abbeef10386757ea0f2`，前记录 SHA-256 为
`48b40297b7dd06b5d03c6d48f18717119de82921c310ba1a61be3dd56f794d9c`；审计由 22 行增至 23 行。
启动时仓库 `HEAD=origin/main=cfdba45a027b26d1e4ca20f94e7fe02e07e97ae3`。

## 5. 后续硬门

1. 不手工运行日增量或模拟仓；等待候选按冻结的 19:30 口径自然串行执行 Top30、Top20。
2. 跑批完成后独立核验 scheduler 整日状态、真实原始批次 `.BJ=0`、S1—S9、S10、不可变信号、
   Top30 与 Top20 账户日、各自重放/前瞻验收、飞书开始/完成、幂等和零人工修数。
3. 只有 Top20 首个自然 `FORWARD` 独立 PASS 后，才允许在后续另一交易日评估 16:00 早探测候选；
   不把发布切换与早探测提升合并为一个变量。

# P3-2A 数据质量与系统运行只读查询协议（结果前冻结）

> 冻结日期：2026-07-25（Asia/Shanghai）
>
> 协议：`p3-web-operations-v1`
>
> 状态：`FROZEN_BEFORE_IMPLEMENTATION`

## 1. 目标与边界

P3-2A 只施工数据质量、系统运行和通知投递三组只读查询，使后续 Web 页面能回答：

1. 最新已登记交易日的数据是否足以用于信号；
2. S1—S10、北交所排除、批次身份和数据快照是否一致；
3. 日增量、哨兵、对账、信号和模拟仓各步骤是否完成，是否曾失败后恢复；
4. 飞书某一逻辑消息的每次投递是否成功、重试或恢复；
5. 运行时使用的最后一份已登记 release 身份是否和信号代码快照一致。

本阶段不施工页面，不修改 scheduler、生产镜像、策略、模型、信号、G0—G9/C0、原始数据或
任何追加式账本；不接券商、不开放远程访问、不提供写接口、任意路径、SQL、日志搜索或导出。

## 2. 三组冻结契约

### 2.1 `data_quality_summary(as_of)`

端点：`GET/HEAD /api/v1/data-quality`。

返回字段至少包括：

- 身份：`as_of/data_snapshot_sha256/code_snapshot_sha256/sentinel_report_sha256`；
- 日增量：终态、尝试数、失败数、恢复标识、批次数、市场行数和 operator；
- 批次链：截止该日终态 `finished_at` 的登记批次数、登记总行数、来源 API 数、规范化账本快照
  重算值、与 `daily_runs.data_snapshot_sha256` 的一致性；
- 当日新增批次：仅返回 `batch_id/source_api/row_count/content_sha256/ingest_time`，不得返回
  `params_json`、本地路径或原始记录；
- S1—S10：每项状态、脱敏指标和异常计数；不返回异常逐行证券明细；
- `.BJ`：通过日增量硬校验、S1 排除计数以及信号证据共同表达，任何 Web 返回证券出现 `.BJ`
  仍立即失败；
- 口径声明：`raw_parquet_rehash_status=NOT_EVALUATED`。

批次身份链按 `ingest_time <= daily_run.finished_at` 截止，只使用
`batch_id/source_api/params_json/row_count/content_sha256` 规范化重算，必须精确等于日运行登记的
`data_snapshot_sha256`。查询不会挂载或逐字重哈希 `data/raw`；因此只能声称“登记身份链一致”，
不得声称“查询时重新验证了全部原始文件”。

哨兵报告必须同时满足：路径在 `logs/sentinels/` 白名单内；S1—S10 恰好各一项；
`required_failures` 与明细一致；报告的代码/数据快照等于 PASS 影子运行；报告结果与不可变信号中
绑定的 `sentinel_results` 完全一致。否则返回 `EVIDENCE_MISMATCH`，不得降级展示旧值。

### 2.2 `system_run_summary(as_of)`

端点：`GET/HEAD /api/v1/system/runs`。

固定步骤为：`daily_increment → sentinels → next_open_reconciliation → shadow_signal →
paper_cycle → paper_replay`。每一步返回领域状态、是否适用、尝试数、失败数、恢复标识、首个错误
类型、终态时间和证据引用。不得把最终 PASS 覆盖早先失败。

状态规则：

- 任一适用步骤的最新终态 FAIL，综合为 `FAIL`；
- 终态全部 PASS，但存在早先失败或 `daily_scheduler_cycle_failed` 事件，综合为 `WARN`；
- 尚未到期或没有业务上应有的步骤，显示 `NOT_DUE/NOT_APPLICABLE`，不算失败；
- 必需步骤缺证据且无法证明“不适用”，显示 `NOT_READY`；
- 核心运行状态和通知投递状态永远分列。

release 审计链必须逐条验证 `previous_record_sha256/record_sha256`。只返回运行完成前最后一个
`START_PASS` 的镜像、代码快照、Git 身份、只读根和挂载目标，并与 PASS 影子代码快照交叉核对。
这证明“已登记启动身份”，不等于实时 Docker inspect。查询服务禁止挂 Docker socket，故
`live_container_identity_status=NOT_EVALUATED`。

`logs/scheduler/health.json` 只作为当前记录心跳返回原始状态、detail 和 `updated_at`，不使用查询
时钟推导健康度，不暴露 PID，也不把可变心跳放大为历史运行裁决。

### 2.3 `notification_delivery_summary(message_id)`

端点：`GET/HEAD /api/v1/notifications/{message_id}`；`message_id` 必须为 16 位小写十六进制。

跨脱敏 `feishu_YYYYMMDD.jsonl` 精确查找同一逻辑消息，按 `delivered_at/attempt` 返回全部尝试，
只允许配置列出的九个字段。响应必须保留失败、`retryable`、后续 `recovered` 和最大尝试数；
消息正文、业务字段、Webhook、签名、环境变量和原始异常文本永不返回。找不到返回 `NO_DATA`，
重复 attempt 身份或非法状态返回 `EVIDENCE_MISMATCH`。

## 3. 权威输入白名单

固定读取：

- `ledger/daily_runs.csv`
- `ledger/ingest_batches.csv`
- `ledger/shadow_runs.csv`
- `ledger/shadow_reconciliations.csv`
- `ledger/paper_runs.csv`
- PASS 影子运行登记的 `data/shadow/signals/` 信号文件
- PASS 影子运行登记的 `logs/sentinels/` 报告
- `logs/notifications/feishu_YYYYMMDD.jsonl`
- `logs/releases/scheduler_releases.jsonl`
- `logs/scheduler/health.json`

不得读取 `.env`、`data/raw`、Parquet、模型文件、Docker socket、Git 元数据、系统进程表或项目外
文件。绝对路径、`..`、符号链接、白名单外证据和查询期间变化全部 fail closed。

## 4. 原子性、脱敏与资源上限

每次查询先固化输入集合、大小和修改时间，再读取与验证，最后复核；变化时最多重试两次。
相同参数与相同证据必须产生相同 `snapshot_id`、ETag 和业务响应。`generated_at` 取权威证据中
最新时间，不使用查询时钟制造变化。

单响应最大 1 MiB；当日新增批次最多 32 条，单消息最多 16 次投递，单步骤最多 64 次尝试，哨兵
脱敏指标规范化后最多 64 KiB。越限返回 `CONFLICT`，不得截断后冒充完整。

HTTP 继续只允许 GET/HEAD、关闭文档、`Cache-Control: no-store`、使用现有脱敏错误包络。

## 5. Docker 隔离

复用 P3-0 `web-query`，只新增 `logs/sentinels`、`logs/releases`、`logs/scheduler` 三个只读目录
挂载；不新增宿主端口、不挂 `data/raw`、不加载 `.env`、不挂 Docker socket或项目根目录。Web UI
本阶段不代理新端点，待 P3-2B 页面目标再显式加入前端 allowlist。

## 6. 通过条件

1. 本协议与机器配置提交、推送早于实现和真实验收；
2. 批次前缀身份链重算与日运行快照精确一致，篡改、重复批次、坏参数和坏哈希均 fail closed；
3. S1—S10 和信号绑定完整，缺项、重项、状态冲突、报告换包和 `.BJ` 均 fail closed；
4. 运行步骤保留失败—恢复链，通知投递不改变核心结论；
5. release 哈希链、运行代码身份和只读挂载核对通过，实时容器身份保持 `NOT_EVALUATED`；
6. notification 查询完整保留每次尝试且不泄露正文、路径或凭据；
7. API 方法、错误脱敏、响应上限、稳定快照和 Docker 只读挂载测试通过；
8. 真实只读查询只报告已有证据，不运行采集、哨兵、scheduler、模型或回测；
9. 全仓测试、Ruff、compileall、依赖、Compose、脱敏和 `git diff --check` 通过；
10. scheduler 容器、镜像、代码快照和健康状态施工前后不变。


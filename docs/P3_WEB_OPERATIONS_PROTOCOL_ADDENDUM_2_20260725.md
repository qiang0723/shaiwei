# P3-2A 结果前冻结补遗二：哨兵时钟语义

> 日期：2026-07-25（Asia/Shanghai）
>
> 适用协议：`p3-web-operations-v1`
>
> 状态：`FROZEN_BEFORE_IMPLEMENTATION`

## 发现

首份补遗冻结后继续核对真实 `20260724` 信号、哨兵报告和影子账本，确认信号中的
`data_complete_at` 来自日增量完成时刻；哨兵在随后构建前瞻 qlib/信号的影子任务内部运行，故报告
`generated_at` 合法地晚于 `data_complete_at`。二者不应相等。

## 权威修正

首份补遗第 2 条“报告 `generated_at` 必须精确等于信号 `data_complete_at`”作废，改为全部满足：

1. `daily_run.finished_at == signal.data_complete_at`；
2. `shadow_run.started_at <= sentinel.generated_at <= signal.generated_at`；
3. `signal.generated_at <= shadow_run.finished_at`；
4. 上述时间全部必须含时区；
5. 报告、信号与 PASS 影子运行的代码/数据快照仍须三方一致。

该修正只纠正既有时钟含义，不放宽未哈希绑定的 WARN，不改查询范围、状态门或生产代码。


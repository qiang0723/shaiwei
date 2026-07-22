# P0-R 飞书通知健壮性复核

> 裁定时间：2026-07-22（Asia/Shanghai）
>
> 结论：**回归 PASS，P0.5 施工入口打开；生产投递继续观察。**

## 触发证据

- 2026-07-21 的 `daily_catchup_started` 出现一次 `NETWORK_TimeoutError`，之后 4 个真实事件投递 PASS。
- 2026-07-22 的 `daily_catchup_passed` 出现一次 `NETWORK_TimeoutError`，之后 3 个真实事件投递 PASS。
- 两次失败均未影响日增量、门禁、信号或对账结果，也未覆盖原日志；但连续两个交易日发生，已不再按单次偶发事件忽略。

## 冻结语义

- 单一逻辑通知最多尝试 3 次，退避为 1 秒、2 秒；不会无限重试或阻塞核心流水线。
- 只重试瞬时网络/OSError、响应解码异常，以及 HTTP 408、425、429 和 5xx；非法 Webhook、配置/类型错误及飞书明确返回的 API 拒绝不重试。
- 每次尝试都向 `logs/notifications/feishu_YYYYMMDD.jsonl` 追加一行。首次 FAIL 永不删除；若后续 PASS，则 PASS 行以 `recovered=true` 明确表示重试恢复。
- 同一次 `send` 的正文、事件时间和 `message_id` 固定，重试只刷新签名时间。日志记录 `attempt`、`max_attempts`、`retryable` 和 `recovered`。
- `message_id` 由脱敏后的事件、标题和业务字段稳定生成；同一业务身份可以被识别和分组，但不包含 Webhook、签名或 Token。
- 飞书自定义机器人没有被本项目认定为提供服务端幂等键或恰好一次投递。超时可能发生在服务端已接收之后，因此重试仍可能出现同 ID 的重复正文；该风险通过正文 ID 和逐次日志显式暴露，不伪称绝对去重。
- 通知最终 FAIL 仍不得改变日增量、影子信号、对账或研究任务的退出语义；任务状态和通知状态继续分开。

## 回归证据

- 瞬时超时后第 2 次成功：日志严格为 `FAIL → PASS`，消息正文和 ID 一致，最终 `recovered=true`。
- HTTP 503 持续失败：严格执行 3 次后停止，退避为 1 秒、2 秒，三条失败证据均保留。
- 飞书 API 明确拒绝：只尝试 1 次，不对永久错误盲目补发。
- 非官方 Webhook：网络调用前拒绝，日志不泄露 URL。
- 仓库全量测试：167 项 PASS。
- Ruff、compileall、`pip check`、`git diff --check` 全部通过；凭据仍只来自本地 `.env`。

本次没有人为制造真实网络超时，也没有向生产群额外发送重复测试消息。后续 Docker scheduler 的自然投递用于生产观察；若同一 `message_id` 出现 FAIL 后 PASS，可直接证明真实重试恢复。

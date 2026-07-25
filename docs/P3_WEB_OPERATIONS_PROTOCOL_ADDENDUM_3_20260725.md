# P3-2A 实现前提交补遗三：通知 schema 代际

> 日期：2026-07-25（Asia/Shanghai）
>
> 适用协议：`p3-web-operations-v1`
>
> 状态：`FROZEN_BEFORE_IMPLEMENTATION_COMMIT`

## 发现

首次真实只读查询在返回任何业务结果前 fail closed：2026-07-22 通知健壮性升级之前的脱敏飞书
记录没有 `message_id/attempt/max_attempts/recovered/retryable`，升级后记录才使用当前稳定 schema。
旧记录是已知历史格式，不是当前通知证据损坏。

## 权威兼容规则

1. 文件日期早于 `20260723` 且 `message_id` 为空的记录定义为
   `LEGACY_UNADDRESSABLE_NOTIFICATION`；
2. 旧记录不得合成 ID、不得按消息查询、不得混入当前重试/恢复统计；
3. 系统运行响应必须返回 `legacy_unaddressable_attempt_count`，并继续把相关文件哈希纳入证据切片；
4. 文件日期自 `20260723` 起，缺失或非法 `message_id`、字段不完整仍为 `EVIDENCE_MISMATCH`；
5. 任何非空但格式非法的历史 `message_id` 也立即失败；
6. `notification_delivery_summary(message_id)` 只查询当前九字段完整 schema，不把旧记录当成“无失败”。

该补遗只解决既有 schema 迁移，不覆盖失败尝试，不更改 2026-07-23 以后冻结的通知语义。


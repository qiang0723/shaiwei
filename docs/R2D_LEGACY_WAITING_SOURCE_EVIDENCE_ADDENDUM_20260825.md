# R2D 旧生产等待源证据勘误

原 R2D 协议推送后继续核对实物，确认当前旧生产 snapshot
`4e5244b6b02739dd209a9b01ea715c43ed9a874a7014156e20cf364f06a82708` 尚未包含 R2-1R0 scheduler
timeline 模块。要求旧容器证明“16:00 timeline 已闭合为 `WAITING_SOURCE`”因此不可观测，不能在工程中
假设它存在，更不能补造旧 timeline。

本勘误只替换该证据载体，不改变发布时机和裁决：

- Phase B 前读取旧容器真实维护的 `logs/scheduler/health.json`；必须为 `waiting_source`，`detail` 精确
  等于稍后冻结的唯一目标交易日，`updated_at` 必须是该交易日 UTC+8 16:00 之后；
- 同时确认旧 container/image/snapshot/HEAD 仍精确、healthy，且没有进入 daily/shadow/paper 正式周期；
- timeline 验收从候选启动后的第一个自然 cycle 开始；不得为旧版本回填或合成 timeline。

原协议其他身份、两阶段切换、四挂载、顺序 legacy 恢复、首个自然日和重新授权要求全部不变。本勘误
发生在源码实现和执行 scope 之前，不读取策略效果，不授权 promote/restart 或生产运行。


# 日增量早探测生产发布守护协议

> 冻结日期：2026-08-03（Asia/Shanghai）
>
> 目标交易日：2026-08-04
>
> 协议：`daily-early-readiness-release-guard-20260804`
>
> 状态：`FROZEN_BEFORE_GUARD_IMPLEMENTATION`

## 1. 目标

在不手工触发日增量、不覆盖既有前瞻产物的前提下，于 2026-08-04 受控窗口把生产 scheduler 从已
完成 Top20 首个自然 `FORWARD` 的当前 release，单变量切换到已经通过静默等待补正工程门的候选。

本协议只授权实现与断网预执行守护；冻结提交推送后仍不得在 2026-08-03 晚间 promote、改 current、
启动或重启生产。真实执行只能发生在目标日窗口并再次通过全部机器门。

## 2. 冻结日期与窗口

- 项目内冻结 Tushare 交易日历确认：`20260803` 后首个开市日为 `20260804`，随后为
  `20260805/06/07/10`。
- 守护时区固定 `Asia/Shanghai`；窗口固定为 `2026-08-04 16:05:00`（含）至 `19:00:00`（不含）。
- 16:05 给 16:00 原 scheduler 首轮留下明确边界；19:00 截止为 19:30 硬兜底保留至少 30 分钟。
- 早于、晚于或日期不等于目标日均必须在任何 Docker/release 变更前失败关闭。

## 3. 精确身份

候选固定为：

- image：`shaiwei:scheduler-0640574ba7353c3e`；
- image ID：`sha256:85711ae0b4c3b19de1554f778cb0ff2ee10f5b1e962e2ef79e1d0953a6a5e79f`；
- code snapshot：`0640574ba7353c3eef888eac2f706a29606db728319d3717b7ecdfc25de40c40`；
- Git：`fa6c67ab541c19b056221303756d81ad98ee122e`。

切换前生产固定为：

- image：`shaiwei:scheduler-4e5244b6b02739dd`；
- image ID：`sha256:722f63de15932cb2698e82db7c0140f02921f27f126e1c0235ca62e0a1213b76`；
- code snapshot：`4e5244b6b02739dd209a9b01ea715c43ed9a874a7014156e20cf364f06a82708`；
- Git：`210af4dab33c85b38c05b28f56c176b7970c41db`。

候选已于补正工程门中 `BUILD_PASS`，本守护禁止重新 build 或替换镜像。

## 4. 前瞻边界

执行前必须同时确认：

1. Top30 `model_baseline` 最新 PASS 为 `20260731 → 20260803`，代码快照为当前生产快照，产物
   SHA-256 为 `ff8ddb0beb9e468611bdc527e3c0ee8c4dda08da3bef4ebd043328e91f671235`；
2. Top20 `model_top20` 最新 PASS 同为 `20260731 → 20260803`，代码快照相同，产物 SHA-256 为
   `f0c4eae56bd4f90bd3ea5578c014f8a024d2df9aa796b38e60b56e5de2c326fc`；
3. release readiness 必须为 `CROSS_SNAPSHOT_WITH_NEW_DATA`，且可用新交易日精确等于
   `["20260804"]`；没有新日、多个新日或任一账户已越过冻结边界均失败关闭。

## 5. 执行动作与恢复

1. 工作树必须干净，`HEAD=origin/main`，发布审计链 PASS，候选标签/运行时身份完全一致，当前生产
   release 与运行容器完全一致且 healthy。
2. 新鲜状态只允许恰好一次 `promote(candidate, start=true)`；不得先单独 promote、不得手工运行
   daily/shadow/paper，不得通过重复调用追到成功。
3. `release.promote(..., start=true)` 必须复用既有原子状态：启动失败先恢复旧 current 标签与 release
   state。守护随后必须再启动并验证旧 current，避免“状态已回滚但容器仍坏”这一半恢复状态。
4. 若进程中断后出现“candidate 已 promoted、旧 scheduler 仍在运行”的唯一可恢复中间态，只允许
   调用一次 `start_current()` 续接；失败则必须 `rollback(start=true)` 恢复旧生产。
5. candidate 已是运行中且 healthy 时返回 `ALREADY_ACTIVE`，不得再次 promote/start；其他混合身份
   一律 BLOCKED。
6. 成功只证明切换与隔离契约通过；不得在守护内等待数据、补跑、评价策略或宣称 16:00 SLA。

## 6. 工程验收门

- schema 必须禁止未知字段，并锁定日期、窗口、候选、旧生产、双账户证据和全部布尔要求；
- fixture 覆盖时窗、Git、审计、镜像、运行容器、双账户、唯一新日、fresh promote、already active、
  promoted-but-not-started 恢复、启动失败恢复旧生产及恢复失败双重上报；
- Docker/Git 只能定向读取非敏感字段，禁止完整 inspect、`.Config.Env` 或 `.env`；
- 全仓、Ruff、compile、依赖、三套 Compose、脱敏和断网只读 Docker 专项通过；
- 预执行只能得出 `GO_EARLY_READINESS_RELEASE_GUARD_PREEXECUTION_ONLY`，不代表已经生产切换。

## 7. 目标日切换后的验收

真实执行完成后仍须独立核验首次探测/就绪/正式完成时点、日增量整日 PASS、实际 raw `.BJ=0`、
S1—S10、信号、开盘对账、Top30/Top20、飞书、重放、幂等、零人工修数及生产身份。单日成功不得
外推为稳定 16:00—17:00 SLA。

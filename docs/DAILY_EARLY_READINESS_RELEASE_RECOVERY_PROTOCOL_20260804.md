# 日增量早探测生产发布恢复协议

> 冻结日期：2026-08-04（Asia/Shanghai）
>
> 目标交易日：2026-08-05
>
> 协议：`daily-early-readiness-release-guard-20260805`
>
> 状态：`FROZEN_BEFORE_RECOVERY_GUARD_ACTIVATION`

## 1. 背景与目标

`daily-early-readiness-release-guard-20260804` 已按原文永久过期。项目内没有它被派发或执行的证据，
2026-08-04 自然整链仍由旧生产 release 完成并通过，故旧日分类为
`AUTOMATION_DISPATCH_NOT_OBSERVED`，不是守护运行失败，也不是日增量失败。

本恢复协议只授权把既有守护的默认配置切到一个全新的日期绑定版本，在 2026-08-05 受控窗口内将生产
scheduler 从旧 release 单变量切换到已通过静默等待补正工程门的同一候选。它不是盲预注册：8 月 4 日
漏派发和自然运行结果已经可见；但候选、窗口、恢复状态机和验收门没有因结果而改变。

## 2. 冻结日期与窗口

- 项目内冻结交易日历确认 `20260805` 为 `20260804` 后首个开市日。
- 时区仍为 `Asia/Shanghai`；窗口仍为 16:05:00（含）—19:00:00（不含）。
- 早于、晚于或日期不等于目标日必须在任何 release/Docker 变更前失败关闭。
- 旧 v1 配置、协议、预执行验收和 8 月 4 日未派发验收均不得删除、改写或包装成成功执行。

## 3. 不变身份

候选保持：

- image `shaiwei:scheduler-0640574ba7353c3e`；
- image ID `sha256:85711ae0b4c3b19de1554f778cb0ff2ee10f5b1e962e2ef79e1d0953a6a5e79f`；
- code snapshot `0640574ba7353c3eef888eac2f706a29606db728319d3717b7ecdfc25de40c40`；
- Git `fa6c67ab541c19b056221303756d81ad98ee122e`。

切换前生产保持：

- image `shaiwei:scheduler-4e5244b6b02739dd`；
- image ID `sha256:722f63de15932cb2698e82db7c0140f02921f27f126e1c0235ca62e0a1213b76`；
- code snapshot `4e5244b6b02739dd209a9b01ea715c43ed9a874a7014156e20cf364f06a82708`；
- Git `210af4dab33c85b38c05b28f56c176b7970c41db`。

不得重建、改标签、替换候选或修改生产模型/信号/门禁。

## 4. 新的前瞻边界

执行前必须精确确认：

1. Top30 `model_baseline` 最新 PASS/FORWARD 执行日为 `20260804`，代码快照为旧生产快照，产物
   SHA-256 为 `691987e0fdc3cae0fed405d6d6e7eb9c50c1e49d0404a46f31de408be472e89f`；
2. Top20 `model_top20` 最新 PASS/FORWARD 执行日为 `20260804`，代码快照相同，产物 SHA-256 为
   `26de5b7fcaa0682e3e8d47a4c4120f685dbe8766b30189303f37d75a81abafec`；
3. release readiness 必须为 `CROSS_SNAPSHOT_WITH_NEW_DATA`，且可用新交易日精确等于
   `["20260805"]`；没有新日、多个新日、任一账户越过边界或身份漂移均失败关闭。

## 5. 冻结动作与恢复语义

- 工作树干净、`HEAD=origin/main`、审计链 PASS、候选运行时身份精确、旧生产容器 healthy 后，fresh
  路径只允许一次 `promote(candidate, start=true)`。
- 唯一可恢复中间态仍是“candidate 已提升、旧 scheduler 仍运行”，只允许一次 `start_current()`；
  candidate 已 active 且 healthy 时返回 `ALREADY_ACTIVE`，其他混合身份一律 BLOCKED。
- 启动失败必须重新读取状态并启动旧 current，或 `rollback(start=true)`；恢复后再次验证旧 release
  与旧 healthy scheduler，双重失败同时上报。
- 守护不得调用 daily/shadow/paper，不得手工等待数据或重复追成功。

## 6. 施工与目标日验收门

冻结提交必须先推送；随后最小施工仅允许：守护默认配置从 v1 指向 v2、测试同时锁定 v1 永久边界与
v2 当前边界、Makefile 文案更新。宿主和断网只读 Docker 专项、全仓、Ruff、compile、依赖、Compose、
脱敏、Git 同步均须通过，预执行不能改生产。

若目标日实时门全部通过并返回 STARTED，仍须等待自然 scheduler 链独立验 16:00 探测/就绪、19:30
硬兜底、日增量、raw `.BJ=0`、S1—S10、信号、开盘对账、Top30/Top20、飞书、重放、幂等、零人工
修数和新生产身份。单日成功不外推为稳定 SLA。

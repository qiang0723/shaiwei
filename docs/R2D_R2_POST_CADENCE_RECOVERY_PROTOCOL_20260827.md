# R2D-R2 探测节拍恢复协议

## 1. 目标

在不重复 Phase A、不重建候选、不重跑 fixture、不改变策略或业务口径的前提下，为 named-volume
scheduler 候选重新建立一次可满足、可审计的启动机会。

R2D-R1 已在 2026-08-27 16:05 的唯一预检中因健康证据时间为 15:58:45 而失败关闭；16:29:00 旧
scheduler 自然产生了同状态的新证据，证明问题是探测节拍而非候选、数据或锁故障。

## 2. 结果前冻结变量

后继目标日预定为冻结交易日历中的下一交易日 `20260828`。最终执行协议只能在 20260827 旧生产自然
周期完整结束后生成，并绑定该周期形成的最新真实边界：

- 20260827 daily、shadow、Top30/Top20、通知和 `.BJ=0` 的完整结果；
- 两个账户最新 FORWARD 产物及代码快照；
- 当时的 `HEAD=origin/main`、恢复控制器组件哈希；
- 原 R2C-R1 候选、image ID、代码快照、named-volume authority 与 fixture 四组哈希；
- release state 仍为 `current=候选 / previous=旧生产`，旧 scheduler 仍为原身份且 healthy。

这些真实身份未形成前，不生成执行 scope，不申请启动授权。

## 3. 唯一恢复变量

唯一变化是把一次性检查时点从 16:05 后移到 **16:40—19:00（UTC+8）**。16:40 为旧 scheduler
约 30 分钟探测节拍预留至少一个完整观察周期和安全余量，不改变任何业务到期时钟。

启动门仍必须同时满足：

1. 旧 scheduler 健康证据为目标日前一交易日的 `noop`，且 `updated_at` 在目标日 16:00 之后；
2. 目标日 daily、shadow、paper 全状态记录均为 0；
3. readiness 为 `CROSS_SNAPSHOT_WITH_NEW_DATA`，且唯一日期为目标日；
4. 候选、旧生产、release current/previous、控制器、双账户最新 FORWARD 与 fixture 身份全部精确一致；
5. 受控 Git 树干净且 `HEAD=origin/main`；
6. R2D-R1 已关闭，Phase A 不重复，同一新 scope 无论成功或失败均不得重跑。

不得用等待期间形成的业务记录绕过第2项；如旧 scheduler 已进入目标日，恢复立即失败关闭。

## 4. 权限与停止点

本协议当前只授权文档留痕与后续恢复工程，不授权 `start_current`、promote、restart、build、fixture、
手工跑批、历史回填、密钥、外网、Web、模型、策略或生产业务。

20260827 自然周期完成后，后继工程须生成独立 R2 协议/config、失败关闭测试和精确 release scope，
通过验证、提交并推送。用户逐字批准新 scope 前必须停止。

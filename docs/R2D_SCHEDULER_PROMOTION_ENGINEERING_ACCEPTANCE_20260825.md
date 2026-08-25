# R2D Scheduler named-lock 发布工程验收

## 1. 结论

`GO_ENGINEERING_READY / EXECUTION_NOT_AUTHORIZED`。

R2D 两阶段发布控制器、真实协议、候选/旧生产身份、R2C-R1 fixture 证据和精确 release scope 已闭合。
本验收只说明发布工程已准备好，不构成 promote、restart、真实业务或策略有效性授权。

## 2. 结果盲自然基线

- 2026-08-25 日增量：`PASS`，5 个批次、15,648 行，数据快照
  `40fa616924eade02329d50760a3dd6ae584360bcbc09e1ce63b6593e3e657a6b`。
- 影子周期：`PASS`，信号日 `20260825`，旧生产代码快照
  `4e5244b6b02739dd209a9b01ea715c43ed9a874a7014156e20cf364f06a82708`。
- `model_baseline`：执行日 `20260825`、`PASS`，产物
  `a7760947ce37126e455c520da77545264b41ee58df504f192b743505cd60bd4c`。
- `model_top20`：执行日 `20260825`、`PASS`，产物
  `2120d49edc026d878f88533b1ce0bb67c59b4787add918646c2d6fc7b7959731`。
- 旧 scheduler 最终健康证据为 `noop / 20260825`，更新时间
  `2026-08-25T12:09:48.825823+00:00`；其物理 SHA-256 为
  `42e34fb0999de9aa9d23e634d044b56ccb721091cd779bac814020f4cb3ac3c1`。
- 本地冻结交易日历包含 `20260826`。本节只读状态、日期与哈希，不读取策略效果。

## 3. 冻结身份与执行窗口

- 候选保持 R2C-R1 真身：`shaiwei:scheduler-88e3f471565ba461`，image ID
  `b7565001...baa72`，snapshot `88e3f471...abec0`，lock authority
  `docker-named-volume-v1`；禁止重建或重跑 fixture。
- 旧生产保持 `shaiwei:scheduler-4e5244b6b02739dd`，image ID `722f63de...13b76`，旧三 bind
  mount 与 `legacy-bind-flock-v0` 不变。
- 宿主控制器绑定源码 HEAD `9ff6516e6683dd8a70147e79132aa05556fb2ac5` 和四组件 SHA-256
  `455aad3798b6c32f68e434da64f14ebb300047fd79de592df4f47bd0b958e625`。
- Phase A：2026-08-25 20:45—23:30（UTC+8），只允许一次 `PROMOTE_NO_START`，旧容器不得重启。
- Phase B：2026-08-26 16:05—19:00（UTC+8），只有旧容器在目标日 16:00 后闭合
  `waiting_source / 20260826` 且 readiness 只暴露该交易日时，才允许一次 `START_CURRENT`。

## 4. 精确 release scope

- guard：`config/r2d_scheduler_release_guard_v1.yaml`，物理 SHA-256
  `e8423780fadc28eca1fd82914d8dc71154cbe41e5be502bd7e4dd260f8088808`。
- scope：`config/r2d_scheduler_release_scope_v1.json`。
- scope SHA-256：`4145d6018a1cb38f48432677dce1e68558cdaf48ad5c3e81d12f7067eac58292`。
- 动作：`R2D_PROMOTE_NO_START_20260825_AND_START_20260826_ONCE`。

scope 精确绑定候选、旧生产、两账户最新 FORWARD、旧周期健康证据、fixture 四组哈希、两阶段日期窗口
与控制器组件身份。用户未以该 scope 和动作精确批准前，两阶段均不得执行。

## 5. 机器验收

- R2D 专项：10 PASS。
- 全仓 1,918 PASS；架构 13 PASS。17 条 warning 均为既有第三方弃用或 pandas 未来行为提示，未改变
  裁决。
- Ruff、compileall、pip check、差异和脱敏检查：PASS。
- 当前尚未 build、重跑 fixture、promote、restart、读取 secret、联网、手工跑批或修改生产账本。

## 6. 下一停止点

工程提交推送后停止，等待用户精确授权。若 Phase A 窗口过期、任一身份/基线哈希漂移或次日不再是
唯一 readiness 日期，本 scope 自动失效，不顺延、不改日期复用；须重新生成新 scope。

## 7. Phase A 执行回执

用户于 2026-08-25 精确批准 scope `4145d601...8292` 和冻结动作。20:45:21（UTC+8）同一守护器
只读预检返回 `READY_TO_PREPARE`；20:45:57 执行唯一一次 no-start promote，终态 `PREPARED`、
`mutation_invoked=true`、`started=false`。

- release current：候选 `shaiwei:scheduler-88e3f471565ba461` / `b7565001...baa72`；
- release previous：旧生产 `shaiwei:scheduler-4e5244b6b02739dd` / `722f63de...13b76`；
- 发布审计记录 SHA-256：`45bf0302e2595f82877a733ae527b1e3c8918d1cd5cef3b9858e21f2fb512a37`；
- 旧 scheduler 仍为原容器 `183b8c6c5edd`，创建于 2026-08-03，三 bind mount、原代码快照且
  `healthy`；没有重启或启动候选。

Phase A 至此关闭，不重复执行。下一停止点为 2026-08-26 Phase B：未同时满足冻结窗口、旧容器
`waiting_source / 20260826`、唯一 readiness 日期、候选/旧生产/双账户/fixture/控制器全部身份门时，
守护器必须在 mutation 前阻断。

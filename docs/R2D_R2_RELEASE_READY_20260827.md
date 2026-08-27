# R2D-R2 探测节拍恢复发布就绪验收

## 裁决

`GO_RELEASE_READY_NOT_EXECUTION_APPROVAL`。

R2D-R2 只修复 R2D-R1 唯一预检早于旧 scheduler 约 30 分钟探测节拍的问题；候选、旧生产、
R2C-R1 fixture、四挂载、16:00 后新鲜 noop、目标日零写入和唯一 readiness 门均未改变。

## 20260827 自然闭环

- daily `b45a42c7a9bb` PASS，5 批、15,648 行，数据快照 `959248c9...c6246`；
- 五个真实交易日批次逐文件读取确认 `.BJ=0`，规范批次身份 `aef437f1...3044`；
- S1—S9 PASS、S10 NOT_APPLICABLE，哨兵文件 SHA-256 `10895bf4...f664`；
- shadow `d9ba3471959d` PASS，信号 SHA-256 `3893781a...c6a4`；
- Top30/Top20 均 PASS，产物 SHA-256 为 `8179107a...8d29` / `d4559607...9fc1`；
- 飞书九项开始、完成和对账投递 9/9 PASS，文件 SHA-256 `d80ed204...bf55`；
- 零人工修数，旧 scheduler、候选及 release current/previous 身份未漂移。

## 冻结身份

- R2 入口源码提交 `7740dd7e46458f512f276f8ba5a96ed04e5f5a9a` 已先推送；
- 五组件 controller SHA-256 为 `a2cb5d9e...0bdd`；
- guard config SHA-256 为 `72500864...4378`；
- release scope SHA-256 为 `a2e66d95dc13d3ea71d9068a880d9074300955c82a553fa867c985bfa2b729d5`；
- 候选仍为 `shaiwei:scheduler-88e3f471565ba461` / image ID `b7565001...aa72`。

## 权限与失败关闭

- 唯一窗口为 2026-08-28 UTC+8 16:40—19:00；Phase A 永久不得重复；
- 目标日 daily、shadow、paper 任一状态记录非零即阻断；
- 健康证据必须为 20260828 16:00 后新鲜 `noop / 20260827`；
- readiness 必须仅为 `[20260828]`，所有身份与 fixture 必须精确一致；
- 同一 scope 成功或失败均不得重跑，窗口过期不得顺延。

## 验证与停止点

R2D 专项 14 PASS；Ruff、架构、全仓和脱敏门须在终版提交前复核。未 build、未 fixture、未

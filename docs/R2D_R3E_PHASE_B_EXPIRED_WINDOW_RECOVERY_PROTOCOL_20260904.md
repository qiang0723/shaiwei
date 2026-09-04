# R2D-R3E Phase B 过期窗口恢复协议

## 结论

R2D-R3D-R1 Phase A 已于 2026-09-03 唯一完成并关闭，但 2026-09-04 16:40—19:00 UTC+8 的
Phase B 窗口内没有生成独立 start scope、没有取得 Phase B 授权，也没有执行 `start_current`。
2026-09-04 22:14 复核时窗口已经过期，禁止补造、顺延或复用原日期的 scope。

本恢复节点只把 start-only 边界重绑到冻结日历中的下一交易日 2026-09-07；不得重复 Phase A、重建
候选、重跑 fixture、读取策略效果、手工跑批或修改任何门槛。

## 过期后的真实现场

- release current 仍是候选 `shaiwei:scheduler-97d8c05eab2a1e8c` / image ID
  `sha256:b64ae11b76c4005876781085c1bdfa08dc500153cd5645594de2fb90b7cc5ebe`；previous 仍是旧生产。
- release audit 仍为 34 条，末条仍是 Phase A 的 `PROMOTE_PASS`；没有 Phase B release 事件。
- 运行 scheduler 仍是旧容器 `7a55151d4d5d686b01fbf26c76432754302358b2faa653eac21ca07ee78780c4`，
  旧 image ID `sha256:722f63de...13b76`，running/healthy、restart count 0、只读根及三个 bind 加
  `shaiwei_runtime_locks_v1` 锁卷四挂载完整。
- 旧生产随后自然完成 20260904：daily 与 shadow 状态 PASS，Top30/Top20 两账户均为 PASS、
  freshness PASS、operator=`docker-scheduler`，代码快照仍为 `4e5244b6...2708`。本协议只核对日期、
  状态、身份与哈希，不引用或裁决任何收益、净值或策略效果。
- 22:12 UTC+8 的 scheduler health 为 `noop / 20260904`；它发生在 20260904，不能冒充下一目标日
  20260907 16:00 后的新鲜边界。

冻结日历 `data/qlib_forward/versions/4e5244b6b027-f4430e0fdc0f/calendars/day.txt` 的 SHA-256 为
`c9916944c6865cf4e1e6b15af7ac90a54d2275320d25353873071f08d892b114`，明确列出 20260904 后下一交易日
为 20260907。

## R3E 唯一变量

新配置 `config/r2d_scheduler_release_guard_r3e_start_v1.yaml` 的 SHA-256 为
`924fac99f5dcdb8afeabb6392a07bbf6946fa6d76c3611be85d9e142deab0ca0`，只重绑自然时间和最新
FORWARD 身份：

- schema 使用既有 start-only 恢复合同 `r2d-scheduler-release-guard-r2-v1`，因此调用 prepare 必须失败，
  Phase A 不得重复；
- target trade date=`20260907`，启动窗口固定为 16:40—19:00 UTC+8；
- legacy boundary 固定为 20260907 16:00 后新鲜 `noop / 20260904`；
- 20260907 daily/shadow/paper 三类账本必须全部为 0；
- expected latest FORWARD 固定为 20260904 的 Top30 artifact
  `f96d333cf246b8efc8b902f1d4f7a3324b422cb627d0188164d18c3229cf676e` 与 Top20 artifact
  `77e1012e46446a6b92d1dd0caf230fb6b9bae900861e48ab2e0b075c485920c8`；
- candidate、旧生产、四挂载、named-volume lock authority、R3A fixture 与控制器组件身份全部不变。

## 20260907 执行前门

只有在 2026-09-07 16:40—19:00 UTC+8 内，才可先运行一次不带 `--execute` 的只读预检。它必须返回
`READY_TO_START`，并同时证明：

1. release current/previous 仍精确等于候选/旧生产，运行容器仍是 healthy 的旧生产且重启为 0；
2. candidate 镜像、R3A fixture、控制器组件、四挂载和锁 authority 无漂移；
3. 最新双账户 FORWARD 仍精确等于上述 20260904 两项身份；
4. readiness 为 `CROSS_SNAPSHOT_WITH_NEW_DATA` 且唯一目标日期为 20260907；
5. health 为 20260907 16:00 后自然形成的 `noop / 20260904`，目标日三类账本仍全部为 0。

任一项不成立即失败关闭，不生成执行 scope、不 restart、不手工补证、不在同一窗口降门槛。

## 授权与停止点

本节点只授权仓库内配置、测试与文档施工。当前不授权生成不可重跑执行 scope，不授权
`start_current`、restart、其他生产 mutation、真实效果读取、外网、密钥、DeepSeek、手工跑批、回填、
候选重建、fixture 重跑或模型/信号/策略/Web 变更。

只读预检通过后，才机械生成绑定届时 Git HEAD/origin、配置 SHA、Phase A 后 release state/audit 与
全部门证据的新 scope，报告唯一命令与失败边界，并等待用户逐字批准。候选首个自然交易日全门通过前，
R2D 不关闭，G1 不开工。

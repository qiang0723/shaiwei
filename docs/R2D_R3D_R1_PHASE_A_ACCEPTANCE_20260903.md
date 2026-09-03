# R2D-R3D-R1 Phase A 只提升不启动验收

## 结论

2026-09-03 20:53—20:54 UTC+8，用户批准的唯一 scope
`a43b44cdf25482ed013e21eac4b657cf501344e96d557bf18ce9f29449525d12` 在冻结窗口内执行一次
`promote_no_start`，控制器返回 `PREPARED`、`mutation_invoked=true`、`started=false`。Phase A 正式
关闭，不得重跑；本次授权不包含 Phase B、start、restart 或其他生产动作。

## 冻结输入与授权

- config：`config/r2d_scheduler_release_guard_r3d_prepare_v1.yaml`
- config SHA-256：`883e34c988229cf0d2657a5ebc48f4246377167ef676f04b8b100a715a93eddc`
- 执行时仓库 HEAD/origin：`8949991d6ffc72afe3c8a096db6237e5e187ce9c`
- 用户批准文本 SHA-256：`b41798d0146fd9638441476c2a3182f78bb9bcf09cf01b1176e7c99d055dc251`
- 不可变执行回执：
  `.release/r2d-r3d-scopes/a43b44cdf25482ed013e21eac4b657cf501344e96d557bf18ce9f29449525d12.execution.json`

前序失败/失效 scope 与回执继续永久保留，不因本次成功覆盖或删除。其中 metadata scope
`d5a013...e20af3` 因错误预填未来 HEAD 作废，`553e8b...ce35` 因旧生产实际为四挂载而在 mutation 前
阻断；本次仅以已冻结的旧生产 lock-volume 拓扑恢复重新绑定控制器身份，没有重建候选或重跑 fixture。

## Phase A 后发布身份

release current 已切为候选：

- image：`shaiwei:scheduler-97d8c05eab2a1e8c`
- image ID：`sha256:b64ae11b76c4005876781085c1bdfa08dc500153cd5645594de2fb90b7cc5ebe`
- code snapshot：`97d8c05eab2a1e8c66110ca303663dc47e992d8827dbb5dee38c8f2fc19e7553`
- candidate Git HEAD：`df44cabe44635b3c6be8e40188140fb54f5ff9a0`
- lock authority：`docker-named-volume-v1`

release previous 已切为旧生产：

- image：`shaiwei:scheduler-4e5244b6b02739dd`
- image ID：`sha256:722f63de15932cb2698e82db7c0140f02921f27f126e1c0235ca62e0a1213b76`
- code snapshot：`4e5244b6b02739dd209a9b01ea715c43ed9a874a7014156e20cf364f06a82708`
- Git HEAD：`210af4dab33c85b38c05b28f56c176b7970c41db`

release state SHA-256 为
`c879228f6514b3a07c0d1a6efec0c68832d0feab7444821e9376de1bfd86c454`；release audit 增至 34 条，
末条为 `PROMOTE_PASS`，记录 SHA-256
`aca0245b0e59e19612a2fd332dcb10188f0cfbfcd4eb5211f1167587819f477d`，完整 audit SHA-256 为
`4524d2d0af6d57dbf1fad6c57dcb623f62eb39f63930d278c26999f895e1eea1`。

## 运行容器未改变

定向只读复核确认运行中的 scheduler 仍是旧容器
`7a55151d4d5d686b01fbf26c76432754302358b2faa653eac21ca07ee78780c4`，镜像 ID 仍为旧生产
`sha256:722f63de...13b76`，状态 running/healthy、restart count 0、根文件系统只读。挂载仍精确为三个
可写 bind：`/workspace/data`、`/workspace/ledger`、`/workspace/logs`，以及可写 named volume
`shaiwei_runtime_locks_v1` → `/run/shaiwei-locks`。候选没有启动，旧容器没有 restart。

## 权限与唯一后继

本次没有读取策略效果、密钥或容器环境变量，没有访问业务外网、手工跑批、回填或改写自然账本。
Phase B 仍为 `authorized=false`。

唯一合法下一节点是 2026-09-04 16:40—19:00 UTC+8 的独立 Phase B：先机械生成新的 start config 与
scope，并在 mutation 前验证旧容器于 16:00 后形成新鲜 `noop / 20260903`、20260904 三类目标账本为
0、readiness 唯一指向 20260904、双账户 FORWARD 仍绑定 20260903，以及候选、四挂载、lock authority、
R3A 与 Phase A 后 release state 全部无漂移。必须报告新 scope 并取得用户逐字批准，才允许一次
`start_current`。在候选首个自然交易日全门通过前，R2D 不关闭，G1 不开工。

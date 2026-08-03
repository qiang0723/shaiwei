# 日增量早探测生产发布守护预执行验收

> 日期：2026-08-03（Asia/Shanghai）
>
> 协议：`daily-early-readiness-release-guard-20260804`
>
> 裁决：`GO_EARLY_READINESS_RELEASE_GUARD_PREEXECUTION_ONLY`
>
> 生产状态：`NOT_PROMOTED_NOT_STARTED`

## 1. 权威结论

2026-08-04 日期绑定的 P0-E 发布守护已完成实现、对抗 fixture 和断网只读 Docker 预执行，工程结论为
GO。守护能够在精确窗口内验证 Git、发布审计、冻结候选、当前生产、Top30/Top20 最新前瞻边界和唯一
新交易日，并只执行一次原子 promote+start；半切换可续接，启动失败必须恢复并重新拉起旧生产。

该裁决不代表生产已经切换。2026-08-03 实际运行 CLI 返回
`BLOCKED / guard target date does not equal the local date`，发生在任何 Git、Docker 或 release 状态读取/
变更之前；没有 promote、current 改写、scheduler 重启或手工日增量。

## 2. 冻结与实现顺序

- 协议与精确配置提交 `cd89247` 先行推送；目标日、窗口、候选、旧生产、双账户产物和恢复语义均在
  守护实现前冻结。
- 实现提交 `069604d` 随后推送；新增独立 352 行守护模块和 284 行测试，没有继续扩大现有 348 行
  Top20 guard 或 581 行 release 热点文件职责。
- 守护复用现有定向 Git/Docker/readiness 适配层；没有完整 `docker inspect`、`.Config.Env`、`.env`
  或凭据读取路径。

## 3. 冻结身份与前瞻边界

| 对象 | 冻结证据 |
|---|---|
| 目标日 | `20260804`，项目内冻结交易日历中为 `20260803` 后首个开市日 |
| 窗口 | `16:05:00`（含）—`19:00:00`（不含），Asia/Shanghai |
| 候选 | `shaiwei:scheduler-0640574ba7353c3e` |
| 候选 image ID | `sha256:85711ae0b4c3b19de1554f778cb0ff2ee10f5b1e962e2ef79e1d0953a6a5e79f` |
| 候选代码快照 | `0640574ba7353c3eef888eac2f706a29606db728319d3717b7ecdfc25de40c40` |
| 候选 Git | `fa6c67ab541c19b056221303756d81ad98ee122e` |
| 当前生产代码快照 | `4e5244b6b02739dd209a9b01ea715c43ed9a874a7014156e20cf364f06a82708` |
| Top30 最新边界 | `20260803` / artifact `ff8ddb0b...1235` |
| Top20 最新边界 | `20260803` / artifact `f0c4eae5...26fc` |

候选经真实 `verify_image()` 再次证明标签与运行时代码/Git 身份逐项等于冻结配置。执行时 readiness 还
必须精确返回 `CROSS_SNAPSHOT_WITH_NEW_DATA` 和唯一新日 `["20260804"]`；当前验收没有伪造真实目标日
readiness。

## 4. 状态机与恢复

守护只接受三种状态：

1. 旧 release + 旧 healthy scheduler：`PROMOTE_AND_START`；
2. candidate 已 promoted + 旧 healthy scheduler：唯一中断态，`RESUME_START`；
3. candidate release + candidate healthy scheduler：`ALREADY_ACTIVE`，零重复变更。

其他 release/container 混合身份全部 BLOCKED。fresh 路径调用一次既有
`release.promote(candidate, start=true)`；该入口失败后，守护重新读取 release state 和容器身份：

- state 已恢复为旧 release 但容器不是旧 healthy：调用旧 `start_current()`；
- state 仍为 candidate 且 previous 为冻结旧 release：调用 `rollback(start=true)`；
- 恢复后再次验证旧 current 与旧 healthy 容器；恢复自身失败时同时报告主失败和恢复失败，不能只
  改标签/状态后宣称恢复。

守护没有 daily/shadow/paper 调用入口，不能手工制造自然证据。

## 5. 验证证据

- 宿主守护/release 专项：55 PASS；覆盖时窗、Git、审计、候选、旧生产、双账户、唯一新日、fresh、
  dry-run、already-active、resume、promotion失败恢复、resume失败回滚和双重失败。
- 宿主全仓：562 PASS，只有既有 Starlette 弃用 warning。
- Ruff、`compileall`、`pip check`、三套 Compose 解析、`git diff --check` 和凭据扫描全部 PASS。
- 独立预执行镜像：`shaiwei:early-release-guard-preflight-069604d`，image ID
  `sha256:e8b08d68e01e893232435c98605e8e222635ce9fdb215134eca21e50ca6b6e80`；运行时代码快照
  `393282d671996596f82db692967f27fcb470692e5da6ca527d8d5c0183e1168c`，Git `069604d...7686`。
- 该镜像在 `--network none`、只读根、`cap-drop ALL`、`no-new-privileges`、无项目挂载、无凭据下
  55 PASS；唯一 warning 是只读根阻止 pytest 写缓存。

预执行镜像使用独立测试标签，没有调用 release build/promote，因此不属于生产候选，也不进入发布
审计。

## 6. 生产不变性

终验时实际生产仍为：

- 容器 `183b8c6c5eddac951d9d9b3cfa58c0d38e351d5b94ee1b1d52b9b8059c23dd3b`；
- 镜像 ID `sha256:722f63de15932cb2698e82db7c0140f02921f27f126e1c0235ca62e0a1213b76`；
- 创建时间 `2026-08-03T09:39:34.800579793Z`；只读根 `true`；状态 `healthy`。

release current 仍绑定旧生产快照 `4e5244b6...82708`；审计仍为 24 行，tip 仍是冻结候选原
`BUILD_PASS` 的 `aa64d960...ee05f`。预执行前后没有新增 PROMOTE/START/ROLLBACK 记录。

## 7. 目标日执行与后验收

只有在 2026-08-04 16:05—19:00 且全部实时门仍精确通过时，才允许执行一次：

```text
make docker-early-release-guard
```

守护 BLOCKED 时不得改配置、日期、前瞻边界或重复追成功。若 STARTED，仍须等待自然 scheduler 链路并
独立验首次探测、首次就绪、正式完成时点、日增量 PASS、raw `.BJ=0`、S1—S10、信号、Top30/Top20、
飞书、重放、幂等和零人工修数。单日成功不外推稳定 SLA。

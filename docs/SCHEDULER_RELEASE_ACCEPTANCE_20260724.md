# Scheduler 发布快照隔离验收（2026-07-24，UTC+8）

## 1. 当前裁决

状态：**PRE_CUTOVER_PASS / RUNTIME_PENDING**。

不可变镜像、开发隔离、挂载白名单、回滚状态机和离线只读查询已经通过；最终生产裁决仍必须等待
2026-07-24 19:30 后的真实交易日周期。未取得新快照下的日增量、影子、模拟仓、通知和幂等证据前，
不得把本文件改写为完整 PASS。

## 2. 迁移前根因证据

迁移前容器：

- image ID：`cb7686862919745c4ef1e09499cae884503aa182dcf1f9d9bd185c2c9c1c2577`；
- 唯一挂载为宿主项目根 → `/workspace`；
- `RW=true`；
- 迁移前健康状态为 healthy。

该证据确认生产 scheduler 的运行代码直接来自开发工作树，符合
`docs/INCIDENT_20260723_CODE_SNAPSHOT_MISMATCH.md` 的结构性根因。

## 3. 两个不可变发布快照

| 角色 | Git 提交 | 代码快照 | image ID |
|---|---|---|---|
| previous | `20d7e92` | `817ebb64508db1a1687fc53fbe82d4e3867fe48f2a86c6d72c1b23c5eb2c086f` | `87f00ccd5786b6cfddc0fe6c72ae497cdc9cba43711c896f0228c2430994457e` |
| current | `d42c742` | `a5a36691f9de5d281685fdc03bc80c628cb3ef1a4bff9228bfceeaccc81b6481` | `e192b338a3bfdfda4c2456dc95ebdf6a97ff47e6ebe71e2e3997b5daaf251d55` |

两个镜像均通过：干净 Git 工作树快照、镜像 OCI 标签、镜像内发布清单逐文件重算三者完全一致。
实现提交已推送 `origin/main`，本地 HEAD 与远端跟踪引用同为 `d42c742`。

## 4. 开发工作树隔离探针

在宿主 `src/shaiwei/` 临时加入受控探针后：

- 宿主动态代码快照由 `817ebb...` 变为
  `05d26023824b47eaa53a0968d1fa4b1c77d291115070e3201bb2e431aa8fdd7a`；
- 已构建镜像内不存在该探针；
- 镜像内重算快照继续为 `817ebb...`。

探针随后删除，宿主快照精确恢复。这直接证明开发文件变化不能进入既有生产镜像，而非仅凭 Compose
文本作推断。

## 5. 发布与回滚证据

未启动生产服务时已完成：

1. promote previous；
2. promote current；
3. rollback previous；
4. re-promote current。

`.release/scheduler_state.json` 最终 current/previous 与上表一致；
`logs/releases/scheduler_releases.jsonl` 当前 6 条记录，哈希链 tip 为
`5d75b4e714b50c636322a1f4222400fdcbfd42ef3c761c51d09f49b62fbdc2a5`，完整校验 PASS。
发布工具没有删除失败候选或覆盖运行 ledger。

## 6. 最终容器静态契约

最终 current 容器已创建但未启动，Docker 实际状态为：

- image ID 精确为 current 的 `e192b338...51d55`；
- root filesystem `readonly=true`；
- capability drop：`ALL`；
- security option：`no-new-privileges:true`；
- 挂载只有 `/workspace/data`、`/workspace/ledger`、`/workspace/logs`；
- 没有 `/workspace` 整仓挂载，没有 Docker socket；
- 容器状态为 `created`，未提前运行 scheduler。

最终镜像在同一挂载白名单下的只读预检：

- 发布快照重算：`a5a36691...6481`；
- 14:37 本地日计划：watermark/eligible target 均为 `20260723`，缺口 0；
- 模拟仓独立重放：5 个账户日、174 个事件、30 个订单、22 个成交，PASS；
- 账本与数据未因预检改变。

## 7. 质量门

- 核心实现后全仓 189 项测试 PASS；
- 最终双镜像回滚契约加入后全仓 190 项测试 PASS；
- Ruff、compileall、`pip check`、Compose 解析和 `git diff --check` PASS；
- 受控提交不含 `.env`、Token、Webhook、签名、绝对本机路径、数据或运行日志。

## 8. 待完成的真实运行证据

2026-07-24 是官方交易日；迁移前最新 daily/shadow/reconciliation/paper PASS 均停在 `20260723`。
19:30 后必须以 current 镜像完成并留痕：

1. 实际容器运行契约与健康检查；
2. `20260724` 日增量 PASS、实际原始批次 `.BJ=0`；
3. S1-S9 PASS、S10 NOT_APPLICABLE；
4. `20260723 → 20260724` 次日开盘对账和 `20260724` 新信号；
5. current 快照下的新模拟仓 FORWARD、独立重放和 acceptance；
6. 飞书开始/完成投递；
7. 完整周期重复运行 NOOP，账本/产物/通知幂等；
8. 发布审计、Git 脱敏与远端同步。

以上全部通过后，才把状态改为 `PASS` 并解除 P2/Web 后端的隔离门禁。

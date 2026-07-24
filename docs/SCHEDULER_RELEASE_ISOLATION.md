# Scheduler 不可变发布与开发隔离规范

冻结日期：2026-07-24（UTC+8）

## 1. 目标与威胁模型

本规范解决生产 scheduler 曾直接将开发仓库以 `.:/workspace` 可写挂载的问题。该结构会让
`src/config/tests/compose` 的开发改动在没有发布动作时立即改变生产代码身份，并已在
2026-07-23 两次触发 FORWARD 快照失配。

隔离后的硬目标：

1. 生产代码、配置、模板、测试和构建入口只来自不可变 Docker 镜像；
2. 开发工作树变化不能进入正在运行的 scheduler；
3. 只有显式 build → verify → promote 才能改变生产镜像；
4. 发布保留 current/previous，可回滚且每一步进入哈希链审计；
5. 数据、ledger 和 logs 继续保存在项目目录，不迁出、不复制到其他目录；
6. 不放宽代码快照、模拟仓、北交所、PIT、幂等或通知门禁。

## 2. 服务边界

`compose.yaml` 将两类容器彻底分开：

- `shaiwei`：开发/一次性任务，可挂载当前工作树；显式清空
  `SHAIWEI_RELEASE_MANIFEST`，继续按 Git 工作树计算动态快照。
- `scheduler`：生产守护，只使用 `shaiwei:scheduler-current`，没有 `build` 和整仓挂载。

生产 scheduler 唯一允许的宿主挂载：

| 宿主项目目录 | 容器目录 | 权限 | 用途 |
|---|---|---|---|
| `data/` | `/workspace/data` | 读写 | 原始批次、派生数据、信号和模拟仓产物 |
| `ledger/` | `/workspace/ledger` | 读写 | 追加式运行与研究账本 |
| `logs/` | `/workspace/logs` | 读写 | 健康、通知、报告和发布审计 |

禁止挂载 `/workspace`、`.git`、Docker socket、其他项目目录或用户主目录。容器根文件系统只读，
只为 `/tmp` 和 `/root/.cache` 提供有界 tmpfs；同时 `cap_drop=ALL`、
`no-new-privileges=true`。

`.env` 仅由 Docker Compose 在启动时读取为容器环境变量，不复制进镜像、不作为文件挂载，也不进入
发布状态或审计。

## 3. 镜像内发布清单

Docker 构建会把冻结快照涵盖的 `src/`、`config/`、`templates/`、`tests/` 和根构建文件复制到
镜像，并在 `/opt/shaiwei/release-manifest.json` 写入：

- 受控文件相对路径；
- 每个文件的 SHA-256；
- 与本地 `code_snapshot_sha256()` 同算法的总快照；
- 文件总数和 schema 版本。

生产镜像设置 `SHAIWEI_RELEASE_MANIFEST`。运行时每次请求代码快照都会重新核对文件集合、逐文件
哈希和总快照；缺文件、增文件、内容变化或清单损坏全部失败即停。镜像标签
`io.shaiwei.code_snapshot_sha256` 必须与运行时重算值、干净工作树值三者一致。

## 4. 受控发布

发布仅允许从干净 Git 工作树执行：

```text
make docker-release-build
make docker-release-promote RELEASE_IMAGE=shaiwei:scheduler-<snapshot-prefix>
```

`build` 生成内容寻址镜像并在一次性只读容器中验证发布清单。`promote`：

1. 复核候选镜像标签与运行时快照；
2. 将现 current 保存为 previous；
3. 将候选提升为 `shaiwei:scheduler-current`；
4. 原子更新 `.release/scheduler_state.json`；
5. 重建 scheduler；
6. 核对实际 image ID、只读根、挂载白名单、运行时快照和健康状态；
7. 向 `logs/releases/scheduler_releases.jsonl` 追加哈希链记录。

`docker-scheduler-up` 不再隐式构建镜像；没有受控 current 镜像时应失败。

状态与审计均在项目目录内：`.release/` 是可再生的本机发布指针且不进 Git，`logs/releases/` 是
运行证据且不进 Git。内容寻址镜像本身保留完整可执行真身。

## 5. 回滚

```text
make docker-release-rollback
```

回滚只允许切换到已验证的 previous 内容寻址镜像；切换后执行与发布相同的容器契约和健康验收。
当前失败候选不会被删除，仍可按内容标签复核。若回滚自身失败，工具恢复原 current 指针并写
`ROLLBACK_FAILED_RESTORED`，不得以删除容器、覆盖 ledger 或修改不可变产物代替恢复。

初次迁移必须先准备两个可验证的隔离镜像并在不启动生产服务的条件下演练
promote → rollback → re-promote；最终只在真实交易日数据窗口执行一次生产启动，使新代码快照与
新生成的 FORWARD 产物在同一受控周期闭环，避免把旧历史产物错误伪装为新版本产物。

## 6. 验收门

本门禁只有同时满足以下证据才 PASS：

- 迁移前 `docker inspect` 证明旧容器确有 `.:/workspace` 可写挂载；
- 镜像快照与干净工作树快照相同，镜像内精确复核 PASS；
- scheduler 实际挂载只有 `data/ledger/logs`，根文件系统只读且无 Docker socket；
- 在宿主开发树制造受控探针时，运行容器看不到该文件且代码快照不变；
- 两个不同内容快照完成无启动 promote/rollback/re-promote，状态与审计哈希链一致；
- 最终 scheduler 健康，日增量、S1-S10、影子、模拟仓、飞书和重复运行按原门禁完成；
- 全仓测试、Ruff、compileall、依赖、差异和脱敏检查 PASS；
- 生产运行所用提交已推送 `origin/main`。

完成本门禁不授权 P2、Web 后端或模型变化；它们仍须另立目标。

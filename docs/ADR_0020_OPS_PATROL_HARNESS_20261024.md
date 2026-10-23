# ADR 0020 · 巡检 harness：独立只读巡检容器 + 飞书去重告警

- 日期：2026-10-24
- 状态：**ACCEPTED 2026-10-24**（用户对 §8 四点均选推荐项：独立巡检容器、变化告警+每日结论、桌面任务保留作补充、只注入飞书变量）
- 关联：`src/shaiwei/ops_patrol.py`、`config/ops_patrol_v1.yaml`、ADR_005（主机可用性，已裁决不禁睡、不迁移）、
  ADR 0016 §11、20260929 事故（同一失败刷 180 条告警无人处理）

## 1. 问题与结果目标

现有巡检两条腿都依赖“有人或 Claude 在场”：`make ops-patrol` 需手动触发；桌面定时任务 `shaiwei-nightly-patrol`
只在 Claude 应用打开且 Mac 醒着时触发，本周两次未按时触发。scheduler 自身只能报“某阶段失败”，报不了
“自己死了、卡住了、到点没跑完”。

目标：

1. 巡检不依赖 Claude 应用，随 Docker 常驻；
2. scheduler 死、卡、截止（18:30）后日链未完成时，≤15 分钟内发出一条告警；
3. 同一问题只告一次、恢复告一次、每日有上限，从机制上杜绝 09-29 式刷屏；
4. 每个开放日一条“日结论”，**“没收到日结论”本身成为电脑睡着或巡检挂了的信号**。

非目标：不解决 Mac 睡眠（巡检与日链同机，睡眠时一起停，ADR_005 已裁决）；不自动修复、不重启任何容器、
不写账本、不触发任何生产动作。

## 2. 现状证据（2026-10-24 00:43 实测）

- 一次性容器内经 `host.docker.internal:8080` 可达 Web：`/healthz` 200（只证明 web-ui 自身）；
  `HEAD /api/v1/system/runs` 200（经 UI 代理到 web-query，证明查询服务）。research-control 无匿名探针。
- 容器内 `shutil.disk_usage` 与宿主一致（358.7 GB 可用）。
- scheduler 心跳 `logs/scheduler/health.json`（status/detail/pid/updated_at），陈旧阈 3600 s；轮询 900 s；
  10-22/10-23 最长周期 714 s，远低于陈旧阈。
- 飞书 `FeishuNotifier` 只依赖 `FEISHU_*` 七个变量；scheduler 正常日约 9 条 started/completed 消息。
- 现巡检中需宿主 Docker CLI：容器 inspect/重启计数、tag 漂移；需 git：账本积压、origin 同步。
  生产容器禁止 Docker socket 与工作树挂载（SCHEDULER_RELEASE_ISOLATION）。
- 先例：`compose.web.yaml` 以 `web-local` 组件（COMPONENT_RELEASE / ACTIVE_LOCAL_READ_ONLY /
  NEW_RELEASE_REQUIRED）登记，不进 `CONTROLLED_FILES`，不改 scheduler 代码快照定义。

## 3. 候选方案

| 方案 | 结论 |
|---|---|
| A 独立常驻巡检容器（`compose.ops-patrol.yaml`，循环巡检） | **推荐**：与 scheduler 解耦，scheduler 死/卡时照样工作；不碰 R2D |
| B 嵌入 scheduler 链尾钩子 | 否：scheduler 死/卡时恰好不跑；且需 scheduler 新候选发布 |
| C 一次性容器 + 宿主 launchd/cron 触发 | 否：违宪（禁止裸宿主守护） |

## 4. 设计（方案 A）

### 4.1 检查分组

- **容器组（告警依据）**：心跳、Web 两探针、交易日历、日链四段（daily/shadow/对账/模拟仓）、重复失败、磁盘。
- **宿主组（不告警）**：容器 inspect/重启计数、tag 漂移、账本积压、origin 同步；仍由 `make ops-patrol` 与桌面任务执行。

`run_patrol` 增加 `mode: host | container`：container 模式不调用 docker/git，报告列出 `skipped_host_checks`；
Web 两模式都用 HTTP 探针（host 走 127.0.0.1，container 走 host.docker.internal），任一探针失败为 FAIL。
宿主模式的容器清单加入巡检容器自身，由宿主巡检看守巡检。

### 4.2 节奏与睡眠感知

- 每 60 s 醒一次比对墙钟，到期才巡检（间隔 10 分钟）；Mac 唤醒后 ≤1 分钟补巡。
- **唤醒宽限**：本轮距上一轮 > 3 个间隔即判定主机刚唤醒，此后 20 分钟（> scheduler 轮询 900 s）内只巡检、
  不告警，避免每次开盖都先报一条“心跳陈旧”。休眠段（起止、时长）记入事件日志，并汇总进下一条日结论。

### 4.3 告警状态机（状态文件 `logs/ops-patrol/state.json`）

- 签名 = 非 INFO 发现的（代码, 关键字段）集合。签名变化且非空 → `ops_patrol_alert`；
  变为空 → `ops_patrol_recovered`；不变 → 不发。
- 每个预期交易日首次被巡检到时 → `ops_patrol_daily`（状态 + 摘要 + 当日休眠段）；与同轮告警合并成一条。
  按预期交易日去重，所以周末不重复发，睡到次日早上醒来也会补发前一日结论。
- 每日上限 8 条（配置项），超限只计数，下一条日结论附“已抑制 N 条”。
- 投递失败不更新签名，下轮重试（仍受上限约束），不阻塞巡检。
- 消息只带代码、交易日、账户 ID、心跳状态与时长，不带净值、持仓、金额（沿用现巡检约束）。

### 4.4 输出

`logs/ops-patrol/latest.json`（覆盖写）、`logs/ops-patrol/events_YYYYMMDD.jsonl`（只记告警/恢复/日结论/休眠段，追加）、
飞书投递记录照旧写 `logs/notifications/`。不写 `ledger/`、`data/`。

### 4.5 容器与隔离

- 镜像：主 `Dockerfile` 从**已推送**的 HEAD 构建，标签 `shaiwei:ops-patrol-<代码快照前 12 位>`；compose 用
  `SHAIWEI_OPS_PATROL_IMAGE` 显式指定，不用浮动标签。镜像层与 scheduler 共享，几乎不占新增磁盘。
- `user 10001`、`read_only`、`cap_drop ALL`、`no-new-privileges`、`pids_limit`、`mem_limit`、`cpus 0.25`、
  `restart: unless-stopped`；自身 healthcheck = `latest.json` 新鲜度 ≤ 30 分钟。
- 挂载：只读 `ledger/`、`data/raw/source=tushare/api=trade_cal/`、`logs/scheduler/`；读写 `logs/ops-patrol/`、
  `logs/notifications/`。无 Docker socket、无工作树、无 `.git`、无 `data/paper`。
- 密钥：只经 compose `environment` 从 `.env` 插值注入 `FEISHU_*` 七个变量，不用 `env_file`
  （Tushare token 等其余密钥不进巡检容器）。
- 网络：默认 bridge，实际出站只有 `open.feishu.cn` 与 `host.docker.internal`；无出站白名单能力，记为已知边界。

### 4.6 新增物

`compose.ops-patrol.yaml`（登记为 `ops-patrol-local` 组件，资产计数 98→99）、`src/shaiwei/ops_patrol_service.py`
（循环、状态机、消息）、`src/shaiwei/ops_patrol_config.py`（配置 schema 单独成模块：容器健康检查不必导入 pandas，
并使 `ops_patrol.py` 保持 ≤400 行）、`config/ops_patrol_v1.yaml` 增 `web_probe` 与 `service` 两段、
Makefile：`ops-patrol-build / ops-patrol-dry-run / ops-patrol-up / ops-patrol-drill / ops-patrol-status / ops-patrol-down`。
`containers.patrol` 在部署提交前保持 `null`，避免部署前宿主巡检先报 `CONTAINER_MISSING`。

## 5. 影响边界

不改 scheduler 代码路径、镜像、`compose.yaml`；不改 Web；不改 R2D 13 个控制器组件；不改任何冻结判据与账本 schema。
`src/` 变化会让 HEAD 代码快照不同于运行中 scheduler 的快照——这在每次提交后都已如此，运行中镜像已烘焙，不受影响。

## 6. 失败关闭与回滚

- 巡检自身读不到日历或账本 → 报 FAIL 并告警，不静默退出；进程崩溃 → `restart` 拉起；反复崩溃 → 宿主巡检
  `CONTAINER_UNHEALTHY`，且当晚收不到日结论。
- 飞书不可达 → 记录投递 FAIL，下轮重试。
- 回滚 = `make ops-patrol-down`：对 scheduler、Web、账本零影响，回到现状（宿主巡检 + 桌面任务）。

## 7. 验收

1. 合成测试：新问题只告一次；不变不发；恢复一次；日结论每预期交易日一次（含周末、隔夜唤醒）；唤醒宽限；
   每日上限与抑制计数；投递失败重试；container 模式不调用 docker/git；Web 探针失败为 FAIL；消息不含数值字段。
2. 部署（用户逐字批准后）：启动 10 分钟内出现 `latest.json` 且 PASS；`make ops-patrol-drill` 用一次性容器
   发**一条**带“演练”标记的消息，不改状态文件；下一个开放日 18:30 后收到一条日结论。
3. 观察 10 个开放日：正常日消息数 = 1；与宿主巡检逐日对照，无漏报。

## 8. 用户裁决（2026-10-24）

1. 方案 A 独立常驻巡检容器 —— 采纳；
2. 消息策略：状态变化告警 + 每开放日一条日结论 —— 采纳；
3. 桌面巡检任务：保留为宿主组补充，观察期（10 个开放日）结束后复审 —— 采纳；
4. 密钥：只注入 `FEISHU_*` —— 采纳。

构建镜像、推送、启动巡检容器与演练消息仍各自需要用户批准；启动须逐字批准。

## 9. 复审触发

迁移到专用主机时重审（ADR_005）；观察期结束复审桌面任务去留；误报 ≥3 次/周须修订本 ADR 的阈值，不得在代码里静默调参。

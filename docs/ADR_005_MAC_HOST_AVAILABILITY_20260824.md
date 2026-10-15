# ADR-005：Mac 宿主连续运行方案

- 日期：2026-08-24（UTC+8）
- 状态：`ACCEPTED_SYSTEM_ACTION_VERIFIED`
- 适用范围：筛微生产 scheduler 的宿主可用性
- 生产发布授权：无

## 1. 背景

R2-1 v1 因 20260813/14 未形成同日双账户证据而永久 `BLOCKED_EVIDENCE`。项目证据显示 20260813
存在约 16 小时 34 分钟容器输出断档，与宿主或 Docker 休眠高度一致；但没有读取项目外历史电源日志，
因此不把该推断写成已证实根因。

R2-1R0 已完成 scheduler phase 时间线工程，但尚未发布。发布前必须先解决宿主进入空闲睡眠这一更上游的
连续性风险；Docker 容器无法在 macOS 整机睡眠时继续执行。

## 2. 2026-08-24 只读现状

`pmset -g custom` 显示接电策略：

- `sleep=1`：系统空闲一分钟后允许睡眠；
- `displaysleep=5`：显示器五分钟后关闭；
- `womp=1`、`powernap=1`、`ttyskeepawake=1`；
- 机器存在内置电池，当前属于便携式 Mac 的使用边界。

`pmset -g assertions` 当时显示 Kimi、Chrome、ChatGPT、音频设备等进程临时持有防休眠断言。这些断言
依赖前台应用生命周期，不能作为筛微生产控制面；应用退出、音频停止或系统重启后可能消失。

Docker 侧已确认：

- scheduler 使用 `restart: unless-stopped`，实际 Docker RestartPolicy 也是 `unless-stopped`；
- 容器 `183b8c6c5edd`、镜像 `sha256:722f63de...13b76`持续 running/healthy；
- 该策略可处理容器退出和 Docker daemon 恢复，但不能阻止宿主睡眠，也不能在 Docker Desktop未启动时
  自行启动 daemon。

## 3. 裁决

采用“接电时宿主不自动睡眠、显示器照常休眠、Docker 容器自行恢复”的最小方案：

1. 只把 AC Power 的系统睡眠设为关闭；不改变电池模式；
2. 保留 `displaysleep=5`，熄屏不等于系统睡眠；
3. 保留 scheduler 的 `restart: unless-stopped`；
4. Docker Desktop 必须设置为用户登录后自动启动；
5. 便携式 Mac 运行窗口必须接电，并保持上盖打开；若使用合盖模式，须满足 macOS 合法外接显示器/电源
   条件，不能把普通合盖当作持续运行；
6. 不使用 `caffeinate`、Kimi/ChatGPT/Chrome 的临时断言、launchd 裸机守护或项目外脚本充当生产保证；
7. 不修改 `powernap`、`womp`、磁盘睡眠、VPN、网络代理或 Codex 连接方式。

## 4. 精确动作与回滚

系统动作必须由用户明确批准后执行：

```text
sudo pmset -c sleep 0
```

执行后只读验证必须满足：接电配置 `sleep=0`、`displaysleep=5`；Docker scheduler 的容器、镜像、创建时间、
挂载和健康状态不变。不得打印完整 Docker 环境变量。

回滚到本次只读审计观察到的原值：

```text
sudo pmset -c sleep 1
```

Docker Desktop“登录后启动”由用户在应用设置内确认；Codex 不读取或修改项目外 Docker Desktop 配置文件。

## 5. 发布时序

宿主动作和验证通过后，仍不能直接把当前工作树挂到生产。下一节点另立不可变 scheduler timeline release：

1. 从已推送干净提交构建候选镜像；
2. 用 daemon fixture 验证 `logs/scheduler` 挂载可写、哈希链可追加且业务账本不变；
3. 避开 16:00—19:30 数据窗口完成受控 promote；
4. 证明新容器根只读、挂载仍仅 data/ledger/logs、快照与 Git 身份一致；
5. 首个自然交易日完整 PASS 后再冻结 R2-1R1，不回填历史 timeline。

## 6. 当前裁决

2026-08-24用户已明确批准并完成`sudo pmset -c sleep 0`；只读复核为AC Power `sleep=0`、
`displaysleep=5`，scheduler原身份保持healthy。

用户随后人工确认Docker Desktop登录启动已开启；Codex未读取其项目外配置。当前终态为
`GO_HOST_AVAILABILITY_COMPLETE`。后继scheduler真实发布仍须独立协议和授权。执行证据见
`docs/R2_1H0_MAC_HOST_AVAILABILITY_ACCEPTANCE_20260824.md`。

本 ADR 未修改Docker Desktop、Docker容器、生产镜像、项目配置、业务账本或运行日志。

## 7. 2026-10-15 修订：合盖/电池是未覆盖的失效模式，增加 AC 下禁止睡眠

**证据（只读，`pmset -g log`，详见 STATE.md 2026-10-14/15 条目）。** `sleep 0` 自 08-24 生效后仍发生 6 次日链次日补跑
（0813、0911、0916、0921、0922、1012），其中 0921/0922/1014 三次跨过下一交易日开盘。电源日志可证的两次：20261012 06:42
`Clamshell Sleep` 且全天 `Using Batt`，16:00–19:30 数据窗口内五次 `Idle Sleep`；20261014 19:15 `Clamshell Sleep`、`Using Batt`，
整夜仅维护性暗唤醒，调度器在暗唤醒中三次补采均 `IngestError`（无网络），飞书投递亦失败，次日 10:05 开盖后 10:18 才补跑。
`sleep 0` 只约束 AC 下的空闲睡眠，不约束合盖触发的 Clamshell Sleep，也不约束电池模式。

**裁决（用户 2026-10-15 对“b 过渡、c 根治”回复“按建议”）。**
- b 过渡：在 AC 电源策略下禁止系统睡眠（含合盖）：`sudo pmset -c disablesleep 1`。只作用于接电状态；电池模式保持默认睡眠，
  以免耗尽电量导致硬关机。由此宿主纪律从“接电 + 开盖”简化为“**接电**”。该命令为系统设置变更，由用户在自己的终端执行，
  Claude 不执行。
- c 根治：将生产 scheduler 迁至不睡眠的专用主机（Mac mini 一类或等价 Linux 主机）。另立迁移协议（含 S10 跨机一致性启用、
  数据/账本/锁卷迁移、发布身份重建），不在本修订内施工。

**精确动作与验证。**
1. 执行前只读记录：`pmset -g custom`（AC 段）与当前 `pmset -g log` 尾部。
2. 用户执行：`sudo pmset -c disablesleep 1`。
3. 只读复核：`pmset -g custom` 的 AC Power 段出现 `disablesleep 1`，且 `sleep 0`、`displaysleep` 不变。
4. 行为验证：接电状态合盖 2 分钟后 `pmset -g log` 不出现新的 `Clamshell Sleep`/`Idle Sleep` 条目，scheduler 心跳继续更新。
5. 记入 STATE.md；巡检（`make ops-patrol`）的 `DAILY_NEXT_DAY_CATCHUP` 作为持续观测指标。

**回滚。** `sudo pmset -c disablesleep 0`。

**边界。** 本修订不改任何判据、代码、镜像、容器或项目配置；不替代 c。若 c 落地，本修订随之退役。

### 7.1 2026-10-15 更正：b 不可行，撤回

用户执行 `sudo pmset -c disablesleep 1` 后只读复核：`pmset -g` 系统级设置无 `SleepDisabled`，AC 策略无 `disablesleep` 项，
`/Library/Preferences/com.apple.PowerManagement` 无该键——命令未产生任何可见效果。`disablesleep` 为 macOS 未入 man 页的
**系统级**开关，不分电源；`-c` 形式被静默忽略。上文“只作用于接电状态”的前提不成立，系本人未经核实写入，予以更正。
唯一生效形式 `-a` 会使电池模式下合盖亦不睡眠（随身携带时发热、耗尽电量），用户裁决不采用。

**现行裁决（用户 2026-10-15）。** 不设置 disablesleep；过渡期纪律恢复为“**交易日 19:30–20:30 接电且开盖**”，
巡检 `DAILY_NEXT_DAY_CATCHUP` 持续观测；**c 专用主机加速推进**，另立迁移协议。上文 b 的精确动作、验证与回滚作废。
如需对已执行的 `-c` 命令做卫生性复原，可执行 `sudo pmset -c disablesleep 0`（无可见效果，非必要）。

### 7.2 2026-10-15 用户裁决：暂不迁移，继续使用本机

用户明确“先不迁移，还是用这个电脑”。c 专用主机**暂缓**（不再“加速推进”），不起草迁移协议；生产继续运行于本机笔记本。
宿主可用性的唯一手段为纪律：交易日 19:30–20:30 接电且开盖；R2D-lite 切换窗口（周六 10:00–16:00）与其后首个自然交易日
同样须接电开盖。已知后果照常接受并如实记录：合盖/电池时日链次日补跑、信号 `on_time=false`、R2-1 自然计数中断；
巡检 `DAILY_NEXT_DAY_CATCHUP` / `SHADOW_SIGNAL_LATE` 持续观测。若用户日后改判，再另立迁移协议。

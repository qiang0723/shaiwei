# ADR 0016 · R2D 拆小：非交易时段切换 + 首自然日验收（R2D-lite）

- 日期：2026-10-14
- 状态：**ACCEPTED 2026-10-15**（用户对 §10 四问回复“按建议”：①接受 R2D-lite，ADR 0011/0012 的执行设计自本日作废；
  ②R3N 四个未跟踪文件提交为离线证据；③切换窗口周六 10:00–16:00；④宿主电源先 b `disablesleep` 过渡、c 专用主机根治，
  切换前须解决。ADR 0013、0014 保留为离线证据。本 ADR 只授权工程与协议施工；每一步生产动作仍须逐字批准。）
- 关联：ADR 0009（锁权威）、0010（执行合同）、0011（收盘后宽窗口）、0012（停放/排空）、0013/0014（离线阶段）；
  docs/SCHEDULER_RELEASE_ISOLATION.md；docs/ASTRA_PROJECT_REVIEW_FOLLOWUP_20260907.md；STATE.md 2026-10-14 条目；
  docs/OPERATOR_UNDERSTANDING_DRAFT_20261014.md §5

## 1. 问题与结果目标

**问题。** R2D 的目标是把生产 scheduler 从旧镜像（代码 210af4d，2026-07-27；bind-mount flock 锁）切到带 named-volume 锁权威的
不可变候选，并通过首个自然交易日验收。自 08-25 起 14 个子轮、12 个启动窗口，候选一次也没有跑过首日：最初的 Phase B 前提
结构上不可能成立，随后健康竞态、预检时点、宿主唤醒、Astra 审出的三项 P1，使路线转入 R3L/R3M/R3N 的离线合同与模拟层。
按代码与 ADR 推出，收口仍需八组工作（生产版阶段存储、真实业务端口、旧 writer 排空执行器、全 writer 隔离、发布谱系 CAS、
停放候选的新启动合同、新控制器基准、新候选与三套 fixture）——这是一个小型发布系统。与此同时：生产停在 7 月代码，
任何修复（例如 ADR 0015）都进不了生产；G1 正控及其后主线全部排在 R2D 之后，已停摆 7 周。

**结果目标。** 在**不降低任何冻结判据与证据纪律**的前提下，用最小的新机制完成一次可回滚的生产切换与首自然日验收，
让主线恢复流动；复杂度只为真实风险付租金。

## 2. 现状证据

- 旧生产自 08-28 连续运行 47 天、0 重启；日链 58/58 PASS；唯一事件为 20260929（ADR 0015）与 6 次宿主休眠导致的次日补跑。
- R2D 全部在途设计都服务于"**交易时段内**（16:40–19:00）无缝切换"：因此才需要停放门、排空见证、WAITING_SOURCE 续接、
  首日 claim 等强合同（ADR 0011 §11-17、ADR 0012 §11-16）。
- 非交易时段（周六白天）里：没有数据窗口、没有信号截止、没有在途周期；旧 scheduler 每 15 分钟一轮 `NOOP`，不持有任何
  周期锁；候选启动后 daily→NOOP、shadow→已有 PASS 则 NOOP、paper→无待处理对账则 NOOP。排空与停放在这个窗口里**自动成立**。
- 现有原语已足够执行切换：`release.promote(no start)`、`start_current` 的容器合同验收（镜像 ID/只读根/四挂载/身份/健康）、
  `r2d_authorized_start` 的单次授权链（scope SHA、逐字批准、O_EXCL claim、MAY_HAVE_WRITTEN 屏障、receipt）。
- 唯一真正的阻碍是 `release_start_readiness`（release.py:305-358）：跨快照启动要求存在晚于最新 paper 执行日的"已完成或规划缺失
  的交易日"，周六不存在这样的日期 → 必然拒绝。该门防的是"新代码重算已完成的 FORWARD 产物"，而非交易时段里不会发生重算。
- 当前 HEAD 下任何 R2D 守卫都会被控制器门拒绝：13 组件白名单已被账本、AGENTS.md、新源码突破；R3N 四个源码/测试文件未跟踪，
  `docker-release-build` 的干净工作树检查也会失败。无论走哪条路都需要**新的基准提交与新的控制器清单**。

## 3. 候选方案

| 方案 | 内容 | 判断 |
|---|---|---|
| A 继续 R2D 原路 | 完成八组工作，交易时段内停放切换 | 数周；为"交易时段内切换"这个并非必要的目标付全部复杂度；期间主线继续停摆 |
| **B R2D-lite** | 周六 10:00–16:00 单次授权切换；新增 readiness 模式 `IDLE_WINDOW_CUTOVER`；复用现有 promote/start/单次授权链；周一首自然日用既有验收机器验收 | 新代码约两处（readiness 模式、scope v2 动作/窗口）+ 协议配置 + 控制器基准；fixture 复用 R2C/R3A；约一周会话 |
| C 放弃切换 | 旧镜像继续跑，锁权威改造搁置 | 修复永远进不了生产；7 月代码越来越远；不接受 |

**选择 B。** 代价：显式作废 ADR 0011/0012 的执行设计（其"证据不超 3600 秒/闭环尝试 1/1/2/独立重放"等检查项作为周六空闲门的
断言复用）；R3N 成果降级为离线证据；接受"切换本身发生在周六、验收发生在周一"的两日跨度。

## 4. 影响边界

- 不改任何判据、股票池、模型、调仓、paper-v1；不改 compose.yaml 的挂载白名单与加固；不改锁权威设计（ADR 0009 不变）。
- 不改旧生产镜像字节；不热补丁；不手工改标签。`make docker-scheduler-up` 的新守卫（2026-10-14）对授权路径无影响：授权路径直接
  调用 `docker compose up`，不经 make。
- 候选镜像以新基准提交从干净工作树构建；R3N 四个未跟踪文件须先**提交为离线证据**（否则构建上下文检查失败）或从受控目录移除。
  建议提交：它们已在全仓 2,454 项测试内，生产模块零引用。

## 5. 合同与数据迁移

**5.1 readiness 新模式 `IDLE_WINDOW_CUTOVER`**（release.py，+约 40 行）：PASS 当且仅当
- 最近开放日 D 的 daily/shadow 为 PASS，D 之前一个开放日的信号已在 D 对账 PASS，两账户在 D 的 paper_runs PASS；
- 下一开放日 > 今天（今天为非交易日），且当前时刻在协议窗口内；
- `health.json` 状态 ∈ {noop, pass}、年龄 ≤3600 秒且非未来值；
- 旧容器 `docker top` 仅有 scheduler 主进程（无 daily/shadow/paper 子进程）；`logs/scheduler/daily.lock` 可非阻塞取得并立即释放
  （旧代码的锁）；named volume 上 `runtime:*` 锁无人持有。
任何一项不满足即 `NOT_READY`，不猜、不等待。

**5.2 scope v2**（r2d_execution_contract.py，+约 60 行）：`schema_version: r2d-execution-scope-v2`，`action: CUTOVER_IDLE_WINDOW_ONCE`，
窗口为带时区的绝对起止（≤6 小时，不跨交易日，不滚动），绑定协议 SHA、git_head=origin_main、state/audit SHA、旧容器 64 位 ID、
候选镜像 ID 与代码快照、compose_project、`rollback_policy: FORBID_AFTER_DISPATCH`、`health_max_age_seconds: 3600`。
批准文本逐字：`批准 scope {digest} 在冻结窗口内仅执行一次非交易时段切换；派发后禁止自动回滚，不授权其他生产动作。`
单次性沿用 O_EXCL claim、MAY_HAVE_WRITTEN 屏障、不可覆盖 receipt。

**5.3 协议配置** `config/r2d_lite_cutover_v1.yaml`：候选/旧版身份、周六窗口、控制器组件清单（重新生成）、首日验收门、回滚窗口。

**5.4 控制器基准**：以新基准提交 B 重算 13（或增减后的）组件哈希；delta 白名单规则不变（账本/文档变化不得使守卫失效——
需把 `ledger/*.csv`、`AGENTS.md`、`STATE.md`、`docs/` 明确列为允许 delta，这是对 release_build_context.py:201-221 的一处修正）。

**5.5 作废与保留**
- 作废：ADR 0011 的 `POST_CLOSE_PARKED` 执行设计、ADR 0012 的停放/排空执行器与"候选在所有业务入口前停放"的要求。
- 保留：ADR 0011 的证据新鲜度/闭环计数/独立重放断言（并入 5.1）；ADR 0012 的"previous 必须是实际运行过的旧版"（promote 语义已满足：
  current=候选、previous=旧生产，切换后不再 promote）；ADR 0013/0014 代码与测试作为离线证据保留，不接线。

## 6. 执行序列（每步单独授权，结果前冻结）

1. 基准：提交 R3N 四文件 + 本 ADR + 协议 → 推送 → 基准提交 B。
2. 工程：readiness 模式、scope v2、协议加载与守卫，合成测试；全仓测试、架构门。推送 → 基准 B′。
3. 候选：`make docker-release-build` → 候选 C（内容寻址）。周六窗口外运行 R2C 锁 fixture 与 R3A 健康 fixture（它们会读写生产锁卷、
   起临时容器——须在非交易时段且旧生产 noop 时运行）。
4. 提升：`promote --no-start`（current=C，previous=旧生产）。注：当前 current 已是 b64ae11b 候选，需先以单次授权把 current 回指
   旧生产（`docker tag` 由工具执行并记审计，不手工），再提升 C；或由 promote 直接覆盖 current 并把 previous 固定为旧生产——
   协议中写死 previous 必须等于运行中的 722f63de。
5. 切换：周六 10:00–16:00，生成 scope v2 → 用户逐字批准 → `r2d_authorized_start --execute`：readiness(IDLE_WINDOW_CUTOVER) →
   屏障 → `compose up -d --force-recreate --no-deps scheduler` → 容器合同验收 → `START_PASS` → receipt。
6. 首自然日：周一 16:00 起候选自然运行；巡检 23:10 报告；验收 = daily/shadow/对账/两账户 PASS + `paper acceptance` + 独立重放 +
   通知留痕 + `assess_post_close`（离线断言）。全部 PASS → 周二记 STATE，R2D 关闭，G1 正控开工。
7. 回滚窗口：周六切换后至周一 16:00 前，任一容器合同/健康/巡检异常 → 以**新的单次授权**执行 `rollback(start=True)`（回到旧生产，
   同一周末内）；周一 16:00 后禁止回滚直至周一日链完成；首日验收失败 → 周一 23:30 后另立回滚授权，并保留候选全部证据。

## 7. 失败关闭

- 任何 readiness 项 NOT_READY、窗口外、state/audit SHA 漂移、旧容器 ID 不符、心跳过期 → 不派发，scope 关闭。
- 派发后未知终态 → `UNKNOWN_AFTER_DISPATCH`，禁止自动回滚，人工新授权。
- 构建上下文有未跟踪/已改受控文件 → build 失败关闭（现有行为）。

## 8. 验收指标

- 工程门：新增测试覆盖 5.1 每一否定分支与 5.2 的窗口/绑定/重放拒绝；全仓测试；架构 13 项；Ruff；脱敏。
- 切换门：`START_PASS` 记录含候选镜像 ID、四挂载、只读根、健康；receipt=`STARTED`。
- 首日门：如 §6.6；另要求 `shadow_runs.on_time=true`、`paper_runs.freshness_status=PASS`、飞书开始/完成投递 PASS。
- 关闭条件：首日门 PASS + STATE 记录 + ROADMAP 表行更新为 `R2D_CLOSED`。

## 9. 退出 / 复审触发器

- 若周六窗口因宿主不可用（见 STATE 2026-10-14 电源日志归因）连续两次错过，先解决宿主（ADR 005 修订或专用主机）再继续。
- 若首日验收失败两次，重新评估是否回到方案 A 的部分要素（例如真实业务端口接线）。

## 10. 需要用户裁决

1. 接受 R2D-lite，显式作废 ADR 0011/0012 的执行设计？
2. 同意把 R3N 四个未跟踪文件提交为离线证据（而非丢弃）？
3. 切换窗口定在周六 10:00–16:00？（备选：周日同窗口）
4. 宿主电源问题（STATE 2026-10-14 ⑤）的处置先于切换：a 纪律 / b `disablesleep` / c 专用主机？

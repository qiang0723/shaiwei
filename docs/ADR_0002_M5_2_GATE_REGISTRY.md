# ADR-0002：M5-2 独立门禁注册表与短命执行器

- 状态：`ACCEPTED_FOR_PROTOCOL_FREEZE`
- 日期：2026-08-05
- 决策范围：M5-2 协议、数据门与合成工程门
- 不授权：真实效果、标签、模型、回测、DeepSeek、外部采集、前瞻、模拟仓、生产或 scheduler 修改

## 1. 问题与结果目标

M5-1 已把非权威研究意图稳定保存到 `REVIEW_REQUIRED`，但其数据库、状态机和 API 被明确冻结为
proposal-only。M5-2 要把首份提案转成可审计的结果前协议，并在未来承载数据门和合成工程门；它必须
提供幂等、并发、崩溃恢复、负面证据和可重建状态，又不能把 M5-1 提案静默升级成研究授权。

本 ADR 的目标是确定长期边界，而不是提前运行研究：M5-1 继续只保存提案；M5-2 使用独立门禁注册表
保存协议冻结、逻辑批准和两类门事件；每个门由显式调用的短命、断网 Docker 入口完成。生产 scheduler、
Web 查询与 M5-1 服务均不成为研究执行器。

## 2. 现状证据与冻结输入

- M5-1 的权威边界见 `docs/ADR_0001_M5_PROPOSAL_CONTROL_PLANE.md`：proposal 不得原地升格为协议或
  执行证据。
- 当前提案由 `config/m5_dynamic_fundamental_cross_pool_proposal_export_v1.json` 内容寻址导出；
  导出同时绑定 proposal ID、request SHA、完整 canonical proposal SHA 和事件链头 SHA。
- 提案状态为 `REVIEW_REQUIRED`，到期时间为 `2026-08-12T10:48:16+00:00`。协议冻结和逻辑批准必须
  在到期前完成；过期后不得延长或复活，只能建立新提案。
- M5-0/M5-1、Web 和生产已有稳定能力不迁移、不回写；P2/M3 的成员 PIT、F1/F2 的基本面证据只作
  只读候选输入，任何哈希漂移都失败关闭。

## 3. 方案比较

### A. 扩展 M5-1 control 数据库

优点是可复用单库事务；代价是把非权威提案与权威协议/门证据放进同一故障域，需要迁移冻结的 schema
和扩大 Web/control 权限，违反 ADR-0001 的“不得原地升格”。拒绝。

### B. 独立 M5-2 gate registry 与证据仓

M5-1 只作为内容寻址、只读输入；新库只管理协议冻结、逻辑批准、DATA/ENGINEERING 门事件及证据。
它保留事务、幂等和恢复能力，又使 M5-1、研究门、Web 和生产可以独立回滚。选择本方案。

### C. 仅 Git 文件加一次性 Worker

文件最少，但无法可靠表达并发状态竞争、响应丢失、崩溃点、负面门事件和幂等重放，容易产生隐形重试。
Git 继续冻结协议，不能替代运行注册表。拒绝。

## 4. 决策

### 4.1 权威边界

1. Git 中先行推送的 ADR、协议、机器配置和 proposal export 是结果前冻结真身。
2. M5-2 registry 的事件链、脱敏追加式 ledger 和不可变 gate manifest 是运行真身；SQLite 是可以由
   这些证据重建的事务投影。
3. M5-1 schema/API/数据库零修改。proposal 在 M5-2 仅作冻结输入，绝不改写成 task。
4. 数据门和工程门必须分别批准：`DATA_GATE_APPROVED` 不能派生 `ENGINEERING_GATE_APPROVED`；任何批准
   都不派生效果、标签、外部调用、队列、模型、回测、前瞻或生产权限。
5. M5-2 当前不新增常驻服务、监听端口、工作队列、lease、heartbeat 或自动重试。每个门必须由显式
   受信 CLI 同步启动。

### 4.2 Protocol scope、release scope 与两段批准

`protocol_scope_sha256` 至少绑定：

- proposal ID、request SHA、canonical proposal SHA、proposal export SHA、事件链头 SHA；
- protocol 路径、物理 SHA、先行 Git commit 和远端祖先证明；
- ADR、机器配置、架构宪法和基础代码身份；
- 本协议只允许的 `DATA_GATE` / `SYNTHETIC_ENGINEERING_GATE` 及全部未授权项。

每个门另有独立 `release_scope_sha256`，它必须绑定 protocol scope、已先行提交推送的实现 commit、
代码束、不可变 Docker image、输入 manifest、挂载、网络、资源、输出和 auditor 身份。这样协议先
冻结、实现后施工、release 再批准，不会要求协议冻结时凭空绑定尚不存在的镜像。

actor 只能诚实写为本机职责 `M5_LOCAL_PROTOCOL_APPROVER`，不得伪造第二个人。数据门 release 只能
追加 `DATA_GATE_APPROVED`；只有数据 GO/PARTIAL GO 且新的工程 release 已先行冻结，才能追加
`ENGINEERING_GATE_APPROVED`。两次批准各自精确绑定 release scope、决策、有效期和权限；对应 scope
任一身份变化即失效。proposal 必须在数据门批准时仍为 `REVIEW_REQUIRED` 且未过期；批准后的 M5-1
取消不回写 M5-2，停止或撤销只能在 M5-2 追加 `REVOKED/STOPPED` 事件。

### 4.3 独立存储

新库建议路径：`data/control/m5_2/runtime/gate_registry.sqlite3`。schema v1 只含四类表：

1. `gate_cases`：当前投影；冻结身份、六轴状态和 current event seq，只有状态与 seq 可更新；
2. `gate_events`：append-only hash chain；记录 IMPORT、PROTOCOL_FROZEN、DATA_GATE_RELEASE_READY、
   DATA_GATE_APPROVED、REVOKED、DATA_GATE_STARTED/RECORDED、ENGINEERING_GATE_RELEASE_READY、
   ENGINEERING_GATE_APPROVED、ENGINEERING_GATE_STARTED/RECORDED、CLOSED/BLOCKED；
3. `idempotency_receipts`：actor/route/key/request/response，并以 `case_id,event_seq` 正反绑定事件；
4. `outbox`：把已提交事件幂等发布到脱敏追加式 gate ledger，不是任务队列。

schema、列、外键、索引、trigger 和关键 SQL 形成冻结 fingerprint。运行使用 WAL、FULL、foreign keys、
`BEGIN IMMEDIATE`；command、event、receipt 必须可全库双向重建。未知 schema、孤儿事件、链断、同键异体
或 outbox 不一致一律失败关闭。

### 4.4 状态与结论

六个轴必须正交：`lifecycle_state`、`data_gate_status`、`engineering_gate_status`、`evidence_tier`、
`authoritative_outcome`、`production_authorization`。

合法主链：

`PROTOCOL_FROZEN → DATA_GATE_RELEASE_READY → DATA_GATE_APPROVED → DATA_GATE_RUNNING →`
`DATA_GO | BLOCKED_DATA`

只有 `lifecycle_state=DATA_GO` 且
`data_gate_status ∈ {DATA_GO_FULL, DATA_GO_PARTIAL}` 可进入：

`ENGINEERING_GATE_RELEASE_READY → ENGINEERING_GATE_APPROVED → ENGINEERING_GATE_RUNNING →`
`ENGINEERING_GO | BLOCKED_ENGINEERING → CLOSED`

证据等级最高只到 `ENGINEERING_GO_ONLY`；策略结论始终 `NOT_EVALUATED`，生产授权始终 `none`。数据
不足是 `BLOCKED_DATA` 或候选级 `DATA_REJECT`，不是策略 REJECT；工程门失败也不能改写数据门结论。
FULL/PARTIAL 事件必须保存按协议顺序排列且互斥完备的 `eligible_candidate_ids` 与
`rejected_candidate_ids`，以及完整 8×3 矩阵；PARTIAL 允许进入 synthetic 工程门，但不能补候选或缩成
单池研究。

### 4.5 Runner 与审计

- DATA runner 只读取 allowlist 中的成员 PIT、财报/日历证据和冻结配置；不得读取标签、未来价格、收益、
  排名、封存效果或模型产物。它只写 case staging。
- ENGINEERING runner 只用 synthetic fixture 验证 8 候选、3 池、24 单元、schema、确定性和失败路径；
  不读取真实数据，不生成本批真实因子值。
- 独立 auditor 不导入研究计算入口，只读重算物理/规范哈希、门状态、矩阵唯一性、`.BJ`、PIT 和双跑
  一致性。runner 自报 PASS 不能直接成为 GO；registrar 仅在 audit PASS 后封存 manifest 并追加事件。

## 5. Docker 与权限

- registry、runner、auditor 均为短命、非 root、只读根、`cap_drop: ALL`、`no-new-privileges`、
  `network_mode:none`，默认 profile 不启动；
- 不挂 `.env`、`.git`、Docker socket、生产 compose、标签/效果目录或 scheduler 路径；
- registry 仅窄写自己的 runtime 和 outbox staging；runner 仅窄写本 case staging；auditor 只读 runner
  产物并窄写 audit staging；
- DATA runner 建议不超过 1 CPU、2 GiB、128 PID；ENGINEERING runner 1 CPU、1 GiB、128 PID；
  auditor 0.5 CPU、512 MiB；
- 不注入 Tushare、DeepSeek 或飞书凭据，不联网补采，不改变生产容器身份。

## 6. 公共合同与 Web

M5-2 将来只产生单一原子只读投影，至少包含 proposal、protocol、两个门、8×3 矩阵、multiplicity、
authority 和 next legal action。Web 不直读 registry DB；它只读取由事件 ledger 生成的不可变投影包。

当前不改 Web。协议和 gate 投影稳定后另立小目标接入；Web 继续显示 `REVIEW_REQUIRED`，不得提前显示
候选通过、收益、排名、最佳候选、freeze/release/enqueue/run 控件或伪造多人会签。

## 7. 迁移、回滚与恢复

- M5-1 零迁移。M5-2 首事件前可删除空 provisional 库；产生首事件后，schema 变化必须新 ADR、v2
  离线 export、hash、shadow rebuild 和 atomic rename，禁止自动 ALTER。
- 回滚只停止 M5-2 CLI/runner，保留 Git 协议、store、ledger 和所有负面证据；M5-1/Web/生产继续运行。
- 门前取消追加 `CANCELLED_BEFORE_GATES`；门后只能追加 STOPPED/INVALIDATED，不删除或回写。
- 数据库损坏时，从 Git freeze envelope、append-only ledger 和 immutable manifests 重建新库，全量
  hash 比对通过后才可原子切换。
- Git 协议纠错只允许 superseding protocol/addendum，不 reset、不 amend 已发布冻结证据。

## 8. 验收与复审触发器

M5-2A 至少证明：协议 commit 已推送且早于 gate started；proposal 在数据门批准时未过期且仍为
REVIEW_REQUIRED；
proposal/export/protocol/config 哈希一致；状态边、stale seq、同键异体、并发、崩溃点、outbox 重放、
schema/ledger/manifest 篡改均可失败关闭；零标签/效果、零 provider、零费用、零生产变化。

若出现真实发现/效果读取、任务队列、自动 Worker、常驻 controller、远程/多人权限、外部调用、模型、
回测、前瞻或生产发布，必须另立 ADR/协议。M5-3 如需执行 store，只能通过 M5-2 的
`engineering_gate_event_sha256` 衔接，不能复用 gate registry 充当通用作业系统。

# M5-2B 动态基本面数据门施工协议（执行前冻结）

- 施工协议 ID：`m5-dynamic-fundamental-data-gate-build-v1`
- 上游 protocol scope：`ab8c33968c4ced325ec79524b774163f2991edd0c4d5d7eb7c139b27e9b17557`
- 机器真身：`config/m5_dynamic_fundamental_data_gate_build_v1.yaml`
- 本阶段终态：`RELEASE_READY_NOT_APPROVED`

## 1. 施工目标与停止线

本阶段只施工、测试和发布 M5-2 DATA_GATE 的合同、候选级 PIT 计算、24 单元门阵、独立审计、独立
registry 以及短命离线 Docker。测试只用完全合成且不含真实证券/财报的数据。

施工完成后生成内容寻址的实现 commit、Docker image、输入身份 manifest 和 data release scope，然后
停止。用户以 `M5_LOCAL_PROTOCOL_APPROVER` 对精确 release scope 另行批准前，禁止：

- 读取真实财报行、真实候选值或 24 单元覆盖结果；
- 初始化项目内正式 M5-2 registry、追加正式 gate 事件或 ledger；
- 运行真实 data gate、synthetic engineering gate 或任何标签/效果阶段；
- 联网、补采、调用 DeepSeek、读取密钥、训练、回测、生成信号或改生产/Web/scheduler。

输入身份清单的构建仅可读取路径、schema、文件大小、行数元数据和物理哈希，不得扫描财务列值。

## 2. 模块边界

新能力位于 `shaiwei.research_gates`，不扩写既有 F1/F2 大文件：

1. `m5_dynamic.contract`：加载并严格校验冻结协议、build contract、release scope 和输入 manifest；
2. `m5_dynamic.statements`：按报表独立做版本选择和候选所需组件配对；
3. `m5_dynamic.features`：八个纯函数公式及有限值/正负/分母/staleness 规则；
4. `m5_dynamic.membership`：月末形成日、下一开市生效日和三池 PIT 成员映射；
5. `m5_dynamic.matrix`：覆盖、半年段、候选裁决、批裁决及非裁决相关性诊断；
6. `m5_dynamic.runner`：只编排 allowlist 输入与 write-once case staging，不含批准逻辑；
7. `m5_dynamic.auditor`：不导入 runner/features，从冻结公式和产物独立复算结构、门阵与哈希；
8. `gate_registry`：独立 SQLite v1 状态机、事件链、收据、outbox 与完整性验证。

生产 scheduler、M5-1 `research_control`、F1/F2、P2/M3、Web 和现有 compose 均不迁移、不改写。
单文件目标不超过 400 行；发现职责混合时先拆分，不允许用新巨型 runner 延续历史单文件增长。

## 3. 成员与形成时钟

每月 `formation_date` 是当月最后一个 SSE 开市日收盘；`effective_date` 是严格下一 SSE 开市日。因子
在形成日收盘已知、下一开盘执行，因此成员必须取 `effective_date` 当日的合法 PIT 成员，而不能取
形成日前成员或当前成员回填：

- P2 科创50官方逐日成员：使用 `effective_date` 对应的官方生效集合；
- M3 自建中盘/小盘逐日成员：使用 `trade_date=effective_date` 且按冻结 `universe_id` 过滤；
- M3 行内 `formation_date` 必须等于对应月末形成日，不能把另一形成批次的日成员错配进来；
- 输出同时保存 `formation_date`、`effective_date`、`universe_id`、`ts_code`；
- 缺下一开市日、缺任一池集合、重复键或出现 `.BJ` 均为全局完整性失败。

这一定义避免月末形成后、次日正式生效的成员变更被错配到旧池。

## 4. 候选所需组件与独立配对

F2 的“三张报表全交集”不得直接复用。M5 每个候选只要求自身公式列出的报表/字段：

- 每张报表先按 `ts_code/end_date` 和形成日独立选取当时已知的最新版本；
- 再按候选所需组件寻找最新、严格相隔一个日历年度的 `1231` 两期；
- 跨表候选要求所需报表的当前期/前期 `end_date` 分别一致，但不得要求未使用的第三张表；
- 候选 `available_date` 是其全部当前/前期组件可用日最大值，必须不晚于 formation close；
- 任何混期、非连续年、同身份冲突或未来版本计数非零均失败关闭。

外部融资依赖是唯一不要求前期现金流的候选：只需要当期筹资现金流以及本期/前期资产。最新年度不能
形成合法连续对时允许机械回退到更早连续对，完成配对后再执行 548 日陈旧门；不得为了非空值回退到
同一身份的旧版本。

八个候选的字段、公式、方向和顺序只从冻结 protocol 读取；runner 不支持临时公式、候选补位、按池
翻向或阈值覆盖。

## 5. 数据门行合同与裁决

长表主键固定为 `(formation_date, effective_date, universe_id, candidate_id, ts_code)`。每行只含审计
所需的 PIT 身份、当前/前期年度、候选可用日、staleness、值和无效原因；不含价格、标签、收益、IC、
排名、持仓、模型或效果列。

每个候选×池的分母是 2021-01 至 2025-12 全部形成日成员行。一个“有效形成月”必须同时满足该池
最低有效横截面，因此不是“当月至少一条非空”。门阵严格输出 8×3=24 个唯一单元，并逐项记录：

- 成员分母、有效分子、总覆盖和最差形成日覆盖；
- 有效形成月数、冻结十个半年段各自有效月数；
- 有效横截面最小值、stale/负值/无效分母/缺组件诊断；
- duplicate/mixed/nonconsecutive/future/source-conflict/`.BJ` 完整性计数；
- 单元 PASS/FAIL 和稳定阻断码。

候选必须三池全 PASS 才进入 `eligible_candidate_ids`。按协议顺序的 eligible/rejected 两集合必须
互斥、并集恰好八个；批裁决只允许 FULL/PARTIAL/NO-GO 三种冻结值。相关性只作诊断，不改门、不改
尝试数、不排名候选。

## 6. 输出与确定性

真实执行时每个 case 只写独立 staging，至少包含：

- `feature_panel.parquet`：上述长表；
- `data_gate_report.json`：24 单元、候选/批裁决、诊断与零效果声明；
- `run_manifest.json`：protocol/release/input/code/image/产物物理哈希；
- `audit_report.json`：独立审计结论和重算身份；
- 脱敏 append-only gate event/ledger 投影（仅 audit PASS 后由 registrar 发布）。

runner 双跑必须产生内容完全一致的 panel/report canonical payload；时间戳、临时目录和宿主绝对路径不
进入确定性内容。已存在目标若内容不同则拒绝覆盖。runner 自报 PASS 不等于 GO；auditor 必须独立
复算 8/3/24、主键、哈希、矩阵、候选集合、`.BJ`、PIT/时钟和未授权列，再允许 registrar 记录事件。

## 7. Registry v1

正式路径保留为 `data/control/m5_2/runtime/gate_registry.sqlite3`，但本阶段只在测试临时目录初始化。
schema 恰好包含 `gate_cases`、`gate_events`、`idempotency_receipts`、`outbox` 四表：

- `gate_cases` 只允许更新六轴状态与 current event seq，其余冻结身份不可变；
- `gate_events`、`idempotency_receipts`、已形成的 outbox payload 禁止 update/delete；
- event 使用 per-case seq 与 SHA-256 前向链；receipt 与 `case_id,event_seq` 正反唯一映射；
- outbox 是已提交事件的发布记录，不是执行队列，不含 lease/heartbeat/retry scheduling；
- WAL、FULL、foreign_keys、busy timeout、`BEGIN IMMEDIATE`、quick_check 和 schema fingerprint 强制；
- 从事件链重放得到的六轴投影必须与 `gate_cases` 逐字段一致，断链/孤儿/同键异体均失败关闭。

本阶段 fixture 覆盖 IMPORT、PROTOCOL_FROZEN、DATA_GATE_RELEASE_READY 以及数据门批准/开始/记录的
合法与非法边；真实 release scope 未批准前，正式库中这些事件一个也不能创建。

## 8. Docker 隔离

使用独立 `Dockerfile.m5-data-gate`、`requirements.m5-data-gate.lock` 和
`compose.m5-gates.yaml`，不扩大现有 1500 行 research compose：

- 精确 digest 的 `python:3.11-slim`，只装 pandas/numpy/duckdb/pyarrow/PyYAML；不装 qlib/torch/Web；
- 默认 profile 不启动，所有入口短命、non-root、read-only root、tmpfs `/tmp`、无网络、drop ALL caps、
  no-new-privileges、最多 128 PID；
- fixture 镜像不含 `data/ledger/logs/.env/.git`；真实 runner 以后只挂独立 `/inputs:ro` 与
  `/outputs:rw`，auditor 只读 runner 产物并窄写 `/audit:rw`；
- 不挂项目根、Docker socket、生产 compose、scheduler、标签/效果/模型目录或任何凭据；
- DATA runner 1 CPU/2 GiB，auditor 0.5 CPU/512 MiB，registry 0.5 CPU/512 MiB。

Docker 构建和 fixture 测试不得启动、重启或重建现有 scheduler/Web 容器。

## 9. Release scope 与批准

实现必须先提交并推送。之后 release scope 精确绑定：

- protocol scope 与本施工协议/机器合同哈希；
- 实现 commit、代码束哈希、镜像 repo digest/image ID、锁定依赖；
- metadata-only input manifest：成员/日历/财报批次的路径、schema、行数、bytes、物理哈希；
- 容器命令、挂载、网络、用户、资源、输出和独立 auditor 身份；
- 权限全为 false，仅 `data_gate_release_ready=true`。

scope 生成后先做脱敏、提交、推送和远端一致性检查，再向用户报告精确 SHA、到期时间和将读取的输入。
只有用户明确批准该 SHA 后，才能追加 `DATA_GATE_APPROVED` 并运行一次真实数据门。任何 commit、image、
input manifest、挂载或 proposal 状态变化都使批准失效，必须重新冻结 release，不能静默沿用。
与允许 API 无关的新增账本行不改变 scope；允许 API 出现新的相关财报修订批次则使旧 scope 失效，
不得在执行时静默改用“最新数据”。

## 10. 验收

施工验收至少覆盖：严格合同、八公式纯函数、候选级组件配对、next-open 成员、十半年门、24 单元、
FULL/PARTIAL/NO-GO、相关性不足、write-once、双跑、独立审计、registry 状态/并发/篡改/崩溃/outbox
恢复、Docker 离线/非 root/只读/窄挂载和凭据扫描。全仓测试、Ruff、compileall、pip check、架构检查、
Compose 解析、git diff check 必须通过；生产 scheduler 身份前后不变。

本协议完成时：`real_financial_rows_read=false`、`real_candidate_values_computed=false`、
`data_gate_approval_recorded=false`、`data_gate_execution_count=0`、`effect_test_count=0`、
`provider_call_count=0`、`strategy_effective=NOT_EVALUATED`、`production_authorization=none`。

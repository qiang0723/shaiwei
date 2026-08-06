# ADR-0004：M5 财报冲突必须由可用时点版本谱系解除

- 状态：`ACCEPTED_FOR_PROTOCOL_FREEZE`
- 日期：2026-08-06
- 决策范围：M5-2B-R2 财报来源内部冲突的版本识别、时点可用性、恢复门与后续扩展边界
- 不授权：真实财务读取、真实冲突诊断、外部采集、源值选择、PIT/候选计算、标签/效果、模型、回测、
  Web、生产或 scheduler 修改

## 1. 问题与结果目标

M5-2B-R1 在冻结输入中确认 23 个相同五字段来源身份对应不同业务值的冲突组，其中资产负债表 8 个、
现金流量表 15 个。R1 正确地封存了 DATA NO-GO，但没有回答这些差异是源端更正、重复拉取的版本漂移、
解析差异还是无法解释的分叉。

R2 的目标不是把 23 组冲突“消掉”，而是回答一个更窄的问题：是否存在不看候选效果、能够独立复算
且对每个历史形成日成立的版本顺序。只有版本的发布或修订生效时点可证明、顺序唯一、适用区间完整，
相应财务值才可能进入后续 PIT 数据门。

## 2. 已知事实与不可触碰边界

- R1 case `a2539149…2068` 已在 event 6 进入 `BLOCKED_DATA`；release v4、三件 runner 产物、audit、
  registry 和 23 组冲突承诺永久保留，不回写、不重跑、不改变裁决。
- 原研究配置的八式、三池、24 单元、公式、方向、548 日陈旧度、覆盖门槛、未来窗和尝试 `N=14/20`
  全部不变；策略仍为 `NOT_EVALUATED`。
- 现有五字段身份为 `(ts_code, f_ann_date, end_date, report_type, update_flag)`。冲突发生在这五字段相同
  的组内，因此仅凭 `f_ann_date` 或相同的 `update_flag` 不能给组内不同值排序。
- 本地 `ingest_time` 只能证明“筛微何时观察到一个批次”，不是源端何时发布或修订该财报。历史回填时
  第一次在本地看到的当前值，不能反推它在更早形成日已经可用。

## 3. 方案比较

### A. 最新本地批次、VIP、非空率或多数值优先

能快速生成单一值，但把抓取时间、接口类型或出现次数误当权威版本顺序；会把当前版本回填到过去，
且选择规则是在看见冲突后提出。拒绝。

### B. 删除冲突组，其余证券继续计算

避免选边，却会对候选和股票池形成选择性缺失；影响方向未知，也改变冻结覆盖口径。拒绝。

### C. 先做独立版本谱系可行性门，只有完整历史链才允许后续重建 PIT

把版本识别与候选计算分离。先用不可变批次元数据、逐版本值承诺和权威发布/修订证据构造版本链；
缺少权威时点、存在分叉或只知道本地首次观察时间时保持阻断。选择本方案。

## 4. 决策

### 4.1 三种时间必须分离

1. `statement_f_ann_date`：源行声明的财报实际公告日；继续按盘后保守规则在下一交易日可用；
2. `provider_revision_effective_at`：能区分相同五字段身份不同值的权威发布/更正生效时点；它是历史
   版本排序的必要证据，不能由本地时间推导；
3. `local_observed_at`：不可变 ingest ledger 的抓取时间；只证明最迟在该时刻观察到该版本，可作为
   前瞻下界和审计证据，不能证明更早历史可用。

若版本没有独立的 `provider_revision_effective_at`，则最多标记为 `FORWARD_ONLY_OBSERVED_VERSION`；
它可从 `local_observed_at` 之后进入未来另立的前瞻协议，但不能满足本轮冻结的历史数据门。

### 4.2 版本链的最小证据

每个冲突身份组必须在不暴露原值的本地受控环境中生成：

- 五字段 statement identity；
- 对本表全部冻结业务字段规范化后的 `value_version_sha256`；
- 来源 API、请求参数承诺、不可变 batch ID/content SHA 与 `local_observed_at`；
- 权威证据的来源类型、文档或记录 SHA、明确的发布/修订生效时间和可重复定位符；
- 每个版本的半开适用区间 `[effective_at, next_effective_at)`；
- 版本链和适用区间的 canonical commitment。

公开/提交报告只保留表级聚合、处置计数和 commitment；证券代码、日期、原值、候选值、绝对路径和
可逆行载荷继续禁止出项目忽略区。

### 4.3 互斥处置

- `LOSSLESS_EXACT_DUPLICATE`：值承诺一致，无损折叠；
- `PIT_VERSION_CHAIN_RESOLVED`：每个不同值都有权威时点，顺序唯一且适用区间完整；
- `FORWARD_ONLY_OBSERVED_VERSION`：只有本地首次观察时点，历史不可回填；
- `UNRESOLVED_MISSING_EFFECTIVE_TIME`：至少一个不同值缺权威时点；
- `UNRESOLVED_AMBIGUOUS_ORDER`：同一时点多值、顺序冲突或分叉；
- `UNRESOLVED_INCOMPLETE_CHAIN`：存在无法解释的跳变、回滚或证据缺口。

任何后三类未解决处置，或仅有 `FORWARD_ONLY_OBSERVED_VERSION`，均不能使历史门通过。禁止 latest
wins、standard/VIP 优先、`update_flag` 大小排序、非空优先、多数投票、数值容差、按效果选源和删除
冲突组。

### 4.4 两阶段恢复，网络与语义读取不混跑

- `LINEAGE_FEASIBILITY`：未来经精确批准后，仅断网读取冻结的本地批次元数据、五字段身份和业务值
  commitment，判断现有证据能否构造完整链；不计算 PIT/候选/覆盖。
- `AUTHORITATIVE_EVIDENCE_ACQUISITION`：只有 feasibility 明确指出缺什么后，才可另立采集协议和预算，
  使用权威公告或带版本语义的源补证；网络采集不得和 DATA_GATE 在同一 release 中发生。

这样即使离线门再次 NO-GO，也能精确回答缺失证据类型，而不会用外部访问或候选结果临时改规则。

### 4.5 权威裁决与后续状态

R2 feasibility 的批级裁决只能是：

- `GO_M5_2_SOURCE_LINEAGE_RECOVERABLE`：全部历史冲突组均为 `PIT_VERSION_CHAIN_RESOLVED` 或无损重复，
  且独立 auditor 复算一致；只授权另立新的 DATA_GATE release，不直接运行候选；
- `NO_GO_M5_2_SOURCE_LINEAGE_PREEXECUTION`：任一冲突组历史链不完整；新 case 进入 `BLOCKED_DATA`，
  策略仍为 `NOT_EVALUATED`；
- `STOPPED`：控制身份、I/O 或封存失败，不能登记数据结论。

R2 不复活 R1 case。新 protocol scope 派生新 case，registry v1 四表零迁移；R1 的 NO-GO 作为前置证据
绑定但保持权威。

### 4.6 独立审计

auditor 不导入主版本链构造器。它重读同一 allowlist，独立规范化值 commitment、验证权威时点来源、
重建区间并复算全部处置、批裁决和脱敏报告。runner 的 GO/NO-GO 或退出码都不能单独进入 registry；
只有 audit PASS 后才能登记。

## 5. 架构、迁移与回滚

- 版本谱系是数据/领域内核，不依赖 runner、registry、Web、通知、`.env` 或 Docker；文件与外部证据由
  窄适配层读取，编排层只负责组合和 write-once 封存。
- 不修改现有 `source_conflicts.py` 的 R1 语义；未来实现新增窄模块，避免让既有分类器同时承担版本
  发现、证据读取和裁决。
- registry schema v1 零迁移；新报告只通过既有 evidence SHA 和简化状态投影进入 registry。
- 回滚只停止新 R2 runner/auditor，保留协议、scope、case、产物和负面证据；生产与 M5-1 不变。

## 6. 验收与复审触发器

纯合成施工至少覆盖：本地观察时间不得冒充修订时间、相同 update flag 不得排序、唯一双版本链、同刻
分叉、缺中间版本、回滚、未来版本、精确重复、报告泄漏、runner/auditor 独立复算、双跑逐字节一致、
旧 R1 case 重放和 registry NO-GO。任何真实读取、外部网络、权威源新增、字段扩展、历史起点变化、
删除冲突样本、效果读取或公式/门槛变化，都必须进入新的 release 或协议，不能夹带。

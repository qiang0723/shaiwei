# M5 多股票池策略工厂：研究方法与治理设计（2026-08-05）

> 状态：`PROPOSED_FOR_MAIN_CONTROL_REVIEW`
>
> 建议裁决：`GO_FREEZE_M5_0_CONTROL_PLANE_PROTOCOL_ONLY`
>
> 本文不授权：真实研究、DeepSeek、数据采集、模型训练、回测、前瞻、模拟仓、Web 写生产或生产发布

## 1. 结论

筛微应把“针对不同股票池持续提出、验证、淘汰策略”建设为固定的平台能力，但不能把它做成一个可在
网页上随意试参、跑回测和一键上线的实验游乐场。建议建设的是受控的多股票池策略工厂：Web 负责
登记假设、生成草案、发起审批、观察状态和读取证据；确定性控制面负责冻结协议、排队、执行、审计和
裁决；一次性 Docker Worker 负责计算；生产 scheduler 始终位于研究系统之外。

统一闭环固定为：

`登记股票池 → 提出机制假设 → 冻结四维身份与评价矩阵 → PIT数据门 → 合成工程门 → 发现期 → 结果盲审查 → 封存效果门 → 独立审计 → 因子级准入/淘汰 → 模型与组合独立验证 → 前瞻 → 生产评审`

M5 首先统一身份、状态机、尝试数、门禁和证据合同；不应在第一目标中同时施工新策略结果。只有这样，
未来不断增加股票池、因子、模型和组合时，平台仍能回答“这个结论究竟对哪个对象、在哪个时点、按哪套
规则成立”，而不是积累一批无法比较的回测。

## 2. 必须继承的既有结论

1. M1 已证明因子定义与股票池身份必须分离；同一公式跨池仍是同一生成假设，但每个池是独立评价单元、
   独立准入结论。
2. M3 已证明跨池评价不能让子池各自翻方向；同一规范 AST、参数和方向必须保持不变，结果后增加股票池
   或改变池规则属于新协议。
3. M4 已证明“数据可构造”“方向成立”“局部改善基线”和“所有效果门通过”是不同结论；任一局部门
   通过不得包装成因子或策略有效。
4. M1/M3 的审查合同失败表明 LLM 响应只是候选输入，不是裁判；结构字段与自由文本不一致、服务端
   结束状态异常或响应不完整，都必须计数并停止，不能补发追成功。
5. M4 的工程、证据发布和审计恢复表明：工程失败、方法失效、证据未闭环、权威 REJECT 必须分层；
   原证据不得删除、覆盖或借恢复协议改研究参数。
6. 正式 `g1-v1` 的窗口不覆盖科创50合法 PIT 历史时，只能使用另名的股票池适配门，并明确它不是正式
   G1。不同池可以使用不同的、事前冻结的裁判版本，但不能共用名称制造可比性假象。

## 3. 四维身份：股票池、因子、模型、组合必须正交

“策略”不是一个不可拆分的名字，而是以下四个版本化对象的组合。任一维变化都产生新的评价身份。

### 3.1 股票池身份 `UniverseVersion`

最小字段：

| 字段 | 含义 |
| --- | --- |
| `universe_id / universe_version` | 稳定身份与规则版本 |
| `universe_kind` | `OFFICIAL_INDEX_PIT` 或 `CUSTOM_RULE_BASED` |
| `official_code` | 官方池必填，自建池必须为空 |
| `constituent_rule_version` | 成分规则或自建形成规则版本 |
| `membership_pit_snapshot_sha256` | 逐日 PIT 成员真身 |
| `membership_lineage_evidence_id` | 公告、发布、生效和修订谱系证据 |
| `benchmark_id` | 与该池匹配的事前基准 |
| `earliest_usable_date / latest_usable_date` | 合法研究时间域 |
| `market_rule_policy_id` | 分板块、分日期的涨跌停、交易单位和 ST 规则 |
| `data_gate_decision_id` | 当前数据门权威结论 |

股票池未通过 PIT 数据门时，只能登记和发起数据恢复草案；不得创建因子评价、模型或组合任务。官方
科创100/200当前仍应显示为 `BLOCKED_OFFICIAL_LINEAGE / NOT_EVALUATED`，不能显示成策略失败。自建
池必须始终展示 `CUSTOM_RULE_BASED`，不得使用官方指数名称替代。

### 3.2 因子身份 `FactorDefinitionVersion`

最小字段：

| 字段 | 含义 |
| --- | --- |
| `factor_id / factor_version / family_id` | 稳定定义、版本和经济机制家族 |
| `canonical_expression_sha256` | 规范公式或代码的内容身份 |
| `mechanism_hypothesis` | 结果前、可证伪的经济解释 |
| `expected_direction` | 结果前方向；不得按股票池或结果翻转 |
| `input_field_set_id` | 允许的数据字段及可用时点 |
| `lookback_policy` | 最大回看及缺失区间规则 |
| `decision_lag / availability_lag` | 信号时点和数据可用滞后 |
| `neutralization_policy_id` | PIT 行业、市值、基线等残差化合同 |
| `missing_value_policy_id` | 停牌、无效分母、覆盖分母和不可估计语义 |
| `source_type / parent_attempt_id` | 人工、论文、LLM、规则、迁移或变异来源 |

参数、窗口、算子、方向、数据字段、中性化或缺失规则任一变化，都必须增加版本或新因子身份；不能在
旧 `factor_id` 下静默覆盖。论文或 LLM 只能提供假设来源，不能提供有效性或准入结论。

### 3.3 模型身份 `ModelDefinitionVersion`

最小字段：

| 字段 | 含义 |
| --- | --- |
| `model_id / model_version` | 模型稳定身份 |
| `feature_bundle_sha256` | 精确因子集合、版本、方向和变换 |
| `label_id / horizon_id` | 标签时钟和预测期限 |
| `split_plan_id` | train/valid/test 与封存窗口 |
| `purge_embargo_policy_id` | 标签成熟、purge 和 embargo |
| `algorithm / hyperparameter_sha256 / seed` | 算法、超参数和随机性身份 |
| `training_code_sha256 / environment_lock_sha256` | 代码和依赖真身 |

一个模型可以包含多个因子，但“因子在某池通过”不等于“含该因子的模型有效”。模型必须独立证明相对
冻结基线的增量，并防止 M2/P2 曾暴露的标签成熟越界、valid/test 污染和重训漂移。

### 3.4 组合身份 `PortfolioPolicyVersion`

最小字段：

| 字段 | 含义 |
| --- | --- |
| `portfolio_policy_id / version` | 组合规则身份 |
| `selection_policy` | 排名、TopK、`n_drop`或分位选择 |
| `weighting_policy` | 等权、风险权重或其他预冻结权重 |
| `rebalance_policy` | 形成、调仓和持有时钟 |
| `initial_capital` | 主判资金规模 |
| `benchmark_id` | 组合基准，须与股票池一致 |
| `execution_policy_id` | 次日开盘、停牌、涨跌停、延迟卖出等 |
| `cost_policy_id` | 佣金、印花税、过户费、最低费用和滑点 |
| `liquidity_policy_id` | 买卖双向容量及历史窗口 |
| `concentration_policy_id / risk_policy_id` | 单股、行业、暴露和回撤约束 |

TopK、持仓数量、调仓周期、资金规模、成本或容量任一变化，都是新的组合评价，不是同一策略的展示
选项。Web 不得让用户在结果页改这些字段后立即重算并与原结果混排。

### 3.5 完整评价键 `EvaluationIdentity`

建议继续强制 M1 的有序身份，并扩展为：

`factor_id / factor_version / universe_id / universe_version / benchmark_id / label_id / horizon_id /
neutralization_id / window_set_id / cost_policy_id / decision_rule_version / model_id / model_version /
portfolio_policy_id / input_snapshot_sha256 / code_bundle_sha256 / protocol_sha256`

因子级任务允许 `model_id` 和 `portfolio_policy_id` 为空，但必须明确 `evaluation_level=FACTOR`；模型或
组合任务不得为空。字段顺序、增删和空值规则纳入 schema，canonical SHA-256 是 Web、Worker、账本、
报告和审计之间唯一连接键。

## 4. 尝试数与多重检验

### 4.1 四类计数必须分开

| 计数 | 定义 | 是否影响研究多重检验 |
| --- | --- | --- |
| `generation_attempt_count` | 每个新公式、代码假设或参数化定义；失败、重复、沙箱/语义拒绝都计 | 是 |
| `evaluation_unit_count` | 一个候选在一个预登记股票池上的评价 | 单独披露；不能冒充独立生成次数 |
| `effect_test_count` | 实际打开封存效果的候选×池×裁判单元 | 是，按冻结家族政策处理 |
| `engineering_attempt_count` | 无结果的实现、发布、挂载或审计工程尝试 | 否，但必须永久审计留痕 |

同一公式预先登记三个股票池：增加一次生成尝试、三个评价单元；不能记成三次独立发现。公式、方向、
参数或机制改变时，即使名字相似也增加新生成尝试。完全相同身份的幂等复跑不增加任何研究尝试。

网络重试只有在未形成完成响应、计费确定且原协议允许时才是同一传输尝试；完成响应、计费不确定、
结构/语义失败不得补发。工程失败发生在任何结果产物前，可记
`INVALID_ENGINEERING_ATTEMPT_NO_RESEARCH_DECISION`；一旦结果已可见，后续修正必须披露结果已知，
不能再声称盲预注册。

### 4.2 多重检验上下文

每个研究协议必须在结果前冻结 `multiplicity_context`：

- `research_domain_id`：如价量、资金流、基本面、残差风险；
- `family_attempts_before / planned_attempts / attempts_after`；
- `effect_tests_planned` 和完整股票池评价矩阵；
- 使用的 `multiple_testing_policy_id`、参数和适用层级；
- 同族主判与更广相关域敏感性两套 N；不得只挑更有利的一套；
- 跨池评价的相关性假设与处理；不得机械假定各池独立。

筛微既有 DSR、HAC/Newey-West 和窗口稳定性门继续由版本化裁判决定。M5 不在结果后统一改数值阈值，
也不强制把所有场景机械当作相互独立试验；它强制把生成次数、实际效果读取单元和裁判政策完整登记。
结果后新增股票池、成本场景、压力期或候选，必须另立批次并累计背景，不得追加到原批“顺便看看”。

## 5. 结果前生命周期

研究进度不能只用一个 `status` 表示。建议固定四个正交状态轴：

1. `lifecycle_state`：流程走到哪里；
2. `evidence_tier`：证据能支持什么；
3. `authoritative_outcome`：当前权威裁决；
4. `production_authorization`：是否允许触碰前瞻或生产。

### 5.1 生命周期状态机

| 状态 | 允许进入条件 | 允许动作 | 典型下一状态 |
| --- | --- | --- | --- |
| `DRAFT` | 用户或研究员提出机制 | 编辑草案，不读结果 | `SUBMITTED` |
| `PROTOCOL_REVIEW` | 四维身份、矩阵、预算和门槛齐备 | 人工复核、机器 schema 校验 | `FROZEN`或`CANCELLED` |
| `FROZEN` | 协议内容寻址且先行提交 | 只允许按协议建工程 | `DATA_GATE_RUNNING` |
| `DATA_GATE_RUNNING` | 股票池注册且源身份绑定 | PIT、覆盖、质量与幂等检查 | `DATA_GO`或`BLOCKED_DATA` |
| `ENGINEERING_GATE` | 数据 GO | 仅合成 fixture/零结果预执行 | `ENGINEERING_GO`或`BLOCKED_ENGINEERING` |
| `DISCOVERY_RUNNING` | 独立 release 和必要外部授权就绪 | 只读发现期、固定预算生成 | `DISCOVERY_LOCKED`或`STOPPED_CONTRACT` |
| `DISCOVERY_LOCKED` | 完成固定次数和机械选择 | 冻结候选，不读封存结果 | `BLIND_REVIEW` |
| `BLIND_REVIEW` | 审查载荷结果盲且合同冻结 | 负面筛选，不修式、不递补 | `VALIDATION_PROTOCOL_REVIEW`或`STOPPED_CONTRACT` |
| `VALIDATION_FROZEN` | 候选、窗口、成本、压力、统计全冻结 | 只允许构建唯一效果 release | `EFFECT_RUNNING` |
| `EFFECT_RUNNING` | 不可变镜像、输入和账本初态通过 | 恰好一次首遍和冻结复跑 | `AUDIT_PENDING`或`BLOCKED_EVIDENCE` |
| `AUDIT_PENDING` | 报告、产物、账本、manifest齐全 | 独立只读审计 | `CLOSED`或`INVALIDATED_METHOD` |
| `CLOSED` | 审计通过且权威结论发布 | 只读展示与幂等复核 | 新协议，不回写旧批 |

任何跨阶段动作都必须由后端状态机拒绝。`BLOCKED_*` 表示尚未评价，`STOPPED_CONTRACT` 表示本批合同
失败，`REJECT` 表示合法效果门已运行且不通过；三者不能互换。

### 5.2 证据等级

证据等级固定单向提升，不因后续效果 REJECT 回写旧层：

`PROTOCOL_ONLY → DATA_GO_ONLY → ENGINEERING_GO_ONLY → DISCOVERY_ONLY → REVIEWED_ONLY →
HISTORICAL_EFFECT_AUDITED → FORWARD_OBSERVING → FORWARD_ACCEPTED → PRODUCTION_RELEASED`

例如科创50的 P2 数据 GO 和工程 GO 不会因 P2-2C REJECT 而失效；原 P2-2 方法失效也不能覆盖
P2-2C 的纠错结果。Web 必须同时显示证据等级与权威结论。

### 5.3 权威结论建议枚举

- `NOT_EVALUATED`
- `BLOCKED_DATA / BLOCKED_ENGINEERING / BLOCKED_EVIDENCE_PUBLICATION`
- `STOPPED_CONTRACT / CANCELLED_BEFORE_RESULTS`
- `INVALID_ENGINEERING_ATTEMPT_NO_RESEARCH_DECISION`
- `INVALIDATED_METHOD`
- `REJECT_DIRECTION / REJECT_EFFECT / REJECT_REVIEW_BLOCKER`
- `GO_DISCOVERY_ONLY / GO_REVIEW_ONLY / GO_HISTORICAL_EFFECT_ONLY`
- `ADMITTED_FACTOR_FOR_UNIVERSE`
- `GO_FORWARD_REVIEW_ONLY / FORWARD_OBSERVING / FORWARD_ACCEPTED`

`ADMITTED_FACTOR_FOR_UNIVERSE`只准入精确因子×股票池评价身份，不授权模型、组合、模拟仓或生产。
生产授权始终使用独立枚举：`none / forward_candidate / canary_candidate / production_current`，且只能由
独立发布协议提升。

## 6. PIT、数据与执行门

每个评价任务必须在读取候选结果前通过以下固定类别：

1. **成员PIT**：官方池使用首批、公告日、生效日和修订谱系；自建池使用当时可知的上市、退市、ST、
   流动性和市值规则。当前成分、月末二级集合和ETF持仓不得回填官方历史。
2. **字段可用性**：每个字段登记源、发布/可用时点、revision policy和`availability_lag`；采集成功不
   等于当日可用。
3. **标签成熟**：train/valid/test末端按预测期限 purge，valid early stopping 不得读取 test 标签或
   价格；任何标签越界使方法失效。
4. **信号与成交时钟**：当日收盘决策、次日开盘执行时，开盘可成交只可读取当日 raw open、
   pre_close、tick和事前状态；不得用当日收盘 flags判断开盘。
5. **容量与无法成交**：买卖双向使用信号日已知历史成交额；持仓卖不出必须保留并后续重试，不能用
   目标持仓覆盖实际持仓。
6. **市场规则**：涨跌停、ST、交易单位、上市/退市和费用按板块与日期版本化；`.BJ`任一非零即
   fail closed。
7. **缺失与覆盖**：分母、合法不可估计、停牌、无行情和无行业/市值的处理结果前冻结；不能按结果
   选择性删除。覆盖门通过也不代表效果有效。
8. **基准**：每个股票池绑定事前合法基准；基准缺失记`NOT_EVALUABLE`并按协议失败，不造代理。

股票池合法历史不足以覆盖某裁判的固定窗口时，必须换成另名、另版本的适配裁判，或停止；禁止沿用
原裁判名称。适配门即使通过，也不能写成正式 `g1-v1` 通过。

## 7. 准入与淘汰

### 7.1 因子级准入

因子只有在精确股票池上同时通过以下事前门，才可获得
`ADMITTED_FACTOR_FOR_UNIVERSE`：PIT/shift、覆盖、方向、跨窗口稳定性、HAC、相关性/冗余、换手、
成本、容量、压力、多重检验和独立审计。正式库为空时必须显示空态，不能虚构相关性对照。

同一因子在A池准入、B池 REJECT、C池因数据阻断完全合法；平台不得生成一个跨池“综合星级”掩盖
差异。跨池迁移可使用事前指定的 home pool 冻结方向，但每个 transfer pool 仍独立裁决。

### 7.2 模型与组合级准入

因子准入后，模型和组合仍须分别冻结效果协议，证明：

- 相对同股票池合法基线的净增量；
- 多窗口和压力期稳定；
- 真实费用、容量、回撤和集中度可接受；
- 训练/预测、订单/成交、持仓/现金全链可重放；
- 与既有生产策略的持仓重叠、风格暴露和风险贡献可评估。

数据 GO、工程 GO、因子 GO 或历史组合 GO 均不自动创建模拟账户。历史通过后只能申请独立前瞻协议；
前瞻样本门达到前保持 `FORWARD_OBSERVING`，不得展示年化、Sharpe或信息比率等不成熟结论。

### 7.3 淘汰与停止

- 普通 REJECT：关闭本批，不翻方向、不调门槛、不追加同批变体；新机制另立家族并累计 N。
- 合同 STOP：不补发、不递补、不用剩余额度回救；候选效果保持`NOT_EVALUATED`。
- 数据 BLOCKED：允许未来按新来源恢复协议处理数据，不得把它表达成策略失败。
- 方法失效：原数值和证据永久保留并标`INVALIDATED_METHOD`，纠错批独立建立，不覆盖旧结果。
- 工程恢复：每次只授权有证据的最小变化；若结果已知，必须标注非盲恢复，不得借机改参数。

## 8. 独立审计与不可变证据

每个效果批至少生成并互相绑定：协议、执行 release、代码束、环境锁、输入 manifest、首遍产物、
确定性复跑产物、效果报告、运行账本、候选裁决账本和脱敏 manifest。

独立审计必须：

1. 不调用模型训练、候选生成或研究计算入口；
2. 重算物理和规范哈希、主键、行数、`.BJ`、PIT/shift及首遍/复跑一致性；
3. 从报告独立重建账本期望行，核对恰好一次和逐字段一致；
4. 重建 manifest 并核对全部输入、产物和账本；
5. 核实尝试数、多重检验上下文、候选裁决、通过数和总裁决；
6. 核实没有把适配门冒充正式G1，没有越权写正式库、前瞻或生产；
7. 审计通过后再披露候选效果，并以完成态复跑证明零新增、零改写。

恢复和纠错只能追加 protocol/addendum/authority overlay；旧协议、报告、账本和 manifest 不得删除或
原地改写。存储格式、Git过滤或换行规则也属于证据合同；Git入库前须证明克隆后物理哈希仍可复现。

## 9. 研究与生产隔离

1. 研究只在一次性、非 root、只读根 Docker Worker 中运行；上游数据和证据只读，结果目录和专属
   账本窄写，无 Docker socket、无宿主端口。
2. 普通研究默认 `network_mode:none`。数据采集或获批 LLM 调用使用专属一次性网络 Worker，secret
   只在需要时窄传入；不得把 Tushare、飞书和 DeepSeek 凭据一起注入。
3. Web 与控制 API 不读取原始 Parquet、`.env`、Docker socket或生产目录，只读取限字段、内容寻址、
   write-once投影。
4. 研究代码、配置或Web施工不得整仓挂载进生产scheduler。生产继续使用受控不可变镜像、只读根和
   持久化挂载白名单。
5. 研究通过后也不直接 promote。必须另立前瞻、模拟账户、canary和生产发布协议，分别绑定镜像、
   信号、账户、观察门和回滚证据。
6. 资源调度须避开每日生产窗口；Worker并发、CPU、内存和超时由队列配额冻结，研究任务失败不得
   影响scheduler退出状态或通知语义。

## 10. Web控制面的治理边界

Web 首期可提供以下受控写动作：

- 新建研究草案；
- 从冻结模板选择股票池、机制家族、发现/验证方案和预算；
- 提交协议复核；
- 对已生成的 canonical protocol 执行人工“冻结批准”；
- 对已冻结且后端返回 `available_actions` 的任务发起排队或取消未开始任务。

Web 首期不得：编辑冻结协议、粘贴任意Python、运行任意命令、改生产参数、解封结果、重跑已完成批、
删除失败证据、一键准入或一键上线。页面只展示后端给出的权威状态，不能自行从多个响应拼接“最新”。

主页面建议固定展示：

- 股票池研究地图：数据门、合法时间域、活跃家族、最近权威结论；
- `股票池 × 因子`矩阵：每格独立的证据等级与权威结论；
- 研究任务中心：阶段、预算、尝试进度、阻断原因、下一合法动作；
- 因子/模型/组合详情：四维身份、门禁、基线、成本、压力和证据链；
- 准入/淘汰历史：原结论、纠错、失效和authority overlay并列，不只显示当前成功项。

Web 所需核心字段建议为：

`study_id, protocol_id, evaluation_identity_sha256, lifecycle_state, evidence_tier,
authoritative_outcome, production_authorization, universe_id, factor_id, model_id,
portfolio_policy_id, generation_attempt_progress, evaluation_unit_progress, budget_authorized,
budget_consumed, data_as_of, frozen_at, started_at, completed_at, audited_at, blocker_codes,
available_actions, report_sha256, manifest_sha256, authority_overlay_id`

`available_actions`必须由后端状态机按身份和授权计算，前端不得自行推断。所有时间使用带时区ISO 8601；
所有英文机器枚举在主视图映射为中文业务语义，原值和哈希置于可展开技术证据。

## 11. 自动化止损与用户授权边界

平台化不等于授权它持续自我试验。建议冻结以下不可协商规则：

1. **一个协议只有一个有界批次**：必须同时冻结候选/响应上限、评价股票池矩阵、效果读取单元、费用、
   CPU/内存、最长运行时间和到期时间；任一项为空不得执行。
2. **终态不自动派生新批**：`REJECT`、`STOPPED`、`BLOCKED`、`PAUSED`或`CLOSED`后，队列不得生成
   新候选、递补、换池、调参或创建“下一轮”。未使用次数、费用和时间全部失效，不结转。
3. **自动恢复不等于自动研究**：只允许在同一冻结身份内做幂等复用，或执行协议已写明的传输层有界
   重试；完成响应、计费不确定、研究结果已见和身份变化都必须停机。
4. **并发受控**：同一研究域默认最多一个真实批次处于`DISCOVERY_RUNNING / EFFECT_RUNNING`；生产
   窗口内不启动重负载任务。排队不构成执行授权。
5. **LLM不拥有后续动作权**：LLM不得决定追加候选、解封样本、改变方向、提高预算、准入、开模拟仓
   或上线。其“建议继续”只能作为不可执行的研究备注。
6. **定时任务只做维护**：可以定时刷新已授权的数据、审计完成态哈希和生成只读投影；不得定时创建
   新研究假设或自动打开封存效果。若未来要做周期性因子挖掘，仍须按周期建立有界批次批准单。

每个新的真实因子批至少需要一份独立的结果前协议，并由用户对下列事项作批次级明确批准：

- 研究域和可证伪机制，不是“继续挖因子”的无限目标；
- 精确股票池及 home/transfer 评价矩阵；
- 生成方式、候选上限、失败/重复计数和机械选择规则；
- 发现、封存、压力和标签成熟边界；
- 多重检验背景、效果门、成本、容量和停止条件；
- 若有外部调用：供应商、对外字段、调用次数、单批费用上限和secret scope；
- 是否允许打开封存效果；该授权只覆盖已冻结候选和窗口；
- 明确`production_authorization=none`，除非以后另立前瞻/发布协议。

建议把授权拆成五个不能互相推导的记录：

| 授权 | 允许内容 | 不能自动推出 |
| --- | --- | --- |
| `protocol_freeze_approval` | 冻结本批研究设计 | 外部调用、效果读取 |
| `external_call_approval` | 固定载荷、次数和费用的联网/LLM批次 | 追加响应、封存效果 |
| `sealed_effect_open_approval` | 按已冻结release打开精确效果单元 | 新变体、前瞻 |
| `forward_account_approval` | 独立模拟账户/前瞻观察 | 生产发布 |
| `production_release_approval` | 指定镜像和发布窗口的受控上线 | 下一版本或新策略 |

项目级总预算、旧批剩余额度、某次“DeepSeek可以多用”或控制面工程GO，都不能替代新批的
`external_call_approval`。同理，用户批准 Web 草案/任务编排不等于批准外发数据或打开真实结果。

## 12. M5-0 建议验收边界

下一主目标只应建设“控制面工程门”，不运行新研究结果：

1. 冻结上述四维 schema、评价键、状态机、尝试计数和权限矩阵；
2. 建立 append-only `study / attempt / transition / decision / artifact` 账本合同；
3. 建立 protocol canonicalizer、状态转换器、权限判定器和完全合成 fixture；
4. 建立股票池注册表只读适配和统一裁判版本注册表；
5. 定义控制 API 与 Web 查询/草案/审批合同，但先不开任意执行和生产能力；
6. 定义一次性 Worker envelope、资源配额、secret scope和生产隔离测试；
7. 用合成任务覆盖正常闭环、PIT阻断、合同STOP、工程失败、方法失效、证据发布阻断、权威纠错和
   幂等复用，不读取现有封存结果。

全部通过只能裁定 `GO_M5_CONTROL_PLANE_ENGINEERING_ONLY`。随后应选择一个已具备合法 PIT、且经济
机制独立的新小批作为首个真实试点；试点仍须单独结果前协议和必要外部费用授权。M5 工程 GO 不等于
任何新因子、策略或生产结果。

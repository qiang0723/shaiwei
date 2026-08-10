# LLM 因子与策略研究工厂治理基线

- 基线 ID：`llm-research-factory-governance-v1`
- 固定日期：2026-08-10（UTC+8）
- 状态：`FROZEN_DESIGN_BASELINE_NOT_EXECUTION_AUTHORIZED`
- 当前主目标：`R2-1_FORWARD_EVIDENCE_CHECKPOINT`
- 当前授权：只固定长期设计；代码、DeepSeek、新候选、效果读取、模拟账户和生产变更均未授权

## 1. 总裁决

筛微长期采用“持续产生、严格验证、逐级准入、持续监控和可追溯淘汰”的研究工厂模式。LLM 是知识
侦察员、因子挖掘员、策略研究员、结果盲反方审稿人和研究记忆管理员；确定性代码、冻结协议、独立
审计和真实前瞻才是裁判。

当前路线没有偏离“拿到可信结果”的目标，但此前局部出现过恢复工程增长快于权威结果、候选数量增长
快于效果裁决的倾向。因此本基线固定长期方向，同时保持 2026-08-09 的
`COURSE_CORRECTION_AND_OBSERVE`：R2-1 到期前不建设常驻 Agent 平台、队列、Worker 或一键研究，不
新增 LLM 批次，也不因等待自然前瞻而制造任务。

本文件是未来协议的上位设计，不是任何外部调用、封存效果、模拟账户或生产发布的批准。旧 D1/M1/M3
协议、失败、STOP、REJECT 和计数保持原样；本基线不改写历史。

## 2. 稳定生产线与研究孵化线

```text
稳定生产线（当前 Mac）
日增量 → 中证800主策略 → Top30/Top20模拟账户 → 对账 → Web/告警

研究孵化线（未来独立高配置研究节点）
知识/机制 → 提案/去重 → 数据/PIT → 工程 → 效果/审计
          → 独立模拟账户 → 自然前瞻 → 监控/衰减/退役
```

两线必须满足：

- 研究节点不替换、不挂载或重启生产 scheduler；
- 研究使用不可变 Docker 镜像、内容寻址输入、独立目录、账本和资源上限；
- 中证800可以同时作为主策略股票池和独立研究股票池，但研究候选不得覆盖主策略身份、配置、模型、
  信号、Top30/Top20账户或历史；
- 新策略即使更好，也先建立独立模拟账户，不自动替换当前主策略；
- 生产切换、并行生产或资金组合必须另立发布、迁移、回滚和用户授权。

## 3. 因子研究与策略研究是并行分支

两类研究共享股票池身份、PIT、尝试计数、结果前冻结、成本、审计和前瞻底座，但不互相冒充。

### 3.1 因子分支

`机制假设 → 唯一 DSL/方向 → 规范化/去重 → 数据/PIT → 发现期 → 结果盲审 → 冻结效果 → G1/适配门
→ 独立审计 → ADMITTED_FACTOR_FOR_UNIVERSE 或 REJECT/STOP`

因子准入只对精确 `factor × universe × evaluation identity` 成立。因子准入不等于模型、组合、模拟仓
或生产有效。

### 3.2 策略分支

`单变量策略假设 → 冻结基线/反事实 → 数据/PIT → 工程 → 模型或组合效果 → 独立审计
→ FORWARD_CANDIDATE 或 REJECT/STOP`

策略研究可以不新增因子，例如只比较一个模型结构、一个固定因子组合权重、TopK、调仓频率或其他一个
组合变量。一次协议只能改变一个可归因变量，不能同时改因子、模型和组合。

## 4. LLM 五类角色

| 角色 | 允许 | 禁止 |
|---|---|---|
| 知识与机制侦察员 | 基于冻结的一手资料摘要和历史失败分类形成机制地图与可证伪问题 | 读取原始行情、持仓、封存效果；把论文结果当本项目证据 |
| 因子挖掘员 | 在冻结字段、DSL、主题、方向和次数内输出单一候选 | 执行代码、读取文件/网络、决定准入、要求追加候选 |
| 策略研究员 | 对冻结基线提出一个模型或组合变量及反事实协议草案 | 同时修改多维、训练/回测、看本批效果后选参数 |
| 结果盲反方审稿人 | 按构造、机制、PIT、稳定性、冗余和可证伪性做负面筛查 | 修公式、递补、给业绩/准入/生产结论、接收发现指标或 OOS |
| 研究记忆管理员 | 审计后整理终态、失败码、重复机制和工程教训 | 改写旧批、自动建 successor、把详细 OOS 反馈给同批生成器 |

首版研究记忆只接收权威终态和失败码，不接收详细样本外数值。若未来让它读取聚合效果，只能服务新的
`RESULT_KNOWN_SUCCESSOR`，并累计原研究域尝试 N。

职责边界：

- DeepSeek：严格 schema 下的创意生成、机制草案和结果盲反方审查；无工具、执行、数据读取或裁决权；
- 本地主控：选择合同、准备脱敏载荷、核对权限、编排一次性任务；若看见受限结果则退出该批经济裁决；
- 确定性代码：唯一负责 schema、AST、去重、PIT/shift、计算、成本、G1、计数、预算和状态转换；
- 独立 auditor：不复用生成器或主裁决实现，独立复算身份、主键、PIT、计数、门和权威终态；
- 用户：拥有协议冻结、外部调用、封存效果、模拟账户和生产发布的最终批准权。

## 5. 生命周期与证据语义

```text
PROPOSAL_ONLY
  → CANONICALIZED
  → DUPLICATE_REJECTED / PRECHECK_PASSED
  → PROTOCOL_FROZEN
  → DATA_GATE → BLOCKED_DATA / DATA_GO
  → ENGINEERING_GATE → BLOCKED_ENGINEERING / ENGINEERING_GO
  → DISCOVERY_RUNNING → STOPPED_CONTRACT / DISCOVERY_LOCKED
  → BLIND_REVIEW → REJECT_REVIEW_BLOCKER / VALIDATION_FROZEN
  → EFFECT_RUNNING → BLOCKED_EVIDENCE / INVALIDATED_METHOD / AUDIT_PENDING
  → REJECT_EFFECT / ADMITTED_FACTOR_FOR_UNIVERSE / FORWARD_CANDIDATE
  → FORWARD_OBSERVING → FORWARD_ACCEPTED
  → MONITORING → DECAY_WARN → DECAY_REVIEW → CONTINUE / RETIRED
  → ARCHIVED_IMMUTABLE
```

- `BLOCKED_*` 表示未评价；`STOPPED_CONTRACT` 表示合同失败；`REJECT` 表示合法效果已运行但不通过；
- `DECAY_WARN` 只触发人工复审，不能让 LLM 自动换因子、改仓或创建下一轮；
- `RETIRED` 表示不再用于新模型或新增资金，生产退出仍须独立协议；
- `ARCHIVED_IMMUTABLE` 不是删除，失败、REJECT、失效方法和历史复算实现都保留；
- 证据等级、权威结论和生产授权是三个不同维度，不得因页面或命名合并。

## 6. 默认最小研究批

R2-1 后的首个受控试点默认：

- 股票池：中证800；
- 研究域：一个独立经济机制；
- home universe：一个；首批不跨池，或最多一个预登记 transfer pool；
- 生成：8 个完成响应；
- 合格候选：最多 3 个；
- 选择：全部响应完成后机械锁定 Top1/Top2；
- 盲审：Top1/Top2 × 四角色，最多 8 个紧凑响应；
- 效果：一个 release、一次真实首遍、一次确定性复跑、一个独立 audit；
- 连续批次：最多 3 个小批后强制阶段复盘；该上限是首版节流，不是永久吞吐上限。

空、截断、schema/语义/DSL/沙箱失败和重复响应都计生成 N，不补第 9 次；跨池增加评价单元，不增加生成
N；工程失败单列 engineering attempt；打开封存结果才计 effect test。预算、次数和时间按批冻结，未用
余额不结转。旧 D1 的 40 响应、模型名、thinking 参数、价格和余额均不能自动成为新批真身。

第一次基础设施失败最多允许一个不改研究参数的有界 successor；第二次仍失败则关闭本批。公共组件
只有被至少 3 个真实批次证明复用后才抽取；此前使用现有内核上的薄适配，不建设通用队列。

## 7. 外发、安全与防止样本外偷看

每个 LLM envelope 至少绑定角色、study/protocol SHA、股票池/evaluation identity、data_as_of、允许/禁止
字段类别、prompt/knowledge/schema/code/input 哈希、attempt、预算、到期时间、discovery/sealed scope、
`result_blind` 和脱敏报告哈希。

禁止外发原始行情行、证券清单、持仓、订单、收益序列、封存/OOS/前瞻结果、`.env`、token、Webhook、
Authorization、绝对路径、日志、provider 原始错误正文、本地文件、SQL、Python、Shell或生产配置。

- 生成器和盲审容器物理上不挂载封存/OOS/前瞻目录；
- 所有响应完成后才机械选择；LLM 审查不修式、不递补；
- 封存效果使用独立 `sealed_effect_open_approval`；一旦打开，公式、方向、池、窗口、成本和阈值冻结；
- 复盘 LLM 与同批生成 LLM 使用独立、无共享对话上下文的 envelope；
- 新调用前重新核对供应商、模型、价格、缓存、计费和响应合同；`BILLING_UNCERTAIN` 立即停机。

## 8. 多策略模拟账户

新策略不必覆盖主策略。只有完成以下链条，才有资格申请独立模拟账户：

`DATA/PIT PASS → HISTORICAL_EFFECT_AUDITED → 执行规则冻结 → 用户批准`

- 每个账户拥有独立 strategy/account ID、初始资金、基准、信号、订单、成交、持仓、现金、NAV和账本；
- 默认初始资金 500,000 RMB，便于同类横向比较；不同股票池使用匹配的冻结基准；
- 账户从批准后的真实日期开始，历史 BACKFILL 不冒充自然 FORWARD；
- 多个有效且相关性不同的策略可以长期并存，未来另立多策略资金组合协议；
- 衰减、暂停和退役不删除账户历史。

## 9. 自动化与未来高配置研究节点

长期应自动化的是确定性编排、计算、证据生成、复跑、审计、状态投影和已批准模拟账户日更，而不是
授权、调门槛或生产上线。

高配置电脑就绪后，以独立 `research-worker` 身份接入：

- 只运行内容寻址、一次性、非 root、只读根的 Docker 作业；
- 与生产 scheduler 使用不同镜像、目录、资源和凭据边界；
- 不从开发工作树直接运行长期任务，不持有生产写权限或 Docker 控制面；
- 数据迁移、只读副本、密钥部署和网络路径另立迁移/安全协议；
- 连续至少 3 个小批证明控制合同稳定后，才评审任务队列和并发 Worker；首版串行。

## 10. Web 边界

不新增独立“LLM 操作台”。在现有策略工厂、因子工厂和实验详情中增加只读透镜：角色、模型/协议/
payload 哈希、外发字段类别、result_blind、封存区可见性、generation/evaluation/effect/review/engineering
计数、预算、失败码、生命周期、证据层、衰减/退役和下一合法动作。

Web 不展示原始 prompt/response/reasoning、证券清单、持仓或收益序列；不设综合分、成功率、排行榜或
“最佳策略”；不提供 external call、open effect、retry、admit、paper 或 production 按钮；不在前端
补算指标或拼装多个“最新”。现有 proposal control 只保留草案、送审和取消，不扩成执行控制面。

## 11. 分阶段路线与停止条件

### 阶段 0 · 当前

只积累 R2-1 自然前瞻。无异常时不新增代码、DeepSeek、候选、协议 release、Web、Worker 或生产改动；
旧 M5 提案按原期限到期，不延长、不复活。退出条件只认真实账本形成
`CHECKPOINT_OBSERVED` 或 `OBSERVED_WITH_EXECUTION_WARN`，并由用户阅读诊断。

### 阶段 1 · R2-1 后的试点准备

对中证800和一个机制做只读 canonical 去重、multiplicity、字段/时钟、metadata/coverage 预检；冻结
D1 successor、策略研究员和紧凑盲审合同，但不调用 provider。预检不通过即 `BLOCKED_PRECHECK`。

### 阶段 2—4 · 生成、盲审、效果

用户分别批准精确外发载荷/次数/费用和封存效果；按第6节小批完成生成、盲审、唯一效果、复跑和独立
audit。REJECT、INVALIDATED 或合同 STOP 即关闭并归档，不追加变体。

### 阶段 5 · 前瞻与衰减

只有历史准入后才申请独立模拟账户。衰减阈值、复审频率、退役和生产发布在首次真实准入后另立协议，
不在没有准入对象时提前造通用框架。

项目级停止条件：连续 3 个小批无历史准入，或 2 个真实批次因审查/调用合同失败，则暂停 LLM 生成线
并复盘；公共控制面未被 3 个批次复用则不建设；主策略和自然前瞻永远不因研究空档被改动。

## 12. 已固定与后置裁决

已固定：因子/策略并行、主策略隔离、多模拟账户、小批节流、角色5首版只读终态/失败码、Web只读、
未来研究节点隔离，以及 R2-1 前零施工。

后置到具体批次：供应商/模型版本、单批费用、外发知识摘要、机制主题和 transfer pool。后置到首次历史
准入：衰减阈值、复审频率、退役细则和是否建立正式队列。高配置电脑的硬件、数据迁移和网络部署在
设备确定后另立实施方案。

## 13. 继承证据

- `docs/D1_LLM_FACTOR_RESEARCH_ARCHITECTURE_20260725.md`
- `docs/D1_LLM_FACTOR_EXECUTION_ACCEPTANCE_20260725.md`
- `docs/D1_LLM_FACTOR_REVIEW_SEMANTIC_CORRECTION_20260725.md`
- `docs/LLM_REVIEW_CONTRACT_V2_ACCEPTANCE_20260802.md`
- `docs/M5_MULTI_POOL_RESEARCH_GOVERNANCE_20260805.md`
- `docs/M5_STRATEGY_FACTORY_ACCEPTANCE_20260805.md`
- `docs/PLATFORM_ROUTE_REVIEW_20260809.md`
- `docs/R2_1_FORWARD_CHECKPOINT_PROTOCOL_20260809.md`
- `docs/ARCHITECTURE_CONSTITUTION.md`

本基线不声明任何因子或策略有效，不改变正式因子库仍为 0、中证800仍为唯一主策略、R2-1 尚未到期
或生产授权为 none 的事实。

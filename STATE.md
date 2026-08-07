# STATE — 筛微施工状态（git 为真身，会话记忆为草稿）

> 每会话开工先读本文件；收工必更新「当前进度」与「待答点」。改判旧口径须显式作废并注明日期。

## 2026-08-07 · A1-1B D1传输合同解环完成，停在A1-1C前

- 新增纯合同模块`llm_factor_contract.py`，承载D1协议、候选schema、attempt/request规划和transport
  response值对象；不含HTTP、环境读取、账本写入或研究执行。旧`llm_factor`公共导入保持同对象兼容。
- `deepseek_client <-> llm_factor`循环已消除，全仓Python循环由2降至1；`llm_factor.py`由1,254降至
  944行并收紧机器上限，`deepseek_client.py`保持808行，新模块357行。
- ordinal 1 canonical request SHA保持`8ddb033e...e21c`；专项兼容、mock transport、恢复、敏感输出与
  未授权先停验证通过。未读取`.env`、未调用DeepSeek、未运行数据/研究/生产、未重启scheduler；七个
  自然账本保持未暂存。
- A1-1B到此停止，不自动进入A1-1C。下一建议包是M3 data/release解环，须新的继续指令；见
  `docs/A1_D1_TRANSPORT_CONTRACT_EXTRACTION_ACCEPTANCE_20260807.md`。

## 2026-08-07 · A1-1A执行内核迁移因冻结身份冲突暂缓

- 完整施工前置检查确认M4 v1协议写死P2-2C executor路径和物理SHA，当前M4 recovery release又绑定
  同时包含M4 metrics与旧executor的代码bundle；P2-2C manifest另有独立纠错代码身份。旧文件改
  wrapper、复制后切换或改写v1 release均会破坏合法历史复算或造成声明/执行不一致。
- A1-C01由待迁移改为`DEFERRED_FROZEN_IDENTITY_CONFLICT`：旧路径保持字节不变，现有机器门继续保证
  它是全仓唯一`src -> tools`债务并禁止新增消费者；只有版本化M4/P2 successor或显式复算归档ADR
  获批后再评审退出。
- 本节点生产代码/冻结文件修改0，删除0，数据/研究/外网/生产运行0，scheduler未重启；七个自然账本
  保持未暂存。下一安全包为A1-1B D1 transport/llm_factor解环，须新的继续指令。见
  `docs/A1_STAR50_EXECUTION_MIGRATION_DECISION_20260807.md`。

## 2026-08-07 · A1-0代码库只读审计完成，A1-1须用户复核后逐包授权

- 当前Git真身为1,068个跟踪文件、583个代码文件、121,353行已跟踪代码；核心Python 62,747行，
  Web UI 14,860行，tools 17,137行，Python测试23,654行。相对A1计划早间冻结点净增主要来自已关闭
  M6的release/runner/auditor与测试，不把有审计价值的代码按行数视为垃圾。
- 静态入口、Python依赖图、前端`main.tsx`可达性、重复函数、Git历史和动态CLI风险已复核；当前满足
  全部删除门的文件为0。零引用项均为历史release/复算/审计CLI；`vite-env.d.ts`为构建声明，均不删。
- 确认唯一`src -> tools`反向依赖位于M4复用P2-2C执行器；另有D1 transport/llm_factor和M3
  data/release两个循环依赖。建议A1-1依次只做执行内核提升、D1解环、M3解环，三包独立提交与回滚；
  Web/D1/config热点继续no-growth并在真实需求触碰时小步抽职责。
- 本节点未改生产代码、未删文件、未运行数据/研究/生产、未碰自然账本。A1-1不自动授权，须用户先
  复核候选清单；完整证据见`docs/A1_CODEBASE_INVENTORY_20260807.md`及
  `config/codebase_inventory_a1_0_20260807.yaml`。

## 2026-08-07 · M6-3C-R3数值谱系复原完成，生产环境已识别但因果未证

- scope`70ae0cc5...5b87`下双镜像probe、collector和独立auditor各唯一成功一次；Top30/Top20新回测、
  Qlib、训练、预测、研究尝试、外网和生产写入均为0，同scope已关闭。
- 规范生产身份完整；两镜像关键包/BLAS版本和原执行器源码一致。主要竞争差异是规范6线程/6 CPU/
  12 GiB完整effect流程，对比诊断1线程/2 CPU/4 GiB单臂入口，以及两base整体内容地址不同。
- 独立audit八项PASS，权威`PRODUCER_ENVIRONMENT_IDENTIFIED_NOT_CAUSALLY_PROVEN`；不能把线程差异
  或其他相关事实冒充唯一根因。5件产物整树`9888eb8e...dcae`，Top20继续禁止、生产none。
- 建议关闭M6-3C连续诊断并进入A1-0只读代码整理清单；若未来坚持因果验证，须另立单变量R4并重新
  授权，R3不自动授权。见`docs/M6_CSI800_TOP30_NUMERIC_PROVENANCE_EXECUTION_ACCEPTANCE_20260807.md`。

## 2026-08-07 · M6-3C-R3只读取证release就绪

- 结果盲实现已按职责拆为镜像探针、证据collector、ULP拓扑与独立auditor；全仓934 PASS，架构10 PASS，
  两套最终镜像断网合成fixture均PASS。无回测入口、无Qlib/Top20/账本/外网挂载。
- 正式scope`70ae0cc5...5b87`绑定实现Git`ad969dca...bde3`、两套base/thin镜像、24文件代码bundle、
  协议/Compose/Dockerfile、规范日报和R2整树；输出根为空。
- 用户继续指令已在冻结协议中授权一次original probe、一次failed probe、一次collector和一次独立
  auditor；同scope失败不得重跑。成功也不恢复Top20或生产。见
  `docs/M6_CSI800_TOP30_NUMERIC_PROVENANCE_RELEASE_ACCEPTANCE_20260807.md`。

## 2026-08-07 · M6-3C-R3零新回测数值谱系协议已冻结

- R3只复原封存规范日报、原M6镜像和失败M6-3C镜像的生产谱系；固定读取既有R2 rows、镜像/包元数据、
  Parquet producer、对应Git对象和依赖锁，不挂Qlib、不读Top20、不训练、不预测、不回测。
- 一次collector与一次独立auditor分别负责证据规范化和复算裁决；分类冻结为根因确认、生产环境已识别
  但因果未证、谱系缺口确认或混合未决。禁止用版本相关性冒充因果，也禁止事后增加容差或第四路。
- 用户“继续下一个任务”已授权该零新回测只读取证；协议提交必须先行推送，再实现与执行。Top20继续
  禁止、研究尝试增量0、生产none。见`docs/M6_CSI800_TOP30_NUMERIC_PROVENANCE_PROTOCOL_20260807.md`。

## 2026-08-07 · M6-3C-R2六次Top30诊断完成，权威MIXED_UNRESOLVED

- 用户绑定scope`f4ade91b...2d13e`逐字批准后，original/current/audit各唯一调用一次并正常退出；
  Top30回放恰好6次、Top20 0、研究尝试增量0，同scope永久不得重跑。
- 三路内部双回放均逐位一致；失败镜像内原/新执行器完全一致，但原M6镜像、失败镜像和封存规范日报
  三者并不相等。独立audit七项检查PASS，按冻结分类权威裁定`MIXED_UNRESOLVED`，不能归因成单独的
  新适配器、失败镜像环境或统一历史复现缺口。
- 两类差异最大绝对值仅`7.53e-16`/`6.18e-16`，但严格门禁止事后加容差。正式7件产物整树
  `5c58f796...750c`，audit`db03a7e5...8c75`；策略仍`NOT_EVALUATED_FOR_PRODUCTION`、生产none，
  Top20继续禁止。
- 若继续只能另立M6-3C-R3零新回测的数值谱系复原协议，查封存生成环境、依赖/BLAS/序列化和既有
  rows差异；不得重跑本scope或放宽比较门。见
  `docs/M6_CSI800_TOP30_COMPATIBILITY_DIAGNOSTIC_RECOVERY_EXECUTION_ACCEPTANCE_20260807.md`。

## 2026-08-07 · M6-3C-R2编排恢复release就绪，停在新精确授权门前

- 新scope`f4ade91b...2d13e`绑定恢复/base协议、实现Git`9c36088f...935e3`、两套正式镜像、代码
  bundle、Compose/Dockerfile、旧失败输入、三路命令/挂载/资源和独立输出；approval及正式输出根均
  不存在，真实Top30诊断0/6、Top20/QLib/封存效果语义读取0。
- 六个服务的tmpfs经Compose v5.3.0展开均为单字符串；三项零挂载fixture实际以UID501、无IPv4路由、
  只读根和可写tmpfs运行PASS。两套镜像内仅挂配置完成scope/运行身份复核PASS。
- 三批provisional分别暴露过窄网络接口判据、错误完整Git和base协议未显式挂载；均在approval/scope
  正式授权前失败关闭并留存身份，真实数据/回测/尝试仍为0。全仓929 PASS、专项11 PASS、架构10 PASS。
- 只有用户逐字批准动作`M6_TOP30_COMPATIBILITY_DIAGNOSTIC_MATRIX_RECOVERY_ONCE`并绑定完整scope
  SHA，才可各运行一次R2 original/current/audit；失败不得重跑，成功也不自动恢复Top20或生产。见
  `docs/M6_CSI800_TOP30_COMPATIBILITY_DIAGNOSTIC_RECOVERY_RELEASE_ACCEPTANCE_20260807.md`。

## 2026-08-07 · M6-3C-R2编排恢复协议已结果盲冻结

- R2只修复R1未加引号的flow-style tmpfs被拆分这一编排问题；旧Compose/scope/approval/失败记录永久
  保留。新版本使用独立Compose、Dockerfile、镜像名、approval路径和输出根，不复用失败scope。
- 原三路矩阵、Top30 6次回放、IEEE-754逐位比较、六类分类、参数、资源和安全边界全部不变；核心
  runner/auditor必须依赖注入复用，不复制第二套回测或分类逻辑。
- 当前只授权结果盲实现、无真实挂载的Compose fixture、镜像和新scope；真实Qlib/封存日报/Top30/
  Top20读取与执行仍为0。新scope生成后停止，须用户绑定新SHA逐字批准恢复动作才可运行。见
  `docs/M6_CSI800_TOP30_COMPATIBILITY_DIAGNOSTIC_RECOVERY_PROTOCOL_20260807.md`。

## 2026-08-07 · M6-3C-R1在容器创建前失败关闭，真实诊断仍为0

- 用户绑定scope`cad1928c...1fc23`逐字批准后，主控于15:15调用一次original入口；Docker因
  `invalid mount path: 'mode=1777'`在创建容器前退出，返回码2。同scope按冻结规则永久不得重跑，
  current和独立audit均未启动。
- 已由Compose v5.3.0展开结果证实：三项未加引号的flow-style `tmpfs`值被逗号拆成五个列表项，
  `mode=1777`被daemon误作路径。这是release编排错误，不是六类Top30兼容诊断之一，不能形成根因
  分类或恢复Top20。
- approval仍显示`consumed=false`，三个输出目录合计0文件；Top30回测0/6、Top20/QLib/封存效果语义
  读取0、研究尝试0、实验账本写入0。scheduler原容器/镜像保持healthy、重启0，7个自然账本改动
  未暂存。见`docs/M6_CSI800_TOP30_COMPATIBILITY_DIAGNOSTIC_EXECUTION_ACCEPTANCE_20260807.md`。
- 若继续只能另立M6-3C-R2结果盲编排恢复，先修并fixture验证tmpfs单字符串，再重建镜像和新scope、
  获取新精确批准；不得修改诊断矩阵、比较口径、参数或复用本scope。

## 2026-08-07 · M6-3C-R1兼容诊断release就绪，停在精确批准门前

- 三路诊断runner、IEEE-754位级证据、独立分类auditor、两套薄镜像和精确scope已完成；最终scope
  `cad1928c...1fc23`绑定协议、实现Git`67d53fa3...9b73d`、两个base/wrapper镜像、8文件代码bundle、
  Qlib/封存M6/原M6-3C失败证据、命令、挂载和资源。approval与真实输出目录均不存在。
- 两套最终镜像断网合成fixture覆盖6类分类并PASS，真实Qlib、封存日报、Top30回测、Top20、模型、
  新预测和实验账本读取/写入均为0；全仓926 PASS、专项8 PASS、架构10 PASS。
- 结果盲发布过程中三批provisional分别暴露错误完整Git、非root目录不可遍历和缺部署证据文件；均在
  scope授权前失败关闭并留存镜像/候选scope身份，正式镜像已通过非root fixture和容器runtime门。
- 只有用户逐字批准动作`M6_TOP30_COMPATIBILITY_DIAGNOSTIC_MATRIX_ONCE`并绑定完整scope SHA，才可
  各运行一次original/current runner与独立audit；失败不得重跑。即使诊断PASS也不恢复Top20或生产。
  见`docs/M6_CSI800_TOP30_COMPATIBILITY_DIAGNOSTIC_RELEASE_ACCEPTANCE_20260807.md`。

## 2026-08-07 · M6-3C-R1 Top30兼容诊断协议已结果盲冻结

- 下一任务只诊断M6-3C首个W1控制臂Top30日报差异，不读取Top20或评价策略。固定三路为原M6镜像+
  原执行器、失败M6-3C镜像+原执行器、失败镜像+新执行器，每路内部双跑，合计6次相同Top30诊断；
  研究尝试增量0，禁止其他窗口/臂/TopK、容差、舍入、模型、新预测或调参。
- 精确比较用日期/行序/四列和IEEE-754浮点位模式；分类只能是全部复现、新适配器差异、失败镜像环境
  差异、历史复现缺口、运行内不确定或混合未决。分类不改旧`BLOCKED_PRE_EFFECT`且不恢复Top20。
- 当前只授权协议推送后的结果盲实现、合成验证、两套薄镜像和精确scope；真实Qlib/封存日报读取与6次
  诊断仍为0。最终scope须绑定动作`M6_TOP30_COMPATIBILITY_DIAGNOSTIC_MATRIX_ONCE`并获用户逐字批准。
  见`docs/M6_CSI800_TOP30_COMPATIBILITY_DIAGNOSTIC_PROTOCOL_20260807.md`。

## 2026-08-07 · M6-3C真实Top20在Top30兼容门前置阻断

- 用户绑定scope`ba4d03be...65fd9`逐字批准后，唯一断网runner于12:11启动一次；输入、运行身份和
  W1控制臂Top30名单通过，但首个`W1/clean_lgbm_control_v1`重建日报与封存规范日报逐内容不一致，
  正确失败关闭为`BLOCKED_PRE_EFFECT`。本scope永久不得重跑。
- `top20_effect_started.json`与report均不存在，Top20尝试消费0、Top20回测0、模型拟合/新预测0；
  runner成功是独立audit前置条件，故auditor未启动且audit目录为空。策略保持
  `NOT_EVALUATED_FOR_PRODUCTION`、生产none，不能把阻断解释为Top20有效或无效。
- effect只含authorization/failure两件，2文件/896字节，整树`d2c22e17...3615a`；失败实现未保存
  新生成日报或逐单元diff，现有证据不能诚实定位具体日期/列值。scheduler原容器/镜像保持healthy、
  重启0，7个自然账本改动未暂存。见`docs/M6_CSI800_TOPK20_CONVERSION_ACCEPTANCE_20260807.md`。
- 若继续只能另立结果盲`M6-3C-R1`兼容诊断/恢复协议：先持久化并解释Top30差异，不读Top20、不放宽
  逐内容门或加容差；新真实执行仍须新scope和用户精确批准。若不继续M6，则下一重大能力前进入A1-0。

## 2026-08-07 · M6-3C真实Top20 release已就绪，停在精确批准门前

- 结果盲实现提交`322c599b...14f40`已推送；7个真实release窄模块最大292行。runner先完成21个Top30
  常规/压力兼容回测，全部逐内容一致后才写Top20尝试标记并执行21个Top20回测；独立auditor不挂
  Qlib或旧effect，单独复算统计、门和终态。
- 正式镜像`69c1a497...afa17`绑定Git`322c599b...14f40`、代码快照`961f51ad...cd2e`及538文件
  发布清单；最终断网合成runner/auditor PASS，真实数据、Qlib和回测读取均为0。
- 首次构建误把短Git手工补成错误40位值，scope入口正确失败关闭；错误镜像`21810132...ed08`已标
  provisional并留痕，未生成scope、未读效果。正式镜像以Git实际完整值重建并重验。
- release scope SHA为`ba4d03be675e63fd94211271e5dc6d4812bc12954fbf8f77ef0eea85c5065fd9`，
  approval文件不存在，组合尝试尚未消费，策略`NOT_EVALUATED_FOR_PRODUCTION`、生产none。只有用户逐字
  批准动作`M6_TOPK20_CONVERSION_EFFECT_ONCE_WITH_INTERNAL_REPLAY_AND_INDEPENDENT_AUDIT`并绑定该SHA，
  才能运行一次runner+一次audit。见`docs/M6_CSI800_TOPK20_CONVERSION_RELEASE_ACCEPTANCE_20260807.md`。

## 2026-08-07 · M6-3结果前补正全调仓日名单分解

- M6-3C真实接线前发现M6-3B合成bundle每窗口/臂只保存一组计划证券，而10日调仓的真实窗口有多组
  名单；若沿用会使`scheduled_top20_name_overlap`只代表单截面。该字段是必需诊断、不参与裁决门，
  因此不改假设、门槛、尝试或四终态，但原工程覆盖在此项上不充分。
- 结果前补遗固定`TopK→窗口→臂→调仓日→名单`，按全部W1—W6调仓日逐日算Top20交集比例后等权
  平均；旧单列表失败关闭，主指标和独立audit必须分别实现。形成补遗时真实effect/Qlib/Top20回测仍
  为0；最终release scope必须绑定补遗SHA后再请求精确授权。见
  `docs/M6_CSI800_TOPK20_SCHEDULE_ADDENDUM_20260807.md`。

## 2026-08-07 · M6-3C Top20真实效果release协议已结果前冻结

- 下一合法节点固定为把M6-3A单变量`TopK 30→20`和M6-3B合成工程GO做成一次性真实效果release；
  冻结输入只认M6-2封存effect、M6-2R独立audit、M6-3A协议和M6-3B正式manifest，旧证据均不改写。
- 当前只授权结果盲实现、合成fixture、不可变镜像和精确scope生成；封存effect语义、Qlib、Top20
  回测、实验账本、前瞻、模拟仓、Web、scheduler和生产均未授权。唯一允许的预执行读取是封存输入的
  元数据/内容哈希身份，不读取预测、日报或效果语义。
- 未来正式runner必须先逐内容复现全部Top30，再允许形成Top20；一次调用内含first-pass/replay，首次
  Top20效果读取消费恰好2个组合尝试，同release不得重跑。独立auditor仍须二次复算。
- 最终scope必须绑定实现Git、镜像、发布清单、Qlib、封存effect/audit、命令、挂载和资源；完整scope
  SHA获得用户针对动作`M6_TOPK20_CONVERSION_EFFECT_ONCE_WITH_INTERNAL_REPLAY_AND_INDEPENDENT_AUDIT`
  明确批准前必须停止。见`docs/M6_CSI800_TOPK20_CONVERSION_RELEASE_PROTOCOL_20260807.md`。

## 2026-08-07 · M6-3B Top20组合转换结果盲工程门GO

- 严格继承M6-3A且只允许`TopK 30→20`一个变化的portfolio-only执行、差分中的差分、Top20直接门、
  四终态、write-once双跑和独立auditor均已在纯合成输入上通过；工程裁决`GO_ENGINEERING_ONLY`，
  策略`NOT_EVALUATED_FOR_PRODUCTION`，生产授权none。
- 正式断网runner内部first_pass/replay物理SHA同为`10fb2449...29a3c`；报告`f3e5fd52...230fa`，独立
  audit`e443a1e8...77690`并逐项复算PASS。真实M6 effect、Qlib、拟合、预测、回测、实验账本和外部
  调用均为0。
- 首镜像嵌入的完整Git身份不属于真实提交，虽代码快照可复算仍被判provisional并原样保留；随后新增
  镜像Git/代码快照强绑定和漂移失败关闭。正式镜像`e14fc6c3...953eb`绑定已推送提交
  `2337076f...534a4f`与代码快照`7857c0a3...008ef`。
- 八个窄职责模块最大361行，独立Compose不扩大旧research compose。全仓903 PASS、架构10 PASS；
  scheduler原容器/镜像保持healthy、重启0。M6-3B已关闭；真实Top20效果只能另立M6-3C精确scope并
  再获用户授权。见`docs/M6_CSI800_TOPK20_CONVERSION_ENGINEERING_ACCEPTANCE_20260807.md`。

## 2026-08-07 · M6-3B结果盲工程协议已冻结，等待合成实现

- 用户指令继续下一任务；M6-3B只建设Top20组合转换的portfolio-only runner、差分中的差分裁决、
  write-once证据和独立auditor，全部使用虚构证券与合成收益，不读取M6 effect或Qlib真实输入。
- 新包固定为`shaiwei.research.topk_conversion`八个窄职责模块；执行/指标不得导入模型训练，独立audit
  不得导入主指标、执行或fixture。另建小型`compose.m6-topk-conversion.yaml`，不继续增长既有大型
  research compose。
- 当前只冻结工程范围，真实效果、模型、回测、实验账本、前瞻、模拟仓、Web、scheduler和生产均未获
  授权。协议提交先行推送后再实现；工程GO后仍须停止在新精确release scope前。见
  `docs/M6_CSI800_TOPK20_CONVERSION_ENGINEERING_PROTOCOL_20260807.md`。

## 2026-08-07 · M6-3A Top20组合转换协议已结果前冻结

- 用户同意按主控建议继续M6组合转换归因；本节点只冻结`portfolio.topk: 30→20`一个变量，复用M6-2
  同一中证800成员、Alpha158、三组封存预测、W1—W6、`n_drop=3`、10日调仓、成交和三档成本，不新增
  模型、seed、因子、预测或其他TopK。
- 正式主要检验固定为两个既有替代分数臂的配对差分中的差分：
  `(替代Top20-控制Top20)-(替代Top30-控制Top30)`，沿用NW(10)+Holm(2)。支持门还要求Top20内相对
  清洗控制组通过原组合门；所有终态均不代表策略有效，生产授权`none`。
- Top20选择依据是M6-2的组合瓶颈归因、单一可解释收窄及既有模拟账户的操作化可行性，不读取模拟账户
  相对业绩。未来必须先逐内容复现原Top30，再读Top20效果；M6 effect、Qlib、模型、回测、账本、Web、
  scheduler和生产均未触碰。
- 当前停止在协议提交推送。若继续须另立M6-3B结果盲工程目标，以合成fixture建设portfolio-only
  runner/auditor；真实效果还需新的完整release scope和用户精确授权。见
  `docs/M6_CSI800_TOPK20_CONVERSION_PROTOCOL_20260807.md`。

## 2026-08-07 · 代码架构与受控整理瘦身检查点已固化

- 用户明确要求持续采用合理代码架构，并在合适阶段进行一次整理瘦身、删除经证明无用的代码。当前
  Git真身约113,500行代码/977个已跟踪文件；核心Python 56,703行、Web 17,196行、tools 17,137行、
  Python测试21,940行，机器清单有13个超过600行的grandfathered热点。
- 现有`architecture-constitution-v1`及其物理SHA保持不变，避免破坏M5冻结scope；新增独立
  `codebase-consolidation-v1`补充门。扫描发现唯一既有`src → tools`反向依赖位于M4-1复用P2-2C纠错
  执行器，已精确登记为A1-0优先债务且禁止新增第二处，不以排除整个文件隐藏。瘦身不设强制删行KPI。
- 首次检查点固定在M6系列关闭后、下一项重大策略池或Web能力前；若不继续M6，则在下一重大功能前
  立即触发。先执行只读`A1-0`，逐文件列出引用、动态入口、替代实现、保护等级和回滚点；用户复核
  候选后才可进入`A1-1`一个职责族一个提交的删除/拆分。
- 不可变数据/账本、冻结协议、验收与失败证据、迁移、真实audit、生产发布/回滚和唯一历史复算能力
  永久排除普通清理。本节点只制定并机器化规则，没有删除或修改任何业务代码、数据、账本、服务或
  生产镜像。见`docs/CODEBASE_CONSOLIDATION_PLAN_20260807.md`。

## 2026-08-07 · M6-2R独立审计恢复PASS，权威归因指向组合转换瓶颈

- 用户批准精确恢复scope`30ab35ed...e1ec1`后，唯一断网auditor-only恢复于08:34完成，退出码0；
  `independent_audit=PASS`、新增尝试0、runner调用0、生产授权none，同scope永久不得重跑。
- 原独立审计算法在基础镜像和薄镜像中物理SHA相同。auditor从封存产物独立重算成员日、RankIC、成本、
  主动收益、换手、回撤、NW(10)、Holm和Top30，并确认first_pass/replay bundle完全相同。
- Ridge与LGBM/Ridge 50/50融合的pooled RankIC增量为+0.008649/+0.008776，分别4/6、5/6窗口为正，
  均过分数门；但1.0x成本下pooled净超额增量为-33.96%/-37.17%，仅3/6窗口为正，最大回撤
  27.78%/26.60%，主要检验Holm p均为1.0，组合门均FAIL。
- 权威终态为`PORTFOLIO_CONVERSION_BOTTLENECK_INDICATED`：分数改善未兑现为固定Top30组合收益；它是
  归因与资源排序结论，不是策略有效或生产准入。下一批最多改变一个结果前冻结的组合转换变量，不增加
  模型、seed、网格或第三臂，且必须另立协议和授权。
- `audit.json`/receipt SHA为`8788bddc...0fd6`/`178f7bd2...3785`；effect前后仍为199文件、
  84,957,571字节、整树`dfbc0b52...d5cb`。scheduler原容器/镜像保持healthy且未重启。见
  `docs/M6_CSI800_MODEL_ATTRIBUTION_AUDIT_RECOVERY_ACCEPTANCE_20260807.md`。

## 2026-08-06 · M6-2真实runner完成，独立audit入口失败并停在恢复前

- 用户批准精确scope`9b609f07...b139`后，唯一断网runner正常完成内部`first_pass/replay`，正式
  report SHA为`65e7b7ae...b29f3`；真实读取已消费恰好2个替代尝试，原release不得重跑。effect共
  199文件/84,957,571字节，整树SHA`dfbc0b52...d5cb`，两遍manifest物理SHA完全相同。
- 唯一auditor进程在进入审计函数前因CLI参数名`release/approval`与函数关键字
  `release_path/approval_path`不一致而`TypeError`退出；audit语义读取0、输出0。暂定runner标签不是
  权威结论，策略保持`PENDING_INDEPENDENT_AUDIT`，实验账本和生产授权均未变化。
- M6-2R恢复协议已冻结：只允许修显式参数绑定，以原镜像为base增加`/workspace`外控制入口，绑定
  原scope/approval和完整effect树后另立auditor-only scope。禁止Qlib、训练、预测、回测、runner重跑、
  指标/门槛/裁决变化和同release重试；新完整scope获用户明确批准前不得执行。见
  `docs/M6_CSI800_MODEL_ATTRIBUTION_AUDIT_ENTRYPOINT_RECOVERY_PROTOCOL_20260806.md`。

## 2026-08-06 · M6-2不可变真实release已就绪，停在精确授权前

- M6-2协议、一次性runner、内部`first_pass/replay`、独立auditor和最终断网镜像均已完成；终版镜像
  `sha256:3c40c9c...cd40e`绑定已推送提交`35fd1d58...1789c`、代码快照`71a0cc5f...1a239`和501文件
  发布清单`e75e5d55...67d5`，镜像内身份复核PASS。
- 精确release scope为`9b609f0764240ff3930a4aeaaf16cef9deb82579d2a5875f1be9e8c4ffb0b139`，种类
  `REAL_EFFECT_RELEASE_READY_NOT_EXECUTION_APPROVAL`；当前除`release_ready=true`外，执行、真实读取、
  拟合、预测、回测、正式效果写入、实验账本、外网、前瞻、模拟仓和生产权限均false/none。
- 最终镜像零挂载断网合成runner/auditor再次PASS，报告SHA为`7f489071...3f92`/`becf2c5a...c319`；
  合成分支不代表真实效果。首镜像`4e45df7f...92a65`因scope CLI参数绑定错误永久provisional，修复前
  未写scope/approval/效果且真实读取0、尝试未消费。
- scheduler仍为原容器`183b8c6c5edd`、原镜像`722f63de...13b76`且healthy，未重启。下一步只能等待
  用户针对完整scope SHA和动作`M6_REAL_EFFECT_ONCE_WITH_INTERNAL_REPLAY_AND_INDEPENDENT_AUDIT`明确
  批准；批准前必须停止。见`docs/M6_CSI800_MODEL_ATTRIBUTION_RELEASE_ACCEPTANCE_20260806.md`。

## 2026-08-06 · M6-2零效果实现完成，等待不可变镜像与精确scope

- 首个实现镜像`sha256:4e45df7f...92a65`断网合成runner/auditor PASS，但正式scope CLI在写入前因
  参数绑定名不一致失败关闭；scope/approval/效果产物均不存在，真实读取0、尝试未消费。该镜像仅作
  provisional，不得生成正式release；最小绑定修复和CLI回归须先提交推送，再重建新镜像。
- 真实runner已按唯一调用内含`first_pass/replay`实现；六窗串行、每窗只拟合LightGBM/Ridge两个模型，
  固定融合不训练第三模型。Qlib日报、成本缩放、主动收益、策略NAV回撤和信号Top30语义均按冻结协议
  形成独立模块，未改中证800生产基线或scheduler。
- 独立auditor不导入主`effect_metrics`、`inference`、执行器或产物写入器；它从Parquet/JSON重算成员日、
  RankIC、成本/主动收益/换手/回撤、NW(10)、Holm、Top30与终态，并逐哈希核对两遍完整产物。
- 专属`compose.m6-attribution.yaml`只定义断网短命runner/auditor，后者无Qlib挂载；scope即使重新哈希也
  不能扩大权限、挂载、命令或资源。完全合成闭环和篡改对抗PASS；全仓856 PASS、架构6 PASS，Ruff、
  compileall、pip check、Compose与diff门PASS。
- 当前仍未构建最终镜像、未生成精确release scope；真实Qlib特征/价格/标签/效果读取、拟合、预测、
  回测、正式输出和实验账本写入仍为0/未授权。下一步先提交推送本实现，再以该提交构建镜像并形成
  完整scope；用户明确批准完整SHA前必须停止。

## 2026-08-06 · M6-2真实release协议已结果前冻结，等待零效果实现

- 本节点只实现一次性真实runner、内部`first_pass/replay`、独立auditor、不可变镜像和精确release
  scope；当前真实特征/价格/标签/效果读取、模型拟合、预测、回测、正式输出和实验账本写入均未授权。
- 三臂、W1—W6、11交易日成熟purge、Top30/`n_drop=3`/10日、成本和两假设NW(10)+Holm全部继承
  M6-0；真实指标补足主动收益、策略NAV回撤和信号Top30重合的操作化，不新增门槛或变体。
- 运行边界冻结为断网短命Docker、6 CPU/12GiB、只读Qlib/scope/approval、专属输出；一次runner内部
  完整双跑，第二进程独立复核。首次效果读取即消费恰好两个替代尝试，失败不得递补或同release重跑。
- 本轮完成实现、镜像和scope并推送后必须停止；只有用户针对最终完整scope SHA明确批准，才可真实
  运行。策略仍`NOT_EVALUATED`、生产`none`。见
  `docs/M6_CSI800_MODEL_ATTRIBUTION_RELEASE_PROTOCOL_20260806.md`。

## 2026-08-06 · M6-1结果盲工程门GO，已停在真实release前

- 协议提交`64fe39d8...e10f`先行推送；独立合同、11交易日成熟时钟、Qlib LightGBM/Ridge工厂、
  50/50排名融合、NW(10)+Holm、五终态、十二失败关闭和不导入主裁决器的audit均已实现。
- 额外发布复核发现首版把只读输入挂进`/workspace/config`导致嵌入式发布清单失败；旧报告/audit作为
  `formal=false` provisional原样保留。修复提交`c6bf7d6d...eaf8`先推送后重建，输入移到`/inputs`，
  runner/auditor均绑定并验证release Git/代码快照。
- 终版断网Docker报告/audit SHA为`43c0716b...1cc2`/`7fb095a3...3a33`，各双跑同哈希、第二遍复用，
  独立audit PASS；全仓838 PASS、架构6 PASS。scheduler仍为原容器/原镜像且healthy，未重启。
- 真实特征/价格/标签/效果、模型拟合、预测、回测和外部调用均为0；工程裁决
  `GO_ENGINEERING_ONLY`，策略`NOT_EVALUATED`、生产`none`。下一步只能另立M6-2完整release scope并
  取得用户明确授权；现有授权不得继承。见
  `docs/M6_CSI800_MODEL_ATTRIBUTION_ENGINEERING_ACCEPTANCE_20260806.md`。

## 2026-08-06 · M6-0中证800模型/组合归因小批协议已结果前冻结

- 本批只回答瓶颈更可能在学习结构、分数到组合转换还是Alpha158既有信息，不寻找最佳模型；中证800、
  Alpha158、`t+11`开盘标签、W1—W6、Top30/`n_drop=3`/10日调仓和1.0x/1.5x/2.0x成本全部冻结。
- 旧Stage0证据原样保留，但其train/valid末11个信号日未显式purge，不能作为本批干净比较控制；新控制
  仅按统一标签成熟规则重建原参数LightGBM，不改当前生产或前瞻基线。
- 两个且仅两个替代假设为固定`Ridge(alpha=1.0)`和LightGBM/Ridge日排名50/50融合；无网格、多seed、
  第三个模型、新因子或组合参数搜索。主要检验为逐日扣费主动收益差的NW(10)，两假设Holm 0.05。
- 当前只完成协议/config/机器测试冻结；实现、真实训练、预测、标签/效果读取、回测、前瞻、模拟仓、
  生产、网络和secret均未授权。下一合法动作须另立M6-1工程目标，且冻结提交先行推送。协议见
  `docs/M6_CSI800_MODEL_ATTRIBUTION_PROTOCOL_20260806.md`。

## 2026-08-06 · Web已补齐M5最新权威BLOCKED_DATA真身

- 结果无关协议提交`6b6bef38ecb0355d584da99f1f1b62192b1d1eaa`先行推送；旧`strategy_factory_v2`
  pointer/快照逐字保留，新`strategy_factory_v3`以固定release、真实运行验收和路线复盘三份哈希证据
  生成，不在请求时扫描registry、日志或生产数据。
- v3快照ID/SHA为`80498300...40840`/`8cf59d2a...6c640`。Web现显示M5动态基本面跨池批次
  `BLOCKED_DATA / LINEAGE_NO_GO_ONLY`、23组仅当前观察版本、历史PIT版本链可恢复0、策略
  `NOT_EVALUATED`、支线`PAUSE`；旧8工作包、活跃任务0、正式因子0和生产授权none不变。
- API继续GET/HEAD only；v3缺失或身份/固定事实漂移时失败关闭，不自动回退旧v2。技术哈希默认隐藏，
  页面未增加执行、重跑、队列、调参或生产控件。
- 全仓815 PASS、架构6 PASS、前端单元33 PASS、五视口fixture 5 PASS、真实桌面/移动2 PASS；axe
  serious/critical=0。Web最终镜像`cb955ccc...13eac`，query/UI healthy。
- scheduler仍为原容器`183b8c6c5edd`、原镜像`722f63de...13b76`且healthy，未重启。验收见
  `docs/M5_WEB_AUTHORITY_PROJECTION_CORRECTION_ACCEPTANCE_20260806.md`。
- 下一独立目标：结果前冻结中证800模型/组合归因小批协议；最多两个预定结构，固定现有数据、Alpha158、
  标签、窗口、成本、成交和组合口径，不做网格、多seed或新增因子。本节不授权该批实现或真实运行。

## 2026-08-06 · 阶段路线复盘完成，主裁决REORDER

- 主窗口联合架构、研究方法和产品交付三个只读专项复盘；一致结论是平台没有整体跑偏，PIT、预注册、
  独立audit和Docker隔离应保留，但近期投入已偏向继续扩控制面，可信效果终态吞吐不足。
- M5历史动态基本面支线`PAUSE`，本地代码不能补出权威历史版本；Registry v1与当前Docker边界冻结，
  不加队列/Worker/通用状态机。多股票池工厂继续，但改为一次一个、最多3候选的可证伪机制批次。
- 中证800生产与Top30/Top20自然前瞻继续，不短样本改模。Web只补M5 `BLOCKED_DATA`等权威事实和阻断
  地图，不重做视觉或增加写控制；该项现已由上方`strategy_factory_v3`验收完成，旧v2保留作回滚。
- 下一主目标建议分两步：先同步Web只读真身，再结果前冻结中证800模型/组合归因小批；固定数据、标签、
  窗口、成本与组合，只比较基线和最多两个预定结构，不做网格/多seed/新增因子。
- 建议资源为结果批60%、生产/前瞻20%、Web真身10%、权威数据源可行性10%、M5通用扩张0%。完整裁决
  见`docs/PLATFORM_ROUTE_REVIEW_20260806.md`；本复盘不授权新施工。

## 2026-08-06 · M5-2B-R2年报行域恢复后真实谱系门权威NO-GO

- 用户批准精确release `f7904929991e90a3d4c220cbdaf88818953694803625c41eb3634731e376e2d5`
  后，新case完成唯一断网runner与独立auditor；两者均正常结束，audit PASS，不再发生锚定范围错误。
- 23个冲突组全部为`FORWARD_ONLY_OBSERVED_VERSION`（资产负债表8、现金流量表15），
  `PIT_VERSION_CHAIN_RESOLVED=0`；权威裁决`NO_GO_M5_2_SOURCE_LINEAGE_PREEXECUTION`，case event 6进入
  `BLOCKED_DATA / LINEAGE_NO_GO_ONLY`。这是历史来源谱系DATA阻断，不是因子或策略REJECT。
- run/audit id为`8ffe2570...d1fab`，独立audit SHA为`e056e41a...2ba45`；registry为4 case/28 event/
  28 receipt/28 outbox、pending 0，event 6重放与outbox二次发布均零新增，旧registry/ledger哈希不变。
- 真实读取仅限获批runner与独立auditor；provider/外部调用0，PIT/候选/效果/模型/回测/生产均未运行。
  scheduler仍为原容器/原镜像且healthy，无M5容器遗留。
- 本release已消费且不得重跑。M5-2C继续阻断；按用户指令先启动一次只读阶段复盘，再裁定是否另立
  权威版本证据恢复协议或重排路线。见
  `docs/M5_DYNAMIC_FUNDAMENTAL_SOURCE_LINEAGE_SCOPE_RECOVERY_REAL_RUN_ACCEPTANCE_20260806.md`。

## 2026-08-06 · M5-2B-R2年报行域恢复release已就绪，等待新精确授权

- 恢复协议提交`cd13e6a0696f67248f20367e85e6cef85947b602`先行推送，行域实现
  `823e8360fed406fe56d2d7797d6d810c03b00ab1`与断网镜像构造
  `213d0a103c9f22b327313bdc568c48eea0a9fff8`随后推送；只修R1/R2年报范围一致性，不改研究或谱系语义。
- reader现于Observation/锚定键/历史allowlist之前限定`end_date=12月31日`且`report_type∈{"1","5"}`；
  季度和其他类型冲突对抗fixture、type 5年报、连字符日期和缺身份fail-closed均已锁定。
- 新metadata-only清单绑定16,841个锚定批次与16,841个历史批次，逻辑/物理SHA为
  `bda3f6b8...35d0df`/`1e4ea075...795ebf`，权威证据0，`semantic_rows_read=false`。
- 新协议scope/case为`0e4ea4ee...b20bc`/`8000c9e1...f49ff`；新镜像为
  `sha256:5dd12995...12d1a`。精确release scope为`f7904929991e90a3d4c220cbdaf88818953694803625c41eb3634731e376e2d5`，
  只授予release ready；approval/execution/真实读取/正式registry/外网/PIT/候选/效果/模型/生产均未授权。
- 全仓812 PASS、架构6 PASS，scheduler仍为原容器/原镜像且healthy。旧scope/case/event 6 `STOPPED`
  永久保留且不得重跑；下一步只能等待用户对新完整scope明确批准一次断网`LINEAGE_FEASIBILITY`。
  见`docs/M5_DYNAMIC_FUNDAMENTAL_SOURCE_LINEAGE_SCOPE_RECOVERY_RELEASE_ACCEPTANCE_20260806.md`。

## 2026-08-06 · M5-2B-R2唯一真实谱系运行因锚定范围不一致STOPPED

- 用户批准精确scope `b01058b55ff3dd6c06cf0722541214ecbb793de92a3115410c073daab26cf155`
  后，正式新case完成至`LINEAGE_GATE_STARTED`；16,853文件输入束校验通过，runner以断网、非root、
  只读根和两个窄挂载执行恰好一次。
- runner在读取anchor财报行后以exit 2失败关闭：`M5 lineage anchor conflict identity changed`；输出和
  audit均0文件，auditor未启动，没有lineage verdict或新DATA裁决，策略仍`NOT_EVALUATED`、生产`none`。
- 静态根因是R1基线只统计年报且`report_type∈{1,5}`，R2 reader在23组锚定校验前却读取全部报表行；
  合成fixture只有年报，未覆盖该范围差异。本轮未为诊断再次读取真实语义数据。
- 新case event 6已`STOPPED`，SHA `2dc732c8...74e27`；registry 3 case/22 event/22 receipt/22 outbox、
  pending 0，重放零新增。旧v3/R1 case head、上一registry/ledger哈希不变，scheduler身份不变且healthy。
- 本release不允许重跑。下一步只能先提交同口径过滤与季度行对抗fixture，重建镜像并生成新scope；用户
  对新完整SHA再次批准前不得运行。见
  `docs/M5_DYNAMIC_FUNDAMENTAL_SOURCE_LINEAGE_REAL_RUN_ACCEPTANCE_20260806.md`。

## 2026-08-06 · M5-2B-R2谱系实现与精确release就绪，停在授权前

- 纯合成实现提交`f2e5483f55278010cde4ea5ff5f8e3b56c09ae37`已先推送：版本commitment、六处置
  谱系构造、未解释回滚门、aggregate-only投影、write-once封存、独立auditor、registry v1新case、
  metadata inventory和批准后内容寻址输入束均完成；R1冲突分类器、旧case和旧证据未改。
- 全仓804 PASS、架构6 PASS；最终断网Docker双跑同结论，fixture SHA为`1b4b0008...e9a62`。新增
  生产模块最大340行；Ruff/compileall/pip/Compose/diff均PASS。
- metadata-only输入清单绑定16,841个R1锚定批次和同一组16,841个历史批次，逻辑/物理SHA为
  `b9b7c7fb...e5d7`/`0576de1f...6780`，权威证据0，`semantic_rows_read=false`；未查看真实冲突证券、
  日期和值。
- 精确release scope为`b01058b55ff3dd6c06cf0722541214ecbb793de92a3115410c073daab26cf155`，绑定
  已推送代码、镜像`sha256:fe9101f1...9b606`和四个窄挂载。当前approval/execution/正式registry写/
  real read/冲突诊断/外网/PIT/候选/效果/模型/回测均false，策略`NOT_EVALUATED`、生产`none`。
- scheduler仍为原容器`183b8c6c5edd`、原镜像`722f63de...13b76`且healthy。下一步只能等待用户对
  完整scope SHA明确批准一次断网`LINEAGE_FEASIBILITY`；联网补证及M5-2C继续未授权。见
  `docs/M5_DYNAMIC_FUNDAMENTAL_SOURCE_LINEAGE_RELEASE_ACCEPTANCE_20260806.md`。

## 2026-08-06 · M5-2B-R2财报来源版本谱系恢复协议已冻结

- 结果前协议提交`ccc799b073520f04954fcb0da9e9d7ea0052b144`已先推送；protocol scope为
  `96c4f996f2641e6b18c26d8228ee72712b2670d70fe0cdedf95c99cd2e463ccd`，派生独立case
  `6b6c849f4ded89f631e1af8127f0e7321898aa7f4ce0c2630806fc8c8ef7be16`。R1 case、release v4、
  23组冲突、audit和`BLOCKED_DATA`裁决不迁移、不改写、不重跑。
- R2明确分开财报`f_ann_date`、权威修订生效时间和本地`ingest_time`：本地抓取只证明观察下界，
  相同五字段身份内的相同`update_flag`也不能给不同值排序。历史恢复至少需要带版本身份/生效时点的
  provider证据或法披/交易所/发行人一手材料；只有本地观察证据的版本最多future-only，不能回填历史。
- 禁止latest wins、普通/VIP优先、非空/多数值优先、容差、删除冲突组或按效果选源。未来先做断网
  `LINEAGE_FEASIBILITY`；若缺权威证据，联网采集必须另立协议，不能和DATA_GATE混跑。
- 当前只允许按build v3施工纯合成版本谱系实现、独立auditor和release；真实财务/冲突读取、外网、
  正式case/event、PIT/候选、标签/效果、模型/回测和生产仍为false/none。见
  `docs/M5_DYNAMIC_FUNDAMENTAL_SOURCE_LINEAGE_RECOVERY_FREEZE_ACCEPTANCE_20260806.md`。

## 2026-08-06 · M5-2B-R1 release v4真实数据门权威NO-GO，终态BLOCKED_DATA

- 用户批准精确scope `8858912f14577a8911e47f0ec338cde82208fe818b4c7a921578e42aeeed6f65`
  后，唯一一次断网真实runner正常封存`NO_GO_M5_2_DATA_PREEXECUTION`：冻结输入共发现23个来源身份
  冲突组（资产负债表8、现金流量表15、利润表0），未选源、未修数，PIT/公式/feature panel均未执行。
- 8候选×3池共24单元全部`FAIL / GLOBAL_SOURCE_IDENTITY_CONFLICT /
  NOT_COMPUTED_GLOBAL_FAILURE`，eligible为0；这是DATA NO-GO，不是策略REJECT，效果测试0、策略
  `NOT_EVALUATED`、生产`none`。
- 独立auditor重读同一输入复算六类计数、commitment和24单元后PASS；run manifest/audit SHA为
  `70cc008b...edc57`/`647ac34e...f5677`。新case event 6
  `DATA_GATE_RECORDED → BLOCKED_DATA`，SHA `7c2615a0...80917e`。
- registry全库2 case/16 event/16 receipt/16 outbox且完整性PASS；登记重放零新增，outbox第二次发布0，
  旧case event 10与旧ledger前缀逐字段不变。M5短命容器已退出，生产scheduler身份不变且healthy。
- 当前禁止M5-2C、标签/效果、模型、回测和生产。若继续必须另立M5-2B-R2结果前数据恢复协议，以新
  case/release/精确授权处理源内部版本冲突，不得按效果选源或回写本轮证据。见
  `docs/M5_DYNAMIC_FUNDAMENTAL_DATA_GATE_RECOVERY_REAL_RUN_ACCEPTANCE_20260806.md`。

## 2026-08-06 · M5-2B-R1恢复实现完成，release v4授权前留痕（已由真实门终态取代）

- 恢复实现提交`18e7502b74919641e02689720dd31b1e36b276a7`已推送：普通/VIP财报源按六类精确
  分类；三类冲突任一出现都不选边、不进入PIT/公式/feature panel，只write-once封存脱敏冲突报告、
  24单元全FAIL矩阵和DATA NO-GO，再由不复用主分类器的auditor重算。
- 两次断网纯合成Docker运行同结论：六类/NULL规范化通过，三种冲突均封存NO-GO，独立audit PASS，
  临时新case进入`BLOCKED_DATA`，旧合成STOPPED case不变，runner/auditor/registry均幂等。全仓761
  PASS、架构6 PASS，生产scheduler身份未变且healthy。
- 新metadata-only输入manifest逻辑/物理SHA为`f4aeb411...9399b`/`683bed3a...f020`，绑定7类API、
  16,843批次和3份成员证据，`semantic_rows_read=false`。最终镜像为`sha256:acb7c6c2...d1ea7`。
- 精确release v4 scope为`8858912f14577a8911e47f0ec338cde82208fe818b4c7a921578e42aeeed6f65`；
  本节记录当时`approval/execution/real read=false`的授权前状态。用户后续已明确批准并完成唯一真实
  数据门，当前权威状态以上方`BLOCKED_DATA`为准；旧v3批准未迁移。见
  `docs/M5_DYNAMIC_FUNDAMENTAL_DATA_GATE_RECOVERY_RELEASE_ACCEPTANCE_20260806.md`。

## 2026-08-06 · M5-2B-R1全局数据失败恢复协议已冻结

- 新ADR与恢复协议已把v3双重阻断转成结果前机器合同：完全重复仅无损折叠；普通内、VIP内或两源交叉
  任一冲突都不选边，write-once封存脱敏冲突报告、全24单元FAIL矩阵与DATA NO-GO，再由独立实现
  重读同一冻结输入复算，audit PASS后才可`DATA_GATE_RECORDED → BLOCKED_DATA`。
- 原八式/三池/24单元、PIT、方向、门槛和尝试`N=14/20`零变化；旧case/release/event 10/零输出证据
  不迁移、不回写、不重跑。registry继续v1四表，零schema迁移。
- 协议提交`c0eb26bdc7e25e50e67e7d4acfbf0460f3c05b6e`已先推送；新protocol scope为
  `6f99c0dfdc5cd75df9bf769fb65318feb4e8e7140082a9dfb924a88a3bb0dc49`，派生新case
  `a2539149d588a0c19f9cb73331f19a66df63e301df03f56fbb2c8e5c74672068`。
- 当前只允许按build v2施工恢复实现与纯合成fixture；真实财务/冲突诊断、正式case/event、gate执行、
  标签/效果/模型/生产仍为false/none。实现和镜像推送后须生成新release scope并再次明确授权。见
  `docs/M5_DYNAMIC_FUNDAMENTAL_DATA_GATE_RECOVERY_FREEZE_ACCEPTANCE_20260806.md`。

## 2026-08-05 · M5-2B release v3真实DATA_GATE因资产负债表源身份冲突失败关闭

- 用户批准精确scope `49fdc6e79ee7591fb03732fc4fa08430f4049b720d0552cca49ff9e153e05830`
  后，正式registry追加v3 APPROVED/STARTED，冻结输入束16,854文件通过控制身份校验；唯一真实断网
  runner在语义读取后以exit 2停止：`balancesheet contains conflicting duplicate source identities`。
- 输出/audit staging均为空；没有24单元矩阵、候选集合、独立audit或`DATA_GATE_RECORDED`，故这不是
  DATA NO-GO，更不是因子/策略REJECT。权威结果仍`NOT_EVALUATED`、生产`none`。
- event 10已追加`STOPPED`并绑定零重试授权，SHA `e0ca4594...b9b3bd`；registry verify PASS，10/10
  outbox已发布，同命令重放不追加、outbox重放0。M5无遗留容器，生产scheduler仍为原容器/镜像且
  healthy。
- 双重阻断是“真实balancesheet来源身份冲突”与“v3对全局完整性错误未先封存可审计NO-GO报告”。旧
  case/release不得重跑或改写；若继续须先冻结superseding protocol/build，建立新case，明确脱敏冲突
  诊断和canonical failure report/auditor合同，再形成新scope供用户重新批准。见
  `docs/M5_DYNAMIC_FUNDAMENTAL_DATA_GATE_REAL_RUN_ACCEPTANCE_20260805.md`。

## 2026-08-05 · M5-2B release v3已就绪，停在第三次精确授权前

- v2协议加载失败已由正式event 6`DATA_GATE_PREEXECUTION_FAILED`留痕，event SHA
  `d258e076...4559c`；payload固定`INPUT_BUNDLE_CONTROL_MISSING / exit 2 /
  semantic_rows_read=false`，registry已恢复`PROTOCOL_FROZEN`，没有DATA verdict。
- 输入包v2修复提交`a7960666b884cc1d5d7add5c1ff2bc69482ab0da`已推送：新增build contract，
  bundle manifest绑定input/build/release/approval逻辑与物理身份，路径强制`<input_sha>-<impl前7位>`；
  v2旧包原样保留。
- v3镜像`sha256:738b9d7f...80d0f`纯合成全链PASS；新release scope为
  `49fdc6e79ee7591fb03732fc4fa08430f4049b720d0552cca49ff9e153e05830`，输入manifest和提案到期均
  不变。M5专项74 PASS、全仓729 PASS、架构6 PASS，scheduler身份不变且healthy。
- v3尚无approval/input bundle/STARTED，真实财务行、候选、数据判决、效果仍为0。v2批准不迁移；
  必须等待用户针对v3完整SHA重新批准。见
  `docs/M5_DYNAMIC_FUNDAMENTAL_DATA_GATE_RELEASE_V3_ACCEPTANCE_20260805.md`。

## 2026-08-05 · M5-2B release v2在协议加载阶段失败，真实语义读取仍为0

- 用户批准v2后正式registry已形成至`DATA_GATE_STARTED`的5事件链；runner随即因输入包缺
  `m5_dynamic_fundamental_data_gate_build_v1.yaml`以exit code 2失败，发生在
  `M5DataProtocol.load`，早于任何财务列读取。
- v2没有feature/report/run/audit产物，不产生DATA verdict或策略结论；旧输入包不补文件、不删除、
  不原地重建。真实财务行/候选/效果仍为0，scheduler未触碰。
- 根因同时包含“漏build contract”和“仅按input manifest命名却封装release/approval”的跨release碰撞。
  恢复只允许新增`DATA_GATE_PREEXECUTION_FAILED`证据边、输入包v2四控制身份，以及
  `<input_sha>-<implementation前7位>`精确路径；研究协议与输入不变。
- 修复须先推送并登记预语义失败事件，再生成release v3；v2批准不迁移，v3仍须用户重新批准。见
  `docs/M5_DYNAMIC_FUNDAMENTAL_DATA_GATE_BUNDLE_RECOVERY_20260805.md`。

## 2026-08-05 · M5-2B release v2已修复并停在重新授权前

- registry挂载恢复提交`a98cd1d4f83dba022b199ae267d0bdc802f5bc2b`已先推送；release合同现强制
  `/inputs:ro`、`/outputs:rw`、`/audit:rw`、`/registry:rw`恰好四个内容寻址挂载。
- 新镜像`sha256:d04f96f5...39e2f3`的断网纯合成8×3/24单元与独立审计PASS；新release scope为
  `a847c4da8541f5fd421747079145e723675cfbe6f5ed2eb15d2b7fa4779a6c96`，沿用同一metadata-only
  输入清单`d9de2ece...f8d4d`与提案到期`2026-08-12T18:48:16+08:00`。
- M5专项71 PASS、全仓726 PASS、架构6 PASS；生产scheduler身份不变且healthy。正式registry、
  approval envelope、input bundle和真实运行产物仍不存在，真实财务读取/候选/门执行/效果均为0。
- 旧批准不能迁移到新scope。当前必须等待用户针对完整新SHA重新明确批准；批准也只覆盖一次断网
  DATA_GATE。见`docs/M5_DYNAMIC_FUNDAMENTAL_DATA_GATE_RELEASE_V2_ACCEPTANCE_20260805.md`。

## 2026-08-05 · M5-2B旧release在真实读取前因registry挂载缺失而作废

- 用户对旧scope`f53085d3...cefe70`表示继续执行后，执行前复核发现其只绑定inputs/outputs/audit，
  未绑定ADR要求的正式`/registry:rw`；继续只能增加未获批挂载或绕过事件链，故在读取真实财务值前
  fail closed。
- 旧scope永久保留并标记`SUPERSEDED_BEFORE_REAL_DATA_READ`；不是DATA NO-GO或策略REJECT。
  正式registry/approval/input bundle/runner/auditor均未创建，真实财务行、候选、门执行仍为0。
- 唯一恢复为release合同强制第四个内容寻址`/registry:rw`挂载；protocol、8式/3池/24单元、输入
  manifest、门槛、尝试N、提案到期和未授权项不变。修复须先推送并生成新scope，用户必须重新批准
  新SHA。恢复单见`docs/M5_DYNAMIC_FUNDAMENTAL_DATA_GATE_RELEASE_RECOVERY_20260805.md`。

## 2026-08-05 · M5-2B精确data release已就绪，停在用户授权前

- M5-2B实现已分批提交并推送，最终实现提交`4369d7f9fa08fca023c07beecb47bc898c56ba72`；科创50
  官方成员源的稳定`code`字段已通过窄source adapter规范化为内部`ts_code`，M3两池仍严格要求
  `ts_code`，未知池/schema漂移继续fail closed。
- metadata-only输入清单绑定7类API、16,843个不可变批次和3份成员证据；逻辑/物理SHA分别为
  `d9de2ece…8d4d`/`3277114e…5919`，`semantic_rows_read=false`。最终断网镜像为
  `sha256:64928c62…555c`，纯合成8候选×3池/24单元与独立审计PASS。
- 精确data release scope为`f53085d3cc428e17f014a3d1b0ab7f2f2f0f4ddf6eb64b2db7042fd26ccefe70`，
  绑定提案到期`2026-08-12T18:48:16+08:00`。scope只标记release ready，所有真实读取、门执行、
  标签/效果、外部调用、训练/回测、Web、scheduler与生产授权均为false/none。
- 最终全仓725 PASS、M5专项70 PASS、架构6 PASS；Ruff/compileall/pip/Compose/diff/脱敏通过，生产
  scheduler仍为原容器`183b8c6c5edd...`、原镜像`722f63de...13b76`且healthy、未重启。
- 当前必须停止。只有用户明确批准上述精确scope后，才可在一次性断网Docker中运行一次真实
  DATA_GATE；任何DATA_GO也不授权后续工程门、效果/G1或生产。验收见
  `docs/M5_DYNAMIC_FUNDAMENTAL_DATA_GATE_RELEASE_ACCEPTANCE_20260805.md`。

## 2026-08-05 · M5-2B数据门实现通过纯合成工程门，待正式release

- 独立`shaiwei.research_gates`已实现：四表SQLite gate registry、候选级财报PIT配对、八式纯函数、
  月末至下一开市日成员映射、8×3门阵、write-once runner、独立重算auditor、元数据输入清单和精确
  release/approval合同，以及仅在批准校验后可用的内容寻址硬链接输入包；新增生产模块最大348行，
  没有扩写F1/F2/M5-1或生产/Web模块。
- 完全合成数据专项47项、全仓721项、架构6项及Ruff/compileall/pip check/Compose/diff门均PASS。
  首次最小镜像运行发现Pandas Spearman暗依赖未锁定SciPy并失败关闭；现改为确定性平均秩+Pearson，
  不扩大冻结依赖，回归后短命断网容器全链PASS：8候选、3池、24单元、独立审计PASS、临时registry
  恰好4表。
- 本节点仍是construction-only：正式registry不存在，真实财务行/候选值/24单元结果均未读取或计算，
  data gate批准/执行、效果/provider/费用/训练/回测/生产均为0/none。下一步须先提交推送本实现，再以
  该提交重建最终镜像并生成metadata-only input manifest与精确data release scope；用户批准scope前
  不得执行真实数据门。

## 2026-08-05 · M5-2B数据门施工合同冻结

- 新施工合同把M5-2B拆为可审计的construction-only节点：本阶段只实现独立registry、候选级PIT
  配对、八式纯函数、24单元门阵、独立auditor和短命离线Docker，全部真实语义测试只用合成fixture。
- 两项旧实现不得直接继承：F2三表共同期不适用于候选所需组件独立配对；P2/M3逐日成员必须取月末
  形成后的下一开市日集合，其中M3行内`formation_date`还须等于对应月末。
- 有效形成月固定为有效候选数达到池最低横截面；aggregate/worst覆盖分母固定为2021-01至2025-12
  全部60个月的全部成员行，54个月与十个半年段门都复用该定义。
- 不扩写既有F1/F2、M5-1或大research compose；新增模块目标不超过400行，使用独立专属镜像与
  `compose.m5-gates.yaml`，不挂整仓data、项目根、`.env`、Docker socket、标签/效果/模型或生产路径。
- 当前仍未读取真实财务行、未计算真实候选、未初始化正式M5-2 registry、未登记门批准、未运行
  data/engineering gate，效果/provider/费用/生产均为0/none。施工合同见
  `docs/M5_DYNAMIC_FUNDAMENTAL_DATA_GATE_BUILD_PROTOCOL_20260805.md`；实现必须在后续独立提交推送后
  才能形成精确data release scope，用户批准该scope前不得执行真实数据门。

## 2026-08-05 · M5-2A科创三池动态基本面协议结果前冻结

- 首份`REVIEW_REQUIRED`提案已通过内容寻址export绑定proposal/request/canonical/event head与七日到期
  身份；M5-1继续是非权威提案控制面、零schema/API迁移，不原地升级为研究任务。
- `m5-dynamic-fundamental-cross-pool-data-preexecution-v1`固定科创50home池和科创板中盘/小盘两个
  `CUSTOM_RULE_BASED`迁移池，登记毛利率、研发强度、应收质量、库存、杠杆、流动性、外部融资与
  自由现金流八个新候选和24个评价单元；与F2六式零重复、不翻向、不补位。
- 协议冻结使八个公式正式计入生成尝试：动态基本面主域`N=6→14`、联合基本面敏感性`N=12→20`；
  当前效果测试仍为0。数据失败也不从N删除，跨池相关性不折减N。
- 新ADR选择独立M5-2 gate registry与短命断网Docker，不扩展M5-1、不建常驻Worker/队列；protocol
  scope与每门release scope分离，数据门和synthetic工程门必须分别批准。
- 本节点只授权协议提交推送。`data_gate_approval_recorded=false`、
  `engineering_gate_approval_recorded=false`，零真实数据读取、零标签/效果、零provider/费用、零模型/
  回测/前瞻/生产/Web/scheduler变化。冻结提交`98f2d10b2eb76809b0bf373d0be1ebcd5d1198b6`已先行
  推送；protocol scope为`ab8c33968c4ced325ec79524b774163f2991edd0c4d5d7eb7c139b27e9b17557`。
  专项与scope测试12 PASS、全仓667 PASS、架构6 PASS；研究与架构专项复核均GO。
- 下一合法动作是先施工并推送M5-2B数据门实现/release，生成精确`data_gate_release_scope_sha256`；
  用户批准前不得运行真实数据门。见`docs/M5_DYNAMIC_FUNDAMENTAL_CROSS_POOL_PROTOCOL_20260805.md`
  、`docs/ADR_0002_M5_2_GATE_REGISTRY.md`与
  `docs/M5_DYNAMIC_FUNDAMENTAL_CROSS_POOL_PROTOCOL_FREEZE_ACCEPTANCE_20260805.md`。

## 2026-08-05 · M5-1A首份跨池研究提案已提交人工复核

- 通过本机Web控制面建立提案`1dc3afa027401c9fd8ad54382f0b024a8b78b73d2216f2c683a33d4c22497efb`：
  主池为科创50，迁移比较池为科创板中盘/小盘PIT研究池；家族为动态基本面，固定8个确定性候选、
  最多24个跨池评价单元、零provider调用、零费用，七日有效。
- 提案于`2026-08-05T18:48:16+08:00`创建并提交，当前`REVIEW_REQUIRED`、事件序号2；运行时库为
  proposals/events/receipts=`1/2/2`，Web三容器和生产scheduler均healthy。
- primary动态基本面域只登记计划N由6至14，联合基本面敏感性域由12至20；
  `actual_research_attempt_increment=0`，DeepSeek、数据读取、标签、效果、训练、回测、前瞻和生产仍
  全部未授权。
- 提案将于`2026-08-12T18:48:16+08:00`到期。下一合法动作是另立M5-2冻结/批准协议并由用户明确
  授权；当前不得自动发布、排队或运行。

## 2026-08-05 · M5-1非权威研究提案控制面GO

- 独立`research-control`、SQLite v1三表和本机Web提案工作台已交付；只允许create、submit-review、
  cancel，状态上限`REVIEW_REQUIRED`。freeze/approve/release/enqueue/run/Worker/DeepSeek/回测/前瞻/
  生产端点均不存在，M5-1的GO不等于研究协议冻结、策略有效或生产授权。
- 服务运行时只接受补正后的v2真身；五个可选池、三个阻断池、五个研究家族及primary/sensitivity
  multiplicity由服务端派生。确定性意向0调用/0费用；LLM调用数和预算只登记上限，不产生调用权。
- 第三轮独立审计曾因孤儿receipt和首次写入未在提交前重建给出NO-GO；现已增加全库双向
  proposal/event/receipt重建，health/read/write前后统一验证，错误响应/status/time整事务回滚；第四轮
  审计最终GO。
- 全仓655 PASS、架构6 PASS、前端32 PASS、五视口69 PASS/11 skip、真实部署14 PASS；Ruff、
  compileall、pip check、Compose、diff与脱敏均PASS。实现提交`d8db2046ff81c06cfefa81aa179918b5cac2e8b8`。
- 最终control/Web镜像分别为`95c00fb5...22e2`/`7e2dc45b...f7cb`，三Web容器healthy；真实控制库
  proposals/events/receipts=`0/0/0`。scheduler容器`183b8c6c5edd`与镜像`722f63de...13b76`施工前后
  完全未变且healthy。验收见`docs/M5_RESEARCH_PROPOSAL_CONTROL_ACCEPTANCE_20260805.md`。
- 下一合法动作不是自动开跑，而是用户在Web建立具体提案并提交人工复核；任何M5-2冻结、批准或执行
  必须另立ADR、结果前协议并重新授权。

## 2026-08-05 · M5-1冻结口径补正先行

- 独立复核发现首份M5-1配置把家族、联合研究域和全局敏感性尝试N压成单值：静态基本面`12`无法
  由绑定的F1单独证明，残差风险也丢失本家族`N=3`与相关价量域`N=273`的双层口径。v1协议/配置
  永久保留，v1配置标为`SUPERSEDED_BEFORE_IMPLEMENTATION`，不得作为运行时真身。
- `m5-research-proposal-control-correction-v1`仅授权v2配置：五家族分别登记primary与可选sensitivity
  作用域、计数和证据，planned-after按生成尝试上限一次增加；跨池评价单元不得机械放大尝试N。
- 确定性生成固定零provider调用/零费用；LLM意向固定调用数和完成响应目标等于尝试上限且费用必须
  大于0、不超过1美元。两者仍都只是提案意向，approval/provider spend/外部调用继续显式未授权。
- 架构宪法已进入v2机器身份和启动漂移门；施工只能在v2全部输入哈希通过后进行。见
  `docs/M5_RESEARCH_PROPOSAL_CONTROL_CORRECTION_PROTOCOL_20260805.md`。

## 2026-08-05 · M5-1研究提案控制面已结果前冻结

- M5-1对象统一为`NON_AUTHORITATIVE_PROPOSAL`，不是研究任务或协议；只施工create、submit-review、
  cancel，状态最多到`REVIEW_REQUIRED`，冻结/release/enqueue/run/Worker/外部调用端点物理不存在。
- 首份架构决策选择独立`research-control`与SQLite单事务操作态；M5-1无外部副作用，不提前建设队列、
  approval、attempt、artifact、outbox或研究ledger。未来M5-2须复审并另立协议。
- 提案绑定补正后的M5 v2快照和M1注册表，严格登记五个可选池、五个研究家族、尝试/候选/评价/费用/
  有效期上限及历史multiplicity背景；model/portfolio和全部执行、结果、生产授权显式为false/none。
- 本机Web写入必须经过loopback Origin、短会话、CSRF、限流和内部Docker secret；control无宿主端口、
  无外网、`.env`、raw、研究结果、ledger、Docker socket或生产挂载。见
  `docs/M5_RESEARCH_PROPOSAL_CONTROL_PROTOCOL_20260805.md`与`docs/ADR_0001_M5_PROPOSAL_CONTROL_PLANE.md`。

## 2026-08-05 · M5-0A跨池评价单元计数补正GO

- M5-0目录把M3的24次生成响应误记为24个评价单元；M3结果前协议和发现验收明确每个响应跨三个池
  评价，因此权威口径应为生成尝试24、评价单元72，相关价量发现域N仍为270。
- 旧目录、旧快照和M5-0工程GO永久保留；只将旧快照中的该字段标为非当前multiplicity真身，不改变
  M3合同STOP、策略NOT_EVALUATED、效果读取0、正式库0或任何生产事实。
- `m5-strategy-factory-count-correction-v1`只授权机器addendum、新内容寻址v2快照和Web只读切换；
  补正已验收通过。新v2快照中唯一业务差异为M3评价单元24→72，旧v1目录全树哈希施工前后不变。
- Web已切换v2并真实返回生成24/评价72/效果0；603项全仓测试及架构、静态、Compose门通过，Web
  双容器healthy，scheduler身份未变。见
  `docs/M5_STRATEGY_FACTORY_COUNT_CORRECTION_ACCEPTANCE_20260805.md`。
- M5-1历史计数阻断解除，但proposal-only仍须独立结果前协议；零research-control、Worker或真实
  研究授权。

## 2026-08-05 · 代码与架构宪法v1生效

- 项目级宪法已将“结果优先、证据裁决、合同先行、依赖向内、失败关闭、生产/研究/Web隔离、继承
  稳定内核和显式迁移回滚”固化为所有后续施工的共同开工/交付门；先进性不再以技术数量衡量。
- `config/architecture_constitution_v1.yaml`建立生产模块400行软门、600行硬门；13个既有超限热点
  逐文件冻结最高行数和退出触发器，允许缩小、禁止增长，防止新需求继续堆入历史大文件。
- `make architecture-check`自动核对宪法入口、热点棘轮和两条依赖方向：领域代码不得反向依赖Web，
  只读查询不得依赖运行配置、通知、生产编排或HTTP API。语义职责、重复逻辑、函数复杂度和抽象
  价值继续由人工清单复核，避免为过机器门制造形式化拆分。
- 后续新增常驻服务/依赖、写API、公共Schema、权威计算、部署权限、跨层依赖或共享扩展点必须先写
  ADR；禁止在功能提交中静默放宽阈值或登记无退出条件的例外。

## 2026-08-05 · M5-0多股票池策略工厂只读工程GO

- 八池、六研究家族和八个既有工作包已形成内容寻址只读投影；固定事实为登记8、可建立草案5、
  数据/PIT阻断3、既有生产1、正式准入0、活跃授权任务0。最终snapshot id为
  `b241428...af9b3`，断网投影复跑同哈希。
- 本机Web新增“策略工厂”：研究地图、家族矩阵、历史工作包和本地临时草案均已接真实只读证据；
  草案不保存、不提交、不冻结、不运行，无写API、Worker、DeepSeek、回测、前瞻或生产授权。
- 全仓599 PASS、前端单元28 PASS、五视口fixture 69 PASS/11 intentional skip、真实部署14 PASS；
  axe serious/critical=0，五档无横向溢出。首次验收发现的辅助文字对比度和Top20已进入FORWARD后
  的旧文案/断言均已按真实证据修正。
- 最终Web镜像`899e4be...960b8`，两个Web容器healthy；scheduler容器`183b8c6c5edd`、镜像
  `722f63de...13b76`、创建时间和代码快照施工前后不变且healthy。见
  `docs/M5_STRATEGY_FACTORY_ACCEPTANCE_20260805.md`。

## 2026-08-05 · M5-0多股票池策略工厂合同已结果前冻结

- 用户确认把“不同股票池持续研究不同策略/因子并通过Web展示”建设为固定能力，并授权研究治理、
  后台架构和Web产品三个专项窗口并行细化；三份方案已回传且没有修改既有生产代码或研究结果。
- M5-0只建设统一目录、authority overlay、内容寻址只读投影、GET/HEAD查询和本机Web工作台；浏览器
  草案固定为`DRAFT_NOT_SUBMITTED`，不保存、不排队、不运行。真实DeepSeek、候选生成、效果读取、
  模型/回测、前瞻、生产与scheduler改动均未授权。
- 当前冻结事实为8个登记池、5个可建立研究草案、3个数据/PIT阻断、1个既有生产策略、正式因子准入
  0、活跃授权任务0；中证800仍是唯一生产主策略。M1历史注册表不改写，后续M2/M3/M4状态通过显式
  overlay表达。
- 每个未来真实研究批必须有候选/池矩阵/费用/资源/时限上限，终态不自动派生下一批；协议冻结、外部
  调用、封存效果、前瞻账户和生产发布五类授权不能互相推导。见
  `docs/M5_STRATEGY_FACTORY_PROTOCOL_20260805.md`及三份`M5_MULTI_POOL_*`专项设计。

## 2026-08-05 · M4-1科创50固定残差因子终版REJECT

- M4-1终版独立审计PASS：三候选方向门2/3，通过适配历史效果门0/3，权威裁决`REJECT`；正式G1因
  2019—2024冻结窗口与科创50官方PIT历史域不匹配仍未运行，正式因子库0插入、生产授权none。
- 35日残差动量预注册方向失败且未读OOS；5日残差反转与40日负特异波动率均为六窗同向，但分别
  败于4项/3项硬门，公共失败项是2倍成本、额外双边10bp和DSR；反转另败于压力回撤。
- 完成态幂等复用PASS，报告、10个Parquet、manifest及两账本共14个文件哈希零变化；两账本按原始
  字节入库，filtered/no-filter Git对象哈希相等。验收见
  `docs/M4_STAR50_RESIDUAL_EFFECT_ACCEPTANCE_20260805.md`。
- M4-1本批关闭：不翻方向、不调公式/门槛、不追加变体、不进前瞻或生产。未来科创50研究须另立有
  独立经济机制的新批并继续累计研究尝试数。

## 2026-08-05 · M4-1R2证据已发布、独立审计顺序补正先行冻结

- 闭环已写入1条运行账本、3条决策账本与manifest；报告`627f304a...656b`及10个Parquet哈希未变。
  独立审计除`candidate_decisions`外全部PASS，尚未披露效果裁决。
- 根因仅为JSON排序后的`gates`键顺序与`failed_gates`冻结评估顺序不同；两个效果分支的失败门成员
  集合、数量4/3及决策标签一致。M4-1R2A只允许“无重复且集合相等”审计，不改门成员或任何结果。
- 两份CSV已发布字节含“LF表头+CRLF追加行”，而通用Git文本属性会在入库时改写物理哈希；同一补正
  仅允许对这两份账本关闭文本规范化，保留manifest绑定字节，不得转换账本或重发manifest。
- 补丁和新release须先推送，再用新断网镜像完成纠正审计与闭环复用零改写。见
  `docs/M4_STAR50_RESIDUAL_EFFECT_AUDIT_ORDER_RECOVERY_PROTOCOL_20260805.md`。

## 2026-08-05 · M4-1R2证据发布闭环已结果前冻结

- 只绑定M4-1R既有报告`627f304a...656b`与两遍共10个Parquet；账本仍0行、manifest仍缺失，审计
  前继续隐藏候选效果，不重算任何研究结果。
- 唯一实现变量为直接对两个预创建CSV自身加`flock`，不创建sibling lock、不放宽`ledger/`父目录；
  新闭环入口须先核封存哈希，只能走报告复用分支，再完成manifest、1+3账本与独立审计。
- 即使闭环后适配门通过，正式G1-v1仍因窗口域不匹配保持未运行，正式库0、生产none。协议见
  `docs/M4_STAR50_RESIDUAL_EFFECT_EVIDENCE_CLOSURE_PROTOCOL_20260805.md`。
- 闭环实现已就绪：独立协调器不导入研究计算路径，统一manifest与账本期望行，审计新增manifest和
  账本逐字段核对；断网Docker仍只给结果根与两个CSV窄写。专项16/全仓592项测试、Ruff、compileall、
  pip check与Compose检查PASS；须先提交推送本实现，再冻结闭环release，当前仍未补账本或读效果。
- 协议YAML的`frozen_at=00:40`为手工时间转录错误，冻结提交`6452b55`的权威Git时间是
  `2026-08-05T09:14:38+08:00`；原协议不改写，已另立纯时间addendum，零方法/范围/封存哈希变化。
- 闭环实现提交`6f2c14c`已先行推送；执行release绑定协议`f79931ec...9abe`、时间addendum
  `578964b7...1664`、代码束`76f11354...9ff3`及11个封存输入，只授权断网报告复用、账本/manifest、
  独立审计和二次幂等；审计PASS前仍不得披露效果。

## 2026-08-05 · M4-1R计算完成但证据发布失败，效果报告封存待审

- M4-1R新镜像完成首遍与内部确定性复跑，两遍各5个Parquet逐字节相等，并写出身份绑定正确、
  自述`determinism_pass=true`的效果报告；未读取或解释报告内候选效果与裁决。
- 随后账本追加需在`ledger/`创建同目录`.csv.lock`，但运行时只给CSV文件窄写、父目录只读，入口以
  `OSError`中止；两本账本仍0数据行且哈希未变，运行manifest缺失，独立审计条件不成立。
- 按预冻结的二次工程失败即停规则，未修改挂载、未第三次调用、未补写账本。权威状态仅
  `BLOCKED_EVIDENCE_PUBLICATION` / `NOT_EVALUATED_PENDING_EVIDENCE_CLOSURE`，正式库0、生产none。
- 如继续须另立M4-1R2，只绑定既有报告与10个Parquet、修锁文件窄写挂载并走报告复用分支；禁止重算
  任何结果，独立审计前不披露效果。见
  `docs/M4_STAR50_RESIDUAL_EFFECT_RECOVERY_FAILURE_20260805.md`。

## 2026-08-05 · M4-1首次效果入口工程失败、M4-1R单点纠错已结果前冻结

- 冻结release后的唯一入口在生成报告、不可变Parquet或账本行前因RankIC一维无名日期索引与
  `_between`两级命名索引假设冲突而`KeyError`中止；异常输出不含任何效果值，人工未查看候选结果。
- 结果目录仍为空，两本专属账本仍仅表头且哈希未变；该次永久记
  `INVALID_ENGINEERING_ATTEMPT_NO_RESEARCH_DECISION`，只计工程尝试，不形成策略裁决。
- M4-1R只授权兼容两级信号索引与一维RankIC日期索引并补回归测试；公式、方向、窗口、标签、
  中性化、Alpha158混合、组合、执行、成本、压力和门槛全部不变。修复与新release均须先推送，才可
  恰好恢复一次。见`docs/M4_STAR50_RESIDUAL_EFFECT_RECOVERY_PROTOCOL_20260805.md`。
- 单点修复提交`f38ad4e`已先推送，专项12/全仓588项测试及Ruff、compileall、pip check、Compose
  检查均PASS；新恢复release精确绑定该提交、代码束`5109ec5b...3c83`、空结果目录和两本表头账本，
  只授权新的断网镜像执行一次恢复首遍与一次内部复跑。

## 2026-08-04 · M4-1科创50残差因子效果协议已结果前冻结

- 固定M4-0三式、方向及40/60区间规则；发现期只做方向门，2023—2025封存期效果须等实现与release
  分别先提交推送后才能读取。零DeepSeek、零模型重训、零生产/模拟仓/Web/scheduler改动。
- 因科创50合法PIT历史不能覆盖G1-v1的2019—2024固定窗，本批使用六个2023—2025半年窗并复用
  原数值门槛，但明确命名为科创50专属适配效果门；正式G1-v1保持
  `NOT_RUN_UNIVERSE_WINDOW_DOMAIN_MISMATCH`，即使历史通过也不插入正式因子库。
- 封存期候选须在PIT行业、log总市值和冻结Alpha158分数之外提供增量信息；组合固定90/10、Top10、
  `n_drop=2`、10日调仓，执行复用P2-2C纠错后的开盘/容量逻辑，并冻结成本、压力、NW与DSR全门。
- 本节点仍未读取标签、RankIC、收益或封存效果。见
  `docs/M4_STAR50_RESIDUAL_EFFECT_PROTOCOL_20260804.md`。
- 实现已以`e45c83e`独立提交推送，全仓586项测试、Ruff、compileall、pip check与研究Compose配置
  PASS；8个执行模块最大387行。执行release绑定协议`a006f62d...a8aa`、代码束
  `2f483b5b...494a`和实现提交，只授权断网Docker首遍加一次内部完整复跑。release推送前仍未读效果。

## 2026-08-04 · M4-0科创50基准残差因子数据/预执行门GO

- 旧M1/M3通用价量批保持权威STOP，不续跑、不补发、不回救；新任务改为独立的科创50基准残差
  机制，只复用P2 v2/P2-1官方PIT成分、复权行情、基准和PIT行业/市值真身。
- 固定三个候选：35期残差动量跳过最近5期、5期残差反转、40期低特异波动；统一使用最近60个基准
  交易日内最新40个同端点股票/基准区间收益，带截距单指数OLS，方向和缺失规则已冻结。
- 本阶段只允许构建发现期特征、核覆盖/确定性和哈希；标签、IC、收益、2023—2025封存验证、G1、
  模型、组合、信号和生产均未授权。零DeepSeek、零外部API、零密钥读取。
- 相关价量研究背景由270次加本批3个固定候选记为273次；未来不重置多重检验。协议见
  `docs/M4_STAR50_RESIDUAL_FACTOR_PROTOCOL_20260804.md`。
- 实现提交`e9f195c`已在任何真实特征值计算前推送；纯fixture与全仓576项测试、Ruff、compileall、
  pip check均通过。一次性执行release固定代码束`a4a5bd4a...d2b3a`，只允许断网、无密钥、非root、
  只读输入和独立结果目录运行两遍（首遍+幂等），不得借本release查看效果。
- 真实结果为577日/28,850成员日，12个全天停牌日按冻结分母排除；其余28,838行三个候选全部有限，
  各自覆盖100%、每日最少49只，重复/非有限/`.BJ`均0。第二遍完整复跑两项哈希不变，独立只读审计
  PASS；权威裁决仅`GO_M4_STAR50_RESIDUAL_DATA_PREEXECUTION_ONLY`。
- 标签、RankIC、收益、封存验证、G1、模型、组合和生产仍未读未跑；策略`NOT_EVALUATED`。下一步
  只能另立M4-1结果前效果协议，不改三式、40/60窗口、方向或缺失规则。见
  `docs/M4_STAR50_RESIDUAL_FACTOR_ACCEPTANCE_20260804.md`。

## 2026-08-04 · M2-0R2科创200恢复完成，数据门仍权威NO-GO

- 2026-07 Tushare月度集合已补齐：即时双查均200行/200只/唯一日期20260731/`.BJ=0`，其余26项
  重哈希一致，24个月二级快照源门PASS；原0行批次永久保留。
- 全新目录重扫官方4页归档、12个候选和13个附件；相对旧恢复证据URL增删0、同URL内容变化0，
  科创200历史成员对仍为0。24个月只有1个月与无调整首批集合一致，官方谱系和PIT仍不可构造。
- 权威终态`NO_GO_M2_STAR200_DATA_GATE`、策略`NOT_EVALUATED`、生产none。断网无密钥全只读复跑
  零查询、七项哈希不变；scheduler仍原镜像healthy。见
  `docs/M2_STAR200_DATA_RECOVERY_V2_ACCEPTANCE_20260804.md`。
- 公开数据路线到此停止，不再按天盲扫同一归档。若继续M2，只接受带发布/生效/版本/修订语义的授权
  历史成分源并另立协议；等待期研究可转向科创50或三类已有合法PIT的自建科创池。

## 2026-08-04 · M2-0R2科创200数据恢复协议已先行冻结

- 用户批准继续处理科创200数据基础层；本任务只复核外部数据缺口，不读取因子/收益，不改变原M2-0
  协议、恢复单和权威NO-GO。
- 唯一Tushare变量为重新即时双查`000699.SH`的2026-07 `index_weight`；其他26个请求复用并重验旧
  哈希。官方材料使用全新内容寻址目录完整重扫至20260804，避免旧缓存掩盖页面更新。
- 即使7月快照补齐，只要9个历史变化区间的官方成员对仍不闭合，仍须NO-GO；月末集合不得反推PIT。
  本提交只冻结协议和配置，联网前须先完成断网fixture、提交并推送。见
  `docs/M2_STAR200_DATA_RECOVERY_V2_PROTOCOL_20260804.md`。

## 2026-08-04 · M2-0R2科创200数据恢复执行器已断网就绪

- 新增独立恢复schema与薄编排，只允许重查2026-07一个分区、复验其余26项并用全新官方目录重扫；
  完成态入口不再读取密钥或请求Tushare，部分中断若缺双查证明则失败关闭。
- fixture覆盖旧证据绑定、路径逃逸、复用证据漂移、双查不一致、`.BJ`、第三次请求和幂等复用；通用
  采集、官方解析、PIT门槛与生产路径未改。全仓572 PASS，Ruff、compileall、pip check通过。
- 本节点仍未执行真实Tushare查询或官方联网重扫、未读取因子/策略结果。须先提交推送本实现，再以
  该固定代码身份执行唯一联网恢复；执行前原27项最新证据仍与M2-0原collection逐项一致。
- 断网容器预检发现当前生产scheduler镜像不含官方抓取所需`curl`；未改生产Dockerfile/镜像，改用
  专属一次性`Dockerfile.star200-recovery`在旧只读运行时上只增加`curl`并复制当前研究代码。该镜像
  不进入release审计、不promote、不启动常驻服务，真实运行仍为非root/只读根/最小挂载。

## 2026-08-04 · P0-E 20260805恢复发布守护预执行GO

- 20260804漏派发和自然结果已经可见，本恢复不主张盲预注册；旧v1/原协议/预执行与未派发验收永久
  保留。协议/配置`1fece49`先行推送，v2只把目标日改为20260805并更新双账户最新FORWARD边界。
- 最小实现`ff51020`随后推送；候选`0640574b...c40`、旧生产`4e5244b6...82708`、16:05—19:00
  窗口、唯一新日门、原子promote+start和失败恢复语义全部不变，测试同时锁定v1不可改写。
- 宿主专项47/全仓563 PASS；断网只读无挂载/无凭据Docker专项47 PASS。今晚入口在任何Git/Docker/
  release读取前以日期不符BLOCKED；生产审计仍24行、旧scheduler未重启且healthy。
- 真实执行只允许20260805窗口恰好一次，BLOCKED不得改日期/锚点追成功；STARTED后另验自然全链。
  见`docs/DAILY_EARLY_READINESS_RELEASE_RECOVERY_PROTOCOL_20260804.md`与
  `docs/DAILY_EARLY_READINESS_RELEASE_RECOVERY_ACCEPTANCE_20260804.md`。

## 2026-08-04 · 自然整链PASS_WITH_NOTIFICATION_WARN、P0-E发布未派发

- 19:34—19:53自然链完成：日增量、S1—S9、影子、开盘对账、Top30/Top20、重放与机器验收均PASS，
  S10 NOT_APPLICABLE；新增8个原始批次共21,158行，逐文件哈希一致且`.BJ=0`。
- Top30/Top20最新FORWARD产物分别为`691987e0...e89f`与`26de5b7f...afec`，观察日累计9/7；两账户
  当日均非调仓日。Top20开始通知首次`NETWORK_SSLEOFError`、第二次恢复，故权威表述为
  `PASS_WITH_NOTIFICATION_WARN`。
- 受控重复`scheduler --once`后三段均NOOP，7个账本、通知、双账户产物和信号物理哈希全部不变。
  release审计仍24行且current仍为旧生产`4e5244b6...82708`，候选`0640574b...c40`未提升；项目内
  无守护派发证据，只分类`AUTOMATION_DISPATCH_NOT_OBSERVED`，不猜应用侧原因。
- 20260804守护已过期且不得改写。下一步另立20260805恢复协议并先行推送，以本次双账户产物作为新
  边界；不得补造旧日发布或手工补跑。见
  `docs/DAILY_EARLY_READINESS_RELEASE_NONDISPATCH_ACCEPTANCE_20260804.md`。

## 2026-08-03 · P0-E 20260804发布守护预执行GO

- 本地冻结交易日历确认20260804为20260803后的首个开市日；窗口固定16:05（含）—19:00（不含）。
  协议/配置`cd89247`先行推送，精确绑定候选`0640574b...c40`、当前生产`4e5244b6...82708`与
  Top30/Top20最新20260803自然FORWARD产物。
- 实现`069604d`支持fresh原子promote+start、唯一半切换续接、already-active幂等；启动失败会依据
  release state重新启动旧current或rollback+start，恢复后再验真实旧容器，双重失败同时上报。
- 守护/release专项55 PASS、全仓562 PASS、断网只读预执行55 PASS；实际今晚CLI在任何状态读取/变更
  前以日期不符BLOCKED。独立测试镜像不进发布审计。
- 生产仍为容器`183b8c6c5edd...23dd3b`/镜像`722f63de...13b76`且healthy；release审计仍24行、current
  未改。真实执行只允许20260804窗口恰好一次，随后另验自然全链。见
  `docs/DAILY_EARLY_READINESS_RELEASE_GUARD_PROTOCOL_20260803.md`与
  `docs/DAILY_EARLY_READINESS_RELEASE_GUARD_ACCEPTANCE_20260803.md`。

## 2026-08-03 · P0-E跨快照静默等待补正工程门GO

- Top20首个自然FORWARD验收暴露：早探测日增量自身可在`WAITING_SOURCE`时零写入、零通知，但
  scheduler仍无条件继续旧影子/模拟仓验收，导致数据到达前7次跨快照失败告警。结果已知恢复协议
  `f21701b`先行推送，旧WARN永久保留。
- 实现`fa6c67a`只在`WAITING_SOURCE`短路本轮shadow/paper并记录脱敏health；PASS仍完整运行下游，
  19:30硬兜底、NOOP、历史补采和所有真正异常失败关闭均未改变。全仓539 PASS，宿主及断网只读
  Docker专项各16 PASS。
- 新候选`shaiwei:scheduler-0640574ba7353c3e` / `sha256:85711ae0...a5e79f`已BUILD_PASS，审计链24行；
  未promote、未改current、未启动。生产仍为容器`183b8c6c5edd...23dd3b`/镜像`722f63de...13b76`且
  healthy。
- 下一步须另立日期绑定的P0-E发布守护，不能直接复用已绑定Top20/20260803的旧guard；只在后续另一
  新交易日单独提升并实测。见`docs/DAILY_EARLY_READINESS_NOTIFICATION_RECOVERY_PROTOCOL_20260803.md`
  与`docs/DAILY_EARLY_READINESS_NOTIFICATION_RECOVERY_ACCEPTANCE_20260803.md`。

## 2026-08-03 · Top20首个自然FORWARD核心PASS、发布切换通知WARN

- 19:30自然跑批完成：日增量`0e17435bc0fa`、S1—S9、影子、信号、次日开盘对账、Top30与Top20
  模拟仓、各自重放和机器验收均PASS；S10为NOT_APPLICABLE，实际新增8个原始批次共21,158行，
  `.BJ=0`。scheduler保持受控容器`183b8c6c5edd...23dd3b`与镜像`722f63de...13b76`、healthy。
- Top20机器账本为BACKFILL 6/FORWARD 6，但其中20260727—31为生产切换追赶；20260803才是本候选
  首次由常驻scheduler自然生成的FORWARD账户日。Top30/Top20当日均非调仓日，分别持仓22/17只，
  会计恒等差0，独立重放和只读验收PASS。
- 17:39—19:16新数据到达前，当前scheduler对旧快照FORWARD产物按失败关闭，连续7次发送同一稳定
  消息ID的`daily_scheduler_cycle_failed`；19:31数据到达后自动追赶并恢复，无日跑批FAIL账本、
  无人工补跑/修数/重启。故权威裁决为`PASS_WITH_NOTIFICATION_WARN`，不得表述为无告警全绿。
- 一个自然日只完成工程闭环，不证明Top20优于Top30或策略有效；两账户继续OBSERVING。P0-E 16:00
  早探测已满足此前置条件，但只能在后续另一新交易日单独提升和实测，不在今晚连带施工。见
  `docs/PAPER_TOP20_FORWARD_ACCEPTANCE_20260803.md`。

## 2026-08-03 · Top20生产候选已受控启动，等待首个自然FORWARD

- 16:05计划任务没有留下守护输出或新增发布审计；17:38复核时审计仍22行、scheduler仍为旧镜像，
  只能继续分类`AUTOMATION_DISPATCH_NOT_OBSERVED`，不猜测Codex应用侧具体原因。
- 用户要求继续可执行下一步后，主控在冻结的16:05—19:00窗口内只执行一次
  `make docker-release-guard`。Git/审计链/候选/旧容器/最新Top30/readiness全门PASS，唯一新交易日
  `20260803`，机器返回`STARTED`。
- 实际scheduler已切换到容器`183b8c6c5edd...23dd3b`、镜像`722f63de...13b76`、代码快照
  `4e5244b6...82708`，只读根且仅挂载data/ledger/logs，定向复核healthy；新增唯一`START_PASS`
  审计哈希`6d227e7f...ea0f2`。
- 本结论仅为发布切换PASS，不是今日跑批或Top20前瞻PASS。不得手工补跑；等待19:30自然串行Top30、
  Top20后再验`.BJ`、S1—S10、信号、两账户、飞书、幂等与首个Top20 `FORWARD`。16:00早探测仍须
  等Top20自然前瞻通过后的另一交易日。见`docs/PAPER_TOP20_RELEASE_START_ACCEPTANCE_20260803.md`。

## 2026-08-03 · F2-1中证800基本面动态六候选效果门权威REJECT

- 结果前协议`cb17b3e`与实现`e3c8aa6`均先行推送；固定六公式/方向、2016H2—2018发现、
  2019—2024六个OOS窗、三压力期、三成本和`90% Alpha158 + 10%动态基本面正式残差`。
- 方向门5/6 PASS；货币资金变化与预注册正方向相反并在读OOS前停止。五项进入G1但0/5 PASS，
  候选净超额`0.152862—0.331122`均低于Alpha158基线`0.518237`；正式库0插入、生产授权none。
- 多重检验不重置：F1静态六次与F2动态六次分别留档、联合计`N=12`；F2只新增6条实验和5条G1
  拒绝。完整二跑的实验/G1/逐日IC/逐日收益/汇总/manifest全部复用且哈希不变。
- 权威终态`REJECT`，不训练模型、不改主策略。F2-1到此停止，不翻方向、不改权重/窗口/成本、不追加
  本家族变体；新机制须另立结果前协议并保留既有12次背景。见
  `docs/F2_CSI800_FUNDAMENTAL_EFFECT_ACCEPTANCE_20260803.md`。

## 2026-08-03 · F2-0R基本面动态合法空值恢复门GO

- 明确披露F2-0数据质量已知，不主张盲预注册；恢复协议`db3dbc0`只把合法不可估计行改为保持全空并
  由原冻结85%/75%覆盖门裁决，不按已知1行设白名单或数量门，公式/PIT/样本/阈值均不变。
- 全样本12,325个无连续年度对记录的联合可用日和六项特征全部为空，部分配对、混期、跨年桥接、
  未来数据、来源冲突、重复键和`.BJ`均为0；质量期仍只有1行不可估计。
- 恢复面板101,600行且SHA与F2-0 v1逐字节相同；六项总覆盖95.7652%—99.9987%、最差形成日
  95.125%—99.875%，全门PASS。终态仅
  `GO_F2_FUNDAMENTAL_DYNAMICS_RECOVERY_DATA_FEATURE_GATE_ONLY`，策略`NOT_EVALUATED`、生产none。
- 正确release镜像双跑三项哈希不变，F2-0五项证据与F1-1 manifest均未改写；宿主全仓534 PASS、
  Docker专项7 PASS，scheduler原容器/镜像保持healthy。见
  `docs/F2_CSI800_FUNDAMENTAL_DYNAMICS_RECOVERY_ACCEPTANCE_20260803.md`。
- 下一步可另立F2-1效果协议；必须结果前冻结六方向、Alpha158增量比较、窗口/压力/成本/G1，并把F2
  六次与F1六次合并披露累计N=12。不得直接看效果、追加第七候选或接生产。

## 2026-08-03 · F2-0中证800基本面动态数据/特征门权威NO-GO

- 结果前协议`ff08765`与实现`795993a`均在首次真实运行前推送；F2只研究连续年度基本面变化，禁止
  重跑F1六项静态水平公式。若未来看效果，F2六项与F1六次合并披露累计N=12。
- 127个形成日、101,600个成员形成日、每期800只；混期、非连续拼接、未来数据、来源冲突、重复键和
  `.BJ`均为0。六项总覆盖95.7652%—99.9987%、最差形成日95.125%—99.875%，覆盖门全部PASS。
- 唯一失败硬门为`2018-05-31 / 000939.SZ`没有截至当时可得的连续年度三表共同对；协议要求0，故
  权威终态`NO_GO_F2_FUNDAMENTAL_DYNAMICS_DATA_FEATURE_GATE`。未读效果、未训练/回测，策略仍
  `NOT_EVALUATED`、生产授权none。
- 同一正确release镜像完整双跑三项哈希不变。构建会话误判曾导致空release镜像覆盖并使一次复跑在
  `git_head()`前失败，已串行重建纠正并留痕；另曾输出一次性研究镜像的非敏感完整构建环境列表，后续
  恢复为仅核对定向字段。scheduler原容器/镜像保持healthy且未重启。见
  `docs/F2_CSI800_FUNDAMENTAL_DYNAMICS_ACCEPTANCE_20260803.md`。
- 如继续须另立F2-0R：合法不可估计行保持空值，由原冻结85%/75%覆盖门裁决；不得把门槛改成“恰好
  允许1行”，不得倒灌或非法拼接。恢复通过前不得查看F2效果。

## 2026-08-03 · F1-1中证800基本面六候选效果门权威REJECT

- 结果前协议`61b69f8`与实现`137a6ac`均在真实效果前推送；固定六项经济方向、2016H2—2018发现、
  2019—2024六个OOS窗、三压力期、三成本情景和`90% Alpha158 + 10%基本面正式残差`，不训练模型。
- 六候选方向门6/6 PASS，但G1 0/6 PASS；六项候选净超额`0.22140—0.34295`均低于Alpha158基线
  `0.51824`。最接近的应计项仅净ICIR略高于基线，仍因增量净超额和DSR失败而REJECT。
- 正式家族只新增6条实验与6条G1拒绝，正式库0插入；全量二跑逐日IC/收益、账本、决策、汇总和
  manifest全部复用且哈希不变。权威终态`REJECT`、生产授权none。
- 断网全仓521 PASS、发布镜像F1专项5 PASS；Ruff/compileall/pip check/Compose/脱敏PASS。
  scheduler原容器/原镜像保持healthy且未重启。见
  `docs/F1_CSI800_FUNDAMENTAL_EFFECT_ACCEPTANCE_20260803.md`。
- F1-1到此结束，不翻方向、不改权重/窗口/成本、不追加本家族变体。新基本面机制必须另立独立家族，
  并把本次6次尝试纳入多重检验背景；本次REJECT不外推为所有基本面因子无效。

## 2026-08-03 · F1-0R中证800基本面最新共同报告期数据门GO

- F1-0 v1的1行错峰结果已知后，恢复协议明确披露不是盲预注册；只改变三表PIT选择顺序：先按
  `ts_code+end_date`精确交集，再选形成日最新共同可用年报。v1协议、NO-GO和三个旧哈希永久保留。
- 结果前协议`10352fe`、实现`44a94dc`均先行推送。101,600个成员形成日记录中，全期183个、质量期
  1个单表提前披露错峰均使用此前完整共同年报；实际混期、未来可用、质量期无共同报告期、源冲突和
  `.BJ`均为0，每期800只。
- 六项v2特征总覆盖95.7677%—100%、最差形成日95.125%—100%，全部硬门PASS；双跑三个v2产物
  哈希一致，v1三个旧哈希也不变。权威终态仅为
  `GO_F1_FUNDAMENTAL_PIT_RECOVERY_DATA_FEATURE_GATE_ONLY`，策略仍`NOT_EVALUATED`、生产授权none。
- 正式运行断网、零Tushare/DeepSeek、零账本修改；scheduler原容器/原镜像保持healthy。见
  `docs/F1_CSI800_FUNDAMENTAL_PIT_RECOVERY_ACCEPTANCE_20260802.md`。
- 下一步可另立F1-1效果协议，结果前冻结方向、中性化/残差化、窗口、成本、六候选多重检验和G1；
  F1-0R本身不授权查看效果、模型、回测、入库、前瞻或生产。

## 2026-08-02 · F1-0中证800基本面PIT数据门权威NO-GO

- 结果前协议固定中证800、2016-01-01至2026-07-31、月末形成、严格次日可用、年度三表同报告期和
  六项无方向基本面公式；全程只读本地不可变批次，断网且未读取`.env`、未调用Tushare/DeepSeek。
- 127个形成日、101,600个成员形成日记录、每期800只；`.BJ`、未来可用、源身份冲突均为0。六项
  总覆盖率95.77%—99.9987%、最差形成日95.125%—99.875%，覆盖门全部PASS。
- 唯一失败硬门为1行三表最新年度报告期不一致；协议要求0，故权威终态
  `NO_GO_F1_FUNDAMENTAL_PIT_DATA_FEATURE_GATE`。这不是因子/策略REJECT；结果、方向、IC、模型、
  回测、信号和持仓均未读取或运行，策略仍`NOT_EVALUATED`、生产授权none。
- 缺失组件类型错误在权威产物前失败关闭，最小修复未改协议/公式/门槛；受控镜像双跑后三个产物
  哈希完全不变。scheduler保持原容器/原镜像且healthy。见
  `docs/F1_CSI800_FUNDAMENTAL_PIT_ACCEPTANCE_20260802.md`。
- 如继续须另立F1-0R恢复协议，结果前裁定“各表最新同年”与“最新共同可用报告期”的PIT语义；v1
  NO-GO永久保留，恢复前不得启动基本面效果验证或生产接入。

## 2026-08-02 · L2-0紧凑因子审查合同v2工程门GO

- M1-2语义合同失败与M3-3服务端结束状态失败共同暴露审查合同可靠性瓶颈；结果前协议先以
  `50d0db7`推送，只授权通用断网工程，不回救、续跑或改写任一旧批。
- 新合同显式non-thinking JSON，不传reasoning_effort；summary最多320字符、finding 1—3条、完整
  规范JSON硬限4096 bytes。最大合法fixture为2655 bytes，低于6000 token保守字节上界。
- 公式重复、超长/超数、非ASCII、结论/disposition矛盾在结构层失败；公式修改、业绩/准入声称和
  模糊变体继续复用冻结语义门失败关闭。实现拆为253/213行两个单职责模块，未修改M1/M3冻结代码。
- 宿主专项16 PASS、全仓504 PASS，断网Docker与宿主报告逐字段一致；provider调用0、密钥读取
  false、真实候选/发现/封存结果未读。scheduler原容器/原镜像保持healthy。
- 权威裁决仅为`GO_COMPACT_REVIEW_CONTRACT_V2_ENGINEERING_ONLY`；未来任何真实批仍须新候选协议、
  live release和用户费用授权，M1-3/M3-4仍不获授权。见
  `docs/LLM_REVIEW_CONTRACT_V2_ACCEPTANCE_20260802.md`。

## 2026-08-02 · M3-3审查合同失败并权威停止，不进入验证/G1

- 用户明确批准固定两条公式、非权威摘要、三池定义和四角色问题外发后，live release先行推送；
  无网络、无密钥预检确认2候选、8请求、账本0行、provider调用0且未解析发现指标或封存结果。
- 第1/8个`deepseek-v4-pro`响应完成传输后，服务端结束状态不符合冻结合同；schema和语义门均未
  评价，按规则立即停止且不补发。该响应计数，但没有候选裁决权；`candidate_decisions={}`。
- 权威终态仅为`STOP_M3_3_REVIEW_CONTRACT`，不能表述为候选经济通过或拒绝。剩余7份不得续跑，
  不改提示、不替换候选、不用剩余额度回救；M3-4验证/G1不获授权。
- 实际1次HTTP 200完成响应，估算费用`$0.00320073`，低于`$0.25`硬上限。断网无密钥双复核均为
  幂等复用和0外部调用，主控未查看叙事；封存验证、压力、G1、模型、回测、持仓和生产均未读未跑。
- scheduler保持原容器/原镜像且healthy。证据见
  `docs/M3_MULTI_POOL_FACTOR_REVIEW_ACCEPTANCE_20260802.md`与
  `config/m3_multi_pool_factor_review_manifest_v1.json`。

## 2026-08-02 · M3-3机械Top2独立审查预执行门GO，真实审查未授权

- 固定M3-2序号3/4两条原式，每条按构造与量纲、经济方向与三池一致性、PIT/数值稳定性、冗余与
  可证伪性四角色审查，共恰好8份未来响应；不可改式、递补或追加发现候选。
- 主控已见部分发现期状态与一条候选排序信息，永久退出经济裁决；未来请求禁止发现RankIC、覆盖、
  排名、证券清单、行情行及任何封存结果，唯一审查权来自固定的结果盲委员会。
- schema通过后仍必须逐字段通过既有自由文本语义门；任何暗改算子/窗口/方向、不同DSL、业绩/准入
  声称或含糊改式语言均计数并整批停止，不补发，直接吸收D1-3A与M1-2失败经验。
- 结果前协议提交`7649c26`、预执行实现提交`9f2c33e`均已先行推送；断网只读镜像连续两次返回
  `GO_M3_3_PREEXECUTION_ONLY`，固定8请求bundle与代码快照同哈希，provider调用0、密钥读取false、
  发现指标字段未解析、封存结果未读，两份专属账本均0数据行。全仓`482 passed`。
- 当前`execution_authorized=false`；真实DeepSeek调用须按固定两条公式、非权威摘要、三池定义与四角色
  问题、恰好8次和`$0.25`上限另获明确授权，并另立不可变live release。验证/G1/模型/回测/信号/
  生产继续封存。见`docs/M3_MULTI_POOL_FACTOR_REVIEW_PROTOCOL_20260802.md`与
  `docs/M3_MULTI_POOL_FACTOR_REVIEW_PREEXECUTION_ACCEPTANCE_20260802.md`。

## 2026-08-02 · M3-2三自建池真实价量发现批GO，机械Top2已锁定

- 在任何真实候选产生前补足M3-1未逐项绑定的复权链与PIT行业物理输入：断网只读Docker复算321只
  历史证券、474个发现交易日、73,839条PIT暴露，六类源批次集合和市场变换代码均已哈希冻结；输入
  快照为`90a8d377…f1193`，`.BJ=0`、provider调用0、密钥读取false。
- 结果前release先行推送后，唯一一次live批完成24/24个`deepseek-v4-pro`响应：15条完成发现评价，
  3条重复AST、1条沙箱拒绝、5条语义合同拒绝；失败全部计N且不补位，相关域终态`N=270`。
- 三池共有8条发现期合格候选；同一规范AST在全市场/中盘/小盘保持同定义，方向只由全市场冻结。
  24次全部完成后按预注册顺序机械锁定序号3和4为Top2，没有人工挑选或看结果调门槛。
- 实际估算费用`0.053605862 USD`，通过`0.50 USD`批次硬熔断。断网、无密钥、证据只读复跑返回
  `idempotent_reuse=true / external_api_calls_this_run=0`，五项核心证据哈希前后不变。
- 2023—2025、压力期、G1、模型、组合、信号和生产均未读取或运行；策略仍`NOT_EVALUATED`、生产
  授权none，scheduler原容器/原镜像保持healthy。终版见
  `docs/M3_MULTI_POOL_FACTOR_DISCOVERY_ACCEPTANCE_20260802.md`与
  `config/m3_multi_pool_factor_discovery_manifest_v1.json`。

## 2026-08-02 · M3-1三自建池价量因子研究预执行门GO

- 结果前协议提交`f37ed4a`、实现提交`f271376a`均已先行推送；断网只读预执行验证M3-0三池
  779,271行真身、发现期474日和封存期727日边界，`.BJ=0`，没有读取任何真实或封存因子结果。
- 纯fixture覆盖自由文本语义门、受限DSL、PIT/shift、全市场方向锚定、子池不得翻向、三池同定义
  评价和机械Top2；未来24个完成响应对应72个评价单元，相关域多重检验N仍固定为270。
- 正式离线双跑报告哈希同为`490552c3…abb4b`；`provider_calls=0`、`api_key_read=false`、真实候选0、
  模型/组合未运行。M3专项15 PASS、Docker全仓458 PASS，镜像`sha256:83e5da58…62c30`。
- 一次未注入release Git身份的临时镜像在`git_head()`处按设计失败；显式绑定`f271376a`重建后通过，
  未静默伪造身份。生产scheduler仍为原容器/原镜像且healthy、未重启。
- 权威裁决仅为`GO_M3_1_PREEXECUTION_ONLY`，策略仍`NOT_EVALUATED`、生产授权none。下一步如继续，
  须另立M3-2 live release，显式授权24次DeepSeek响应和0.50 USD熔断；本阶段不授权API调用。
  见`docs/M3_MULTI_POOL_FACTOR_PREEXECUTION_ACCEPTANCE_20260802.md`。

## 2026-08-02 · M3-1三自建池价量因子研究协议已结果前冻结

- 基于M3-0三个`CUSTOM_RULE_BASED`池，发现期固定为2021-01-04至2022-12-15（474日），末条
  10日标签于2022-12-30成熟；2023—2025共727日整体封存，2026年至7月另作封存压力/近期证据。
- 同一规范AST必须在全市场、中盘和小盘保持完全相同定义；方向只由全市场发现期冻结，子池不得
  各自翻向。覆盖、有效IC日、跨池最弱RankIC、六个半年窗、成本、容量和压力门均已在结果前固定。
- 多重检验不重置：既有GP 166次、D1 40次、M1 40次合计246次均登记为相关价量发现尝试；未来新批
  只允许24个完成响应，完成后有效`N=270`。三个评价单元仍只算一次生成尝试，失败/重复/语义拒绝
  都计N且不补位。
- 未来DeepSeek批按官方当前价格测得最坏`$0.33408`，硬熔断`$0.50`；但本协议不授权API调用。
  当前只允许实现断网纯fixture预执行门，不读取真实因子或封存结果，不运行模型/组合/G1/信号，
  策略仍`NOT_EVALUATED`、生产授权none。见
  `docs/M3_MULTI_POOL_FACTOR_PREEXECUTION_PROTOCOL_20260802.md`与
  `config/m3_multi_pool_factor_research_v1.yaml`。

## 2026-08-02 · M3-0科创板规则型PIT研究池数据与规则门GO

- 结果前提交 `b454345`/`9194742` 冻结三个 `CUSTOM_RULE_BASED` 池的月末形成/次日生效、上市满
  12个月、ST/退市硬退出、60日流动性、20日市值、确定性三等分、结构门和源新鲜度；不得冒充
  科创100、科创200或官方“科创300”。受控实现提交 `414f060` 先于真实运行。
- Docker仅刷新615只冻结科创板证券的`namechange`，新增615批/681行，账本没有其他API；615/615
  新鲜度PASS。科创身份三重校验差异0；`daily`/`daily_basic`各710,806行，重复0、同日正市值覆盖
  100%、`.BJ=0`。
- 数据与规则门权威 `GO_CUSTOM_PIT_DATA_RULE_GATE_ONLY`：首个可用日2021-01-04，此后67个连续
  形成月PASS；全市场64–577只，中盘/小盘各21–192只。逐日真身779,271行/1,351日/588只，重复、
  未来生效、子池交叠/越界和`.BJ`均为0；终端复跑及独立Docker复核哈希一致。
- 结论仅允许另立M3-1结果前因子协议；没有调用DeepSeek、计算因子或效果、运行qlib/模型/回测/
  信号，策略仍`NOT_EVALUATED`，生产授权none。证据见
  `docs/M3_STAR_CUSTOM_PIT_ACCEPTANCE_20260802.md`。

## 2026-08-02 · M2-0科创200官方PIT数据门权威NO-GO

- 首批200只、V1.0/V1.1规则谱系和2024-08-20至2026-07-31指数日线471/471全部PASS；27个
  Tushare冻结分区即时双查一致，修订差异0，`.BJ=0`。
- 24个月度门只返回23期共4,600行，2026-07为0行；更关键的是官方归档4页、12个候选页面和13个
  附件均没有可解析的科创200历史调入/调出成员对，事件为0。二级集合有9个变化区间，23个月中仅
  首月与首批集合精确一致，不能用月末集合反推官方PIT历史。
- 首轮候选谓词漏纳入“临时调整”标题，按先冻结恢复单、再修复的顺序纠正；原报告永久保留并降级为
  provisional。恢复后发现覆盖复跑仍无成员对，权威终态为`NO_GO_M2_STAR200_DATA_GATE`。
- 本结论只阻断官方PIT数据门；没有运行DeepSeek、因子、G1、qlib、模型、回测或信号，科创200策略
  仍`NOT_EVALUATED`、生产授权`none`。见
  `docs/M2_STAR200_DATA_FEASIBILITY_ACCEPTANCE_20260802.md`。

## 2026-08-01 · M2-0科创200数据门协议已结果前冻结

- 下一主线从已停止的M1-2科创50审查批切换到独立的科创200官方数据门；目标固定为000699.SH的
  首批200只、V1.0/V1.1规则谱系、2024-08-20以来官方调入/调出事件、指数日线和24个月度二级集合。
- 本阶段只裁定官方历史成员PIT能否构造；DeepSeek、因子、G1、qlib、模型、回测、信号、模拟账户和
  生产接入均未授权。任何官方成员对或二级集合结果只能在协议提交并推送后读取。
- 协议要求官方一手成员谱系为主真身，Tushare仅作指数日线与月度集合交叉核验；任一必需门不闭合即
  `NO_GO_M2_STAR200_DATA_GATE`，不得用当前成分、ETF PCF或月末集合补造。见
  `docs/M2_STAR200_DATA_FEASIBILITY_PROTOCOL_20260801.md`与`config/m2_star200_v1.yaml`。

## 2026-08-02 · M2-0首轮归档发现覆盖缺陷，终局裁决暂缓

- 首轮官方/Tushare采集后，独立集合对账发现2026-04至05有1对变化，但实现的公告候选谓词遗漏仅含
  “临时调整”的标题，与原协议“定期与临时全部扫描”冲突；这是工程漏扫，不是新研究口径。
- 首轮发现、质量报告和manifest永久保留，但首轮NO-GO降级为
  `PROVISIONAL_INVALID_DISCOVERY_COVERAGE`，不得作为终局结论。27个原始批次和账本不重采不改写。
- 恢复只允许补入临时调整标题，使用新发现哈希、新质量报告和新manifest；协议、来源、成员数、日期、
  24个月门和禁止项不变。见`docs/M2_STAR200_DISCOVERY_RECOVERY_20260802.md`。

## 2026-08-01 · M1-2审查合同失败并权威停止，不进入验证/G1

- 用户明确批准本批DeepSeek外发后，固定批次在第1/8份响应按预注册规则终止：schema PASS，但
  自由文本语义门为`FAIL_SEMANTIC_CONTRACT`，原因码`AMBIGUOUS_CHANGE_LANGUAGE`与
  `DIFFERENT_DSL_EXPRESSION`；该响应计数，不补发、不改提示、不递补。
- 响应虽自报`BLOCKER_FOUND`并含1个critical/1个major finding，但因语义合同无效而没有候选裁决
  权；`candidate_decisions={}`，不能表述为某条因子已被权威经济拒绝。权威终态仅为
  `STOP_M1_2_REVIEW_CONTRACT`，策略仍`NOT_EVALUATED`。
- 实际1次provider调用、1个HTTP 200完成响应、费用`$0.00207321`；无密钥重放外部调用0，5文件证据
  树与review/transport账本三哈希前后不变。封存验证、压力、G1、模型、组合、前瞻和生产均未读未跑。
- 两项请求前基础设施缺陷均以零调用恢复附录先行留痕后最小修复；最终scheduler仍为原容器、原镜像
  且healthy。M1-3验证/G1协议不获授权；不得续跑余下7份或用剩余额度回救。证据见
  `docs/M1_STAR50_FACTOR_REVIEW_ACCEPTANCE_20260801.md`与
  `config/m1_star50_factor_review_manifest_v1.json`。

## 2026-08-01 · M1-2结果盲独立审查执行前门GO

- M1-2工程已拆为5个不超过400行的职责模块，专属review/transport账本、严格JSON+自由文本语义门、
  费用预留和一次性只读Docker入口完成；宿主全仓433 PASS，最终镜像专项20 PASS。
- 断网预检固定2个候选、8个角色请求，`provider_calls=0`、发现指标与封存验证均未读；请求束哈希为
  `4fda6297...f0557`。二次恢复后终版镜像`sha256:15704c6a...04553`绑定实现提交
  `79e20964...cea3f`和代码快照`5d38f231...40da5`。
- 首个镜像因外部传入的完整Git值与实际HEAD不一致而在放行前作废；零API调用。两次过窄测试调用
  只因缺必要只读夹具失败，完整夹具下20/20 PASS，均未扩大live权限。
- 首次live又在首个请求前暴露AlphaGen解析器只读挂载遗漏；账本/输出/调用均为0。恢复附录先行
  推送后仅补该只读挂载和回归测试，协议、请求、候选与预算不变。
- 用户明确批准DeepSeek外发后，live在首请求前又因release覆盖镜像受控`config/`而拒绝；第二份
  零调用附录先行推送后只把release迁到只读`/opt/shaiwei/`并补门禁。仍为0账本行、0输出、0调用、
  0费用，研究协议和载荷未改变。
- 执行release已冻结为仅8次DeepSeek结果盲审查、0.25 USD硬上限；仍不读2023—2025验证、不运行
  压力/G1/模型/组合/前瞻/生产。release提交推送且工作树干净后才可执行，见
  `docs/M1_STAR50_FACTOR_REVIEW_PREEXECUTION_ACCEPTANCE_20260801.md`。

## 2026-08-01 · M1-2科创50机械Top2独立审查协议已结果前冻结

- M1-1终版40/40响应和机械Top2保持不变；M1-2只审查固定两式的经济构造、方向、PIT/次日开盘、
  数值稳定性、冗余与可证伪性，不修式、不递补、不读取2023—2025封存验证窗、不运行压力/G1/
  模型/组合，也不接Web、前瞻或生产。
- 协议冻结前主窗口筛选账本行时误见两式的发现期RankIC和覆盖率；未见封存验证或G1结果。污染字段
  不进入提示或Git摘要，主窗口永久退出本批经济裁决；唯一审查权收窄为不接收任何发现/后续指标的
  固定DeepSeek四角色×两候选结果盲委员会。
- 8份响应必须同时通过严格schema与既有自由文本语义门；含公式/窗口/估计量修改、变体建议、业绩/
  准入声称或模糊文本即计数并整批STOP，不补发。单候选四角色均无major/critical阻断才只允许另立
  M1-3验证协议；否则按原式拒绝且不递补第3名。
- 专项调用硬上限冻结为`$0.25`，真实调用前仍须完成独立模块、断网fixture、不可变镜像和执行release
  的提交推送。本节为零调用协议冻结，`strategy_effective=NOT_EVALUATED`、生产授权`none`。见
  `docs/M1_STAR50_FACTOR_REVIEW_PROTOCOL_20260801.md`与
  `config/m1_star50_factor_review_v1.yaml`。

## 2026-08-01 · M1-1科创50新价量因子发现协议已结果前冻结

- 用户指令继续M1主线后，先冻结独立研究家族`m1-star50-price-volume-v1`；本批只在官方PIT科创50
  上发现受限OHLCV/VWAP因子，不调整或重跑已REJECT的P2 Alpha158/LightGBM/Top10基线。
- 发现信号日固定为2020-08-03至2022-12-15，末条10交易日标签于2022-12-30成熟；2023-01-03至
  2025-12-31整体封存，当前禁止读取候选在该区间的IC、收益、压力、G1或组合效果。
- 生成预算冻结为五主题各8次、共40个DeepSeek完成响应，串行且本批硬上限`$1`；空/截断、重复、
  语法、沙箱及语义失败均计家族N，不补位。正文与唯一DSL不一致、建议变体、声称业绩或触及封存期
  均在候选有效前fail closed。
- 协议远端留痕后已完成零调用工程实现：候选语义门、发布/输入合同、科创50发现评价和批次编排拆为
  四个独立模块，最大300行；旧控制面只增加可选语义钩子。专用attempt/transport空账本、断网预检和
  一次性live Docker profile已加入，宿主专项64 PASS、全仓416 PASS，Ruff/compileall/pip/Compose
  均PASS。尚未构建最终镜像、创建执行release、调用API、读取候选结果或写入任何M1账本行；必须先将
  本工程提交推送并完成断网Docker门，才可另立执行release。
- 策略有效性仍为`NOT_EVALUATED`、生产授权为`none`。详见
  `docs/M1_STAR50_FACTOR_DISCOVERY_PROTOCOL_20260801.md`与
  `config/m1_star50_factor_research_v1.yaml`。

## 2026-08-01 · M1-0多股票池因子研究底座GO

- 用户确认筛微不能长期停留在中证800单股票池/单策略，需要把等待前瞻数据的时间用于科创50、
  科创100、科创200及规则型科创板股票池的因子研究；当前先建设机器可校验的多股票池底座。
- 结果前协议已以`5730259`先行推送；严格注册表登记中证800、科创50/100/200、科创综指和三类
  自建科创板PIT研究池。中证800保持唯一既有生产池；仅中证800与科创50可另立新因子协议，其余
  股票池在官方谱系、数据或规则门通过前机器拒绝进入因子评价。
- 因子身份与股票池分离，跨池评价键强制包含股票池、基准、标签、期限、中性化、窗口、成本和裁判
  版本；准入按股票池独立裁决，生成尝试与评价单元分开记数。自建池不能声明官方代码或使用“指数”
  名称，`.BJ`在全部身份中固定禁止。
- 首次Docker复核发现集合序列化顺序导致宿主/容器哈希不一致，未提交即改为规范排序；终版宿主与
  断网只读Docker双跑均为`acece635...a927f`。专项各17 PASS、全仓402 PASS，Ruff、compileall、
  依赖与Compose均PASS。
- 本目标没有调用DeepSeek、读取新因子结果、运行G1/qlib/模型/回测或写账本。生产scheduler仍为
  原容器`fd8e9615...a5adbb`、原镜像`de87ec74...0261`且healthy，Top20候选和8月3日守护未触碰。
  机器裁决`GO_MULTI_UNIVERSE_FOUNDATION_ONLY`；M1-1只能另立科创50新因子结果前协议。见
  `docs/M1_MULTI_UNIVERSE_FOUNDATION_PROTOCOL_20260801.md`与
  `docs/M1_MULTI_UNIVERSE_FOUNDATION_ACCEPTANCE_20260801.md`。

## 2026-08-01 · Web页面模块化第二阶段GO，因子/实验页完成结构治理

- 结果前协议已先以`2873bdf`推送；因子页入口由952行收窄至23行，实验页入口由861行收窄至21行，
  路由入口不再直接依赖React Query、图表或业务API。目录、详情、比较/历史和展示原语已按领域拆分，
  新增模块最大332行，全部低于600行棘轮，且因子/实验领域间禁止交叉导入。
- HTTP契约、查询参数、页面文案、ARIA、CSS类名、图表口径和既有E2E均未改变；前端单元25 PASS、
  五视口fixture 64 PASS/11预期skip、全仓385 PASS，Ruff、compileall、依赖、账本和脱敏检查均PASS。
- 隔离Web已以镜像`sha256:523c85c...bbe8`重建，`web-query`与`web-ui`均healthy；真实浏览器核验
  七个只读主页面及因子/实验详情在390px无横向溢出、控制台零warning/error。生产scheduler仍为原
  镜像`de87ec74...0261`，创建周期和healthy状态不变，8月3日Top20单次守护未触碰。
- 机器裁决为`GO_WEB_PAGE_MODULARIZATION_ONLY`：只证明结构可维护性改善，不增加页面、研究、策略
  或生产授权。见`docs/WEB_PAGE_MODULARIZATION_PROTOCOL_20260801.md`与
  `docs/WEB_PAGE_MODULARIZATION_ACCEPTANCE_20260801.md`。

## 2026-08-01 · Top20发布守护v2工程GO，8月3日单次任务已安排

- v1未触发事实和原协议永久保留；v2只把目标日改为20260803、最新旧Top30锚点改为20260731，并
  要求删除旧Codex任务`top20`后从本周六新建“下一周一16:05、仅一次”的任务。候选/旧生产镜像、
  16:05—19:00窗口和所有fail-closed门不变。
- 本地官方日历冻结前已确认20260803开市；16:05计划为watermark`20260731`、唯一缺口`20260803`。
  运行时仍须实时重算，任何新PASS、漂移、多日积压、脏树、远端不同步或容器异常均BLOCKED。
- v2最小实现已完成：CLI默认路径指向v2，guard ID仅接受严格日期格式且必须与目标日一致；v1 fixture
  保留。专项本机/Docker各32 PASS，全仓384 PASS，Ruff、compile、依赖、账本追加约束与脱敏均PASS；
  周末真实CLI按设计在Docker前BLOCKED，生产scheduler仍为原镜像且healthy。
- 实现提交`2964ef4`推送并恢复干净同步后，以8月3日16:05时钟注入和真实其余依赖执行完整只读门，
  返回`READY`、`start_invoked=false`、唯一新交易日`20260803`；候选、旧scheduler、发布审计、Git
  与最新Top30`20260731`锚点全部精确匹配，生产未启动或重启。
- 未触发的旧Codex任务`top20`已删除；新一次性任务`top20-8-3`已从本周六指向下周一16:05创建，
  只允许运行一次冻结守护，BLOCKED/失败不重试、不修复，成功后只确认scheduler状态。任务创建不是
  切换完成；8月3日仍须以`START_PASS`、实际容器身份和随后自然整日链路验收为准。协议与终版验收见
  `docs/PAPER_TOP20_RELEASE_GUARD_V2_PROTOCOL_20260801.md`、
  `docs/PAPER_TOP20_RELEASE_GUARD_V2_ENGINEERING_ACCEPTANCE_20260801.md`。

## 2026-08-01 · 7月30—31日前瞻PASS，Top20自动切换未触发

- 两个交易日日增量均PASS：20260730为5批/15,622行/快照`46303e53...e608`，20260731为
  5批/15,619行/快照`b95c06ba...8201`；两日16个实际原始批次共42,315个代码行，逐文件`.BJ=0`。
- 两日S1—S9、影子、次日开盘对账、信号和Top30模拟仓均PASS，S10均NOT_APPLICABLE；Top30独立
  回放与机器验收PASS，累计7个自然FORWARD日，最新净资产458,940.90元。
- 7月30日飞书4次网络超时尝试均在原有有界重试内以稳定消息ID恢复，7月31日7个事件均首次PASS；
  通知保留WARN历史，不推翻核心PASS。
- Top20一次性自动切换未发生：发布审计仍为22条且计划时点后无`START_PASS`，实际scheduler仍为
  旧镜像`de87ec74...0261`并healthy。Top20重放PASS但仍仅6日BACKFILL、0日FORWARD、`NOT_READY`。
- 仓库证据只能裁定`AUTOMATION_DISPATCH_NOT_OBSERVED`；没有守护命令输出或发布记录，Codex应用侧
  未派发的具体原因`NOT_EVALUATED`，不得猜成守护日期/Git/Docker门失败。恢复须另立20260803 v2
  协议，不改写原20260730协议。详见`docs/P05_FORWARD_CONTINUITY_20260731.md`。

## 2026-07-29 · Top20单次发布守护工程GO，明日自动执行已安排

- 结果前协议已先以`c619697`推送；新增独立342行`shaiwei.release_guard`，只在2026-07-30
  16:05—19:00 UTC+8、干净且已同步Git、发布链/候选/旧容器/最新Top30/FORWARD/readiness逐项精确
  PASS时调用一次既有`start_current()`。默认入口只检查，生产CLI没有时间覆盖参数。
- 30个release/guard fixture覆盖日期/时窗、候选/容器/账本漂移、多交易日积压、所有阻断零启动、
  唯一一次启动和已激活幂等；全仓382 PASS，Docker专项30 PASS，Ruff/compile/diff-check通过。
- 真实定向复核曾发现Docker format分隔符兼容问题，守护在变更前BLOCKED；改用明确分隔后候选、
  22条发布审计链和旧scheduler身份复核PASS。生产仍为原容器`fd8e9615...adbb`、原镜像
  `de87ec74...0261`且healthy，未启动或重启。
- 真实Git/候选/旧容器/账本配合明日时钟的整门演练返回`READY`且`start_invoked=false`。Codex本机
  一次性自动任务`top20`已安排在2026-07-30 16:05 UTC+8，只允许运行冻结守护入口一次；BLOCKED
  不重试、不修复。启动成功不等于Top20前瞻PASS，晚间仍须另验整日链路。验收见
  `docs/PAPER_TOP20_RELEASE_GUARD_ENGINEERING_ACCEPTANCE_20260729.md`。

## 2026-07-29 · Top20单次发布守护协议已冻结，尚未施工

- 为解决连续两日人工通知晚于原scheduler完成时点的问题，已冻结
  `paper-top20-release-guard-20260730`：仅允许2026-07-30 16:05—19:00 UTC+8，在本地官方日历
  唯一新交易日、旧Top30最新执行日仍为20260729、候选/发布指针/运行容器身份精确一致时调用一次
  既有`start_current()`。
- 候选固定为`shaiwei:scheduler-4e5244b6b02739dd`；不build、不promote、不手工跑批、不自动回滚，
  任何身份、日期、工作树、远端同步、健康或readiness异常都必须在Docker变更前fail closed。
- 本节只记录结果前协议冻结；守护代码、fixture、Docker验收和下一交易日自动执行安排尚未完成，
  不得据此宣称生产切换已就绪。协议见`docs/PAPER_TOP20_RELEASE_GUARD_PROTOCOL_20260729.md`。

## 2026-07-29 · 今日跑批PASS，Top20切换继续等待下一安全窗口

- 原生产scheduler完成20260729日增量PASS：5个正式市场批次、15,611行、数据快照
  `a9041e56...083`；当日8个实际不可变原始批次共21,147个带代码数据行，逐文件复核`.BJ=0`。
- 影子S1—S9全部PASS、S10为预期的NOT_APPLICABLE；`20260728→20260729`次日开盘对账PASS，
  30个目标、无订单/成交、平均绝对开盘偏差0.6459%、预计成本0。20260729信号在原生产代码快照
  `eb8e7521...7fbd`下生成，信号日无需调仓。
- Top30模拟仓机器验收与独立回放PASS，累计5个自然FORWARD观察日；当前净资产465,560.29元、
  归一化NAV 0.93112058、基准NAV 0.97748743。日增量、影子对账/信号、模拟仓共7条飞书通知均
  第一次投递成功；scheduler保持原镜像`sha256:de87ec74...0261`且healthy。
- 用户再次在整日跑批完成后通知主控。最新Top30执行日已经等于最新日增量日20260729，Top20候选
  跨快照readiness继续正确返回`BLOCKED_FAIL_CLOSED`；本次未强切、未覆盖当日FORWARD产物，也未
  重启或修改生产容器。
- 下一安全窗口为下一个合格交易日产生可用资格后、原scheduler完成该日Top30前；届时仍先启动已
  提升的Top20候选`shaiwei:scheduler-4e5244b6b02739dd`，Top20首次自然运行验收通过后，16:00早探测
  候选再于后续独立交易日切换。

## 2026-07-28 · 今日跑批PASS，Top20切换窗口已关闭

- 原生产scheduler完成20260728日增量PASS：5个市场批次、15,613行、数据快照
  `6d811d8b...d6a`；影子次日开盘对账、S1—S9、信号和Top30模拟仓均PASS，新增账本差异中`.BJ=0`。
- 20260728信号按原生产代码快照 `eb8e7521...7fbd` 生成；Top30完成 `20260727→20260728`，独立重放
  PASS，当前累计4个自然FORWARD观察日。生产容器内验收PASS，飞书日增量开始/完成、影子对账/信号
  开始/完成、模拟仓开始/完成均一次投递成功。
- 用户在整日跑批完成后通知主控。此时最新Top30执行日已经等于最新日增量日20260728，已提升Top20
  候选跨快照readiness正确返回 `BLOCKED_FAIL_CLOSED`；没有更新的合格交易日，禁止事后强切、覆盖
  当日FORWARD产物或回写代码身份。本次未重启、未promote、未tag或修改生产容器。
- 下一安全窗口为20260729进入早探测资格后、原scheduler完成当日Top30前；届时先启动已提升的Top20
  候选 `shaiwei:scheduler-4e5244b6b02739dd`，让其按原19:30口径首次串行运行Top30/Top20。16:00早探测
  候选 `shaiwei:scheduler-0963ed74efef91f9` 继续不提升，待Top20首发独立验收后再另日切换。
- 本机HEAD包含未上线早探测代码，因此本机直接跑旧FORWARD验收会按设计报快照不一致；原生产容器
  内同一验收PASS。这是发布隔离证据，不是今日生产故障。

## 2026-07-28 · 日增量16:00早探测工程门 GO，待独立生产切换

- 用户要求将每日跑批从19:30提前到16:00。Tushare官方口径显示A股日线通常15:00—16:00入库，
  但 `daily_basic` 为15:00—17:00，股票/指数行情总口径也是15:00—17:00；因此16:00不能直接定义
  为“数据必齐”的正式接纳时点。
- `p0-daily-early-readiness-v1` 冻结为：16:00起每15分钟对当日五类正式输入做无写入探测，全部通过
  原完整性门后立即进入原跑批；探测不写raw/ledger、不发失败告警。19:30仍为硬兜底，届时未就绪
  按原流程正式尝试并fail closed告警。
- 不改数据源、字段、行数门、`.BJ`排除、S1—S10、模型、信号、模拟仓或飞书完成语义；历史补采
  不等待探测。代码已复用正式Tushare响应规范化和 `validate_trade_date` 门，未另造宽松口径。
- 相关测试40 PASS、全仓361 PASS，Ruff、compile和diff-check通过；fixture确认来源未齐时状态为
  `WAITING_SOURCE`，Parquet/账本/通知均为0，19:30边界恢复原正式路径；新增生产文件仍低于600行。
- 工程结论仅为 `GO_EARLY_READINESS_ENGINEERING_ONLY`。协议见
  `docs/DAILY_EARLY_READINESS_PROTOCOL_20260728.md`；候选镜像
  `shaiwei:scheduler-0963ed74efef91f9` / `sha256:0a5a64d4...f273` 已构建，断网、只读根、零capabilities
  Docker专项40 PASS。验收见 `docs/DAILY_EARLY_READINESS_ENGINEERING_ACCEPTANCE_20260728.md`。
- 首次异步构建仍在后台完成时又启动一次同身份构建，追加链因此永久保留两条内容完全相同的
  `BUILD_PASS`，各自record哈希不同但镜像/代码/Git身份一致；22条release审计链终验PASS，未提升候选、
  未改生产指针。该操作错误不包装为幂等单次，后续长构建必须持续轮询同一session而不重复发起。
- 当前已提升但未启动的Top20候选镜像保持原样；早探测不得与Top20首次生产切换合并为同一发布变量。

## 2026-07-28 · 本地 Mac 双出口网络路径已固化

- 当前已验证基线保持不变：Codex、GitHub和海外网页经 macOS 系统代理进入 Clash 海外节点；生产
  scheduler/国内采集容器显式清空应用代理，并通过 Docker Desktop bypass 与 `NO_PROXY` 从本地 ISP
  直连 Tushare、Sina、Eastmoney、Baostock。无需修改 Mac 公网地址，也无需为了采集关闭 Clash。
- Docker 镜像拉取继续使用 Docker Desktop → Clash 海外路径；镜像仓库不得加入国内 bypass。宿主机
  临时国内采集只允许进程级直连，禁止通过反复切换 Clash 全局状态影响 Codex 和常驻服务。
- 未来海外数据采集必须使用独立一次性进程或 `research-overseas` Docker profile 显式代理，不得把
  代理重新注入 scheduler、复用生产服务或让国内/海外源在同一常驻容器内争夺网络口径；该 profile
  当前仅为架构边界，尚未施工。
- 2026-07-28 脱敏 `docker-network-check` 实测 Tushare交易日历8行、461ms、三类代理变量均未设置、
  `tushare_no_proxy=true`，确认当前国内容器直连路径有效；检查未写数据或账本。
- 拓扑、流量矩阵、诊断顺序和安全边界见 `docs/LOCAL_MAC_NETWORK_ROUTING.md`。本次只整理文档，
  未修改 Clash、macOS、Docker Desktop、Compose或运行中容器。

## 2026-07-27 · Web 模块化治理第一阶段 GO_MODULARIZATION_ONLY

- 用户确认总量可能达到10万行，并授权当前适合时拆分 Web。`p3-web-modularization-v1` 已严格按
  结果前协议完成，只治理 `query.py`、前端 `validation.ts` 与 `styles.css` 三个最高风险热点；无功能、
  HTTP/JSON 契约、错误码、页面文案、CSS 规则、视觉顺序或生产授权变化。
- 后端1,548行查询单体已拆为474行门面与495/410/244行三个领域模块；前端1,484行校验单体已拆为
  21行门面与454/380/255/244/244行五个领域模块；3,925行样式单体已拆为10行门面与10个不超过
  577行的顺序片段。新增结构闸测试强制本批模块不超过600行并禁止查询层反向依赖配置/API。
- 同一 `as_of` 下14个真实只读API响应重构前后SHA-256逐项一致；生产CSS两份产物名称和SHA-256
  逐项一致。全仓357 PASS、前端单元25 PASS，Ruff、TypeScript、生产构建、Compose和diff-check
  全部通过；`web-query`/`web-ui` healthy。
- scheduler 仍为原容器、原镜像 `de87ec74...0261`、原创建时间且 healthy，未重启。第一阶段不拆
  `operations.py`、`research_projection.py`、`FactorsPage.tsx` 和 `ExperimentsPage.tsx`；它们保留为
  后续独立目标候选，不因本次成功立即扩大重构面。
- 协议与验收见 `docs/WEB_MODULARIZATION_PROTOCOL_20260727.md`、
  `docs/WEB_MODULARIZATION_ACCEPTANCE_20260727.md`。

## 2026-07-27 · Web 模拟仓中文简称展示 GO_LOCAL_READ_ONLY

- `p3-web-security-names-v1` 已把模拟组合实际持仓首列升级为“中文简称 / 代码”；代码继续保留为审计
  标识，名称不参与模型、信号、排序、估值、交易或判决。
- 一次性断网投影器以已登记 `tushare.namechange` 为 PIT 主源、`stock_basic` 当前简称为显式 WARN
  兜底，生成内容寻址 bundle；常驻 Web 只读挂载投影，不读取 raw Parquet、`.env` 或外网。
- 真实源为13,448条名称历史/5,428只证券、5,535只基础简称；1条 `T600018.SH` 交易所测试证券排除并
  计数，其他未知格式仍 fail closed。bundle `9651c35b...fc75` 两遍哈希一致。
- 真实 Web API：Top30 最新账户日22/22、Top20最新账户日18/18均由 PIT 历史名称覆盖，fallback=0、
  missing=0、`.BJ=0`；两账户合计40个持仓行、24只不同证券。
- 全仓355 PASS、前端单元25 PASS、TypeScript/生产构建和真实本机API/静态分块核验通过；Web 镜像
  `sha256:0998e8ea...59e8a`，`web-query`/`web-ui` 均 healthy。scheduler 仍为 `fd8e96152b53`、
  原镜像、原创建时间且 healthy，未重启。
- 协议与验收见 `docs/WEB_SECURITY_NAMES_PROTOCOL_20260727.md`、
  `docs/WEB_SECURITY_NAMES_ACCEPTANCE_20260727.md`。

## 2026-07-27 · Top20 模拟账户已获生产调度授权，受控切换待机器门

- 用户知悉 2026-07-26 完整 Docker 元数据工具输出曾包含环境变量，并接受继续使用现有 Tushare/
  飞书凭据的剩余风险；凭据轮换不再是 Top20 发布硬阻断。该裁决不改变凭据仅存 `.env`、不入 Git/
  日志/文档以及禁止完整容器元数据/环境变量输出的边界。
- `paper-top20-scheduler-v1` 只授权 `model_top20` 模拟账户随 scheduler 串行日更，绑定冻结
  `paper-top20-v1.2` 哈希；无券商连接，策略有效性继续 `NOT_EVALUATED`，Top30 仍先运行且历史不变。
- 2026-07-27 原 scheduler 已完成日增量、S1—S9、影子、Top30 前瞻第3日、重放与飞书开始/完成，
  重复轮询为 NOOP。候选镜像可构建，但跨快照切换必须由新交易日 readiness 裁决；不为立即重启绕过
  门禁。授权见 `docs/PAPER_TOP20_RELEASE_AUTHORIZATION_20260727.md`。

## 2026-07-27 · Web 模拟组合双账户切换 GO_LOCAL_READ_ONLY_REVIEW

- `p3-web-paper-accounts-v1` 固定 `model_baseline` 为默认“主账户 · Top30”，并只新增
  `model_top20`“比较账户 · Top20”这一项严格枚举；总览和股票池/信号页继续使用主账户口径。
- 接入前审计确认两账户各一个身份、各6个唯一且同日账户日、不可变产物哈希与事件链闭合、`.BJ=0`，
  两账户独立重放均 PASS。
- Top30 当前为4日 BACKFILL + 2日 FORWARD，Top20为6日 BACKFILL + 0日 FORWARD；因此本目标
  只授权账户切换和各自证据查看，禁止同图收益比较、策略优劣和有效性结论。Top20 必须明确显示仅工程
  回放、自然前瞻未就绪、生产自动日更未启用。
- 四个模拟组合端点已增加严格 `account_id` 枚举并把账户身份绑定进 snapshot；未知账户 HTTP 422，
  默认调用仍为 Top30。零前瞻返回无锚点/无最新值的完整 NOT_READY 空态，不补0或伪造曲线。
- 页面默认 Top30，可切换 Top20；Top20 常驻显示仅工程回放、前瞻0日、生产自动日更未启用和不可比较
  策略优劣。总览与信号页不随局部选择改变。
- 全仓349 PASS、前端单元24 PASS、五视口64 PASS/11 skip、真实桌面/移动14 PASS；终版 Web
  镜像 `fa45aa76...2e0ba7`，两个 Web 容器 healthy。scheduler 仍为原容器 `fd8e96152b53`、原镜像、
  原创建时间并保持 healthy。
- 本节结论只授权本机只读复核；后续生产调度授权已由独立
  `PAPER_TOP20_RELEASE_AUTHORIZATION_20260727.md` 作出，不回写本节 Web 裁决。仍不授权同图绩效
  比较、策略有效性或实盘。协议与验收见 `docs/WEB_PAPER_ACCOUNT_SWITCH_PROTOCOL_20260727.md`、
  `docs/WEB_PAPER_ACCOUNT_SWITCH_ACCEPTANCE_20260727.md`。

## 2026-07-26 · P4-0 科创100数据源PASS、官方历史谱系NO-GO

- 用户确认把拟议“科创300”改为官方科创100，并授权由主控判断是否立即施工；当前生产 scheduler
  使用不可变镜像且 healthy，Web/研究施工与生产隔离，因此裁决现在可启动。
- `p4-star100-data-protocol-v1` 固定指数 `000698.SH`、官方发布日 2023-08-07、最早可能研究可用日
  2023-08-07和截止日2026-07-26。2019-12-31只作为编制方案基日，不授权成员历史前移。
- 官方首批名单100/100、规则V1.0→V1.1谱系、718/718个指数交易日和35/35个月度100只集合均PASS；
  40个Tushare请求即时双查差异0，复跑新增请求0，`.BJ`、重复、未知代码和日线异常均为0。
- 官方归档扫描5页、16个候选页面和17个附件；12期季度调整附件均可解析，但科创100历史调入/调出
  成员对材料为0。Tushare检测到12个集合变化区间只能作为二级诊断，不能补造公告日、生效日和官方
  版本。因此 `official_adjustment_lineage_complete=false`、`pit_constructible=false`，P4-0数据门
  权威NO-GO；这不是策略REJECT，`strategy_effective=NOT_EVALUATED`。
- 当前停止在P4-1前，不构建qlib、特征、模型、IC、收益、回测、排名或信号。恢复须另立协议并取得
  带发布/版本证据的官方历史拟生效/已生效样本；不得用当前成分、ETF PCF或Tushare月末集合绕过。
- 协议与验收见 `docs/P4_STAR100_DATA_FEASIBILITY_PROTOCOL_20260726.md`、
  `docs/P4_STAR100_DATA_FEASIBILITY_ACCEPTANCE_20260726.md`；脱敏来源真身为
  `config/p4_star100_manifest_v1.json`。

## 2026-07-26 · Web 1.1.1 易读与只读交互补正 GO_LOCAL_READ_ONLY_REVIEW

- 七页主视图已默认使用中文业务结论、日期、状态、行动、结果和原因；快照/哈希、模型/Qlib/代码身份、
  英文枚举、批次/运行/消息 ID 与原始错误名移入“查看技术证据”或分节详情，审计与复制能力仍保留。
- 实验目录的哈希式 ID 已改为“实验 1、实验 2……”人类编号；真实桌面/移动 E2E 会逐一核对当前分页
  原 ID 不进入目录正文，同时保留点击类型化详情。拒绝、失效、权威停止、仅发现层等坏消息未弱化。
- 已实现并保留证据抽屉、日期范围、搜索/筛选、严格比较、行详情、分页、通知详情等只读交互；没有增加
  生产重跑、调参、交易、删除、写入或远程能力，也没有修改 API、`src/`、config、compose 或生产证据。
- 前端单元 22 PASS；五视口 fixture 64 PASS/11 intentional skip；真实部署 12 PASS；全仓 339 PASS，
  Ruff、`git diff --check`、CSP、同源、axe、回流和 FCP 均通过。14 张真实截图已更新。
- 仅重建隔离的 `web-query`/`web-ui`，均 healthy；scheduler 仍为原容器 `fd8e96152b53`、原镜像和原创建
  时间，healthy 且未重启。验收见
  `docs/WEB_1_1_1_READABILITY_INTERACTION_ACCEPTANCE_20260726.md`。

## 2026-07-26 · Web 1.1 移动实验目录可读性补正 GO_LOCAL_READ_ONLY_REVIEW

- 390/320px 实验目录已从桌面宽表改为紧凑三列目录，首要信息固定为实验 ID、中文结论和中文权威状态；
  原始英文机器枚举仅保留在 `title`/`aria-label` 与详情页，不再在窄列逐字折行。
- `DISCOVERY_REJECTED`、`INVALIDATED_METHOD`、`AUTHORITATIVE_STOP`、`DISCOVERY_ONLY` 等坏消息仍以
  “发现层拒绝”“方法已失效”“权威停止”“仅发现层”明确展示，没有弱化或改判。
- 真实 390px 实验页由 3,617px 进一步降至 2,740px，单条目录行不超过 72px；320px 与 390px 均无
  页面级横向溢出。前端单元 22 PASS、五视口 fixture 64 PASS/11 intentional skip、真实部署 10 PASS；
  全仓 339 PASS、Ruff 和 `git diff --check` 通过。
- 仅重建隔离的本机 `web-query`/`web-ui`；scheduler 仍为原容器 `fd8e96152b53`、原镜像与原创建时间，
  healthy 且未重启。验收见 `docs/WEB_1_1_MOBILE_EXPERIMENT_CATALOG_FIX_20260726.md`。

## 2026-07-26 · Web 1.1 全面重设计 GO_LOCAL_READ_ONLY_REVIEW

- 现状审计与重设计协议已先以本机提交 `f1b1dbb` 冻结；七类只读页随后完成信息架构、视觉层级、
  金融状态表达、短样本、表格、响应式和无障碍重构。总览首屏按核心运行/证据完整/今日行动/结果成熟度
  四轴分列，当前 2 日 FORWARD 继续 `OBSERVING`，不画趋势、不展示年化、Sharpe 或信息比率。
- `planned_trade_leg_count` 前端统一为“目标变更证券数”，真实执行事实为“已执行订单腿”；因子正式库 0、
  783 条实验记录非 783 个有效模型、WARN/NOT_EVALUATED/失效方法均未被包装弱化。
- 真实 390px 页面高度中，因子目录由 4,110px 降至 1,839px，实验目录由 10,503px 降至 2,740px；
  七页均无页面级横向溢出，320px 等效 400% 总览同样回流通过。
- 前端单元 22 PASS；五视口 fixture 64 PASS/11 intentional skip；真实桌面/移动部署 10 PASS；截图专项
  2 PASS。严格 CSP、同源零外联、axe serious/critical=0、键盘焦点恢复和 FCP 预算均通过。
- 仅显式重建本地 `web-query`/`web-ui`，两者 healthy；未修改后台 `src/`、config、模型、门禁、账本、
  生产数据或调度。scheduler 原容器/镜像/创建时间持续 healthy 且未重启。验收见
  `docs/WEB_1_1_REDESIGN_ACCEPTANCE_20260726.md`；当前仍只授权本机只读复核，不授权远程或生产接入。

## 2026-07-26 · D1 语义合同恢复工程门 GO，旧 D1-3A 继续 STOP

- `d1-review-semantic-gate-v1` 已先于实现以提交 `45734b1` 冻结；实现提交 `8d3ee97` 增加结构字段/
  自由文本一致性、冻结 DSL/回看期、修改建议、业绩/准入声称和模糊文本 fail-closed 门。
- 旧 8 份响应只读双跑稳定复现 5 PASS/3 FAIL，三份失败身份与权威纠错完全一致；provider 调用 0、
  新增费用 `$0`、W1—W6/压力期/G1/前瞻/生产结果均未读取。工程裁决仅为
  `GO_SEMANTIC_GATE_ENGINEERING_ONLY`。
- 终版本机全仓 339 PASS、断网只读 Docker 专项 13 PASS、脱敏/追加约束 18 PASS；scheduler 原容器/
  镜像/创建时间持续 healthy 且未重启。
- 旧批 `STOP_SEMANTIC_CONTRACT_VIOLATION`、两候选未准入及不补发/不递补边界完全不变。未来新批仍须
  用户新指令和结果前协议；工程 GO 不授权 DeepSeek、人工闸、G1 或生产。验收见
  `docs/D1_LLM_FACTOR_SEMANTIC_GATE_ACCEPTANCE_20260726.md`。

## 2026-07-26 · G8-2 管理人 HTTPS 与费率谱系 NO-GO，禁止进入 G8-3

- 结果前协议提交 `5431790` 先推送，19 个逻辑请求首遍追加 19 条脱敏证据；相同入口和宿主
  `--verify-only` 均新增 0/复用 19，账本/报告/manifest 哈希不变。断网只读 Docker 镜像
  `sha256:72012422...fcab1` 独立复核相同裁决与哈希。
- 六只中只有 `016276` 完成管理人 HTTPS 身份和冻结八日单位/累计净值逐值一致；`017985` 页面/费率/
  法律索引双取成功但冻结解析器不支持其 `div` 型历史表，其余四只本次 Python HTTPS 传输失败。部分
  站点的独立 curl 可达，所以传输失败不等同源数据不存在；本次失败仍永久保留。
- 当前费率页交叉核验 2/6、法律文件索引 2/6、成立日至今有效期谱系 0/6。整体硬门因此权威
  `NO_GO_G8_2`，这是证据认证门失败，不是策略效果 REJECT；G8 继续 `NOT_READY`，生产授权为 none。
- 不立即做传输恢复：华商管理人 HTTPS 端口拒绝和费率有效期未闭环是独立阻断，只修 curl/httpx 或
  HTML 解析也不能改判。若未来继续，必须另立恢复协议并保留本次 19 条证据；不得进入 G8-3、构造
  总收益、读取策略结果或接 scheduler。证据见
  `docs/G8_FUND_MANAGER_CROSSCHECK_ACCEPTANCE_20260726.md`。

## 2026-07-26 · G8-2 管理人 HTTPS 与费率谱系结果前协议已冻结

- 新增 `g8-fund-manager-crosscheck-v1`，绑定 G8-1R 终版协议、账本和恢复 manifest；六只冻结产品、
  八个估值日、管理人域名/请求、逐值比较、双取、证据存储和整体 fail-closed 门均已结果前固定。
- 费率对象固定为 A 类标准申购/赎回费，不假设销售渠道折扣；动态产品页只做当前交叉核验，费率谱系
  必须从成立日至 `2026-07-26` 绑定官方法律文件哈希、公开日、页码/章节和明确有效期，禁止当前费率
  回填历史。
- 本阶段不构造总收益、不读取策略收益、不运行 G8、不改门槛、不接 scheduler/Web/生产。全部硬门
  通过也只允许另立 G8-3 协议；任一产品缺 HTTPS、缺日、净值冲突或费率谱系不全即
  `NO_GO_G8_2`，G8 继续 `NOT_READY`。
- 协议与口径见 `config/g8_fund_manager_crosscheck_v1.yaml`、
  `docs/G8_FUND_MANAGER_CROSSCHECK_PROTOCOL_20260726.md`；真实采集与机器裁决尚未执行。

## 2026-07-26 · G8-1R 监管主源恢复采集 GO，仅授权进入 G8-2

- 原 Docker 执行的空体 `502` 和错误完整 Git SHA 已永久保留；恢复协议只改变执行环境，原失败
  evidence、bundle 和冻结账本前缀均由采集前门与断网终验强制核验，未删除或改写。
- 一次性无 `.env` 宿主进程首遍追加 54、第二遍追加 0；6 条净值区间证据包含 48 条唯一 A 类记录，
  48 条逐公告分红备注证据全部 `PRIMARY_CAPTURED_UNAUTHENTICATED`。终版账本共 55 条数据行。
- 同提交镜像在断网、只读挂载条件下独立复核通过；恢复 manifest `915d013b...fb2e`、终版账本
  `0b05e285...13b96`，代码快照 `7e0d39f5...7497`，Git HEAD `542fb214...85e2`。
- 机器门为 `GO_G8_2_CROSSCHECK_AND_FEE_LINEAGE_ONLY`，不是 G8 PASS。监管源仍为 HTTP；管理人
  HTTPS 逐值对账和费率有效期谱系未完成，故 G8 继续 `NOT_READY`、生产授权 `none`。
- scheduler 原容器/镜像/创建时间持续 healthy 且未重启。验收见
  `docs/G8_FUND_PRIMARY_CAPTURE_ACCEPTANCE_20260726.md`。

## 2026-07-26 · G8-1R Docker 出口与镜像身份恢复协议已结果前冻结

- G8-1 首个逻辑请求双取均为空体 `502`，已追加一条 `QUARANTINED_HTTP_STATUS` 并在第一个
  请求后停止；Docker 默认/host 网络只读探测均复现空体 502，宿主直连在 G8-0 已 PASS。
- 首次镜像操作层还手工传入了错误的完整 Git SHA；短前缀与真实提交相同，但全长身份不同。该运行
  因此不能升级，原账本/证据包必须永久保留。
- `g8-fund-primary-capture-recovery-v1` 只把执行环境改为项目 `.venv` 的一次性 `env -i`
  宿主进程；不读 `.env`、`trust_env=False`，其余 54 请求/108 观察、选行、双取、限速、存储和失败门
  不变。
- 恢复协议支持已经实现：采集器接受新协议 ID，但在任何网络请求前强制核验冻结的旧账本前缀、
  失败行和证据包；新协议的请求/解析/验收仍复用原实现，账本 operator 显式标记宿主恢复。
- 实现已经先提交推送；完整 SHA 由 Git 实时读取。两遍宿主采集和同提交 Docker 断网独立验账均已
  按上方终态通过；本节只保留结果前协议与原因，不再代表当前进度。

## 2026-07-26 · G8-1 采集工程完成，原 Docker 执行失败并由 G8-1R 接管

- 已实现公开净值/分红接口的串行双取、原文 base64 证据包、安全响应头、唯一 A 类解析、
  追加式账本、同内容复用、修订隔离和断网哈希重验。
- 合成全流程两遍模拟 54 个逻辑请求/108 次观察：首遍追加 54，次遍追加 0；双取不一致、
  非空母级行、同请求新内容和证据篡改对抗测试全部按协议失败关闭。
- 专用 `g8-primary-capture` 一次性容器不注入 `.env`，只给 `data/g8/fund_evidence` 和单一账本文件
  写权限，根文件系统只读、无 Docker socket。
- 宿主全仓 315 PASS，Ruff/compileall/Compose/diff-check PASS。原 Docker 执行已在首个请求按协议留证停止；
  后续只能按上方 G8-1R 新协议恢复，不得重写原结果。

## 2026-07-26 · G8-1 监管主源采集协议已结果前冻结

- `g8-fund-primary-capture-v1` 只授权固化 `2026-07-15~2026-07-24` 六只产品的法定净值原文和
  逐公告分红备注；预期 6 个净值请求、48 个分红请求，各双取，共 108 次 HTTP 观察。
- 双取不一致、非 200、结构漂移或同请求出现新内容必须留证隔离后 fail closed；同内容复跑只复核已有证据，
  不追加账本。
- 证据包只落项目 `data/g8/fund_evidence`，追加账本只记相对路径、哈希、行数和状态，不记净值/金额/
  备注原文或凭据。
- 本协议后续已经实现；原 Docker 真实执行失败并永久留证，恢复工作只能由 G8-1R 新协议承接。即使
  恢复全部 PASS，也只允许进入管理人 HTTPS 交叉核验与费率谱系阶段；G8 保持 `NOT_READY`。

## 2026-07-26 · G8-0 法定产品证据源可行性门

- 证监会基金电子披露站作为六只冻结产品的法定集中主源可机器读取；`2026-07-15~2026-07-24`
  六只各 8 个估值日，共 48 条唯一可用 A 类记录，详情页六项身份、净值、法定文件与公告入口完整。
- 主源分红备注接口结构 PASS，允许绑定净值公告逐条留存分红/除息说明；真实分红事件样本和费率有效期
  谱系仍未形成。
- 监管站当前 HTTP PASS、HTTPS TLS FAIL；即时双取一致不能证明传输身份或长期无修订。机器裁决仅为
  `GO_G8_1_PRIMARY_CAPTURE_ONLY`，未完成管理人 HTTPS 交叉核验前不得标 `VERIFIED`。
- 本阶段未持久化净值数值、未施工采集器/账本、未读策略结果、未运行 G8；G8 保持 `NOT_READY`，
  生产与 Web 均未修改。协议与证据见 `config/g8_fund_evidence_source_v1.yaml`、
  `docs/G8_FUND_EVIDENCE_SOURCE_FEASIBILITY_20260726.md`。

## 2026-07-26 · P3-4B 模型/回测页面 GO

- `p3-experiment-ui-v1` 已完成 `/experiments` 目录和严格 kind/ID 详情页；真实 783 条记录按记录、
  发现、G1、工程、权威历史效果和失效方法分层，不提供成功率、排行榜、表现排序或最佳模型。
- 原 P2-2 常驻“可复算、非权威”并链接 P2-2C；P2-2C 的权威历史结论保持 `NO_GO / REJECT`。
  G1 详情完整显示十五门；无逐日 NAV 时明确不画净值或交易时序。
- 目录筛选/分页与响应身份、tier/outcome、decision 必需键、P2 三窗口、G1 十五门、未知字段和 `.BJ`
  均 fail closed。P3-4A 投影 `c2993c39...d31e1fe` 未重建或改写。
- 全仓宿主/Docker 各 299 PASS；前端单元 22 PASS、五档 fixture 浏览器 63 PASS/7 intentional skip、
  真实部署 10 PASS，两类 npm 审计 0 漏洞。终版 Web 镜像 `2da4299a...bcfad5`，两个 Web 容器
  healthy；scheduler 原容器/镜像/创建时间持续 healthy 且未重启。验收见
  `docs/P3_EXPERIMENT_UI_ACCEPTANCE_20260726.md`。

## 2026-07-26 · P3-4B 模型/回测页面协议已结果前冻结

- `p3-experiment-ui-v1` 冻结 `/experiments` 目录和严格 kind/ID 详情页，首要问题是“这是什么证据、
  当前是否权威、能否用于研究结论”；783 条记录不得包装成 783 个模型、成功率、收益排名或最佳策略。
- 结构审计确认十种 evidence tier、19 种实际 adapter 组合，实验 ID 12—43 字符且全部满足安全 slug；
  审计未重算或选择策略结果。目录只使用后台精确筛选、固定排序和 25 条有界分页。
- 深链详情缺目录层 outcome，协议只授权 `experiment_summary` 复用同一后台适配器增加
  `outcome_status`；不改变数值、authority、lifecycle、投影或哈希。详情按 tier 冻结 decision 键，
  未知键 fail closed，不做通用 JSON dump。
- 失效方法、provisional、工程 GO、发现层、G1 和权威历史效果必须分开表达；现有详情无逐日 NAV，
  页面不得伪造净值曲线。当前只完成协议冻结，尚未授权宣称页面 GO。

## 2026-07-26 · P3-4A 实验目录后端 GO

- 内部 `GET/HEAD /api/v1/experiments` 与类型化 `experiment_catalog` 已实现；真实 783 条记录全部
  可列且身份唯一，目录与详情身份一致。实际 outcome 为 FAILED 509、DISCOVERY_ONLY 196、
  RECORDED 49、G1_REJECTED 18、DISCOVERY_REJECTED 4、ENGINEERING_GO_ONLY 3、REVIEW_STOPPED 2、
  历史效果拒绝和失效方法各 1；正式准入仍为 0。
- 十类 outcome 已逐类 fixture 锁定；未知组合 `NOT_EVALUATED`，缺字段 `EVIDENCE_MISMATCH`。查询只
  允许精确筛选、固定 UTC 排序和 1—100 有界分页，不提供表现排序、数值结果或 raw JSON。
- 终版双协议投影 `c2993c39...d31e1fe` 连续两遍同 snapshot；bundle/manifest SHA-256 分别为
  `cf72e70c...e4d773` / `ca1e60d9...61292c`，旧投影未改写。终版 Web 镜像
  `bb0082bb...c27d7b` healthy、只读根；UI 代理仍对实验目录返回 404。
- 全仓 296 PASS，Ruff、compileall、依赖、Compose、前端生产构建、脱敏和写拒绝探针均 PASS。
  scheduler 原容器/镜像/创建时间持续 healthy，未重建或重启。验收见
  `docs/P3_EXPERIMENT_CATALOG_ACCEPTANCE_20260726.md`；页面须另立 P3-4B。

## 2026-07-26 · P3-4A 实验目录协议已结果前冻结

- `p3-experiment-catalog-v1` 只新增内部 `GET/HEAD /api/v1/experiments`，以现有不可变研究投影为
  唯一来源；当前结构基线为 783 条（778 研究实验、3 P2 工程、原 P2-2 与 P2-2C 各 1），身份与
  分类字段无缺失。本目标不施工页面、不扩 UI 代理、不运行模型/回测/G1/LLM。
- 目录以十类适配器级 `outcome_status` 分开记录、发现、G1、工程、历史效果和失效方法；禁止把
  783 条混称为有效模型，禁止收益/IC/回撤排序和筛选，也不返回数值效果或 raw JSON。
- 精确筛选、固定 UTC 时间降序、kind/ID 稳定并列键和 1—100 有界 offset 分页已冻结；翻页必须
  保持相同 snapshot。新协议必须进入 write-once 投影 source hash，旧投影不改写。
- 当前只完成协议冻结，尚未授权宣称后端 GO；施工与验收见后续 P3-4A 终版记录。

## 2026-07-26 · P3-3C 因子工厂页面 GO

- `p3-factor-factory-ui-v1` 已完成因子目录、单因子 tear sheet、2—3 因子严格比较和追加式准入
  历史四层页面；真实投影如实显示正式库 0、研究因子 10、当前权威 REJECT 8、仅历史 2，不提供
  综合分、排行榜、表现排序或“最佳因子”。
- 单因子完整展示十五项 G1 门、六窗口、压力期、组合/成本和证据身份；覆盖、分位收益/单调性、
  自相关、候选池相关固定 `NOT_EVALUATED · recomputed=false`。历史查询保留当前权威覆盖提示且
  不调用最新比较，压力期集合不一致和 fingerprint 冲突均 fail closed。
- P3-3B `meta.as_of=null` 只作 ISO 日期传输元数据窄修；研究 data、切片、判决、权威状态、投影
  快照和哈希输入未变。真实投影 `9afe4d11...180f13` 完成目录→详情→历史→比较桌面/移动闭环。
- 全仓 283 PASS、前端单元 18 PASS、fixture 浏览器 48 PASS/7 intentional SKIP、真实部署 8 PASS；
  两类 npm 审计 0 漏洞。终版 Web 镜像 `c437111e...d2e07fe`；scheduler 原容器/镜像/创建时间保持
  healthy 且未重建。验收见 `docs/P3_FACTOR_FACTORY_UI_ACCEPTANCE_20260726.md`。

## 2026-07-26 · P3-3C 因子工厂页面协议已结果前冻结

- `p3-factor-factory-ui-v1` 冻结因子目录、单因子 tear sheet、2—3 因子严格比较和追加式准入
  历史四类可复核 URL，只消费 P3-3B 四组因子 HTTP 查询。正式库 0、当前权威 REJECT 8、
  仅历史因子 2 必须作为真实结论展示，不使用综合分、排行榜、收益排序或浏览器补算。
- 历史 `as_of` 视图禁止调用只支持最新权威版本的比较接口；详情与准入历史必须同快照才组合。
  P3-3B 的 `meta.as_of=null` 与前端日期门冲突，本协议只授权 ISO 日期传输元数据窄修，不改 data、
  权威状态、判决、快照身份或研究口径。
- 移动导航按 Web 1.0 基线收敛为“总览 / 因子 / 组合 / 更多”，模型/回测继续禁用。当前只完成
  协议冻结，尚未授权宣称页面 GO；施工与验收见后续 P3-3C 终版记录。

## 2026-07-26 · P3-3B 因子与实验只读后端 GO

- `p3-factor-experiment-query-v1` 的五组类型化查询已实现；真实投影包含 10 个因子身份、18 个 G1
  版本、8 个当前权威版本、8 个当前权威 REJECT、2 个仅历史因子和 0 个正式入库因子。
- 一次性 `research-projector` 在断网、非 root、只读根文件系统容器内构建 write-once 哈希投影；
  web-query 只读挂载 `data/web/research_snapshots`，不挂原始研究目录、不读 `.env`、无 Docker socket
  和宿主端口。终版 snapshot 为 `9afe4d11...180f13`，双跑字节与哈希一致。
- 778 个研究实验与 P2 三类运行均有独立 adapter；D1 STOP 只覆盖冻结 Top2，原 P2-2 为
  `INVALIDATED_METHOD`，P2-2C 为 `AUTHORITATIVE_CURRENT / NO_GO / REJECT`。旧决策不覆盖、不删除。
- 四类缺失 tear-sheet 指标固定 `NOT_EVALUATED`，不返回逐日序列、原始 `params_json/result_json`、
  原始路径或密钥。非权威版本、跨家族和 fingerprint 不一致的比较均 fail closed。
- 宿主与 Docker 全仓均 282 PASS；施工中发现并修复 JavaScript MIME 的 Python 版本漂移。scheduler
  原容器/镜像/代码快照持续 healthy，未重建或重启。验收见
  `docs/P3_FACTOR_EXPERIMENT_QUERY_ACCEPTANCE_20260726.md`。
- 页面仍未授权；下一步可另立 P3-3C 因子工厂页面协议。模型/回测完整页仍须先冻结
  `experiment_catalog`，不得让前端自行扫描投影或账本。

## 2026-07-25 · P3-3A 因子与实验查询契约 GO

- 只读审计 778 个通用实验、18 个 G1 判决、40 个 D1 尝试、8 个 D1 复核及 P2 三层账本；主键、
  外键、JSON、18 组 G1 报告/证据/factor-test 路径与 SHA-256 全部一致。未运行模型、回测、G1 或
  LLM，未生成候选或读取新策略效果。
- 18 个 G1 判决实际对应 10 个“研究家族 + 精确公式”身份和 18 个实验版本；8 个身份有当前权威
  版本（Stage-1 正确 Top2 两个、P1 终版六个），2 个只有 Stage-1 历史非权威版本，正式库仍 0 插入。
  `experiments.admitted=false` 不能把未提交 G1 的尝试解释成 REJECT。
- P1/Stage-1 旧代、D1 原机器 GO、P2-1 provisional 与原 P2-2 失效方法必须在查询层应用明确 authority
  overlay；原记录保留，当前权威结论不得被旧行覆盖。因子覆盖率、分位收益/单调性、自相关和候选池
  相关性缺统一登记证据，冻结为 `NOT_EVALUATED`，Web 不补算。
- `p3-factor-experiment-query-v1` 已冻结五组类型化只读查询；允许下一目标 P3-3B 施工一次性 Docker
  研究投影构建器和查询后端。web-query 禁止直接挂整个 `data/research`，只可读
  `data/web/research_snapshots/` 的限字段、write-once、哈希绑定投影。
- 当前不授权因子/模型页面。`experiment_summary` 只支持已知 ID 详情；完整模型/回测页仍缺独立
  `experiment_catalog` 列表契约。审计与协议见 `docs/P3_FACTOR_EXPERIMENT_EVIDENCE_AUDIT_20260725.md`
  和 `docs/P3_FACTOR_EXPERIMENT_QUERY_PROTOCOL_20260725.md`。

## 2026-07-25 · P3-2B 两个运维证据页面 GO

- `p3-web-operations-ui-v1` 已由先行提交 `fa63883` 结果前冻结并推送；随后完成 `/data-quality`
  与 `/system-runs` 两页，以及按稳定 `message_id` 打开的独立通知证据抽屉。
- 数据页必须把“数据结论 PASS”和“哨兵证据 WARN”并列，常驻展示哨兵未哈希绑定、原始 Parquet
  未重验和 `.BJ` 三层门；系统页分列核心/通知状态并保留失败—恢复链、legacy 通知和实时容器身份
  `NOT_EVALUATED`，没有把恢复后的 WARN 粉饰成全绿。
- 两页各自只消费一个 P3-2A 原子响应；通知详情是带独立快照身份的按需查询，不静默合并系统页。
  精确代理 allowlist、动态失败/未就绪文案、五视口、axe、fixture 与真实浏览器、Docker 隔离和脱敏
  均 PASS。终版 Web 镜像 `cd922d89...7bada`；生产 scheduler 的容器、镜像、创建时间和 healthy
  状态不变。协议见
  `docs/P3_WEB_OPERATIONS_UI_PROTOCOL_20260725.md`，验收见
  `docs/P3_WEB_OPERATIONS_UI_ACCEPTANCE_20260725.md`。

## 2026-07-25 · P3-2A 工程 GO，证据 WARN

- `p3-web-operations-v1` 已完成数据质量、系统运行和通知投递三组只读查询；页面仍未施工，未修改
  scheduler、生产镜像、策略、模型、信号、门禁、原始数据或追加式账本。
- 数据质量查询只重算截止日 `ingest_batches` 登记身份链并绑定 S1—S10/信号；不挂载或逐字重哈希
  `data/raw`，因此 `raw_parquet_rehash_status=NOT_EVALUATED`，不得把账本一致冒充原始文件重验。
- 系统运行查询分列核心步骤、失败恢复、通知投递和 release 审计身份；不挂 Docker socket，实时容器
  身份继续 `NOT_EVALUATED`。协议见 `docs/P3_WEB_OPERATIONS_PROTOCOL_20260725.md`。
- 冻结后、实现前核查发现现有信号/影子账本未保存哨兵报告哈希或 S1—S10 明细，无法满足原定逐项
  哈希绑定；结果前补遗将其明确为 `IDENTITY_MATCH_UNHASHED`，数据质量可读结论与证据完整性分列，
  后者固定 WARN。P3-2A 不越权回写生产 schema，见
  `docs/P3_WEB_OPERATIONS_PROTOCOL_ADDENDUM_20260725.md`。
- 继续核对真实时钟确认 `signal.data_complete_at` 是日增量完成时刻而非哨兵时刻；第二份结果前补遗
  将绑定修正为“日增量完成 ≤ 哨兵生成 ≤ 信号生成 ≤ 影子运行完成”，仍要求三方代码/数据身份一致，
  见 `docs/P3_WEB_OPERATIONS_PROTOCOL_ADDENDUM_2_20260725.md`。
- 首次真实查询在返回结果前发现 2026-07-22 通知升级前的历史记录没有稳定 `message_id`；第三份补遗
  将其定义为只计数、不可按消息寻址的 legacy schema，严禁合成 ID。2026-07-23 起缺 ID 仍 fail
  closed，见 `docs/P3_WEB_OPERATIONS_PROTOCOL_ADDENDUM_3_20260725.md`。
- 真实查询截至 2026-07-24：69,020 批/45,160,002 行登记身份链重算一致，S1-S9 PASS、S10
  NOT_APPLICABLE；数据结论 PASS、哨兵证据 WARN、系统运行 WARN，完整保留影子失败恢复、核心故障
  消息和通知恢复。全仓 277 PASS，终版 Web 镜像 `6c244c9a...7190`，生产 scheduler 原容器/镜像/
  代码快照和 healthy 状态不变。结论见 `docs/P3_WEB_OPERATIONS_ACCEPTANCE_20260725.md`。

## 2026-07-25 · D1-3A 语义合同纠错后停止

- D1-2B 机械 Top2 的身份、原始表达式、冻结方向与不可变证据已绑定；D1-3A 只授权恰好 8 份
  DeepSeek 对抗复核、专项 `$0.25` 硬上限，不生成新候选、不改公式/方向/窗口，不读或外发
  W1—W6、压力期、G1、前瞻和生产结果。
- 主窗口在协议冻结前核对候选 18 身份时误见其发现期 RankIC 与覆盖率；该污染已永久登记，数值不
  重复、不外发。DeepSeek 请求本身仍为结果盲态，但主窗口不得承担最终人工闸；独立盲审须另立
  D1-3B 授权，未获授权前最多停在 `GO_INDEPENDENT_HUMAN_GATE`，不得运行 G1。
- 结果前提交 `12b3101` 推送后，以独立不可变镜像完成 8/8 份 schema PASS 响应；4 份报阻断、4 份
  未报阻断，专项费用 `$0.01472214`、D1 累计 `$0.091348347`，无重试或计费不确定性。断网无密钥
  复跑 0 外部调用且全部证据哈希不变；生产 scheduler 原容器/镜像/创建时间保持 healthy。
- 组装零业绩独立盲审包时发现 3 份响应虽 schema PASS 且结构字段声称未提新公式，正文却建议替换
  聚合/估计量或尝试其他波动变体，违反冻结 prompt。语义有效数仅 5/8；协议要求 8/8 且禁止补位，
  因此原 `GO_INDEPENDENT_HUMAN_GATE` 被权威改判为 `STOP_SEMANTIC_CONTRACT_VIOLATION`。
- D1-3 本批终止：不启动独立盲审、不读取 W1—W6、不运行 G1，两候选均未获准进入效果评价；
  `strategy_effective=NOT_EVALUATED / production_authorization=none`。原报告/账本/响应不改写，纠错见
  `docs/D1_LLM_FACTOR_REVIEW_SEMANTIC_CORRECTION_20260725.md` 及同名 JSON。
- 真实追加后仅修复一项测试生命周期断言：允许账本为预执行 0/0 或完整 8/16，拒绝中间态；runner、
  协议、prompt、release、响应与账本均未修改，也未再次联网，原执行镜像/快照仍是唯一运行真身。

## 2026-07-25 · D1-2B 首批 40 份真实响应完成

- `d1-llm-dsl-v1-batch-001` 已取得恰好 40/40 份完成响应，估算费用
  `0.076626207 USD`；36 份完成冻结发现期评估，2 份重复 AST、2 份 DSL
  沙箱拒绝均按协议计 N，不递补。
- 第 2 个请求发出前因独立尝试反馈控制流缺陷 fail closed；无重复请求、无
  计费不确定性。恢复附录先行推送后从序号 2 完成剩余 39 份，序号 1 未重发。
- 纠错范围仅限“独立尝试忽略历史反馈”和“部分批次从下一缺失序号恢复”；
  第 1 份响应及三份账本前缀、四类忽略区产物均按哈希永久保留。
- 恢复附录：
  `config/d1_llm_factor_execution_recovery_v1.yaml`；
  说明：`docs/D1_LLM_FACTOR_EXECUTION_RECOVERY_20260725.md`；终版验收：
  `docs/D1_LLM_FACTOR_EXECUTION_ACCEPTANCE_20260725.md`。
- 机器结论 `GO_D1_3_REVIEW / strategy_effective=NOT_EVALUATED /
  production_authorization=none`。当前仍不运行 W1–W6、压力期、G1 或生产信号。

2026-07-26 用户授权增加 `model_top20` 模拟比较账户，初始资金仍为 500,000 RMB。结果前协议已明确：
只消费同一份已对账 Top30 不可变信号，按原排名保留前 20 并等权到 5%；不换股、不补位、不调分，
也不冒充前瞻链未实现的 `n_drop2`。Top20 表示目标上限，实际持仓可因交易单位、停牌、涨跌停或现金
约束少于 20。原 `model_baseline` 账户、账本行和产物必须字节不变；Top20 使用独立账户、策略哈希、
状态链与产物目录。协议提交推送前不生成或查看 Top20 结果，工程验收前不提升 scheduler，短期观察不
构成策略有效性结论。结果前时间补遗进一步纠正了机械沿用基准仓 7月23日的问题：Top20 的
7月17—24日全部为 BACKFILL，首个可能的自然 FORWARD 从冻结后的下一交易日 2026-07-27 起算；原
`0f24238` 提交永久保留。见 `docs/PAPER_TOP20_PROTOCOL_20260726.md`、
`docs/PAPER_TOP20_PROTOCOL_ADDENDUM_20260726.md` 和 `config/paper_top20_v1.yaml`。结果前 v1.2 证据
补遗还纠正了“共享账本整文件哈希不变”的物理矛盾：权威条件为旧文件字节是新文件完整前缀、Top30
规范行哈希不变且只追加 Top20 行；Top30 产物整树仍须完全不变。见
`docs/PAPER_TOP20_PROTOCOL_EVIDENCE_ADDENDUM_20260726.md`。

## 当前阶段
阶段 0（基线）已完成；阶段 1 已完成有界 GP 预演和 `p1-moneyflow-v1` 首个正式数据增强家族，二者均按冻结 `g1-v1` 结论 REJECT，正式因子库仍为 0 插入。锁竞争修复后当前代码版本连续三次完整“信号 → 下一交易日开盘对账”已于 2026-07-22 完成 3/3，核心任务验收 PASS、通知通道 WARN；同日完成飞书通知健壮性修复。P0.5 `model_baseline` 已持续前瞻观察；新增 `model_top20` 已完成六日 BACKFILL、独立重放和幂等工程验收，前瞻仍为 NOT_READY，且因凭据轮换与 release window 尚未接 production scheduler。P3-3B 已完成因子与实验的不可变安全投影、五组类型化查询及 HTTP 后端；P3-3C 因子工厂与 P3-4B 模型/回测页面均已完成，Web 1.0 七类本机只读页面全部可用。P4-0 科创100源采集PASS，但官方历史成员谱系NO-GO，已停在P4-1前且未评价策略效果。

结果路线现为：P0.5 持续积累真实前瞻观察；P1 首批六个简单资金流候选已全部 REJECT 且停止本家族追加变体；生产 scheduler 与开发工作树的发布快照隔离已于 2026-07-24 完整 PASS。P2-0 的 `p2-star50-protocol-v1` 永久保留 NO-GO：Tushare 首份权重按 T+1 仅能从 2020-08-03 生效，冻结起点缺 7 个交易日且无历史版本/修订字段。`p2-star50-protocol-v2` 以官方首批名单和全量调整公告重建 `000688.SH` 成员谱系；1,456 个交易日每日均为 50 只，和 72/72 个 Tushare 月度集合完全一致，官方谱系数据门 GO。P2-1 独立工程门 GO 只证明真实数据集、动态 instruments、隔离 qlib 与 synthetic 通路可运行。原 P2-2 因标签成熟、开盘时钟和卖单容量三项方法违约永久标记 `original_p2_2_model_valid=false`、`original_p2_2_execution_valid=false`，旧数值可复算但旧 `NO_GO/REJECT` 不再权威，所有旧证据原样保留。P2-2C 以结果前推送的 `c6fbbaf` 只修复上述三项并完成唯一 purged 训练与一遍确定性复核：三窗基础净超额 -8.51%/-19.25%/-23.87%，727 日 pooled 基础/2x/额外滑点 -52.97%/-56.19%/-56.02%，三测试窗和 microcap_2024 回撤超过 20%；合法 CSI800 对照仍缺使分散化 `NOT_EVALUABLE`。权威终态 `authoritative_historical_effect_gate=NO_GO`、`strategy_effective=REJECT`、`production_authorization=none`，本基线停止，不调门槛、不追加变体、不进入前瞻或生产；中证800继续是唯一生产主策略。P3-0 已完成可信只读查询底座；P3-1、P3-2B 与 P3-3C 已完成总览、模拟组合、股票池/信号、数据质量、系统运行和因子工厂六类正式页面及真实浏览器/Docker 安全验收，Web 1.0 本机只读首版可用。D1-0、D1-1、D1-2A 和 D1-2B 均已完成；D1-3A 已完成恰好 8 份结果盲态对抗响应，专项费用 `$0.01472214`，但其中 3 份自由文本违反“禁止替代公式/变体”的冻结合同，权威终态为 `STOP_SEMANTIC_CONTRACT_VIOLATION`。2026-07-26 已完成未来新批所需的语义一致性工程门，离线精确复现 5 PASS/3 FAIL，但旧批仍不进独立人工闸，不读取 W1—W6/压力期，不运行 G1；策略未评价且无生产授权。完整目标、输出、通过条件和禁止事项见 `docs/ROADMAP.md`。

2026-07-19 用户明确后台仍为主线，同时授权 Web 方案旁路持续优化。P0.5 三组模拟仓只读查询已于 2026-07-22 稳定，Web 技术栈与页面原型评审闸门已打开；Web 代码仍须在不影响首个 `FORWARD` 验收和后台主线的前提下另立目标。初版方案见 `docs/WEB_DESIGN.md`。

2026-07-22 已确认 Web 设计协作方式：主线负责指标与证据口径裁决，Dashboard 架构能力负责信息层级与下钻，Quant Visualization 负责量化图表，Figma UI/UX 负责视觉与原型，浏览器 QA 负责竞品核对、响应式与交互验收。P0.5 首批查询契约现已稳定，可另立目标引入前端实现；Figma 等外部工具不得承载真实数据、密钥或不可变证据，设计真身仍须导出并保存在本仓库。

2026-07-25 用户明确 Web 调研统一交由“Web 1.0 专项审计”承担：涉及竞品、金融信息展示、交互规范、无障碍或前端技术选型时，由专项只读核查并回传来源、发现、适用边界和变更提案；主窗口只负责口径/范围裁决、采纳与施工调度，不重复扩散调研。专项不得直接改生产代码、后台契约或 v1.0 基线，未经主窗口裁决的新发现只进入 `OBSERVE/PROPOSE`。没有明确决策问题时不频繁启动专项。

2026-07-22 Web 1.0 专项完成 v1.0-rc1 冻结候选：审计确认当前实际可复用入口仅为 `paper_portfolio_snapshot`、`paper_orders_fills`、`paper_nav_series`、`verify_paper_replay` 与前瞻验收裁判，且均为 Python 只读查询而非 HTTP API；其余页面契约全部显式标为需求提案。设计将产品进一步明确为“专业因子工厂与量化决策台”，已补齐七页信息架构、因子目录/tear sheet/对比/准入历史、指标字典、查询映射、状态/空态/错误态、金融图表、响应式/WCAG、React/Ant Design 候选栈、独立 Docker `web` profile 边界和低保真可点击路线，并补充“专业、安静、清晰、有重点”的视觉原则、8 px 栅格、字体/色彩/数字规则及 5 秒扫视验收。因子展示借鉴 WorldQuant BRAIN、Qlib/MLflow、Alphalens/QuantRocket 和 MSCI Barra 的生命周期、实验追踪、tear sheet 与归因范式，但不继承其指标阈值、排行榜或黑箱评分。见 `docs/WEB_DESIGN.md` 及配套 `WEB_*.md`。未经主控复核不接生产、不启动 Web 服务。

2026-07-23 用户确认 Web 1.0 初始版本按上述方案冻结，v1.0-rc1 升为 v1.0 初始设计基线。该确认覆盖产品定位、七页信息架构、因子工厂四层结构、指标与状态语义、视觉原则、低保真交互和首期实施顺序；不等于批准新增 HTTP 查询、Web Docker 服务、生产数据接入或正式前端施工。进入代码前仍须逐项裁决 `docs/WEB_DESIGN.md` 第 12 节的接口、部署、字段和样本门槛。

2026-07-23 用户确认 v1.0 冻结后仍可联网持续调研方案的合理性、先进性和专业性，并可在第一版 Web 实现后基于真实使用证据优化。冻结后的新发现先进入调研观察或变更提案，不静默改变 v1.0 指标、状态、契约和页面主任务；第一版后按决策效率、误读点、下钻深度、数据密度、性能、响应式和可访问性复盘，视觉微调走 v1.0.x，口径/契约/页面任务变化走 v1.1 评审。受控演进规则见 `docs/WEB_DESIGN.md` 第 13 节。

2026-07-23 主控完成 Web 1.0 七项架构复核并以 `ACCEPT_WITH_GUARDRAILS` 裁决：接受原子 `overview_snapshot`、FastAPI 只读适配层、隔离 `web` profile、逐仓确定性投影、脱敏受限导出和四组因子工厂查询设计；`latest_signal` 只允许返回信号时点事实和计划交易腿，次日真实可成交性必须等执行日对账。复核发现现有 `net_excess` 是包含 BACKFILL 初始化的全账户累计净值差，不能冒充 FORWARD 业绩；首页主结果须以后一个 BACKFILL 账户日为锚生成 FORWARD 专属组合/基准序列。前瞻描述性结果可从首日展示，年化至少 252 完整账户日/12 个月/95% 覆盖，Sharpe/信息比率至少 504 日/24 个月/40 调仓周期且须后端冻结序列相关修正，720 日仍由 G8 独立裁决。Web 容器不得继承生产 `.env` 与整仓写挂载，查询服务无宿主端口。全文见 `docs/WEB_ARCHITECTURE_RULINGS_20260723.md`。

2026-07-25 P3-0 只读查询后端工程 GO：结果前提交并推送 `1e895c0` 冻结 `p3-web-query-v1`，随后实现稳定证据切片、原子 `overview_snapshot`、模拟仓逐仓投影、事件/状态链独立重放、BACKFILL/FORWARD 锚点、最新信号时钟和次日对账 `NOT_DUE` 边界。FastAPI 只开放 8 个 GET/HEAD allowlist，关闭文档与写方法；独立 `shaiwei-web` profile 不加载 `.env`，query 无宿主端口，UI 只绑定 `127.0.0.1:8080`，两容器非 root、只读根、无 Docker socket。当前真实快照截至 2026-07-24，重放 PASS、FORWARD 2 日、`.BJ=0`；核心运行和通知均保留先失败后恢复历史，因此综合 WARN 但必需证据完整。全仓 210 PASS，终版 Web 镜像 `1c25025b...ae630`；scheduler 容器/镜像/代码快照施工前后完全不变且 healthy。见 `docs/P3_WEB_QUERY_ACCEPTANCE_20260725.md`。

2026-07-25 P3-1 Web 1.0 首批正式界面 GO：结果前冻结 `b75b4b3`，依赖审计后以两份先行安全补遗永久记录并最终移除第三方路由器，终版实现提交 `133c673`。三个页面严格复用 P3-0：总览只读一个原子响应，模拟组合四响应跨快照 fail closed，信号页不把计划差冒充成交并在 `NOT_DUE` 时不预测执行事实；未知状态、坏哈希/数字和 `.BJ` 均阻断。逐响应随机 CSP nonce、零外部资源、只读静态/API allowlist、刷新/错误/空态、五视口、axe 和真实部署均通过；全仓 214 PASS，fixture 浏览器 18 PASS/7 intentional SKIP，真实浏览器 6 PASS，npm 两类审计均 0 漏洞。终版镜像 `e9232bfd...25a9d`，scheduler 原镜像和启动时间不变且 healthy。见 `docs/P3_WEB_UI_ACCEPTANCE_20260725.md`。

2026-07-22 用户授权在 P0 后增加 P0.5“模拟组合与前瞻绩效闭环”，并将其置于资金流验证之前。首版只运行正式模型基准仓：初始资金冻结为 500,000 RMB，消费不可变信号，以信号后下一交易日官方开盘作为唯一成交时点，持续记录订单、成交、实际持仓、现金、成本和每日净值；无法成交时不得把目标权重冒充实际持仓。未来 LLM 主观研判若启用，必须进入独立账户并与模型基准仓并行比较。`paper-v1`、账本、查询和 Docker 日任务均已落地，BACKFILL 验收见 `docs/P05_BACKFILL_ACCEPTANCE_20260722.md`。

2026-07-23 P0.5 首个自然 `FORWARD` 验收 PASS：`20260722` 信号由 Docker scheduler 在首个官方开市日 `20260723` 形成账户日，`paper-v1` 与受控代码身份一致；8 个新增原始批次 21,151 行逐文件重哈希一致且 `.BJ=0`，S1-S9 PASS/S10 NOT_APPLICABLE。非调仓日正确产生 0 订单/0 成交，追加 22 条持仓、现金和 NAV 共 24 个连续事件；现金 180,557.98 元、持仓市值 298,225.30 元、净资产 478,783.28 元、会计恒等差 0.00。`paper-verify` 重放 5 日/174 事件 PASS，`paper-acceptance` 对代码/策略/operator/新鲜度/北交所/通知/哈希 fail closed 后 PASS；飞书模拟仓开始/完成均首次投递成功，另两类自然网络超时在同消息 ID 第 2 次自动恢复。受控重复运行全链 NOOP，相关账本、通知与不可变产物行数和哈希均不变。完整证据见 `docs/P05_FORWARD_ACCEPTANCE_20260723.md`；这只完成工程闭环，当前前瞻样本为 1 日，不证明策略有效。

2026-07-16 已记录长期定位：LLM 因子挖掘将作为筛微未来的主要研究工作，但不是生产策略控制者；输入不局限于观象，还包括筛微本地数据、论文/规则/研报/网页、开源代码、经授权的新数据源和历史实验记忆。原“待 P0.5 后再评审”的等待条件已于 2026-07-25 满足并由下述 D1-0 裁决取代；常设系统仍未授权。

2026-07-25 D1-0 LLM 持续因子研究方案评审完成，终态 `REVIEW_COMPLETE / NOT_AUTHORIZED_TO_RUN`。裁决为自建筛微窄控制面，首轮仅让 DeepSeek 输出严格 JSON 中的一条受限量价 DSL；本地 parser/sandbox、实验总账和不变 `g1-v1` 执行与裁决。40 次固定为五主题各 8 次（4 独立 + 4 同主题有界变异），所有完成响应、空/截断/格式错、重复、语法和沙箱失败均计 N；W1-W6 解盲前机械 Top2 须过人工经济解释闸，拒绝不递补。旧 GP 最终 40 候选只作冻结参考，其家族因历史纠错已机械计 N=166，禁止新建干净家族重置 N，也不宣称 DSR 配对。建议模型 `deepseek-v4-pro` thinking/high，按 16k 输入/8k 输出、40 次全 cache miss 理论 $0.5568，草案硬熔断 $0.75；尚待用户确认。观象、实时知识雷达、资金流/财务、任意 Python、常设服务和生产接入均不进入首轮。本次未调用 LLM、未生成/评价候选、未访问项目外目录；见 `docs/D1_LLM_FACTOR_RESEARCH_ARCHITECTURE_20260725.md`、`docs/D1_LLM_FACTOR_RESEARCH_PROTOCOL_DRAFT_20260725.md` 和 `config/d1_llm_factor_research_v1.yaml`。

2026-07-25 D1-1 LLM 因子研究零调用工程门完成，终态 `GO_ENGINEERING_ONLY / D1_2_NOT_AUTHORIZED`。已实现严格单候选 JSON schema、固定 40 次确定性排程、现有 AlphaGen DSL parser/sandbox、敏感输出隔离、mock provider、追加式 `llm_factor_attempts` 账本及其与 `experiments` 总账的确定性一一对应；孤儿记录和哈希冲突均在再次调用前 fail closed。独立 research compose 为非 root、只读根、完全断网、无 `.env`/端口/Docker socket/生产挂载的一次性 fixture。最终 synthetic 证据为 attempt/experiment 各 1 行、双账本 1:1、重放幂等、外部 API 调用 0、真实市场读取 false、G1 false；本地全仓 232 PASS、容器对抗 17 PASS。生产 scheduler 容器、镜像、受控代码快照和启动时间施工前后不变且 healthy。见 `docs/D1_LLM_FACTOR_ENGINEERING_ACCEPTANCE_20260725.md`。

2026-07-25 D1-2A 真实调用前冻结完成，终态 `GO_PREEXECUTION_ONLY / D1_2B_NOT_AUTHORIZED`。已按 DeepSeek 官方模型/价格、thinking、JSON、响应和错误合同冻结 system prompt、五主题模板、严格反馈序列和 10 条知识 manifest；前四次独立提案无反馈，后四次必须携带同主题全部历史尝试，W1-W6/G1/前瞻字段 fail closed。受限客户端在当前未授权配置下只接受 `MockTransport`，live factory 在读取环境前拒绝；追加式 transport 事件、请求前累计最坏费用预留、成功响应 write-once 恢复、429/500/503 有界重试、悬空/超时 `BILLING_UNCERTAIN` 禁止重发和敏感输出脱敏均已通过。全仓 247 PASS、断网 Docker 对抗 29 PASS，真实 API、secret 读取、行情和 G1 均为 0；生产 scheduler 身份与启动时间不变且 healthy。见 `docs/D1_LLM_FACTOR_PREEXECUTION_ACCEPTANCE_20260725.md`。

## 已定口径（冻结，改动须走 STATE 显式作废流程）
- 规划基线：可行性报告 v0.5.4（开工基线版，2026-07-09），判据 G0-G9 + C0 已生效，执行期不得回溯修改。
- 股票池/基准：中证 800（SH000906）起步；日频信号、双周（10 交易日）调仓；30 只持仓；手动执行。
- 数据源：Tushare Pro（1 万积分）主源 + AKShare 行情交叉校验 + Baostock 歧义交易状态核验；管线 = Parquet+DuckDB → pandera 校验 → qlib bin。
- 复权/量纲/PIT/ST/停牌等硬口径：见 AGENTS.md 与 docs/DATA_SPEC.md。
- 回测窗口起点：2016-01-01（早于 2008 不可前移，除非重估幸存者偏差缺口）。
- 本机：Mac M5 10 核 24G；joblib ≤8 进程；torch 用 CPU。
- G0 六窗口：2026-07-15 在任何回测运行前预注册为 3 年训练 + 次年检验（W1-W6，检验年 2019-2024），详见 docs/GATES.md；此项补足日期口径，不改 G0 公式。
- 基线训练窗内部切分：末 6 个月固定作 LightGBM 早停验证；标签固定为“次一开盘买入、10 个交易日后开盘卖出”的 `Ref($open,-11)/Ref($open,-1)-1`；均在首次回测前冻结。

## 当前进度
- [x] Day 0：v0.5.4 报告+SHA256 存证；Git 基线 `9ab3c96` / tag `baseline-v0.5.4`；Python 3.12 隔离环境、依赖锁、7 项测试、Ruff、qlib/LightGBM/Tushare/AKShare 运行时检查通过
- [x] Day 1-5 代码层（非数据验收）：Tushare 基础/停复牌/历史名称/公司行为/申万历史行业/行情/财务采集计划、AKShare 独立源、不可覆盖 Parquet+哈希账本、动态存续池、ST-PIT、后复权/量纲、财务 PIT、S1-S10 统一入口
- [x] Day 6-7 代码层（非实测验收）：原子构建且整树内容哈希绑定的 qlib 原生 bin、Alpha158+LightGBM 六窗口基线、双周/次开盘标签与成本情景、影子信号 manifest、AlphaGen 上游锁定+CPU/申万 L1 PIT 行业与市值中性化 RankIC benchmark（完整覆盖 setup+evolution 的耗时/RSS）
- [x] 阶段 0 自动流：`make stage0-plan/stage0-run`；按 as-of+代码+数据快照续跑，采集按参数+文件哈希去重，首个失败即停，最终 G0 审计不含任何阶段 1 命令
- [x] 真实首跑边界与吞吐修复：Tushare 合法空响应规范化为冻结 schema 的 0 行批次；1 万积分按全局 0.15 秒请求起点间隔+8 路在途请求隐藏网络延迟，完成即补位且两窗口有界缓冲，硬顶仍为 400 次/分钟，账本仍串行有序提交
- [x] 证据链硬化：G0 逐批重哈希原始 Parquet 与 qlib 派生树；从六窗口明细重算冻结公式，逐项核对影子订单和 AlphaGen summary/候选结果与实验账本；拒绝空候选、空预测、伪结论和损坏缓存；空数据实测以退出码 2 拒绝，`next_phase_authorized=false`
- [x] 关键门禁补强：S1 严格服从北交所范围开关；S2 固定有界双算样本；S3 固定四类样本并核对复权连续收益；S4 核对 VWAP 绝对量纲；S5 核对三表结构与 `688502.SH/20221231` 真实更正；S7 以实施分红或除权 pre_close 双证据归因因子倍率，无证据源补丁不进入累计链且保留 raw/corrected 审计字段；S8 核对成交额单位；qlib 使用方向性 PIT 涨跌停字段
- [x] 离线质量门：164 项测试、Ruff、compileall、pip check、账本追加约束通过（2026-07-16；不等同真实数据验收）
- [x] Day 1-3 已完成实测采集：bootstrap 261 批；停复牌 2,557 批；名称变更 5,445 批；分红送转 5,445 批；申万历史行业 10,890 批（Y/N 各 5,445）；各阶段冻结计划逐项同序、0 重复并已记录 PASS
- [x] Day 3-4 行情采集与账本审计：daily+adj_factor+daily_basic 24,792/24,792 个唯一请求，共 31,946,896 行；全量文件哈希复核通过，三表主键均无重复，daily 缺 adj_factor 为 0、混合零行组为 0；仅 4 只退市股共 13 个 `daily` 独有交易日，不作伪填充，交由 S1 按冻结口径裁决。后复权/量纲当前真实断点 S4/S7 预跑 PASS，S7 修正 3 只股票 11 个有证据的源因子补丁、未归因有效跳变 0
- [x] S1/S6 全市场实测：目录读取禁用 Hive 分区推断，避免路径日期覆盖 payload 字符串日期；`suspend_timing` 非空只作为日内事件，不再冒充全天停牌；退市生效日按生命周期右开区间处理（337 只退市证券在 `delist_date` 当日行情行数实测为 0）。Baostock 仅补采 85 个歧义窗口、10,198 个证券日并逐批哈希记账，其中 10,188 日确认不交易、10 日确认正常交易并纠正主源冲突。S1：5,534 只证券、排除 331 只北交所、0 异常，PASS；S6：234,621 个权威停牌日、0 个非 NaN 行，PASS。
- [x] 行情瞬时空响应闭环：25% 内容审计发现 `000750.SZ` 两个密集接口请求曾无报错返回 0 行；直接重查分别得到 2,392/127 行，确认源端瞬时空响应。查询器现对密集接口按冻结退避重试并硬校验响应 `ts_code`；旧零行批次不可变保留，新批次以相同参数追加且成为目录最新版。70% 全量已采集 market 复核后混合零行组为 0，仅余 4 只退市股共 13 个 `daily` 独有交易日，不作伪填充，交由后续哨兵按原口径裁决。
- [x] 长流程网络韧性闭环：真实采集三次因短时 DNS/本地代理抖动按首错即停，均保持严格可恢复前缀；直连探测证明 `api.waditu.com` 可达，Tushare 子进程现仅对该域名自动绕过桌面代理。最大尝试从 3 增至 6，1/2/4/8/16 秒指数退避共覆盖约 31 秒；测试锁定前 5 次失败、第 6 次恢复仍能成功落盘，其余域名代理设置不受影响。
- [x] AKShare 交叉源连接闭环：东方财富历史行情 API 对 curl 同参数正常、但对 Python/requests 在代理与直连路径均持续主动断连，6 次指数退避仍失败；不跳过 S8，改用同一 AKShare 库的新浪 `stock_zh_a_daily` 独立行情适配器。新浪 volume=股，采集层除以 100 统一为手后再与 Tushare 比对；四只冻结样本与阈值不变。
- [x] Day 5：财务三表逐股采集 16,335/16,335 个唯一请求、743,743 行；2016Q1-2026Q2 三表 VIP type 1/type 5 共 504 个分页请求、845,005 行。分页固定为 0/4,000/8,000，尾页饱和即 FAIL；S5 以 `688502.SH/20221231` 验证旧值 2023-02-16、新值 2023-03-08，三表 PIT 全量 PASS
- [x] Day 6：qlib 全量 bin、Alpha158+LightGBM 六窗口基线和影子执行均已真实完成；5/6 窗口正超额，+50% 成本合并累计超额 +49.23%；30 只影子订单及信号 SHA-256 已绑定实验账本
- [x] qlib 全量 bin 已真实构建；首窗基线在模型训练前被 MLflow 3.14 拒绝旧文件目录跟踪后端，失败尝试已记实验账本。实验跟踪现固定为忽略目录内的本地 SQLite，不改模型、窗口、随机种子或 G0 判据
- [x] 六窗口 Alpha158+LightGBM 已真实完成：基准成本 5/6 窗口正超额，+50% 成本合并超额 +49.23%，两项 G0 回测条件均通过；影子步骤正确拒绝了与当前快照不匹配的哨兵报告。根因是旧代码哈希包含 Git HEAD，纯证据提交也会误使代码快照漂移；现将快照严格限定为可执行代码、配置、锁文件、模板、测试与构建入口，状态文档和不可变证据不再影响运行身份
- [x] Day 7 AlphaGen 历史结果已显式纠错（2026-07-16）：原 CSI300 100 候选报告曾以仅 1 个有效日频 IC 的表达式得到 RankIC 0.129759 并误判 `scale_stage1`；该路线结论作废但原账本不删。加入至少 252 日硬门后，同批重跑耗时 80.95 秒、峰值 RSS 6,488,637,440 bytes、73/100 失败，完整样本最大 RankIC 0.0242577，权威结论改为 `reduce_and_rerun`。此纠错不改变已通过的数据哨兵和 Alpha158 G0 基线，只作废 GP 放大结论。
- [x] G0 最终审计：S1-S9 全部 PASS、开发态 S10 NOT_APPLICABLE，未归因异常 0；六窗口正超额数 5；+50% 成本合并累计超额 +49.23%；数据账本 66,322 批、34,151,949 行逐批重哈希通过，`stage0_complete=true`、`next_phase_authorized=false`
- [x] 两项动手验证：S4 在 10,586,765 行上确认 VWAP/价格量纲恒等比 1.0、价格带外 0 行；AlphaGen CPU 吞吐实测成立，但选型结论按 252 日纠错结果执行，不再引用单日假优胜
- [x] fund_comparator.csv 于 2026-07-15 冻结：不看历史收益，按产品定义+成立日机械选取中证800/A500各3只；纳入、费用和R1替换规则见 `docs/FUND_COMPARATOR_SPEC.md`
- [x] 前瞻影子闭环代码与隔离预演（2026-07-16）：日增量 PASS 后由 Docker 守护在隔离子进程续跑完整 S1-S10、版本化 qlib、Alpha158 日频评分与飞书，严格按 10 个交易日才改变目标组合；下一交易日按真实开盘回填方向性涨跌停可成交性、换手和成本。G0 的 `data/qlib_bin` 永不修改，前瞻 qlib 以整树哈希校验后原子切换且仅保留当前/上一版。最终代码快照 SHA-256 `cfd0987240ad65a0eaa4128f85c039a348a2a0f63465f601ed33f75c7d53bd00` 下预演 S1-S9 PASS、S10 NOT_APPLICABLE，qlib SHA-256 `d4799c334516111956aecfd3004677d1aa5d32194c6cbbf34484283e793010ae`，799 个有效分数，LightGBM Booster SHA-256 `bc8f3c5cbd26e1146a1e998e57327f137c4f6b167ab261b6928b085e005f3632`，首日 `rebalance_due=true`，信号 SHA-256 `a9ffb6b250bfc94737fab42853dbba9fd2caa18c764b865f63adfe4cd1d99263`；同快照复验直接复用产物，实验账本前后均为 442 行，幂等 PASS。预演不写正式影子运行账本，不计入连续三日验收。
- [x] G1 准入裁判 `g1-v1`（2026-07-16、首次阶段 1 因子准入前冻结）：将量纲含混的 `DSR/t≥3.0` 明确为必须同时满足 `DSR≥0.95` 与方向冻结后的 `Newey-West(10) t≥3.0`；同研究家族全部总账尝试（含失败）机械计 N，裁判不能自报。PIT/shift 测试报告、候选代码/数据、证据、规则与实验总账均以 SHA-256 绑定；15 项门全部过才准入，普通不达标写不可变 REJECT，证据损坏则失败即停。独立 `factor_admissions.csv` 不污染实验 N；本项只建裁判，不启动因子生成、不改变阶段 1 授权状态。
- [x] Stage-1 有界施工预演（2026-07-16）：中证800、40 候选/1 代/seed 2，请求发现期 2016-01-01~2018-12-31；因本地日历从 2016 年开始且需 100 日回溯，实际起点显式为 2016-06-01。修复负日历索引、252 日门、白名单 parser、嵌套累计回溯 shift 哨兵、方向无关 `|RankIC|` 适应度/Top2 排序、确定性实验 ID 和按 benchmark 哈希版本化汇总。最终代码 SHA-256 `e03da3ac79a70d0d98e71c0424cf9eb1534b415124608ab89c6b4021871460d7`、数据 SHA-256 `978b297203dcc4bf3ee4a2746fed29622f4934b1e860abf95d58f60c1b6d1914`、benchmark SHA-256 `6e9958df32011cde56442ed8dd4ad8a64af2d227202c579d2f92cfd914f5e031`；4/40 有效，最优 `|RankIC|=0.0201423`，仍为 `reduce_and_rerun`。正确 Top2 `a4bdd797c134` / `b3a54f79cf6f` 的 DSR 分别 0.6332/0.8053、HAC t 0.3447/-0.0201、均仅 3/6 正向窗，候选净超额 0.2403/0.4014 均低于基线 0.5182，七门失败并 REJECT；正式库 0 插入。裁判复验 `reused=true`、准入账本行数不变。此前单日假优胜、回溯边界失败、有符号误排序和固定汇总冲突均保留为纠错审计，不覆盖。
- [x] G8 同风险口径 `g8-v1`（2026-07-16、首次三年裁决前冻结）：策略与六只冻结产品逐只按滞后一天的 60 日年化波动率降至该对较低风险，权重≤1、零收益现金、禁止缺失净值前填；三年窗至少 720 个共同日、风险覆盖率≥95%。只有三年篮子中位数净超额>0、至少 4/6 产品为正且三个年度子期至少 2/3 为正才 PASS，未满三年只能 NOT_READY。产品文件 SHA-256 `0d2c2e7657cc1375d18574f5bd7e94561d45d026d6e1dfb391cc85425616b8be`，合成规格 SHA-256 `e979946cee3eadf1274d5ed8ecfb9269a0c7ad4848cb0d0ea7178f508baedaa6`；机器入口 `make g8-spec`，当前不读取未来净值、不作提前结论。
- [x] 前瞻影子真实运行第 1 日（2026-07-16）：19:38 日增量以 5 个市场批次、15,613 行整日 PASS，数据快照 `e98ed68838c269d94a04f6bbf937aac718a59f90f1376f2799e7e4e07530eb0b`；连同三份 stock_basic 刷新共 8 个新原始 Parquet、21,147 行逐文件重哈希一致，实测 `.BJ` 0 行。S1-S9 PASS、S10 NOT_APPLICABLE，19:45 生成首个真实影子信号，qlib `d2aa8b37384844fd40ae59deff5ea6312abe5a171a41e437b9905cb2f6973b49`、模型 `0050a5d1f849fdf40e6dcb392a0b04f88ea036d98172c434d2e95432d045a1b4`、信号 `a7af3881ad1369731543414f6c2876a3d2544d859d65eb620bff67a40eac28b2`，`rebalance_due=true`、`on_time=true`。飞书补采开始/完成和影子开始/完成均投递 PASS；完整周期再次运行返回 NOOP，原始/日/影子/对账账本行数及通知数均不变。手工 `--once` 与后台轮询曾在影子非阻塞锁上正常竞争，却被 CLI 作为失败上报；现锁竞争结构化返回 BUSY/退出 0，真正异常仍失败，旧误报警记录保留不删。
- [x] 前瞻影子先导信号（2026-07-16）：已生成 1 个真实信号但尚无次日开盘对账；机器状态为 `signal_count=1`、`reconciled_trade_days=0`、`trial_ready=false`。该信号使用代码快照 `86e31bf28d2ac5f390d3cac904936202c722979585f40bdd775a88037c6c45a0`；其后锁竞争处理修复使当前代码快照变为 `c5c5ce55826edfc0d6fa816fa85c3aeb8cdaa8a6be504fdbd9edb5db1a140cc9`，故本日保留为有效先导证据，不计入当前版本连续稳定性计数。
- [x] 前瞻影子真实运行（2026-07-17）：19:43 日增量以 5 个市场批次、15,610 行整日 PASS，连同 3 个 `stock_basic` 刷新共 8 个新原始 Parquet、21,144 行，逐文件哈希一致且实际 `.BJ` 0 行；S1-S9 PASS、S10 NOT_APPLICABLE。先导信号 `20260716` 的次日开盘对账 30/30 可成交、PASS，但因代码快照属锁竞争修复前版本，仍不计入当前版本三次验收。19:50 当前代码快照 `c5c5ce55826edfc0d6fa816fa85c3aeb8cdaa8a6be504fdbd9edb5db1a140cc9` 生成 `20260717` 信号，`on_time=true`、`rebalance_due=false`；飞书增补开始/完成、对账、信号开始/完成共 5 次投递全部 PASS。该信号待 2026-07-20 开盘对账后才计当前版本第 1 次，因此当前正式计数仍为 0/3。
- [x] 前瞻影子当前版本第 1 次完整闭环（2026-07-17 → 2026-07-20）：19:37 日增量以 5 个市场批次、15,613 行整日 PASS；连同 3 个 `stock_basic` 刷新共 8 个新原始 Parquet、21,147 行，逐文件元数据与 SHA-256 重算一致，实际 `.BJ` 0。S1-S9 PASS、S10 NOT_APPLICABLE，代码/数据/qlib/模型/信号/对账哈希逐项绑定一致。`20260717` 信号在 `20260720` 对账 PASS；因两期均为同一非调仓目标组合，30 个持仓观察行全部有有效开盘数据但实际交易腿为 0，故 `trade_count=0`、换手 0、预计成本 0，目标持仓平均绝对开盘偏差 2.9554%。20:27 生成 `20260720` 信号，`on_time=true`、`rebalance_due=false`、当前代码快照一致；飞书开始/完成、对账、信号开始/完成 5 次均 PASS。同日重复影子周期返回 NOOP，原始/日/实验/影子/对账账本、信号、对账与通知数量均不变；零人工修数、失败 0、恢复 0。正式计数 1/3。
- [x] 前瞻影子当前版本第 2 次完整闭环（2026-07-20 → 2026-07-21，通知 WARN）：21:16 日增量以 5 个市场批次、15,615 行整日 PASS；连同 3 个 `stock_basic` 刷新共 8 个新原始 Parquet、21,150 行，逐文件元数据与 SHA-256 重算一致，实际 `.BJ` 0。S1-S9 PASS、S10 NOT_APPLICABLE，代码/数据/qlib/模型/信号/对账哈希逐项绑定一致。`20260720` 信号在 `20260721` 对账 PASS；同一非调仓目标组合仍无交易腿，30 个持仓观察行均有有效开盘数据，`trade_count=0`、换手 0、预计成本 0，平均绝对开盘偏差 1.6790%。21:53 生成 `20260721` 信号，`on_time=true`、`rebalance_due=false`、当前代码快照一致。飞书日增量开始投递首次遭 `NETWORK_TimeoutError`，其后日增量完成、对账、信号开始和信号完成连续 4 次 PASS；按已冻结“告警通道故障不得改变核心任务退出码”语义保留原始 FAIL 并记通知 WARN，后续成功证明通道自行恢复，未手工补发或改账。重复影子周期返回 NOOP，各账本、信号、对账与通知数量均不变。正式计数 2/3；`forward_report.json` 虽已 `trial_ready=true`，仍不得提前完成。
- [x] 前瞻影子当前版本第 3 次完整闭环及 P0 验收（2026-07-21 → 2026-07-22，通知 WARN）：19:37 日增量以 5 个市场批次、15,615 行整日 PASS；连同 3 个 `stock_basic` 刷新共 8 个新原始 Parquet、21,150 行，逐文件行数与 SHA-256 重算一致，实际 `.BJ` 0。S1-S9 PASS、S10 NOT_APPLICABLE；`20260721` 信号在 `20260722` 对账 PASS，同一非调仓目标组合仍无交易腿，30 个持仓观察行均有有效开盘数据，`trade_count=0`、换手 0、预计成本 0，平均绝对开盘偏差 1.7414%。19:45 当前代码快照 `c5c5ce55826edfc0d6fa816fa85c3aeb8cdaa8a6be504fdbd9edb5db1a140cc9` 生成 `20260722` 信号，`on_time=true`、`rebalance_due=false`，信号与产物哈希复核通过。飞书日增量开始、对账、信号开始和信号完成 4 次 PASS，日增量完成投递一次 `NETWORK_TimeoutError`；后续三次 PASS 证明通道自行恢复，核心任务按冻结语义 PASS、通知 WARN。受控重复运行返回 NOOP，五类账本、信号、对账产物与通知数量/哈希均不变；全部运行账本 operator 为 `docker-scheduler`，零人工修数。至此当前版本正式闭环 3/3，完整证据见 `docs/P0_FORWARD_ACCEPTANCE_20260722.md`。
- [x] 验收后健壮性复核（2026-07-22）：飞书瞬时网络、HTTP 408/425/429/5xx 和响应解码异常采用最多 3 次有界退避；同一逻辑消息固定 `message_id`，每次尝试追加保留，后续成功显式记 `recovered=true`。永久配置/API 错误不重试，通知结果仍不改变核心任务退出语义。167 项全量测试、Ruff、compileall、依赖和差异检查通过；完整语义与证据见 `docs/P0R_NOTIFICATION_ROBUSTNESS_20260722.md`。
- [x] P0.5 模拟组合与前瞻绩效闭环（2026-07-23）：初始资金 500,000 RMB 与 `paper-v1` 策略 SHA-256 `eaa341b5a3eee94347c7a8453a3e52f1986e3707abfbb6bb69a6d9298c320cc8` 保持冻结。四日 BACKFILL 后，Docker scheduler 自然完成 `20260722 → 20260723` 首个 FORWARD：日增量、S1-S10、次日对账、24 个账户事件、会计恒等、北交所排除、策略/代码/数据/产物哈希、飞书开始/完成均通过；查询返回 `forward_status=PASS/forward_observation_count=1`。独立重放累计 5 日、174 事件、30 历史订单、22 历史成交 PASS；机器验收 PASS。受控重复运行全链 NOOP 且 8 类账本/运行文件、通知、信号、对账与账户产物哈希和行数不变；自然通知重试及事件中断 fixture 覆盖两类恢复。完整证据见 `docs/P05_FORWARD_ACCEPTANCE_20260723.md`。当前继续自动积累 FORWARD，仅以 `OBSERVING` 展示，不把一天结果视作策略有效。
- [x] P1 资金流全量回填与特征准备（2026-07-24）：在读取任何资金流效果前冻结 `p1-moneyflow-v1` 六候选、T+1、残差暴露、W1—W6、成本和 G1 停止规则。全量补齐 2016-01-04 至 2026-07-23 共 2,563 个官方交易日，新增 2,551 个不可变批次、10,564,186 行，幂等复跑 0 新增。严格单日审计 2,517 日 PASS、46 日 FAIL；46 日显式重采均内容稳定、0 修订，`moneyflow-quality-v2` 在不放宽单日门的前提下整日隔离，全期/发现期/W1—W6/压力期/最长缺口全部 PASS。形成 10,459,212 行 T+1 原始候选、3,169,528 行核心残差、2,335,871 行正式残差及 1,164,697 行六窗 Alpha158 预测缓存，主键重复、血缘违规和 `.BJ` 均为 0；canonical 残差数据快照 `9f9e72bc0e4de0c0d231455b278d6cb536eb5da59124e03eaaea29066929477e`，生产代码快照保持 `261f58...`。完整证据见 `docs/P1_MONEYFLOW_FEATURE_ACCEPTANCE_20260724.md`。
- [x] P1 六候选正式效果比较与 G1 裁决（2026-07-24）：完成 W1—W6 × 正常费用/双倍成本/额外双边 10bp 共 108 个证据单元、三段压力期、37 个质量警告日 `NOT_FOR_VERDICT` 稳定性诊断和逐候选 `g1-v1`。两代工程失败尝试均未删除，最终同家族实验 N=18；第三代六候选均为 4/6 正向 OOS 窗，但 RankIC 保留率、增量净 ICIR、增量净超额、DSR 和 HAC t 共同不通过，机器结论全部 REJECT，正式库仍为 0。最终汇总 SHA-256 `9d6e8580f03748d42d9a81195f6a5b2146d111b9400afe175e02ba9789bbde24`；完全相同复跑六类产物/账本均 `reuse=true`，实验 18 行、准入 12 行不变。41 项 P1 隔离测试、184 项全仓测试、Ruff、compileall、`pip check` 通过，生产代码快照精确保持 `261f58b858dbc46d49ffb9f623e8868dcb10891cc2dadd2292728da6de7eb4fa`。完整证据见 `docs/P1_MONEYFLOW_EXPERIMENT_ACCEPTANCE_20260724.md`。
- [x] 2026-07-23 生产快照失配故障闭环：两次日周期在 `paper_forward_acceptance` 因 FORWARD 产物与当前受控代码快照不一致而失败，scheduler 后续恢复 healthy/PASS；现有不可变证据不能还原具体漂移文件，但能确认整仓开发目录挂载使无发布动作的受控文件变化可能进入生产运行时。RCA 已入 `docs/INCIDENT_20260723_CODE_SNAPSHOT_MISMATCH.md`；P2 与 Web 后端施工前必须先通过不可变 release 快照、显式只读挂载、发布前哈希门和回滚证据组成的生产/开发隔离门禁。
- [x] 生产 scheduler / 开发工作树发布隔离门禁（2026-07-24）：生产改为内容寻址不可变镜像、只读根和仅 `data/ledger/logs` 三处持久化挂载，无整仓、`.git` 或 Docker socket；开发探针证明既有镜像身份不受宿主改动影响，跨快照启动在无新交易日时 fail closed。首次真实运行暴露镜像无 `.git` 而哨兵仍调用 Git 的兼容故障，失败账本与飞书告警保留；最小修复后 previous D/current E 均同时绑定代码快照与嵌入 Git 提交并完成 E→D→E 回滚。`20260724` 最终 daily、对账、S1-S10、信号、模拟仓第 2 个 FORWARD、独立重放、acceptance、通知恢复和全链 NOOP 幂等均 PASS；scheduler healthy。完整验收与 RCA 见 `docs/SCHEDULER_RELEASE_ACCEPTANCE_20260724.md`、`docs/INCIDENT_20260724_RELEASE_GIT_IDENTITY.md`。
- [x] P2-0 科创50历史数据/PIT 可施工性门禁（2026-07-24，NO-GO）：结果前提交并推送 `e524f04`，冻结 `000688.SH`、独立 dataset/config/model/benchmark/signal/ledger、Top10/n_drop2、10 日调仓、成本/流动性/集中度/暴露和三个年度 OOS 窗。Docker 串行采集 8 个年度日线分片 + 80 个月度权重分片，88 项各双查一致后新增 88 个不可变批次、5,190 行，复跑 0 追加；日线 2020-07-23 后 1,456/1,456 覆盖，权重 72 个已完成月快照均 50 只、权重和 99.996%~100.005%，重复、未知代码、`.BJ` 和即时修订均 0。源端首份权重 2020-07-31，按 T+1 最早 2020-08-03 生效，冻结起点缺 7 个交易日；接口又无发布时间/版本/修订原因，PIT 数据结论 NO-GO。未建 qlib、未看策略效果、未改生产 scheduler。证据见 `docs/P2_STAR50_DATA_FEASIBILITY_ACCEPTANCE_20260724.md`。
- [x] P2-0 科创50官方成员谱系数据门（2026-07-24，v2 GO）：永久保留 v1 NO-GO 后，在联网取证前提交并推送 `3013710` 冻结 `p2-star50-protocol-v2`；Tushare `index_weight` 只作集合对账，不使用权重数值或月末日期代替官方生效日。串行取得并哈希固化 10 页上交所公告归档、25 个候选页面和 22 个附件；官方首批 XLSX 完整给出 50 只，发布证据允许最早可用日 2020-07-23。24 期调整公告含 23 期共 82 对替换、1 期明确无变动；按公告日/生效时点重建 2020-07-23~2026-07-24 的 1,456 个交易日、72,800 行，每日严格 50 只，`.BJ=0`，与 72/72 个 Tushare 月度成员集合精确一致。机器分层为 `official_lineage_complete=true`、`tushare_crosscheck_pass=true`、`pit_constructible=true`、`engineering_complete=false`、`strategy_results_inspected=false`、`production_authorization=none`。未建 qlib、未看策略效果、未改生产 scheduler；证据见 `docs/P2_STAR50_OFFICIAL_LINEAGE_ACCEPTANCE_20260724.md`。
- [x] P2-1 科创50独立工程门（2026-07-24，工程 GO）：真实数据施工前提交并推送 `00bc030` 冻结协议并绑定 v2 五项证据哈希；新增 2020-07~2026-06 的显式 72 月份域，fixture 证明“缺月 + 另一月双快照但总数不变”仍 fail closed。official daily membership 唯一驱动 72,800 个成员日和动态 instruments；72,719 个行情 bar + 81 个全天停牌使覆盖 100%，daily_basic/申万 L1 PIT 均 100%，重复、上市前、退市后、无法解释缺口和 `.BJ` 均为 0。独立 qlib 共 1,293 文件、整树 SHA-256 `b8f736ef...b78729`，双遍哈希一致并复用；完全合成 fixture 打通 dataset/qlib/Alpha158/LightGBM/TopK/backtest，120 个观察日中 110 个存在非现金持仓。机器结论 `engineering_complete=true`、`strategy_results_inspected=false`、`strategy_effective=NOT_EVALUATED`、`production_authorization=none`；未在真实 provider 上训练、预测、回测或查看效果，证据见 `docs/P2_STAR50_ENGINEERING_ACCEPTANCE_20260724.md`。
- [!] P2-2 科创50原历史效果裁决（2026-07-25，方法失效但证据保留）：任何真实 handler/model/backtest 前提交并推送 `ed5b1b0`，原三窗、压力、成本数值及 54/54 确定性产物仍可复算；但后续审计确认标签 t+11 成熟越界进入 valid/test、次日开盘判断读取当日收盘 flags、395 笔卖单中 14 笔超过冻结 5% 容量（最大 11.3038%）。因此永久分列 `original_p2_2_model_valid=false`、`original_p2_2_execution_valid=false`，旧 `historical_effect_gate=NO_GO` / `strategy_effective=REJECT` 仅描述失效方法输出，不能支持权威决策。旧提交、报告 `94c458ae...f5ce9`、manifest、两账本和 115 文件整树不修改、不删除；见 `docs/P2_STAR50_EFFECT_INVALIDATION_ADDENDUM_20260725.md`。
- [x] P2-2C 科创50综合方法纠错（2026-07-25，权威 NO-GO/REJECT）：结果前提交并推送 `c6fbbaf`，只修复 train/valid 最后 11 个信号日 purge、执行日 raw open/pre_close/tick 与 prior-close 时钟、买卖双向信号日 20 日中位 amount 5% 容量；其他 Alpha158/LightGBM seed42 超参、窗口/test、压力映射、Top10/n_drop2、调仓、成本和门槛逐字段不变。三窗 242/242/243 日、各 25 次调仓，基础净超额 -8.51%/-19.25%/-23.87%；727 日 pooled 基础/1.5x/2x/额外双边10bp 为 -52.97%/-54.59%/-56.19%/-56.02%，正窗 0/3；W1/W2/W3 与 microcap_2024 回撤越过 20%。纠错基础 909 笔和全部场景/压力 3,856 笔的买卖容量违规均为 0；84 个名字跨信号日继续卖出。合法 CSI800 对照缺失使分散化 `NOT_EVALUABLE`。两遍 54 份 model/prediction/NAV/trade/holding 物理哈希完全一致；机器终态 `authoritative_historical_effect_gate=NO_GO`、`strategy_effective=REJECT`、`production_authorization=none`。完整证据见 `docs/P2_STAR50_EFFECT_CORRECTION_ACCEPTANCE_20260725.md`。
- [x] P4-0 科创100官方谱系与源数据门（2026-07-26，NO-GO）：结果前提交并推送 `7750d65` 冻结 `000698.SH` 和一手来源纪律；40个Tushare请求即时双查稳定，718/718指数日线、35/35个月度100只集合、首批官方100只和V1.0→V1.1规则版本均PASS，复跑新增请求0。官方归档扫描5页、16个候选页面和17个附件，12期季度调整附件均可解析但科创100历史成员对材料为0；Tushare显示的12次集合变化只作二级诊断，不能补造官方公告日、生效日和版本。机器终态 `official_adjustment_lineage_complete=false`、`pit_constructible=false`、`strategy_effective=NOT_EVALUATED`、`production_authorization=none`；未进入qlib/模型/回测/信号。证据见 `docs/P4_STAR100_DATA_FEASIBILITY_ACCEPTANCE_20260726.md`。
- [x] D1-2A LLM 真实调用前冻结（2026-07-25，GO_PREEXECUTION_ONLY）：官方模型/价格和请求/响应/错误合同、system prompt、五主题模板、同主题全历史反馈、10 条知识 manifest、受限 DeepSeek 适配层、累计费用熔断和 transport 恢复账本均已冻结。当前 `execution_authorized=false` 时真实 transport、运行时 secret 加载和网络在创建前被拒绝；宿主脱敏测试仅作 `.env` 秘密与 Git 跟踪文件的不回显比对。断网 Docker 同时证明成功恢复不二次请求、429 有界恢复和读超时后 `BILLING_UNCERTAIN` 禁止重发。全仓 247 PASS、Docker 对抗 29 PASS；API/行情/G1/生产授权均为 0。证据见 `docs/D1_LLM_FACTOR_PREEXECUTION_ACCEPTANCE_20260725.md`。
- [x] D1-2B 首批真实生成（2026-07-25，GO_D1_3_REVIEW）：结果前冻结总授权 `$10`、本批恰好 40 个完成响应和 `$1` 熔断，只读 2016-06-01—2018-12-31 发现期，W1—W6/压力期/G1/前瞻/生产禁读禁跑。首份完成后控制流 fail closed；恢复附录锁定原响应、账本字节前缀与产物哈希，仅修独立反馈和连续恢复，从序号 2 完成剩余 39 份，无重发或计费不确定性。终态 40/40：36 `DISCOVERY_EVALUATED`、2 `duplicate_ast`、2 `sandbox_rejected`，费用 `$0.076626207`；无密钥、断网、只读重放为 `idempotent_reuse=true / external_api_calls_this_run=0` 且 160 文件证据束哈希不变。机械 Top2 已锁定但未解盲 W1—W6或运行 G1；`strategy_effective=NOT_EVALUATED`、`production_authorization=none`。证据见 `docs/D1_LLM_FACTOR_EXECUTION_ACCEPTANCE_20260725.md`。
- [x] D1-3A Top2 盲态对抗复核及语义纠错（2026-07-25，STOP_SEMANTIC_CONTRACT_VIOLATION）：8/8 响应结构 schema PASS，但自由文本审计为 5 PASS/3 FAIL；三份以正文建议公式/构造变体却声明未提变体。按 8/8 有效且不补位规则停止，不进独立人工闸，不读 W1—W6，不运行 G1。
- [x] D1 语义合同恢复工程门（2026-07-26，GO_SEMANTIC_GATE_ENGINEERING_ONLY）：确定性正文/结构一致性、完整 DSL、回看期、修改/业绩/准入和模糊文本 fail-closed 门已通过 339 项全仓、13 项断网 Docker 与旧批 5/3 精确复核；零 API/费用，不改变旧 STOP，未来新批仍须新指令与新协议。
- [x] M1-1 科创50价量因子发现批执行前门（2026-08-01，GO_LIVE_DISCOVERY_ONLY）：独立协议与执行 release 均已在结果/API 调用前冻结并推送；发现期固定 2020-08-03 至 2022-12-15，封存验证窗从 2023-01-03 开始。最终镜像 `sha256:7729c89e...411c`、内嵌代码快照 `180ad8fc...4473`，断网输入门为 577 日/28,850 成员日且 `.BJ=0`；宿主全仓 422 PASS、镜像专项 18 PASS、依赖与发布清单 PASS。当前 provider 调用和费用仍为 0，只允许后续恰好 40 个 DeepSeek 完成响应、1 USD 硬熔断和发现期机械 Top2；验证/G1/模型/组合/生产均未授权。证据见 `docs/M1_STAR50_FACTOR_PREEXECUTION_ACCEPTANCE_20260801.md`。
- [x] M1-1 科创50价量因子发现批（2026-08-01，GO_DISCOVERY_TOP2_LOCKED）：40/40 响应与 80 个传输事件完整，14 条发现评价、6 条 schema 拒绝、20 条语义拒绝，费用 `$0.071831434`；机械 Top2 锁定为序号 28（流动性/成交量）和序号 11（反转/均值回归）。终态组装曾因共享 experiments 未按 protocol 过滤而 fail closed；恢复附录先行推送，`eff0bea` 只修精确 protocol 一一对应，零新增 provider 调用、候选/指标/账本不变。无密钥复跑外部调用 0 且四哈希不变；验证/G1/模型/组合/生产均未运行，策略仍 NOT_EVALUATED。证据见 `docs/M1_STAR50_FACTOR_DISCOVERY_ACCEPTANCE_20260801.md`。

## 后台任务
运行态以 `logs/pipeline/stage0_20260715.jsonl` 和 `ledger/ingest_batches.csv` 为准；自动流按 as-of+代码+数据快照及逐批文件哈希安全续跑。

- 飞书自定义机器人作为运行守护与告警通道：流水线启动/失败/完成和长步骤心跳均发送签名消息；凭据仅在本地 `.env`，投递结果脱敏记录于 `logs/notifications/`，告警通道故障不得改变核心任务退出码。2026-07-16 真实连通性、流水线启动与完成三类消息均投递 PASS。
- Docker `scheduler` 在每轮日增量对账后调用前瞻影子子进程；无日增量 PASS 时轻量 NOOP，有 PASS 时按「次日对账 → 当前快照门禁 → 版本化 qlib → 模型与信号」顺序失败即停。运行账本为 `ledger/shadow_runs.csv`、`ledger/shadow_reconciliations.csv`，汇总为 `logs/shadow/forward_report.json`；不连接券商、不产生真实订单。

## 预注册实验（v0.5.4 封笔后新增，效力以本文件 git 时间戳为准）
- **阶段 1 第四臂：CogAlpha-lite**（LLM 代码级因子进化，源自 arXiv 2511.18850 / ACL 2026 评审建议，2026-07 预注册）：
  - 规格：4-6 个研究主题（价值质量/量价/流动性/风险脆弱/风格状态），LLM 提出与变异代码，AST 白名单沙箱执行（禁文件/网络/动态执行/未声明库）；与 GP 臂同数据、同成本情景、同因子预算。
  - 记账：每一次生成尝试（含失败/被沙箱拒绝）计入实验总账 N；失败原因结构化回灌下一轮 prompt。
  - 准入：走 G1 五项原样；「可陈述经济含义」由人陈述，LLM 的经济性判断仅作研究记录不作准入依据。
  - 止损：G2 同款——相对同预算 GP 臂增量 ICIR 持续为负或与 GP 库 |ρ|>0.7 → 停止投入。
  - 护栏：GP 臂先行；共用阶段 1 的 6-8 周硬上限；沙箱/prompt 设施窗口内建不完 → 自动顺延阶段 2 与 RD-Agent 并列，不得挤占第 8 周决策点。

## 观察与借鉴项（不改冻结基线）
- CogAlpha（arXiv 2511.18850，仅论文宣称级）三项借鉴：①防信息泄漏单元测试 → 阶段 2 RD-Agent 产出抽检自动化（与 S5 同精神）；②失败样本回灌 prompt（每代最差样本+原因分析入 prompt）；③GP 滚动重挖时按主题分批（不同算子子集/种子表达式）注入事前多样性 → 阶段 1 小实验。
- 观察：CogAlpha 代码开源状态；若开源且出现独立复现，作为「代码级 LLM 进化」范式的 G7 通道候选。已确认 ACL 2026 收录（场馆升级，证据等级仍为作者自测）；其成绩为 20 因子+LightGBM 组合的整体结果，非单因子能力。
- LLM 持续研究线的公开参考已扩展为 Alpha-GPT、AlphaAgent、RD-Agent-Quant、Chain-of-Alpha、CogAlpha、QuantaAlpha、FactorEngine 与 AlphaQT-Bench。当前判断为“研究范式与开源组件已较完整、公开长期实盘证据仍不足”；只借鉴可验证组件，成熟度和作者收益不得替代筛微 G1 与真实影子结果。详见 `docs/LLM_RESEARCH.md`。

## 待答点
- F1-0 v1的`NO-GO`和旧证据永久保留；F1-0R以最新共同可用年报语义通过数据门。F1-1六项固定方向
  均成立，但G1全部REJECT、正式库0插入；不得把数据GO写成因子有效，也不得以方向门PASS冒充准入。
  本家族不做结果后变体；未来新的基本面机制须另立家族并纳入本次N=6。
- L2-0只完成未来新批可复用的紧凑审查合同工程门；它不改变M1-2/M3-3的STOP，不允许补发剩余响应
  或进入M1-3/M3-4。未来启动真实审查仍须先有独立新因子批、结果前候选绑定和用户明确API/费用授权。
- M1-0多股票池底座已GO；M1-1科创50价量因子批已锁定机械Top2。M1-2第1/8份响应因自由文本语义
  合同失败而权威`STOP_M1_2_REVIEW_CONTRACT`，没有候选裁决权，策略仍`NOT_EVALUATED`；M1-3验证/
  G1不获授权，不续跑、不补发、不递补。科创100/200、科创综指和规则型池仍先过各自数据门。
- P2 已形成互不覆盖的证据层：v1 永久 NO-GO 证明 Tushare 不能单独充当 PIT 真身；v2 官方成员谱系数据门 GO 证明 2020-07-23 起的数据可行；P2-1 工程 GO 证明独立数据集、qlib 和 synthetic 通路可运行；原 P2-2 数值可复算但模型/执行方法均失效；P2-2C 三项方法纠错后的权威历史结论为 `NO_GO/REJECT`。不得把效果失败或原方法缺陷表述成前述数据/工程门失败。
- 后台结果路线已完成 P2-2C 权威纠错并停止该基线。P1 六候选和 P2-2C 均保持 REJECT；P2 不进入前瞻观察或生产，不调参、不追加变体。P3-0 查询底座、P3-1 三页、P3-2A/P3-2B 运维页、P3-3B/P3-3C 因子工厂和 P3-4A/P3-4B 模型回测目录与页面均已 GO，本机 Web 1.0 七类页面可用且不反向改后台口径。
- P4-0 已证明科创100基础源可采，但当前公开官方归档不足以闭合历史调入/调出谱系；P4-1因此阻断，策略保持`NOT_EVALUATED`，不得表述为科创100无效。后续只有取得带发布时间和版本/修订证据的官方历史成员源后，才能结果前另立恢复协议；从未来季度前瞻固化官方拟生效样本只能覆盖未来，不能自动修复既有12期。
- P0.5 初始资金人民币 50 万元的自然 `FORWARD` 已累计 2 个账户日，后续由 scheduler 持续追加。50 万元下首个真实信号有 8 个目标因主板 100 股/科创板 200 股门槛无法买入；这是实际账户约束结果，不允许用碎股或目标权重补齐。两日前瞻仍只证明工程运行，不把四日 BACKFILL 或短样本净值用于策略裁决。
- P1 已于 2026-07-24 完整结束：长期主源仍为 `tushare.moneyflow`，`moneyflow-pit-v1` 固定下一交易日可用；46 个稳定失败日继续按 `moneyflow-quality-v2` 整日隔离。六候选同预算比较均未在 Alpha158 之外形成可准入增量，全部 REJECT，正式库 0 插入；不增加本家族变体、不看结果调门槛、不接生产。数据层可作为未来独立预注册家族的只读输入，但须把既有 N=18 纳入多重检验背景。详见 `docs/P1_MONEYFLOW_EXPERIMENT_ACCEPTANCE_20260724.md`。
- 官方规则复核发现沪深主板风险警示股票自 2026-07-06 起均由 5% 调整为 10%。当前中证800正式信号不含 ST，故不推翻 P0 三次结果；P0.5 以按板块和日期分段的 `paper-v1` 执行规则处理，不回改冻结的历史模型与 G0 门禁。后续若生产信号范围允许 ST，须另立数据/门禁修订评审，不能沿用旧 `limit_rules.st=0.045` 冒充现行实盘规则。
- 飞书连续两个交易日各有一次网络超时已完成 P0-R 修复：最多 3 次有界重试、稳定消息身份、逐次留痕和恢复标识均已回归。生产自然投递继续观察；飞书不提供本项目可依赖的恰好一次语义，超时重试的同 ID 重复消息风险须在 Web 与运维审计中保留。
- D1-3A 的 8 份响应虽全部 schema PASS，但 3 份正文违反“禁止替代公式/变体”合同；权威终态已由原机器 GO 改为 `STOP_SEMANTIC_CONTRACT_VIOLATION`。2026-07-26 已补齐并验收未来新批所需的语义一致性工程门，但它不回溯挽救旧批。本批不补响应、不递补候选、不进独立人工闸、不读 W1—W6、不运行 G1；未来重启仍必须另立新批和结果前协议，不能用剩余额度静默修补。
- 原始数据异地备份等用户找到远程服务器后再施工；取得服务器地址和明确授权前，不写入项目外目录，也不以同机副本冒充备份。
- G8 公式已冻结；G8-1R 已完成六只产品监管 HTTP 主源的 54 条不可覆盖证据和两遍幂等/断网复核，
  但状态上限仍为 `PRIMARY_CAPTURED_UNAUTHENTICATED`。管理人 HTTPS 交叉核验、费率有效期谱系和
  裁决账本尚未施工；完成前不得升为 `VERIFIED`、构造总收益或运行 G8，也不能以聚合平台数据冒充
  权威源。
- 本机 `.env` 的 `TUSHARE_TOKEN` 已就绪且未入 git；阶段 0 自动流已完成，后续仍可按代码+数据快照和不可变账本安全续跑。

## 作废记录
- 2026-07-15：作废“京东方A（000725.SZ）2023-04-29 为 S5 永久更正样本”。真实定向查询显示该期间 type 5 为 0 行，默认返回仅有同一 f_ann_date 的 type 1/update_flag 0 与 1，无法构造时点区间；官方口径说明 type 5 才是调整前保留值。全市场 20221231 扫描找到 136 组公告日可分隔且数值变化的沪深配对，改用 `688502.SH/20221231`（旧 2023-02-16 type 5/update 0，新 2023-03-08 type 1/update 1）。此改判修复失效数据样本，不修改 G0-G9/C0 判据。

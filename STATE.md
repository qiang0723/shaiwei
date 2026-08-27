# STATE — 筛微施工状态（git 为真身，会话记忆为草稿）

> 每会话开工先读本文件；收工必更新「当前进度」与「待答点」。改判旧口径须显式作废并注明日期。

## 2026-08-27 · R2D-R2 发布工程就绪，等待精确执行授权

- 20260827 旧生产自然周期完整 PASS：daily 5批/15,648行、真实批次 `.BJ=0`、S1—S9 PASS/
  S10 NOT_APPLICABLE、shadow及Top30/Top20双账户PASS、飞书9/9 PASS、零人工修数；旧 scheduler、
  候选和release current/previous身份未漂移。
- R2入口提交`7740dd7`已先推送；独立config绑定双账户最新产物、R2C-R1 fixture、旧生产和
  controller组件`a2cb5d9e...0bdd`。唯一变化为20260828启动检查后移至16:40—19:00。
- 精确scope=`a2e66d95dc13d3ea71d9068a880d9074300955c82a553fa867c985bfa2b729d5`，动作
  `R2D_R2_START_CURRENT_20260828_ONCE_AFTER_CADENCE_MARGIN`。当前只到
  `GO_RELEASE_READY_NOT_EXECUTION_APPROVAL`；未build、未重复fixture/Phase A、未start/restart、未读密钥、
  未访问外网。用户逐字批准scope前停止，成功/失败均不得重跑。见`docs/R2D_R2_RELEASE_READY_20260827.md`。

## 2026-08-27 · R2D-R1 预检失败关闭并冻结 R2D-R2 恢复方向

- 16:05:07唯一只读预检因旧 scheduler 健康证据时间为15:58:45、早于冻结的16:00下限而
  `BLOCKED_BEFORE_MUTATION`；scope `bb74c299...119a`永久关闭，不重试、不顺延。候选未启动，旧生产
  原容器/镜像持续healthy，业务、密钥、外网和生产mutation均为0。
- 旧 scheduler 于16:29:00自然刷新同一`noop / 20260826`，定位为约30分钟探测节拍与16:05自动触发
  未对齐，不是候选、数据、锁或业务故障；后续证据不用于重开R1。
- R2D-R2只允许把下一交易日的一次性检查后移到16:40—19:00；16:00后新鲜noop、目标日三类账本0
  行、readiness唯一、候选/旧生产/fixture/四挂载等门全部保持。须等20260827自然周期完成后绑定最新
  双账户产物、最终HEAD和组件哈希，另立R2 config/scope并再次获用户逐字批准。见
  `docs/R2D_R1_EARLY_PREFLIGHT_BLOCK_20260827.md`与
  `docs/R2D_R2_POST_CADENCE_RECOVERY_PROTOCOL_20260827.md`。

## 2026-08-26 · R2D-R1发布工程完成并生成精确启动scope

- 终态`GO_RELEASE_READY_NOT_EXECUTION_APPROVAL`。恢复控制器以`noop / prior-day + 目标日daily/shadow/
  paper全状态0行`替换结构性不可能的`waiting_source`门；恢复协议禁止重复Phase A，旧协议仍原样兼容。
- 实现`106a843`已先推送，组件SHA=`8c4660c2...20e5`；专项28、全仓1,925 PASS，Ruff/diff-check
  PASS。Docker build/fixture/promote/start/restart、业务、ledger、secret、网络均为0。
- 精确scope=`bb74c299...119a`，动作
  `R2D_R1_START_CURRENT_20260827_ONCE_AFTER_LEGACY_NOOP_BOUNDARY`，只允许20260827 16:05—19:00
  全部门通过后启动一次同一候选；用户未逐字批准前停止，窗口或身份漂移即失效。见
  `docs/R2D_R1_RELEASE_READY_20260826.md`。

## 2026-08-26 · R2D-R1旧生产19:30时钟证据恢复协议冻结

- 20260826旧生产自然周期已完整PASS：daily 5批/15,649行、raw `.BJ=0`，shadow S1—S9 PASS/
  S10 NOT_APPLICABLE，Top30/Top20及开始/完成飞书均PASS；候选未启动，旧生产身份不变。
- 原R2D Phase B窗口16:05—19:00要求旧容器形成`waiting_source / 20260826`，但旧镜像实际
  `ready_hour/minute=19:30`，该证据在窗口内结构性不可能出现。原scope于19:00过期、mutation=0，
  永久不得重用或补造；这不是数据、锁或候选失败。
- R1唯一变量预注册为20260827用`当日16:00后新鲜noop / 20260826 + 目标日三类业务账本0行 +
  readiness仅[20260827]`证明旧writer未进入目标日；Phase A、候选、fixture、身份、四挂载和首日门
  全不变。当前只授权源码/测试/config/docs，启动仍须实现推送后新精确scope和用户批准。见
  `docs/R2D_SCHEDULER_LEGACY_CUTOFF_RECOVERY_PROTOCOL_20260826.md`。

## 2026-08-25 · R2D Phase A no-start提升完成

- 用户精确批准scope `4145d601...8292`；20:45只读预检`READY_TO_PREPARE`，20:45唯一执行返回
  `PREPARED`、`started=false`，发布审计SHA=`45bf0302...12a37`。Phase A关闭不重复。
- release current现为named-volume候选`b7565001...baa72`，previous为旧生产`722f63de...13b76`；旧
  scheduler仍是原容器`183b8c6c5edd`、原三bind挂载、原代码快照且healthy，未重启、候选未启动。
- 下一节点仅为20260826 16:05—19:00 Phase B。必须先由旧容器闭合
  `waiting_source / 20260826`且readiness只暴露该交易日；任一身份、双账户或fixture漂移均在mutation前
  阻断。当前真实候选业务、手工跑批、secret、外网、Web、模型与策略改动均为0。

## 2026-08-25 · R2D发布工程与精确scope准备完成

- 终态`GO_ENGINEERING_READY / EXECUTION_NOT_AUTHORIZED`。20260825自然日增量、影子及Top30/Top20
  两账户均PASS；本地冻结交易日历确认20260826，检查仅使用状态、日期和哈希，未读策略效果。
- 真实guard绑定R2C-R1候选、旧生产、fixture四组哈希、控制器组件身份和两账户最新FORWARD；两阶段
  冻结为20260825 20:45—23:30只promote不启动、20260826 16:05—19:00等待旧容器
  `waiting_source`后才start。
- 精确scope=`4145d601...8292`，动作
  `R2D_PROMOTE_NO_START_20260825_AND_START_20260826_ONCE`。用户未逐字批准前不得执行；窗口过期或
  任一身份漂移即失效，不允许顺延复用。
- R2D专项10、架构13、全仓1,918 PASS；Ruff、compileall、pip check、差异与脱敏检查PASS。当前
  build/fixture/promote/restart/业务/ledger/secret/网络均为0。见
  `docs/R2D_SCHEDULER_PROMOTION_ENGINEERING_ACCEPTANCE_20260825.md`。

## 2026-08-25 · R2D控制器与候选运行时身份分离勘误

- 候选在R2D控制器施工前已完成唯一fixture，故最终仓库snapshot不可能仍等于候选snapshot；禁止为
  追求相等重建候选或重跑已关闭scope。
- 候选继续精确绑定`55f98e7`/`88e3f471...abec0`/`b7565001...baa72`及原fixture；宿主控制器另绑
  最终HEAD和组件SHA，并机器证明候选→控制器差异只含四个release控制文件、测试、R2D config/docs，
  不含Docker/Compose/settings或scheduler业务路径。
- 本勘误替换原scope中的仓库snapshot相等要求，其他边界不变；Docker/生产/业务/ledger/secret/网络
  均为0。见`config/r2d_scheduler_controller_identity_addendum_v1.yaml`与
  `docs/R2D_CONTROLLER_IDENTITY_SPLIT_ADDENDUM_20260825.md`。

## 2026-08-25 · R2D旧生产等待源证据勘误

- 原协议推送后实物核对确认旧生产snapshot `4e5244b6...2708`尚无scheduler timeline，故不可要求
  其提供16:00闭合timeline，也禁止补造。
- 只替换证据载体：Phase B前必须由旧容器现有`logs/scheduler/health.json`证明目标日16:00之后
  `waiting_source`且detail=唯一目标交易日；候选timeline从首个自然cycle起验。其余R2D冻结边界不变。
- 勘误发生在源码实现和执行scope之前；Docker/生产/业务/ledger/secret/网络均为0。见
  `config/r2d_scheduler_named_lock_promotion_addendum_v1.yaml`与
  `docs/R2D_LEGACY_WAITING_SOURCE_EVIDENCE_ADDENDUM_20260825.md`。

## 2026-08-25 · R2D结果盲生产提升协议冻结

- 候选精确绑定`b7565001...baa72`、HEAD `55f98e7`、snapshot `88e3f471...abec0`、
  `docker-named-volume-v1`及R2C-R1 report/tree/receipt/scope四组哈希；旧生产继续绑定
  `722f63de...13b76`和三bind挂载，当前未切换。
- 冻结两阶段发布：16:00—19:30之外只做一次no-start promote，旧容器继续healthy；下一唯一可用
  交易日仅在旧16:00探测闭合`WAITING_SOURCE`后start一次。候选启动失败只允许新旧不并行的顺序
  legacy恢复；候选首次业务写入后关闭自动legacy rollback。
- 当前只授权复用既有daily release guard补齐lock-authority、四挂载、受控Git树、等待源闭合、fixture
  哈希和自然日验收门；Docker build/fixture/volume/tag/promote/restart/业务/ledger/secret/网络均为0。
  工程推送且自然跑批闭合后，须另立精确日期与scope并再次获批。见
  `config/r2d_scheduler_named_lock_promotion_v1.yaml`与
  `docs/R2D_SCHEDULER_NAMED_LOCK_PROMOTION_PROTOCOL_20260825.md`。

## 2026-08-25 · 三类市场观察页面只读评估归档

- 三份20260824本地页面仅作机制/UI参考，不导入HTML、内嵌股票快照或第三方接口数据。价值顺序为
  行业强度→全市场趋势→涨停情绪，分别对应TP-F板块排序、市场状态和拥挤风险辅助。
- 行业页同日成分快照仅1,577/5,550（28.4%），47/90行业零覆盖；宽度/等权代理不得裁决。全市场页
  含330只`.BJ`和205只ST；涨停页缺炸板池、全量晋级分母且留存口径待核，均不可直接接研究/生产。
- 冻结`PROPOSED_NOT_AUTHORIZED`：主线仍为R2D→G1阳性对照→TP-F-0B；TP-F优先复用项目内PIT申万
  行业，涨停情绪不阻塞首版。当前代码/配置/数据源/Web/模型/账本/生产均不改。见
  `docs/MARKET_OBSERVATION_CAPABILITY_PROPOSAL_20260825.md`。

## 2026-08-25 · R2C-R1真实named-volume fixture全绿

- scope`8887bbdf...9a22`唯一候选构建PASS、唯一完整suite 10/10 PASS；候选
  `b7565001...baa72`精确绑定HEAD `55f98e7`、snapshot `88e3f471...abec0`和
  `docker-named-volume-v1`，scope永久关闭不重跑。
- 34条受控命令完成候选原生no-op-flock 8线程、4独立进程、双容器EX/SH/NB、SIGKILL、8进程合成
  ledger及错误mount门；report=`6e5a9ec2...208b`，tree=`36b9cc9c...dee6`，独立复算一致。
- scope容器/错误卷残留0，稳定锁卷保留；生产scheduler原容器/镜像/创建时间不变且healthy、重启0，
  未promote/restart。终态`BUILD_PASS / FIXTURE_PASS / GO_R2D_PROTOCOL_ONLY`、生产none。
- 下一步只能另立R2D结果盲生产提升协议并再次精确授权；未批准前不切current、不启动R2-1R1。见
  `docs/R2_1R0L_B_R2C_R1_NAMED_VOLUME_FIXTURE_ACCEPTANCE_20260825.md`。

## 2026-08-25 · R2C-R1 fixture入口恢复工程完成

- 终态`GO_RELEASE_READY_NOT_EXECUTION_APPROVAL`。第2项已改为候选原生固定payload：不传显式
  `lock_root`，候选内no-op `flock`后8线程最大临界区并发为1；daemon命令形状继续绑定真实authority、
  稳定named volume、断网、只读根与降权。其余9门、顺序和失败/不重跑语义未改。
- 专项14、联合95、架构13、全仓1,907 PASS；controller/payload为400/95行，工程snapshot=
  `88e3f471...abec0`。Docker daemon/build/fixture/volume/promote/restart及业务/ledger/secret/网络均为0。
- 下一步仅可在实现推送后绑定最终HEAD、上述snapshot、候选和新scope，申请动作
  `R2C_R1_RUNTIME_LOCK_FIXTURE_ENTRY_RECOVERY_ONCE`的一次build+一次suite；未批准不执行，未全绿不进
  R2D/R2-1R1。见`docs/R2_1R0L_B_R2C_R1_FIXTURE_ENTRY_RECOVERY_ACCEPTANCE_20260825.md`。

## 2026-08-25 · R2C-R1 fixture入口恢复协议冻结

- 永久绑定原R2C scope、候选、claim/report/tree哈希及`LOCK_BEHAVIOR_NOT_EVALUATED`；原scope不重跑、
  稳定锁卷不删除，旧失败不改写。
- 唯一变化冻结为第2项候选原生payload：继承真实Docker authority/named-volume mount，不传显式
  `lock_root`，候选内no-op `flock`后8线程临界区最大并发必须为1；其余9门、安全、顺序和失败语义不变。
- 当前仅授权源码/测试/config/docs与零Docker本地子进程门；build、fixture、volume变更、promote/restart、
  业务/ledger/secret/网络和生产均为0。实现推送后须生成新HEAD/快照/候选/scope并再次精确批准。见
  `config/r2_1r0l_b_r2c_r1_fixture_entry_recovery_v1.yaml`与
  `docs/R2_1R0L_B_R2C_R1_FIXTURE_ENTRY_RECOVERY_PROTOCOL_20260825.md`。

## 2026-08-25 · R2C候选构建PASS但fixture入口合同失败

- 终态`BUILD_PASS / FIXTURE_FAIL / NO_GO_PROMOTION`。scope `2da6de12...d5afa`恰好构建候选
  `da267602...ea4d7`并调用一次断网suite；身份门PASS，第2项8线程门在进入并发临界区前FAIL，后8项未跑。
- 根因是宿主单测显式传`tmp_path lock_root`，而真实`docker-named-volume-v1`权威正确禁止显式根；属于
  `FIXTURE_ENTRY_TEST_CONTRACT_MISMATCH`，不是锁行为失败，权威`LOCK_BEHAVIOR_NOT_EVALUATED`。
- 原scope不重跑；稳定锁卷已创建，scope容器/临时错误卷残留0，生产scheduler原身份healthy未重启。
  下一合法节点R2C-R1只做候选原生no-op-flock 8线程入口恢复，其余9门不变；新工程/镜像/scope均须
  另批。见`docs/R2_1R0L_B_R2C_NAMED_VOLUME_FIXTURE_FAILURE_20260825.md`。

## 2026-08-25 · R2C真实Docker锁fixture编排工程完成

- 终态`GO_RELEASE_READY_NOT_EXECUTION_APPROVAL`。新增400行宿主编排器与75行固定容器payload，
  claim-first后逐项运行冻结10门；输出根存在即拒绝同scope重跑，失败也固化报告和证据树。
- 精确身份、只读/断网/降权、合成挂载、双容器、SIGKILL、ledger并发和三类坏mount均进入机器合同；
  不把fixture职责堆入release或锁内核。snapshot=`8009eeb5...7b70`。
- R2C专项11、联合专项92、架构13、全仓1,904 PASS；Docker build/fixture/volume、生产promote/restart、
  真实业务/ledger、网络和密钥均为0。推送后只可生成最终HEAD/snapshot/tag/scope精确授权，未批准前
  停止。见`docs/R2_1R0L_B_R2C_FIXTURE_ENGINEERING_ACCEPTANCE_20260825.md`。

## 2026-08-25 · R2C named-volume真实fixture协议冻结

- 冻结`r2-1r0l-b-r2c-named-volume-fixture-v1`：只验证R2B最终候选在真实Docker named volume上的
  线程、独立进程、双容器EX/SH/NB、SIGKILL、合成ledger与错误mount合同；不读取业务结果。
- 候选build恰好1次、fixture suite恰好1次，同scope任一失败均不得重跑；fixture须claim-first、断网、
  只读根、无secret/业务/生产挂载，并固化逐项状态、命令计数、候选身份与证据树哈希。
- 当前仅授权fixture编排源码、测试、config和文档；Docker build/fixture、volume创建删除、promote/
  restart、真实业务与ledger写均为0。编排实现推送后须复算最终HEAD/snapshot/tag/scope并另获精确授权。
  见`config/r2_1r0l_b_r2c_named_volume_fixture_v1.yaml`与
  `docs/R2_1R0L_B_R2C_NAMED_VOLUME_FIXTURE_PROTOCOL_20260825.md`。

## 2026-08-25 · R2B统一跨进程锁工程完成

- 终态`GO_ENGINEERING_COMPLETE / R2C_NOT_AUTHORIZED`。timeline、daily、shadow、paper与canonical
  ledger已迁移到统一逻辑锁；旧timeline局部mutex模块删除，生产直接`flock`只剩统一后端，三个研究
  历史入口继续仅登记。
- Compose冻结`shaiwei_runtime_locks_v1`，业务data/ledger/logs仍留本地bind。新镜像必须带lock
  authority标签并通过四挂载门；旧生产三挂载在迁移窗口保持可观测，不因此重启。
- 全仓1,893 PASS、架构13 PASS；新模块205/85/56行，release抽离后583行，paper热点670→664行；
  工程snapshot=`626cacdf...d4cb`。当前生产仍为`183b8c6c5edd`/`722f63de...13b76`、healthy、
  `legacy-bind-flock-v0`。
- Docker build、named-volume fixture、promote/restart、业务/结果读取、真实ledger写、外网与密钥均为
  0。下一节点R2C须精确绑定终版HEAD/snapshot后另批唯一候选与一次断网fixture，通过前不进R2-1R1。
  见`docs/R2_1R0L_B_R2B_UNIFIED_LOCK_ENGINEERING_ACCEPTANCE_20260825.md`。

## 2026-08-25 · R2B统一锁工程协议冻结

- 冻结`r2-1r0l-b-r2b-unified-lock-engineering-v1`：只施工统一逻辑锁、五类生产关键路径迁移、
  Compose named lock volume及release精确挂载门；业务data/ledger/logs继续留在项目bind mount。
- daily/shadow非阻塞、paper blocking、timeline EX/SH与ledger EX语义保持；三个研究`flock`入口只登记
  不改动。生产缺/错mount、未知authority/资源、逆序或递归锁全部fail closed。
- 本节点不授权Docker build/fixture、生产promote/restart、业务读取/运行、真实ledger写、外网、密钥、
  模型、Web或DeepSeek。工程推送后R2C仍须绑定精确HEAD/snapshot另批唯一候选与fixture。见
  `config/r2_1r0l_b_r2b_unified_lock_engineering_v1.yaml`与
  `docs/R2_1R0L_B_R2B_UNIFIED_LOCK_ENGINEERING_PROTOCOL_20260825.md`。

## 2026-08-25 · R2A锁语义只读审计完成并冻结统一锁权威

- 终态`GO_ARCHITECTURE_ONLY / IMPLEMENTATION_NOT_STARTED`。只读清点确认timeline、daily、shadow、
  paper与canonical ledger都在Docker Desktop项目bind mount上直接依赖`flock`；正常scheduler虽然串行，
  但重复scheduler、手工/恢复入口及跨容器发布仍需要真实跨进程互斥。
- 实际生产仍为容器`183b8c6c5edd`、镜像`722f63de...13b76`且healthy；三持久化挂载在容器内均为
  `fakeowner`文件共享。没有发现账本损坏，也不据此推翻任何既有业务或研究结论。
- ADR-0009选择“业务data/ledger/logs继续留项目目录，仅锁文件进入专用Docker named volume”，并以
  稳定逻辑资源ID统一线程/进程/容器锁。该方案仍须真实多进程、双容器、SIGKILL释放与ledger并发
  fixture证明；不得把Docker文档推断当PASS。
- 本节点源码、配置、Compose、ledger、镜像、fixture、promote、restart、业务读取/运行均为0。下一
  合法节点R2B只做结果盲工程；其后R2C另批唯一候选与fixture，全部通过前不进R2-1R1。见
  `docs/ADR_0009_DOCKER_INTERPROCESS_LOCK_AUTHORITY.md`与
  `docs/R2_1R0L_B_R2A_LOCK_SEMANTICS_AUDIT_20260825.md`。

## 2026-08-25 · TS具体事件策略关闭，但经济假设家族继续研究

- 用户明确裁决TS大方向不能关闭。权威分层为：既有TS-v3—v6事件策略与TS-B身份保持
  `CLOSED_REJECTED`，TS-C两版资格身份保持`CLOSED_NOT_EVALUATED`；旧结果、预算和留出期均不重开。
- `TS_ECONOMIC_HYPOTHESIS_FAMILY=ACTIVE_RESEARCH`：强市场/板块、个股右侧结构与高质量回踩继续作为
  长期主题，但ACTIVE不表示有效，也不授权参数搜索、LLM、效果、模拟仓或生产。
- 当前优先后继仍为TP-F横截面排序形态。顺序冻结为scheduler跨进程锁/发布→G1阳性对照→TP-F-0B
  结果盲数据与身份预检；通过后再逐批申请候选和费用授权。见
  `docs/ADR_0008_TS_FAMILY_CONTINUATION_AFTER_EVENT_LANE_CLOSURE.md`。

## 2026-08-24 · R2-1R0L-B-R1B新候选构建通过但跨进程fixture失败

- 终态`BUILD_PASS / FIXTURE_FAIL / NO_GO_PROMOTION`。绑定HEAD `76ec0bc`与snapshot
  `6be617e4...c1e2c`恰好构建候选`b6c4e18a...d6b83`，构建审计`740bd185...6eb5`；同镜像唯一断网
  只读fixture为14/15。
- R1进程内互斥及无效`flock`下8线程门已在真实bind mount通过；唯一失败收敛为4个独立Python进程，
  两条首记录均引用零前驱，四worker均被SHA链门拒绝。JUnit=`2729c195...c8e1b`，失败timeline=
  `b6686cf5...30cfd`，输出树摘要=`945dd02c...fe9a`；同scope不重跑。
- 生产仍为原容器`183b8c6c5edd`、原镜像`722f63de...13b76`且healthy；新旧候选均未运行或promote。
  下一步先做R2A只读锁语义审计与ADR，统一核对ledger/daily/paper/shadow等同类`flock`假设，不直接
  申请第三候选。见`docs/R2_1R0L_B_R1B_SCHEDULER_TIMELINE_FIXTURE_FAILURE_20260824.md`。

## 2026-08-24 · R2-1R0L-B-R1并发锁恢复工程完成

- 裁决`GO_ENGINEERING_COMPLETE / NEW_CANDIDATE_NOT_BUILT`。协议`8e0898f`先行推送，实现`ed8e4ec`
  已推送；新代码快照`6be617e4...c1e2c`。writer先取规范路径进程内互斥，再保留`flock`完成跨进程锁，
  最后才校验链、append、flush、fsync；注册表只保留持有/等待路径。
- 新增互斥本体、无效`flock`下8线程32事件、真实`flock`下4独立进程16事件三层门；timeline专项15、
  架构13、全仓1,879 PASS，Ruff/compileall/pip/diff-check PASS。writer 360行，新锁模块54行。
- Docker build/fixture/promote/restart及真实业务均为0；生产仍为原容器`183b8c6c5edd`、原镜像
  `722f63de...13b76`且healthy，失败候选与产物原样保留。下一节点须绑定最终HEAD和上述snapshot，
  另批唯一新候选与唯一bind-mount fixture。见
  `docs/R2_1R0L_B_R1_TIMELINE_LOCK_RECOVERY_ACCEPTANCE_20260824.md`。

## 2026-08-24 · R2-1R0L-B-R1并发锁恢复协议冻结

- 绑定L-B失败候选、JUnit、分叉timeline与输出树哈希，失败scope不重跑、旧候选和产物永久保留。
- R1只恢复timeline append临界区：新增按规范路径的进程内互斥，既有`flock`继续承担跨进程锁；注册表
  只保留正在持有/等待的路径。Schema、phase、预算、跨午夜、通知和业务账本均不变。
- 本节点只授权源码、测试、合同和验收；Docker build/bind-mount fixture/promote/restart、真实业务、
  回填、密钥读取、Web、模型和生产账本写入均为0。工程推送后，新候选与唯一fixture仍须另批。见
  `docs/R2_1R0L_B_R1_TIMELINE_LOCK_RECOVERY_PROTOCOL_20260824.md`。

## 2026-08-24 · R2-1R0L-B候选构建通过但断网fixture失败

- 终态`BUILD_PASS / FIXTURE_FAIL / NO_GO_PROMOTION`。绑定HEAD `0018224`与代码快照
  `ccf4aa05...823d34`恰好构建一个候选镜像`56a97f02...0064f`，镜像label、运行时manifest和Git身份
  一致；构建审计记录为`3045ab97...eb832`。
- 同一镜像只运行一次断网、只读、无业务挂载的synthetic fixture，12项中11 PASS、1 FAIL。并发测试
  在Docker bind mount留下两条都指向零哈希的首记录，独立读取正确报`SHA-256 predecessor mismatch`；
  JUnit=`e3a8ce0f...8d7e`，失败timeline=`582c7f0d...88d9`，输出树摘要=`f4d3382c...a9e`。
- 同scope不重跑；候选不promote。生产scheduler仍为原容器`183b8c6c5edd`、原镜像`722f63de...13b76`
  且healthy，真实业务、回填、Web、模型、生产账本写入均为0。下一步须另立R1，先补进程内互斥并保留
  跨进程锁，再以新HEAD/快照另批唯一候选与唯一fixture。见
  `docs/R2_1R0L_B_SCHEDULER_TIMELINE_FIXTURE_FAILURE_20260824.md`。

## 2026-08-24 · R2-1R0L-A隔离Git构建上下文工程完成

- 裁决`GO_ENGINEERING_COMPLETE`。scheduler builder不再要求整个live worktree干净；它只接受
  `HEAD==origin/main`的受控Git archive，受控tracked/staged/untracked变化继续fail closed，自然账本和
  非受控用户草稿保留但不进入上下文。
- 实现`d2c4992`已先推送；真实零Docker smoke在七份自然账本和三份草稿共存时生成1,287个受控文件，
  snapshot=`ccf4aa05...823d34`，`.env/data/ledger/logs`均未进入且临时根已自动删除。
- `release.py`由581降至579行，新职责位于219行独立模块。专项20、联合专项66、架构13、全仓1,876
  PASS；Ruff/compileall/pip/diff-check PASS。build/fixture/promote/restart均为0，scheduler原容器和镜像
  仍healthy。
- 下一节点L-B必须另获授权，只允许一次候选build和一次断网timeline fixture；L-C生产提升继续单独
  精确授权。见`docs/R2_1R0L_A_SCHEDULER_BUILD_CONTEXT_ACCEPTANCE_20260824.md`。

## 2026-08-24 · R2-1R0L不可变timeline发布协议冻结

- 用户已人工确认Docker Desktop登录启动开启，R2-1H0终态升级为`GO_HOST_AVAILABILITY_COMPLETE`。
- 发布前审计发现旧builder要求整个live worktree干净，与scheduler持续追加自然账本及既有用户草稿
  冲突；禁止为构建暂存/提交/stash/reset这些文件。R2-1R0L冻结从已推送HEAD生成项目内忽略的Git
  archive上下文，受控dirty/untracked仍fail closed，非受控运行证据不进入镜像。
- 当前只授权协议；16:00—19:30窗口内不做测试洪峰、build、fixture、promote或restart。下一节点
  R2-1R0L-A仅施工archive builder工程，推送后再申请一次候选build+断网fixture授权，生产提升另批。
  见`docs/R2_1R0L_SCHEDULER_TIMELINE_RELEASE_PROTOCOL_20260824.md`。

## 2026-08-24 · R2-1H0接电防休眠已执行并验证

- 用户明确批准后，AC Power `sleep`已由1改为0；原生管理员弹窗完成认证，密码未进入Codex、项目或
  Git。复核`displaysleep=5`及其余接电字段不变，电池、VPN、代理和其他程序均未修改。
- scheduler仍为容器`183b8c6c5edd`、镜像`722f63de...13b76`、原启动时间，状态running/healthy，
  RestartPolicy仍为`unless-stopped`；Docker构建/提升/重启和真实业务运行均为0。
- 用户随后人工确认Docker Desktop登录启动开启，终态为`GO_HOST_AVAILABILITY_COMPLETE`。后继
  timeline release已另立协议，构建与提升仍分开授权并避开16:00—19:30窗口。见
  `docs/R2_1H0_MAC_HOST_AVAILABILITY_ACCEPTANCE_20260824.md`。

## 2026-08-24 · ADR-005宿主连续运行方案裁定

- 只读核对发现接电配置`system sleep=1分钟`、`display sleep=5分钟`；当前防休眠来自Kimi/Chrome/
  ChatGPT/音频等临时断言，不能作为生产保证。scheduler的Docker重启策略已是`unless-stopped`且healthy，
  但Docker无法阻止宿主睡眠。
- 裁决`GO_HOST_DESIGN_ONLY / SYSTEM_ACTION_PENDING_USER_APPROVAL`：只在接电时设`system sleep=0`，
  保留熄屏5分钟和电池策略；不用`caffeinate`、裸机launchd或前台应用断言。便携式Mac须接电且不普通
  合盖，Docker Desktop登录启动由用户在应用内确认。
- 精确系统动作`sudo pmset -c sleep 0`及原值回滚`sudo pmset -c sleep 1`已登记；系统动作随后经用户
  明确批准并验证，执行终态以上方R2-1H0记录为准。仍须确认Docker Desktop登录启动，再另立不可变
  scheduler timeline release；避开16:00—19:30数据窗口发布。见
  `docs/ADR_005_MAC_HOST_AVAILABILITY_20260824.md`。

## 2026-08-24 · R2-1R0运行连续性工程完成

- 裁决`GO_ENGINEERING_ONLY`。独立合同/事件校验/写入三模块完成；按启动日JSONL逐事件文件锁、fsync、
  SHA-256链覆盖9类phase、两账户子阶段、封闭outcome和慢阶段飞书回执，跨午夜与并发链均通过。
- `daily.py`仅增readiness/collection薄编排，未改`paper_cycle.py`热点；phase写失败在body前失败关闭，
  飞书失败不改核心状态。专项30、架构13、全仓1,865 PASS；Ruff/compileall/pip/diff-check PASS。
- 真实跑批、回填、历史时间线、Docker构建/重启、生产发布、策略/模型/门禁/账本变更均为0；scheduler
  仍为原容器`183b8c6c5edd`、原镜像`722f63de...13b76`且healthy。R2-1 v1仍`BLOCKED_EVIDENCE`。
- 下一步先裁定宿主防休眠方案，再另立不可变scheduler release；发布稳定后才冻结R2-1R1连续区段，
  20日/2次自然调仓门不降低。见
  `docs/R2_1R0_SCHEDULER_CONTINUITY_ENGINEERING_ACCEPTANCE_20260824.md`。

## 2026-08-24 · R2-1R0运行连续性工程协议冻结

- ADR-004与R2-1R0协议已结果盲冻结：独立按日JSONL、逐事件SHA-256链、文件锁与fsync记录
  readiness/daily/shadow/paper及两账户execute/verify/acceptance；业务账本继续为权威。
- 实现前合同自检已显式补足`PHASE/DURATION_WARNING_NOTIFICATION`事件种类、通知投递状态与
  `READY/NOT_READY`封闭outcome；阈值、权限和生产边界均未改变。
- 慢阶段只固化WARN并尝试通知，不改变核心PASS；R0不授权硬超时、kill、历史回填、macOS设置、
  `caffeinate`、Web或生产release。下一步只实现合成工程门，current scheduler保持不变。见
  `docs/ADR_004_SCHEDULER_PHASE_TIMELINE_20260824.md`和
  `docs/R2_1R0_SCHEDULER_CONTINUITY_ENGINEERING_PROTOCOL_20260824.md`。

## 2026-08-24 · R2-1自然前瞻检查点确认阻断

- 截至20260821，机器投影为live-dual `13/20`日、自然调仓`0/2`次；固定起点后15个官方开市日仅
  覆盖13日，20260813/14因账户未在执行日同日完成而永久属于受控追赶，v1权威终态确认
  `BLOCKED_EVIDENCE / MISSING_LIVE_DUAL_OPEN_DAYS`。两日最终计算均PASS，不是策略效果失败。
- 20260813存在约16小时34分钟容器输出断档，与宿主/Docker休眠高度一致但未越权读取项目外电源
  日志；20260814 shadow耗时217.9分钟，而相邻14次中位9.9分钟，现有证据不能继续区分休眠与资源
  争用。20260817—21已恢复5个连续同日双账户日，scheduler当前healthy。
- v1“固定起点100%覆盖”和“异常只顺延”在形成永久缺口后冲突，继续等待不能恢复通过；不得补账或
  改名。下一步建议先做R2-1R0运行连续性/阶段留痕工程，再以“缺口后连续区段自动重置”另立R2-1R1，
  20日/2次自然调仓门不降低。修改macOS电源设置、宿主守护或生产release仍须用户另行批准。见
  `docs/R2_1_FORWARD_CHECKPOINT_BLOCKED_EVIDENCE_AUDIT_20260824.md`。

## 2026-08-24 · A1-6B封存组件身份工程完成

- 裁决`GO_ENGINEERING_COMPLETE`。通用封存校验精确绑定历史 registry SHA、逐资产 SHA 与组件快照；
  R2/R4 真实scope在当前registry演进后仍通过，registry/path/asset SHA/snapshot四类篡改均fail closed。
- R4组件已改为`CLOSED_FROZEN`，两个closed builder拒绝签发新release；当前97/97构建资产仍全覆盖。
  专项59、架构13、全仓1,851 PASS；效果/新尝试/删除均0，生产none，scheduler原容器healthy未重启。
  M6保持关闭，下一步回R2-1自然前瞻。见
  `docs/A1_6B_SEALED_COMPONENT_IDENTITY_ACCEPTANCE_20260824.md`。

## 2026-08-24 · A1-6A M6阶段关闭与代码复盘

- 裁决`M6_CLOSED / REVIEW_COMPLETE_NO_SAFE_DELETE`。核心Python已达644文件/119,512行，较A1-2
  增45,801行，但`>400`/`>600`仍为26/12、循环依赖0；M6源码岛133文件/23,066行且全部<=400。
- M6结论已足够：归因指向组合转换，Top20未评价，生产Head30仅研究尺度有效，50万元退市恢复因
  极值资本门`INFEASIBLE`；不再追加M6变体。历史release/recovery仍是唯一复核入口，异机归档未就绪，
  `SAFE_DELETE_NOW=[]`。
- A1-6A发现的R4 active状态与历史scope依赖已由A1-6B闭合；历史身份与当前注册表现已解耦。见
  `docs/M6_STAGE_CLOSURE_AND_CODEBASE_REVIEW_20260824.md`。

## 2026-08-24 · M6-5C-C-R4唯一真实恢复终态

- scope`117e69a8...c51d`唯一runner先claim再完成first/replay，ordinal 2 experiment为`362b5b223108`，
  家族累计2次；两遍bundle同SHA`4e91436f...d2ef`。唯一独立auditor 14项全PASS，audit
  `14b35de8...4686`，同scope永久关闭。
- 红股权益阻断已解除，风险退出1单/1成交、容量违规0；但最大现金比例42.9416%>35%、最大目标L1
  85.9510%>50%，故权威诊断`RECOVERY_DIAGNOSTIC_FAILS_FROZEN_CAPITAL_GATES`、capital
  `INFEASIBLE`、生产none。不得以其余门通过或5/6正超额窗口放宽极值门；M6-5C-C关闭，不追加同家族
  变体。见`docs/M6_CSI800_PRODUCTION_HEAD30_DELISTING_ENTITLEMENT_EXECUTION_ACCEPTANCE_20260824.md`。

## 2026-08-23 · M6-5C-C-R4 successor release终版

- 裁决`GO_RELEASE_READY_NOT_EXECUTION_APPROVAL`。实现`9231372`已推送；新镜像
  `dd29fe14...6435b`只构建1次，daemon fixture只运行1次，六窗登记→退出→detached到账→再退出、
  claim先于reader、同scope拒绝重开、内部重放和独立重建均PASS。
- metadata-only scope为`117e69a8...c51d`；真实读取、ordinal 2 ledger、approval、claim、effect、
  audit和生产均为0。全仓1,838 PASS，scheduler原容器持续healthy且未重启。当前必须停止并等待用户
  逐字绑定scope和冻结动作精确授权；R2 scope永久关闭。见
  `docs/M6_CSI800_PRODUCTION_HEAD30_DELISTING_ENTITLEMENT_RELEASE_ACCEPTANCE_20260823.md`。

## 2026-08-23 · M6-5C-C-R4红股权益successor release结果前冻结

- R4只把R3验收的`execute_entitlement_recovery_day`接入新release；旧模拟器仅允许增加默认保持原入口
  的窄executor注入点，禁止复制整条模拟、风险、费用或指标计算。新组件独立登记，不改封存R2资产。
- 尝试家族不重置：ordinal 2、parent=`6797875cf3c0`、运行前1次、claim后2次；R2 scope永久关闭。
  当前只授权工程、一次镜像构建、一次断网fixture和metadata scope，真实读取/账本/approval/执行/生产
  均为0。见`docs/M6_CSI800_PRODUCTION_HEAD30_DELISTING_ENTITLEMENT_RELEASE_PROTOCOL_20260823.md`。

## 2026-08-23 · M6-5C-C-R4 successor release工程门

- 裁决`GO_SUCCESSOR_BUILD_READY_NOT_EXECUTION_APPROVAL`。独立组件与claim-first ordinal 2合同完成；
  旧模拟器只增加默认保持旧入口的executor，successor显式调用R3入口；旧R2资产与默认行为不变。
- synthetic六窗均证明登记→清仓→detached到账→再次退出，first/replay与独立重建一致；专项54、架构
  13、全仓1,834 PASS。真实读取、canonical账本写、镜像、daemon fixture、scope和生产均为0。
  下一步必须先推送实现，再只构建一次新镜像并运行一次断网fixture。见
  `docs/M6_CSI800_PRODUCTION_HEAD30_DELISTING_ENTITLEMENT_RELEASE_ENGINEERING_ACCEPTANCE_20260823.md`。

## 2026-08-23 · ADR-002封存组件注册表权威裁决

- 已裁定封存release以scope自哈希绑定的历史注册表SHA、固定资产路径和逐资产SHA为权威，不再错误
  要求历史SHA等于持续演进的当前全仓注册表；当前/未来release仍必须使用当前注册表且保持构建资产
  100%恰好一次纳管。该改动只修只读复核语义，不改R2 scope/镜像/产物，也不授权旧scope重跑。
  见`docs/ADR_002_FROZEN_COMPONENT_REGISTRY_AUTHORITY_20260823.md`。

## 2026-08-23 · M6-5C-C-R3红股权益恢复工程GO

- 终态`GO_ENGINEERING_ONLY / strategy_effect=NOT_EVALUATED / production=none`。独立paper-v2入口在
  红股上市日为已卖空原仓但仍有效的登记日权益建立零数量/总成本0的detached position，再调用冻结
  风险引擎；到账后可处置，现金、费用、订单、事件Schema和既有语义均不变。
- 初版直接修改风险引擎被3个历史release身份门正确拒绝，未提交、未发布、未读真实结果；终版恢复
  `risk_exit_engine.py` SHA`634b4bb3...fd31`和paper-v1 engine SHA`44e64d1a...1d6b94`，以新入口
  保持兼容。专项联合42、架构13、全仓1,826 PASS；真实读取、账本、release/scope和生产均为0。
  见`docs/M6_CSI800_PRODUCTION_HEAD30_STOCK_DIVIDEND_ENTITLEMENT_RECOVERY_ACCEPTANCE_20260823.md`。
- 下一步只能另立ordinal 2结果盲release，让runner显式使用新入口并生成新镜像/scope后再申请精确
  授权；R2 scope永久关闭，不得把工程GO写成策略有效。

## 2026-08-23 · M6-5C-C-R3红股权益恢复结果前冻结

- R3只补paper-v2的合法状态：登记日权益在原仓卖空后仍有效；红股上市日先建零数量、总成本0的
  detached position，再复用冻结到期动作加精确整数股。成本字段仍表示累计现金支出，不冒充税法
  成本；现金股利、已有持仓、应收估值、退市参数、事件Schema和paper-v1全部不变。
- 本节点只授权独立适配模块与synthetic工程门，真实读取、账本、release/scope和生产均为0。工程通过
  即停；未来真实恢复为同家族ordinal 2、历史尝试1，须另立release协议和新授权。见
  `docs/M6_CSI800_PRODUCTION_HEAD30_STOCK_DIVIDEND_ENTITLEMENT_RECOVERY_PROTOCOL_20260823.md`。

## 2026-08-23 · M6-5C-C-R2真实诊断claim后失败

- scope`94a45605...9829`唯一runner先完成canonical claim与receipt再进入真实reader，尝试家族已消费
  ordinal 1；首遍在红股权益上市日因原持仓已清空、paper-v2未定义新持仓及成本基础语义而fail closed。
  first pass未完成、replay未开始、auditor 0，策略仍`NOT_EVALUATED`、生产none；同scope永久关闭。
- experiment=`6797875cf3c0`，receipt=`cb555a8c...f510`，唯一effect文件为failure
  `b06bd93e...7fc7`。scheduler未变且healthy。继续只能另立结果盲paper-v2权益处置恢复协议，以同家族
  ordinal 2和新scope重新授权；paper-v1身份、退市参数与收益门均不得改。见
  `docs/M6_CSI800_PRODUCTION_HEAD30_DELISTING_RISK_REAL_EXECUTION_FAILURE_R2_20260823.md`。

## 2026-08-23 · M6-5C-C-R2 release终版

- 终版裁决`GO_RELEASE_READY_NOT_EXECUTION_APPROVAL`。实现`68f1192`先推送；R2镜像
  `e423a6cd...ad79`只断网构建1次，daemon fixture只运行1次并真实穿过scope loader，claim顺序、
  同scope拒绝重开、内部重放和独立重建均PASS。
- 新metadata scope为`94a45605...9829`；真实approval/claim/effect/audit路径均不存在，真实读取与
  canonical ledger写入0、家族尝试仍0。scheduler原容器持续healthy且未重启。当前必须停止并等待
  用户重新绑定新scope与冻结动作精确授权；原R1 scope/approval永久关闭。见
  `docs/M6_CSI800_PRODUCTION_HEAD30_DELISTING_RISK_SCOPE_RUNTIME_RECOVERY_RELEASE_ACCEPTANCE_20260823.md`。

## 2026-08-23 · M6-5C-C-R2 scope运行时恢复工程门

- 工程裁决`GO_SUCCESSOR_BUILD_READY_NOT_EXECUTION_APPROVAL`。中央构建注册表新增显式metadata模式，
  默认全仓严格文件门不变；release scope要求组件三条登记路径与scoped哈希逐项相等并重算组件身份，
  Compose/Dockerfile身份只取同一封存记录，不再要求组件镜像携带无关构建资产。
- successor fixture已在宿主测试中真实穿过`ReleaseScope.load()`；R2 approval/claim/effect/audit使用全新
  隔离路径。专项34、架构13、全仓1,817 PASS；真实读取、账本、approval、镜像构建和fixture真实运行
  仍为0。下一步仅可在实现推送后构建一次R2镜像并运行一次daemon fixture，通过后生成新scope并停在
  用户精确授权前。见
  `docs/M6_CSI800_PRODUCTION_HEAD30_DELISTING_RISK_SCOPE_RUNTIME_RECOVERY_ENGINEERING_ACCEPTANCE_20260823.md`。

## 2026-08-23 · M6-5C-C真实入口claim前失败与R2冻结

- scope`2afe815f...ec85c`唯一runner在`ReleaseScope.load()`因组件镜像不含无关全仓构建资产而失败；
  execute_loaded/claim/真实读取均未进入，ledger与receipt写入0、家族仍0、auditor 0、scheduler不变。
  原scope/approval不得重跑或复用。
- R2只允许注册表显式metadata模式、scope按登记路径+scoped哈希重算组件身份，并强制successor fixture
  穿过真实scope loader；默认全仓严格门、领域/claim/输入/门槛/挂载不变。见
  `docs/M6_CSI800_PRODUCTION_HEAD30_DELISTING_RISK_SCOPE_RUNTIME_RECOVERY_PROTOCOL_20260823.md`。

## 2026-08-23 · M6-5C-C-R1 release终版

- 终版裁决`GO_RELEASE_READY_NOT_EXECUTION_APPROVAL`。successor镜像`be1e9b47...192fd9`由已推送
  `5a142da`唯一断网构建；daemon fixture唯一运行PASS，六窗共6次锁存退出，claim先于reader、拒绝
  重开、内部重放和独立重建均闭合。首次失败镜像`faf2ac66...c963cbf`永久关闭。
- metadata-only scope为`2afe815f...ec85c`；真实目标/价格/效果读取0、真实ledger/approval/effect/audit
  0，scheduler原容器持续healthy且未重启。当前必须停止并等待用户绑定scope与冻结动作精确授权唯一
  真实运行；结果仍只具post-hoc诊断权限、生产none。见
  `docs/M6_CSI800_PRODUCTION_HEAD30_DELISTING_RISK_RELEASE_ACCEPTANCE_20260823.md`。

## 2026-08-23 · M6-5C-C首次fixture失败与R1冻结

- 实现`aac357d`推送、断网镜像`faf2ac66...c963cbf`构建成功；唯一fixture在协议前序文档身份校验处
  失败，根因是Docker context遗漏三份验收文档。合成领域未进入，真实目标/价格/效果读取0、真实账本/
  approval 0、scheduler不变；原镜像不得重跑。
- R1只授权专用dockerignore与三份只读文档COPY，successor用新镜像名且只构建/fixture各一次；不改
  领域代码、claim、门、Compose或全局dockerignore。见
  `docs/M6_CSI800_PRODUCTION_HEAD30_DELISTING_RISK_RELEASE_CONTEXT_RECOVERY_PROTOCOL_20260823.md`。
- R1工程已`GO_SUCCESSOR_BUILD_READY`：专用context仅开放src/config/单一manifest/三份指定文档，
  base+R1协议与失败证据双绑定；专项35、架构13、全仓1,815 PASS，构建资产94/94。实现推送后只可
  构建一次新名successor并运行一次synthetic fixture，真实权限仍为0。见
  `docs/M6_CSI800_PRODUCTION_HEAD30_DELISTING_RISK_RELEASE_CONTEXT_RECOVERY_ENGINEERING_ACCEPTANCE_20260823.md`。

## 2026-08-23 · M6-5C-C claim-first release实现门

- 工程裁决`GO_IMPLEMENTATION_READY_FOR_ONE_OFFLINE_IMAGE`：runner在真实reader前先fsync canonical
  ledger与receipt；独立auditor只读封存产物和claim，不挂raw/R2。新组件Docker/Compose不扩大生产
  `CONTROLLED_FILES`，新生产模块均低于400行。
- 合成六窗每窗恰好1次锁存风险退出（共6次），PIT前一交易日时钟、内部重放、独立重建、claim先于
  reader和同scope拒绝重开均PASS；专项34、架构13、全仓1,814 PASS。真实目标/价格/效果读取0、真实
  ledger追加0、approval 0、scheduler不变。实现推送后仅可构建一次断网镜像并生成metadata-only
  scope，随后停在用户精确授权前。见
  `docs/M6_CSI800_PRODUCTION_HEAD30_DELISTING_RISK_RELEASE_ENGINEERING_ACCEPTANCE_20260823.md`。

## 2026-08-23 · M6-5C-C claim-first结果盲release协议冻结

- M6-5C-C已冻结：只把M6-5C的“连续10个有效收盘严格低于1元后锁存退出、不补位、留现金”作为
  单一post-hoc恢复变量；生产Head30目标、50万元账户、费用/容量和原六窗口门均不变。风险`as_of`
  固定为执行日前一官方交易日，执行日收盘及未来数据禁止参与触发。
- 新尝试家族`m6_head30_500k_delisting_risk_overlay_v1`从ordinal 1开始；未来runner必须先向canonical
  experiment ledger fsync claim、再fsync receipt，之后才准读真实目标/价格/效果。当前只授权代码、
  synthetic daemon fixture、独立镜像和metadata-only scope，不授权approval、真实读取、账本写入、
  Web、scheduler或生产。见
  `docs/M6_CSI800_PRODUCTION_HEAD30_DELISTING_RISK_RELEASE_PROTOCOL_20260823.md`。

## 2026-08-23 · M6-5C-B-R1退市风险执行适配工程门

- 最终裁决`GO_EXECUTION_ADAPTER_ENGINEERING_ONLY`。旧`paper/engine.py`保持860行和
  `44e64d1...1d6b94`原始SHA；paper-v2由362行独立风险编排、193行卖出原子和16行策略类型组成，
  默认/显式空指令的paper-v1两日金标均为`dd7b40...d1faa`。非调仓风险退出、失败保留持仓与现金、
  v2留现金和全部越权门通过，退市日无显式处置仍硬停。
- 专项25、旧M6联合51、架构13、全仓1,808、账本86 PASS；Ruff、compileall、pip check、diff-check
  PASS。真实目标/价格/效果读取0、账本追加0、release/scope 0；scheduler原容器持续healthy且未重启。
  下一步只能另立M6-5C-C claim-first runner/replay/auditor/release结果盲工程，真实诊断仍须精确授权。
  见`docs/M6_CSI800_PRODUCTION_HEAD30_DELISTING_RISK_EXECUTION_ADAPTER_ACCEPTANCE_20260823.md`。

## 2026-08-23 · M6-5C-B兼容失败与R1恢复协议冻结

- M6-5C-B合成功能门曾通过，但全仓23项旧M6 release测试因`paper/engine.py`字节身份变化失败；真实
  目标/价格/效果读取0、canonical ledger写入0。原协议的“旧engine抽薄”裁决为
  `NO_GO_DUE_TO_ARCHIVED_PREDECESSOR_IDENTITY`，不能用新功能通过覆盖历史可复核性失败。
- M6-5C-B-R1已显式冻结唯一恢复变量：旧engine恢复并保持SHA`44e64d1...1d6b94`、860行；paper-v2
  改走独立、低于400行的风险适配编排和卖出原子，paper-v1空指令只作精确委托。R1仍不授权真实
  读取、账本、回测、release/scope、Web、scheduler或生产；实现后必须让旧M6和全仓门全部恢复。

## 2026-08-23 · M6-5C-B退市风险执行适配结果前冻结

- M6-5C-B协议已冻结：新增研究专用`paper-v2-delisting-risk-exit`和默认空的`forced_exit_codes`窄
  指令；只有新策略允许风险剔除后目标权重小于1，风险卖出可在非调仓日执行，卖不出则保留持仓和锁存。
  `paper-v1`不得接收非空指令，订单/成交Schema及默认语义不得改变。
- 施工前旧engine SHA为`44e64d1...1d6b94`、860行；固定两日合成买卖全结果哈希为
  `dd7b40b3...e9d1faa`。本节点只抽出卖出职责、建设研究策略类型和synthetic对抗门，不读真实目标/
  价格/效果，不写真实账本，不构建release/scope，不碰Web或scheduler。

## 2026-08-23 · M6-5C-A退市风险退出方法工程门

- 工程裁决`GO_METHOD_ENGINEERING_ONLY`。连续10个有效交易收盘严格低于1元时，未持有目标进入
  `BUY_BLOCKED`、持仓进入`EXIT_LATCHED`；锁存不因后来价格恢复而撤销，持仓清空后显式转为
  `DISPOSED`。目标顺序保持，移除权重留现金，不补位、不重分配、不猜退市价。
- 新纯状态机232行、合同加载器86行；冻结热点`paper/engine.py`保持860行且字节未改。专项12、架构
  13、全仓1,793、账本86 PASS，Ruff、compileall、pip check及diff-check PASS。真实目标/价格/效果
  读取0，真实账本追加0，`paper-v1`、Web、scheduler和生产身份不变。该方法由已知W6失败触发，未来
  历史结果只具`POST_HOC_METHOD_RECOVERY_DIAGNOSTIC`权限。下一步另立M6-5C-B执行适配工程，不与
  真实回放或生产合并。见
  `docs/M6_CSI800_PRODUCTION_HEAD30_DELISTING_RISK_METHOD_ACCEPTANCE_20260823.md`。

## 2026-08-23 · A1-5A真实效果attempt claim工程门

- 工程裁决`GO_ENGINEERING_ONLY`。未来真实效果入口必须先向canonical experiment ledger追加确定性
  claim并fsync，再写内容寻址receipt并fsync，之后才允许调用effect reader；claim后任何失败均保守
  消费尝试，相同scope不得通过幂等路径重开。最终结果与裁决仍由版本化report和独立audit表达。
- 8个已关闭旧runner已按路径和源码SHA精确登记，自发现门要求全部带冻结effect-start marker的入口
  与登记表集合相等；旧源码、scope和证据均不回改。共享模块271行，`ledger.py`390行；专项19、架构
  13、全仓1,781、账本86 PASS，Ruff、compileall、pip check及diff-check PASS。真实效果读取0、真实
  账本追加0，Web/scheduler/生产身份不变。未来M6-5C或其他真实效果节点仍须另立迁移协议、release
  scope和用户授权。见`docs/EFFECT_ATTEMPT_CLAIM_GATE_ACCEPTANCE_20260823.md`。

## 2026-08-23 · A1-4C-R1查询恢复与本机只读发布

- R1最终裁决`GO_LOCAL_READ_ONLY_RELEASED`。通知证据按每个`attempt=1`拆分
  occurrence，单次连续性、声明max、16次硬上限、跨事件、重复身份和字段白名单均继续失败关闭；详情
  只取截止日最新occurrence，同日统计仍保留全部尝试。不改日志、发送端、message ID或scheduler。
- 真实证据截至2026-08-21恢复为数据质量PASS、系统运行PASS、通知WARN（9个消息、12次尝试、3次
  失败后3次恢复，早期40条不可寻址记录保留）。`operations.py`由1,160降至1,060行，新解析模块172
  行；HTTP门已扩至全部关键只读接口，并加入v1/v2 state、旧candidate不可覆盖归档和successor
  新→previous→同一新恢复路径。
- 专项58、架构13、全仓1,766、账本86和前端33 PASS；Ruff、compileall、pip check、Compose和
  diff-check PASS，生产npm依赖漏洞0。实现`ea987be`推送后归档旧candidate`70d2cf6f...b3ee9`，
  successor candidate为`9c7ac1a8...d3b27`、release identity为`60d15cbb...a2b13`，两角色均只
  构建1次。新→旧v2→同一新三段、全关键API、CSP及真实浏览器8页均PASS；当前state为v2第2代，
  scheduler容器/镜像/快照/revision/health全程不变。仅授权本机只读Web，不授权外网、写入、交易或
  生产策略变更。见
  `docs/BUILD_IDENTITY_WEB_RELEASE_QUERY_RECOVERY_ACCEPTANCE_20260823.md`。

## 2026-08-23 · A1-4C真实release验收发现与R1冻结

- 工程提交`a6d20f4`推送后，双镜像各只构建一次；真实candidate为`70d2cf6f...b3ee9`、release
  identity为`373ef4f2...28b7`，control/runtime镜像分别为`bb81a2fb...e94a`与`61889afd...e252`。
  v2身份、内嵌manifest、daemon定向字段、新→旧→同一新回滚演练、loopback端口和scheduler不变均
  PASS；最终三项Web容器运行新镜像且healthy，前端33项PASS，生产依赖审计0漏洞。
- 真实浏览器随后发现数据质量/系统运行查询因“单消息通知尝试超过固定上限”失败关闭。最高相同
  message ID累计25/20行；旧/新镜像`operations.py`哈希同为`fc0f9b03...f692c`，证明是稳定内容ID在
  多日合法复用后被查询层误聚成一次重试，不是本次release回归，旧版回滚不能恢复。故最终裁决暂为
  `BLOCKED_QUERY_ACCEPTANCE`，不记本机发布GO；新release保持本机只读运行且不触碰scheduler。
- R1已结果前冻结：按每个`attempt=1`拆分投递occurrence，单次仍严格顺序且不超过max/hard limit，
  详情返回截止日最新occurrence；不改日志、发送端、message ID或重试。实现须从1,160行热点
  `operations.py`抽出纯解析模块，并把release门扩至七页关键API；随后用当前v2作为previous完成
  successor新→旧v2→同一新演练。见
  `docs/BUILD_IDENTITY_WEB_RELEASE_QUERY_RECOVERY_PROTOCOL_20260823.md`。

## 2026-08-23 · A1-4C Web双镜像release工程门

- 结果前协议提交`42ab126`已先行推送；工程裁决`GO_RELEASE_READY_NOT_DEPLOYED`。A1-4B v1保持兼容，
  新增v2双镜像合同，同时绑定`web-runtime`与`research-control`的已推送Git revision、完整源码bundle、
  三项注册构建资产、角色/服务、内容寻址image ID、四项标签与镜像内manifest，成功仍固定生产授权
  `none`。Makefile的build/up/status已统一进入release CLI，禁止单镜像或直接Compose旁路。
- 运行时门失败关闭核验只读根、cap drop、no-new-privileges、精确可写目录、网络和loopback端口，并
  禁止整仓及Docker socket挂载；提升编排预登记旧镜像，要求新→旧→同一新三段演练，候选替换后的
  任一失败均回到旧基线。专项57、架构13、全仓1,751 PASS；Ruff、compileall、pip check、Compose和
  diff-check PASS。scheduler与三项Web容器仍为原镜像且healthy，真实候选/attestation/新镜像/重启
  均为0。下一步只有在本实现推送后才可各构建一次双镜像候选并执行本机只读发布；runner记账、退市
  规则、模型与生产scheduler继续不动。见
  `docs/BUILD_IDENTITY_WEB_RELEASE_ENGINEERING_ACCEPTANCE_20260823.md`。

## 2026-08-21 · A1-4B组件构建身份注册与release门

- 协议提交`9cc9df8`先行推送；工程裁决`GO_ENGINEERING_ONLY`。中央注册表将91个Git跟踪构建资产
  以`GLOBAL / COMPONENT_RELEASE / FIXTURE_ONLY / ARCHIVE_CANDIDATE`四类全部且仅登记一次，分别
  为49/39/1/2项；10个组件的类、状态、复用政策和消费者路径均通过严格Schema与机器门。全局49项与
  `CONTROLLED_FILES`构建资产集合相等，基础Dockerfile COPY继续反向闭合；活跃Web三项和M7专属
  ignore边界已锁定。`CONTROLLED_FILES`常量未扩大；受控树因新增config/src/tests合同从1,209变为
  1,214文件，开发快照为`b00264fa...65c`，未提升到运行scheduler。
- 通用attestation门绑定注册表身份、全部构建资产SHA/组件快照、源码bundle、Git commit/origin、
  内容寻址镜像ID及三项标签；合成Web正向和21个越权/篡改对抗场景通过，成功结果仍固定
  `execution_authorized=false`、生产授权`none`。专项25、架构13、全仓1,719 PASS；Ruff、compileall、
  pip check和diff-check PASS。scheduler与三项Web容器均保持原镜像且healthy，无构建/重启/发布。
  真实Web attestation和新镜像仍为0；未来若重建须另立A1-4C真实Web release节点。runner原子记账与
  M6-5C退市方法继续独立，不得夹带。见
  `docs/BUILD_IDENTITY_COMPONENT_GATE_ACCEPTANCE_20260821.md`。

## 2026-08-21 · A1-4A构建身份覆盖只读审计

- 审计裁决`PASS_PRODUCTION_GLOBAL_WITH_COMPONENT_FINDINGS`：36个Dockerfile、54个compose和1个专属
  ignore共91个构建资产；全局快照内49个，组件级42个。生产侧57个现存根级`CONTROLLED_FILES`与
  基础Dockerfile COPY精确相等，受控树1,209文件，运行scheduler镜像带快照/Git标签且healthy，故
  不改全局清单、不重建或提升生产镜像。
- 42个组件资产中27个的当前SHA可在跟踪证据中精确定位，15个无当前SHA跟踪引用；其中活跃本地Web
  的`Dockerfile.web`、`Dockerfile.control`、`compose.web.yaml`虽有镜像ID留痕且容器healthy，但镜像
  缺代码快照和revision标签，须在下一次Web重建前补组件release manifest。10个关闭研究资产保持
  冻结，2个无消费者Dockerfile只列A1复核候选，删除0。Docker context结合专属ignore后20篇COPY文档
  缺失0。机器清单复算一致，全仓1,694、架构13、Ruff与diff-check PASS；未改运行身份。下一步仅可
  另立A1-4B组件身份注册/门禁，不得把42个资产机械并入生产快照。见
  `docs/BUILD_IDENTITY_COVERAGE_AUDIT_20260821.md`。

## 2026-08-21 · 实验账本提交基线纠偏

- 提交`f548cbd`中的两条Head30补录内容正确，但提交候选误以旧HEAD为基线，漏掉工作树中此前由
  scheduler合法追加的8条2026-08-11至08-20自然前瞻记录；该提交中的`ledger/experiments.csv`
  快照明确标记为基线无效。精确对账确认旧快照867行、完整活账本875行，旧快照ID缺失0、同ID内容
  差异0，Head30两行逐内容一致；这是提交/暂存区管线问题，不是研究结果或账本追加器错误。
- 本节点以完整活账本建立一次性非前缀纠偏基线，不新增尝试、不改效果或裁决，生产授权仍为`none`。
  纠偏提交为`601a782`；永久门已加入`HEAD -> index -> working tree`和`HEAD^ -> HEAD`双重检查，
  本次唯一例外精确绑定父子提交、路径、前后Git blob SHA、机器收据和说明文档，例外清单身份亦由测试
  固定，禁止通配豁免。追加门已由24份扩至全部41份Git已跟踪CSV账本，并强制实际跟踪集合与受控
  清单完全相等，今后新增、删除或漏登记都会失败关闭；账本专项86、架构13、全仓1,694 PASS，Ruff
  与diff-check PASS。M6-5B/M6-5C继续暂停。见
  `docs/M6_CSI800_PRODUCTION_HEAD30_LEDGER_BASELINE_REPAIR_20260821.md`与
  `docs/LEDGER_APPEND_ONLY_GUARD_ACCEPTANCE_20260821.md`。

## 2026-08-21 · M6生产Head30审查校准与尝试账本闭环

- 外部审查复核后，C-1权威状态保持`VALIDATED_RESEARCH_SCALE`、生产授权`none`，但精确比较口径已
  校正：Head30处理臂1/1.5/2倍成本六窗口复合净超额为41.6224%/25.0290%/10.3673%，合法封存
  `Top30/n_drop3`控制臂同口径为68.7790%/65.9315%/63.1317%。处理臂平均窗口累计换手38.1256、
  累计记录成本4.1461%，明显高于控制臂5.6070、0.5673；W4最大回撤21.5427%。因此结论是“绝对
  G0通过、相对控制臂明显变弱”，不再把旧G1汇总数当本次精确对照，也不把“涨市跑输、跌市跑赢”
  写成已验证规律。见`docs/M6_CSI800_PRODUCTION_HEAD30_AUDIT_ADDENDUM_20260821.md`。
- 原R1/R2 release均禁止账本写入，但两次真实效果读取各消费1次`m6_portfolio_converter`尝试，形成
  canonical ledger缺口。已通过独立历史对账协议向`ledger/experiments.csv`幂等追加R1
  `e97f4e185e33`与R2`3ce8e73c0733`两行；目标行SHA为`939c9c1e...34d79`，连续复跑新增0，同ID
  异内容失败关闭。新增专项测试锁定效果读取/账本一一对应及paper-v1退市生效日无处置证据的
  fail-closed；R2效果文件未变、新尝试0。M6-5B继续暂停，不授权paper-v2、M6-5C或生产。见
  `docs/M6_CSI800_PRODUCTION_HEAD30_AUDIT_RECONCILIATION_ACCEPTANCE_20260821.md`。

## 2026-08-20 · 平台研究重心校准，M6生产Head30协议结果前冻结

- M6-5B-R1 scope `c73b4afb...c74757`获精确批准并唯一启动；真实语义读取后消费1次新账户可行性
  尝试，家族累计2次。首遍因持仓`002505.SZ`进入2024-08-30退市生效日但没有显式处置规则而按
  paper-v1正确失败关闭；首遍未完成、replay/audit未运行，effect仅3个失败留痕、audit 0文件，
  R2五文件树不变。权威状态`BLOCKED_BY_UNMODELED_DELISTING`，策略仍`NOT_EVALUATED`、生产none；
  原scope永久不得重跑。下一步不做R2技术补丁，只可另立M6-5C方法裁决，先闭合当时可知的退市风险
  退出或实际处置证据，再以新尝试家族和新scope申请授权。见
  `docs/M6_CSI800_PRODUCTION_HEAD30_500K_ENTRYPOINT_RECOVERY_EXECUTION_FAILURE_20260820.md`。
- M6-5B-R1入口恢复工程已GO：协议提交`6812f25`先于实现`3f13e15`并均已推送；只修runner/auditor
  CLI显式参数映射，领域`run/audit`、paper-v1、目标和门槛不变。最终镜像`afe3d033...32b6b7a`
  由daemon断网合成fixture真实穿过两个CLI、内部重放和独立重算并PASS；专项18、架构13、全仓
  1628 PASS。新effect/audit根0文件，精确scope为`c73b4afb...c74757`；真实语义未读、家族累计仍1、
  scheduler原容器healthy、生产none。下一步仅可由用户绑定新scope与动作精确批准唯一真实50万元
  first/replay+独立audit，新增1次、累计2次，同scope不得重跑。见
  `docs/M6_CSI800_PRODUCTION_HEAD30_500K_ENTRYPOINT_RECOVERY_ENGINEERING_ACCEPTANCE_20260820.md`。
- M6-5B scope `62f88802...7570d`获批后唯一启动，但在进入`run()`前因CLI把`release`直接展开给
  要求`release_path`的函数而失败；effect/audit均0文件、封存目标/价格/收益/效果未读、auditor未
  启动、新语义尝试0，家族累计仍1，scheduler原容器healthy、生产none。原scope永久关闭不得重跑。
  已结果盲冻结M6-5B-R1入口恢复协议，只允许显式修正runner/auditor参数映射并要求最终镜像用合成
  输入穿过两个真实CLI；新镜像/输出根/scope完成后须再次精确授权。见
  `docs/M6_CSI800_PRODUCTION_HEAD30_500K_ENTRYPOINT_FAILURE_20260820.md`与
  `docs/M6_CSI800_PRODUCTION_HEAD30_500K_ENTRYPOINT_RECOVERY_PROTOCOL_20260820.md`。
- M6-5B恢复版发布工程已GO：schema检查意外打印一个W1调仓目标数组，按冻结合同显式计为家族第1次
  尝试；价格/收益/效果仍未读取，原v1保留但禁执行，恢复协议提交`d65ec19`先行推送。真实路径直接
  复用`paper.engine.execute_day`，固定21,815个不可变原始批次并逐文件核哈希/行数；runner断网
  first/replay，auditor无R2/raw挂载且独立重算。最终镜像`1f2a6daf...59b86`经daemon纯合成fixture
  PASS，精确scope为`62f88802...7570d`；scheduler原容器healthy、生产none。下一步只能由用户绑定
  scope与恢复动作批准一次真实50万元回放，新增1次、家族累计2次，同scope不得重跑。见
  `docs/M6_CSI800_PRODUCTION_HEAD30_500K_RELEASE_ENGINEERING_ACCEPTANCE_20260820.md`。
- M6-5A 50万元账户可行性结果盲工程门已GO：协议提交`5c7c58c`先于实现`53a198e`并均已推送；
  独立模块机械实现paper-v1费用/整手、卖后买、现金、信号日前20日成交额中位数5%容量和冻结裁决门。
  最终镜像`9b116f46...f427b5`由daemon断网、只读根fixture双跑同哈希，第二遍`reused=true`；专项7、
  架构13、全仓1610 PASS。真实目标/价格/收益/Qlib读取0、拟合/预测0、新尝试0，scheduler未重启且
  healthy、生产none。下一节点仅为M6-5B结果盲release工程；真实50万元回放仍须精确scope与用户授权。
  见`docs/M6_CSI800_PRODUCTION_HEAD30_500K_FEASIBILITY_ENGINEERING_ACCEPTANCE_20260820.md`。
- M6-4B-R7 scope `c08605ca...7b717`获精确批准并唯一完成auditor-only执行：完整R6-R2谱系、主结果
  精确身份、首遍/replay物理一致、独立`1e-12`容差和decision一致共17项实质检查全部PASS；当前
  独立SHA `1e7d00db...45d13`与历史SHA不同但仅作诊断。权威策略状态为
  `VALIDATED_RESEARCH_SCALE`；R2五文件树前后哈希不变，audit恰好2文件、新增尝试0、scheduler
  healthy、生产none。R7永久不得重跑；M6-4B历史效果审计链已闭合，但不得直接切换生产。下一节点
  应另立50万元账户尺度成交/容量/成本可行性与自然FORWARD协议。见
  `docs/M6_CSI800_PRODUCTION_HEAD30_AUDIT_OUTPUT_ROOT_RECOVERY_EXECUTION_ACCEPTANCE_20260820.md`。
- M6-4B-R7输出根恢复工程已GO：协议提交`a3e2e01`先于实现`7732fb2`并均已推送；显式创建新的
  audit根且保持`create_host_path=false`。最终镜像`8611728a...78528d`的daemon断网fixture把与未来
  真实服务相同的宿主根挂载为可写，完成哨兵写读哈希删除并确认前后为空，同时不挂载effect；完整
  R6/R5/R4/R3/R2谱系及哈希权威三组对抗门PASS。专项14、架构13、全仓1603 PASS；精确scope为
  `c08605ca...7b717`。真实effect语义未读、audit未运行、新增尝试0、scheduler healthy、生产none。
  下一步仅可由用户绑定完整scope与动作精确批准唯一auditor-only执行，R2-R6均不得重跑。见
  `docs/M6_CSI800_PRODUCTION_HEAD30_AUDIT_OUTPUT_ROOT_RECOVERY_ENGINEERING_ACCEPTANCE_20260820.md`。
- M6-4B-R6 scope `349859a6...9a90fa`获精确批准并唯一调用，但在Docker创建容器前因新的宿主audit
  输出根不存在且`create_host_path=false`而失败关闭；容器创建false、auditor调用0、effect语义未读、
  audit 0文件、新增尝试0，R2五文件树不变、scheduler healthy、生产none。R6永久不得重跑，策略为
  `NOT_AUTHORIZED_PENDING_AUDIT_OUTPUT_ROOT_RECOVERY`。下一步只能另立R7输出根恢复协议，在新scope前
  以daemon fixture验证真实可写bind source存在且不挂载effect，再重新精确授权。见
  `docs/M6_CSI800_PRODUCTION_HEAD30_AUDIT_HASH_AUTHORITY_RECOVERY_EXECUTION_FAILURE_20260820.md`。
- M6-4B-R6哈希权威恢复工程已GO：协议提交`0f8522b`先于实现`7540364`并均已推送；只删除协议外
  “当前独立SHA必须等于历史独立SHA”裁决门，仍记录当前/历史SHA并保留主结果精确身份、首遍/重放
  物理一致、独立`1e-12`容差和decision精确一致。最终镜像`cdd7a960...dac9af`经daemon断网、无
  effect fixture完成R5/R4/R3/R2谱系和三组对抗门；专项14、架构13、全仓1589 PASS。精确scope为
  `349859a6...9a90fa`；真实effect语义未读、audit未运行、新增尝试0、scheduler healthy、生产none。
  下一步仅可由用户绑定该scope和动作精确批准唯一auditor-only执行，R2/R3/R4/R5均不得重跑。见
  `docs/M6_CSI800_PRODUCTION_HEAD30_AUDIT_HASH_AUTHORITY_RECOVERY_ENGINEERING_ACCEPTANCE_20260820.md`。
- M6-4B-R5 scope `baa43d73...24789`获精确批准并唯一运行：完整谱系预检、R2只读加载和独立重算
  均完成；主身份、首遍/重放、`1e-12`容差等价及decision一致全部PASS，唯一失败项是实现额外要求
  本次独立canonical SHA等于历史R3独立SHA的`independent_result_lineage`。audit写出前失败，输出
  0文件；R2树不变、新增尝试0、scheduler healthy、生产none。R5永久不得重跑，策略为
  `NOT_AUTHORIZED_PENDING_INDEPENDENT_HASH_AUTHORITY_RECOVERY`。下一步只能另立R6，删除该协议外
  字节级约束但保留当前SHA记录/容差/裁决门，再建新scope并精确授权。见
  `docs/M6_CSI800_PRODUCTION_HEAD30_AUDIT_LINEAGE_ENTRY_RECOVERY_EXECUTION_FAILURE_20260820.md`。
- M6-4B-R5谱系入口恢复工程已GO：协议提交`fef88da`先于终版实现`51ca37a`并均已推送，只新增
  R3协议只读挂载；R3 loader/审计语义和R2效果零修改。最终镜像`73f3b0a5...5fba0`由daemon
  断网、无effect fixture调用与真实入口相同的完整谱系预检，R5/R4/R3/R2 authority全闭合，
  `effect_mounted=false`、审计未调用；专项13、架构13、全仓1575 PASS。精确scope为
  `baa43d73...24789`；真实effect语义未读、新增尝试0、生产none。下一步仅可由用户绑定该scope
  精确批准唯一auditor-only执行，R2/R3/R4/R5均不得重跑。见
  `docs/M6_CSI800_PRODUCTION_HEAD30_AUDIT_LINEAGE_ENTRY_RECOVERY_ENGINEERING_ACCEPTANCE_20260820.md`。
- M6-4B-R4 scope `d07daefb...3bd71`获精确批准并唯一创建auditor-only容器，但在读取R2 effect前
  因镜像内缺失R3协议YAML而失败关闭；R4 audit 0文件、effect语义未读、新增尝试0，R2五文件树
  哈希不变，scheduler healthy、生产none。R4永久不得重跑，策略为
  `NOT_AUTHORIZED_PENDING_AUDIT_LINEAGE_ENTRY_RECOVERY`。下一步只能另立R5，使用最终镜像daemon
  fixture覆盖与真实入口相同的完整谱系预检，再生成新scope并重新精确授权。见
  `docs/M6_CSI800_PRODUCTION_HEAD30_AUDIT_ENTRYPOINT_RECOVERY_EXECUTION_FAILURE_20260820.md`。
- M6-4B-R4入口路径恢复工程已GO：协议提交`da89e70`先于终版实现`ace34db`并均已推送，只把R3被拒的
  `/inputs/original-protocol.yaml`替换为镜像内allowlist合法路径，冻结loader和R3审计语义零修改。
  最终镜像`27dadcef...9fb4`经Docker daemon断网真实创建fixture，合法路径/协议哈希和继承审计
  合成门PASS；专项12、架构13、全仓1562 PASS。精确scope为`d07daefb...3bd71`；R4真实
  effect语义未读、audit未运行、新增尝试0、家族累计2、生产none。下一步仅可由用户绑定该scope
  精确批准唯一auditor-only执行，R2/R3/R4均不得重跑。见
  `docs/M6_CSI800_PRODUCTION_HEAD30_AUDIT_ENTRYPOINT_RECOVERY_ENGINEERING_ACCEPTANCE_20260820.md`。
- M6-4B-R3 scope `b38628de...14d3`获精确批准并唯一调用auditor-only容器，但在读取R2 effect前因
  旧`ReleaseProtocol.load`拒绝挂载路径`/inputs/original-protocol.yaml`而失败关闭；恢复audit 0文件、
  effect语义未读、新增尝试0，R2五文件树哈希不变，生产none。R3永久不得重跑，策略仍
  `NOT_AUTHORIZED_PENDING_AUDIT_ENTRYPOINT_RECOVERY`。下一步只能另立R4入口路径恢复、新镜像/
  新输出根/scope并再次精确授权，不得改变R3审计语义。见
  `docs/M6_CSI800_PRODUCTION_HEAD30_AUDIT_IDENTITY_RECOVERY_EXECUTION_FAILURE_20260820.md`。
- M6-4B-R3 auditor-only身份恢复工程已GO：原`real_audit.py`零修改，版本化合同将主结果精确哈希、
  独立`1e-12`数值等价和三方decision精确一致分离；专项13、架构13、全仓1550 PASS。薄镜像
  `91cca665...c9d3c`从R2镜像精确派生，断网合成fixture覆盖浮点尾差、主身份/裁决漂移和树篡改。
  精确scope为`b38628de...14d3`；真实恢复audit未运行、R2 effect未由恢复入口读取、新增尝试0、
  生产none。下一步只能由用户绑定该scope批准唯一一次auditor-only恢复，同scope不得重跑。见
  `docs/M6_CSI800_PRODUCTION_HEAD30_AUDIT_IDENTITY_RECOVERY_ENGINEERING_ACCEPTANCE_20260820.md`。
- M6-4B-R2 scope `9b78ef69...f9b4a`获精确批准并唯一完成runner与内部重放，空成交价路径安全
  越过，首遍/replay物理哈希一致；本次消费1个新组合转换尝试，家族累计2次，模型/预测新增0。
  主计算与独立重建均给出`VALIDATED_RESEARCH_SCALE`，但唯一独立audit因冻结合同要求独立浮点
  重算与主结果canonical SHA逐字节相等而失败；50处差异最大`3.73e-9`且既有容差等价检查PASS。
  本scope永久关闭，结果在auditor-only恢复前不具权威性，策略标记
  `NOT_AUTHORIZED_PENDING_INDEPENDENT_AUDIT_RECOVERY`、生产none。下一步只能另立零Qlib/零回测/
  零新增尝试的独立审计恢复协议与新scope，仍须用户精确批准。见
  `docs/M6_CSI800_PRODUCTION_HEAD30_PRICE_RECOVERY_AUDIT_FAILURE_20260820.md`。
- M6-4B-R2零效果读取恢复工程已GO：先行冻结提交`eb1d7c3`，仅把空/非法成交价规范化为缺失并进入
  既有持仓价格回退，二级无效明确失败关闭；没有新增价格源或改变策略。版本化运行profile独立拆分，
  主合同368行；专项39、架构13、全仓1537 PASS。不可变镜像`a6544af...64b29`经daemon纯合成
  fixture双跑与独立重建PASS；新输出根为空，R1三产物哈希不变。精确scope为
  `9b78ef69...f9b4a`，真实效果/R2尝试0、生产none；下一步只能由用户绑定该scope批准唯一runner+
  replay+独立audit，同scope不得重跑。见
  `docs/M6_CSI800_PRODUCTION_HEAD30_PRICE_RECOVERY_ENGINEERING_ACCEPTANCE_20260820.md`。
- M6-4B-R1 scope `ea648bda...83d2c`获精确批准并唯一运行：容器成功创建，真实处理臂开始读取，
  1个组合转换尝试已消费；首遍在2024-07-04处理`SZ002505`时成交价接口返回空值，`full_target`
  在进入既有持仓价格回退前对`None`转浮点而失败关闭。无完整首遍/replay/report，独立audit未启动，策略仍
  `NOT_EVALUATED`、生产授权none；R1永久不得重跑。下一合法节点仅为零效果读取的R2空值处理
  语义冻结与工程恢复，新真实运行必须另建输出根/scope/镜像并再次精确授权。见
  `docs/M6_CSI800_PRODUCTION_HEAD30_ENTRYPOINT_RECOVERY_FAILURE_20260820.md`。
- M6-4B精确scope获批后，唯一入口在Docker创建容器前失败关闭：YAML内联`tmpfs`被逗号拆成五个
  挂载项，daemon以`noexec`非绝对路径拒绝。effect/audit均0文件、真实效果未读、尝试0，scheduler
  healthy；原scope `15b3c785...143b3`永久不得重跑。已结果前冻结M6-4B-R1编排恢复协议，只修
  tmpfs序列化并增加daemon创建fixture；结果盲实现专项19、架构13、全仓1517 PASS。最终镜像
  `1958741...63c3`经daemon实际创建合成fixture PASS，新scope为`ea648bda...83d2c`。真实读取与尝试
  仍为0；下一步只能由用户绑定新scope精确批准恢复runner+replay+独立audit。
- Opus 5核心发现经代码与证据复核成立：历史回测是`Top30/n_drop=3`，生产信号是当期
  `rank-head Top30`等权全目标替换；50万元模拟账户又与1亿元研究尺度不同。Kimi提交不整体回滚，
  既有TS/RF/TP-F证据永久保留，但新增真实效果读取暂停到组合转换、G1阳性对照和资金定位三项校准。
- 第一优先级`M6-production-head30`协议已结果前冻结：只复用M6-2干净控制臂六窗口封存预测和旧
  对照日报，不训练、不生成分数；唯一变量是完整生产转换器，原G0公式不变，一个新组合转换尝试。
- 本节点仅授权纯转换器、合成/失败关闭测试和release scope准备；真实Qlib/封存预测值/收益读取、
  模拟仓或生产修改均未授权。未来必须由用户绑定新scope SHA精确批准一次runner+replay+独立audit。
  首轮机器合同测试捕获M6主协议SHA转录错误；原协议不改写，结果盲hash addendum仅纠正该
  身份且锁定问题/G0/权限/尝试数不变。
- 结果盲工程预检已GO：独立`full_target`适配器覆盖确定性Head30、保留证券再平衡、10日节奏、
  方向性成交与失败关闭；协议合同机械锁定权限/G0/一次尝试。真实runner/auditor/镜像/scope尚未
  施工，真实预测/效果读取0、实验账本新增0。下一节点仅为M6-4B release工程。
- M6-4B结果盲发布工程合同已冻结：只建设runner/replay/独立auditor、隔离Docker和精确
  release scope；控制臂不重跑，真实Qlib/封存效果保持未读，组合尝试仍为0。工程完成后必须
  停在绑定精确scope的用户授权前。
- M6-4B结果盲发布工程已就绪：实现提交`27fdd6c`已构建为`linux/arm64`不可变镜像
  `sha256:67beb7e...cca81d`；镜像内合成双跑、独立重建均PASS。精确release scope为
  `15b3c7854409adb6d9f32f74f583a156088513d17520f43e8df61d04321143b3`。真实Qlib、预测值、
  控制报告内容和效果仍未读取，组合尝试0、生产授权none；下一步只能由用户绑定该scope精确批准
  唯一runner+replay+独立audit，不得直接运行或同scope重跑。
- 外部复核指出的`risk_degree`未绑定缺口已在结果前关闭：策略现在必须显式接收协议1.0，缺失或
  0.95均失败；合同锁定完整treatment components及权重恒等式，新增生产selector交叉测试，并删除
  无效副本成交。专项8、架构13、全仓1506 PASS；真实效果/尝试仍为0。
  见`docs/PLATFORM_RESEARCH_REFOCUS_DECISION_20260820.md`与
  `docs/M6_CSI800_PRODUCTION_HEAD30_PROTOCOL_20260820.md`。

## 2026-08-20 · TP-F趋势回踩横截面因子准备GO（仅准备级）

- 用户批准把TS被否决信念改写为横截面因子形态：TP-F-0A准备裁决完成（结果盲、不冻结公式、
  不授权候选/效果）。TS证据链作为形态级设计输入（事件形态产能不成立；趋势市费前转正；
  分数用于排序而非闸门），其收益数值一律不得作为参数来源。
- 下一合法节点：TP-F-0B结果盲数据与身份预检（复用RF-0C机器与注册表）；正式小批仍须R2-1
  检查点+用户逐批授权。见`docs/TP_F_0A_TREND_PULLBACK_FACTOR_PREPARATION_20260820.md`。

## 2026-08-19 · TS-C v2资格赛失败关闭（许可开启年坍缩）

- v2唯一画像失败关闭：冻结的"≥50%交易日开启"规则只产生2个许可开启年（2020/2025），低于
  下限4。逐年开启占比：2019 42.6%、2020 83.1%、2021 41.6%、2022 0%、2023 25.6%、2024
  41.3%、2025 66.7%——v3月级双许可使策略按设计多数时间空仓，任何逐年密度门都与之结构性
  不兼容。零消耗，本scope关闭不重跑。
- TS-C继续的最后合法路径：另立全新协议只保总量/信号日门（≥120/≥40）、不设逐年要求（承认
  策略多数时间空仓的设计事实），用户定是否立项；否则TS-C关闭。scheduler未动。见
  `docs/TS_C_QUALIFICATION_V2_CLOSURE_20260819.md`。

## 2026-08-19 · TS-C触发器资格赛STOP（年度门与设计语义冲突）

- 唯一结果盲画像完成（R2恢复，零消耗），审计7/7 PASS：三臂总量均密（3038/1098/138条、
  373/258/75信号日）但2022年全部零事件——v3月SMA6双许可在熊市整年不成立是设计行为
  （允许长期空仓），冻结的"每年≥10条"门与之结构不兼容。裁决STOP，不降门不调参。
- 继续的唯一合法路径：另立全新预检协议，从设计语义论证按"许可开启年"评价密度（用户定是否
  立项）；否则TS-C关闭。scheduler原容器healthy未重启。见
  `docs/TS_C_TRIGGER_QUALIFICATION_ACCEPTANCE_20260819.md`。

## 2026-08-19 · RF-1正式单机制协议冻结，工程骨架就绪待双门

- RF-1协议`357975f2...afdc`冻结并推送：DeepSeek小批（≤8响应/≤3候选/$1批熔断/$2总上限）、
  候选合同（D1安全AST、必须同引$open+$close、≤50日/20token/80节点）、五层去重、发现期
  2016-06—2018-12机械Top1/Top2、G1裁判为唯一效果权威。
- 工程骨架就绪：候选合同+注册表去重+release硬门（缺冻结release即`RELEASE_NOT_AUTHORIZED`
  失败关闭）+对抗fixture，容器内7/7 PASS，全仓1485 PASS。
- 执行双门未满足前不动工：R2-1检查点（20日/2次调仓门）+用户逐批授权+冻结release。
  见`docs/RF_1_FORMAL_SINGLE_MECHANISM_PROTOCOL_20260819.md`。

## 2026-08-19 · RF-0C字段与身份预检GO_FORMAL_PROTOCOL

- 补充停牌证据层（suspend_d∪Baostock'0'）后唯一画像全门通过：覆盖率99.87%、未解释缺失0
  （5个缺口归位真实停牌）、注册表与RF-0B封存逐字节一致；R2恢复链零消耗、审计8/8 PASS、
  scheduler未动。该GO仅授权起草RF-1正式单机制协议（8响应小批/至多3候选/五层去重），正式批
  仍须R2-1检查点+用户批准+DeepSeek逐批授权。见
  `docs/RF_0C_FIELD_IDENTITY_PREFLIGHT_ACCEPTANCE_20260819.md`。

## 2026-08-19 · RF缺口谱系诊断完成：5键全部权威解释

- 唯一诊断+独立审计6/6 PASS：5个未解释成员日全部被独立Baostock状态'0'确认为真实停牌，
  Tushare suspend_d接口漏记。数据源覆盖缺口坐实，非面板构造错误。RF-0B的BLOCKED_DATA裁决
  不变、门槛不降；RF机制继续的唯一合法路径是另立全新预检协议+用户批准。
- 报告SHA`c6fe58fe...25fd`、审计SHA`3849debf...62f4`；scheduler原容器healthy未重启。
  见`docs/RF_0B_GAP_LINEAGE_DIAGNOSTIC_ACCEPTANCE_20260819.md`。

## 2026-08-19 · RF-0B字段与身份预检BLOCKED_DATA

- 唯一结果盲画像完成（R2+R3恢复链，零消耗）：1,359,127个PIT成员日中5个未解释无bar缺失
  超过冻结上限0，权威`BLOCKED_DATA`，机制按协议关闭；open/前收盘覆盖率99.87%、`.BJ`=0、
  无重复无冲突。身份注册表（104次LLM尝试+G1 29身份+Alpha158 158式）完整构建且效果列零
  读取，可服务下一个家族去重裁判。审计8/8 PASS；scheduler未动。
- 唯一合法继续方式：另立5日数据谱系诊断协议（参照M7先例），由用户决定是否立项；否则研究
  移交下一方法家族。见`docs/RF_0B_FIELD_IDENTITY_PREFLIGHT_ACCEPTANCE_20260819.md`。

## 2026-08-19 · TS-B留出期一次定音REJECT，TS家族研究终结

- 新身份TS-B（父版规格逐字节不变、废除发现期）在物理未读的2024—2025留出期唯一一次读取：
  56笔、费前单笔+83.47元（转正）、胜率41.1%、净+0.68%，但牛市两年基准+39%下超额-42.3%、
  DSR 0.5%，超额/正超额年/DSR三门失败，权威`REJECT_TS_B_HOLDOUT_AND_CLOSE`，审计9/9 PASS。
- 完整证据闭环：熊市（2021—2023）每笔负期望，牛市（2024—2025）每笔微正但98%现金完全踏空；
  发现期"+24.5%超额"确认为熊市持币假象。**该策略熊市亏钱、牛市踏空**，非边际修正问题。
- TS家族两个身份、四个效果协议全部权威否决，预算归零，证据链归档；同家族不得以任何已读
  结果重启。scheduler原容器healthy未重启。见
  `docs/TS_B_HOLDOUT_EFFECT_ACCEPTANCE_20260819.md`。

## 2026-08-19 · TS-v6-4删除固定止盈发现期REJECT，TS支线权威关闭

- 最后1次效果预算的发现期读取完成：删除固定止盈后父版188事件53笔闭合、费前单笔期望
  -101.49元、胜率32.1%、净-1.38%、DSR 77.4%，核心五门失败，权威
  `REJECT_TS_V6_4_NO_TAKEPROFIT_DISCOVERY_AND_LANE_CLOSES`。盈亏比1.32→1.76方向性改善、
  右尾打开，但胜率进一步下降，退出侧单变量不足以修复负入场经济学。
- 确定性复算一致（manifest同为`46f13525...1677b`），独立审计10/10 PASS（含无止盈记录验证）；
  报告SHA`93dae765...9292`；scheduler原容器healthy未重启。
- **TS支线权威关闭**：预算归零，不再立同家族新效果协议；全部协议、验收、失败留痕、不可变
  输入与账本永久保留；未来重启须另立全新身份与结果前协议，不得以已读结果为参数来源。
  见`docs/TS_V6_4_NO_TAKEPROFIT_EFFECT_ACCEPTANCE_20260819.md`。

## 2026-08-18 · TS-v6-3排序子集发现期效果权威REJECT

- 唯一一次发现期真实效果读取完成（R2恢复scope，首次零结果失败按用户裁决记0次消耗）。
  v6-1冻结Top-94质量排序子集在父版完全相同语义下：45笔闭合、费前单笔期望**-498.24元**
  （父版-58.90元）、胜率28.9%（父版38.1%）、净收益-4.79%、DSR 73.6%，五门失败，权威
  `REJECT_TS_V6_3_RANKED_SUBSET_DISCOVERY`。质量分数机制分支永久关闭，不重跑不调分。
- 确定性复算逐字节一致（first/replay manifest同为`08debc90...0891`），独立审计10/10 PASS；
  报告SHA`87379a83...4cec`、审计SHA`5cca4765...5243`；scheduler原容器healthy未重启。
- 效果预算：本读取消耗1次，**剩余1次**只准用于退出机制单变量研究（另立协议+用户批准），
  否则TS支线权威关闭归档。见`docs/TS_V6_3_RANKED_SUBSET_EFFECT_ACCEPTANCE_20260818.md`。

## 2026-08-18 · TS-v6-1入场质量排序零效果预检GO

- 用户2026-08-18裁决已冻结执行：零效果节点禁止任何outcome条件分析；TS支线剩余独立效果
  协议预算2，耗尽则权威关闭；触发人群重定义作废（R3G-1画像已证明仅BREAKOUT_RETEST过密度门）。
- 协议`378e3ebc...920c`先于实现推送（`1c3b220`）；实现`5e51300`推送后断网构建镜像
  `3149f657a2c7`。唯一一次真实画像只读v6-0冻结观察表（188+180键对账精确一致），语义标记后
  0次技术修复，确定性复算PASS，独立审计11/11 PASS。
- 结果：开发期Top-94（55信号日、53/15/26年度、三轴IQR>0且均改变混合选择），留出期冻结cut
  保留74条（38信号日、15/59年度），全部冻结门通过。裁决
  `GO_TS_V6_1_RANKING_EFFECT_SCOPE_PROPOSAL_ONLY`，策略仍`NOT_EVALUATED`，生产授权none，
  留出期收益与2026继续物理封闭。
- profile/manifest/audit SHA为`ed43d498...c78c9f`/`31356ad1...73d434`/`50d8b8e6...a473`；
  代码快照`f83a2fe2...495b2a`。scheduler原容器`183b8c6c5edd`保持healthy未重启。
- 该GO仅授权起草TS-v6-3独立效果协议并需用户再次批准：候选集为94条冻结事件，入场/退出/
  仓位/风险与父版主点逐字节一致，唯一变量为质量分数排序子集，主KPI对比父版-88.80元费前
  基线。若REJECT，剩余1次预算只准用于退出机制单变量研究。见
  `docs/TS_V6_1_ENTRY_QUALITY_RANKING_PREFLIGHT_ACCEPTANCE_20260818.md`。

## 2026-08-17 · TS-v6-0入场质量零效果预检权威STOP

- 断网唯一画像和独立audit已完成。开发期父事件188条；固定L9九点事件数为
  31/17/13/55/40/13/83/31/19，全部未过冻结90条总事件门。最高密度点83条、43个信号日、年度
  43/11/29、保留率44.15%，除总事件少7条外其余密度/非重复门通过，但不得事后降门槛。
- 机械选点为空，条件密度留出`null`；2024—2025入场后结果、2026、Alpha158、收益、模型、回测均
  未读，效果尝试增量0。父版R3G-2权威REJECT保持，TS-v6策略有效性仍`NOT_EVALUATED`。
- profile/manifest/audit SHA为`34a87090...b88a`/`31e27e80...51b7`/`14b055aa...afee`；独立审计
  13/13 PASS。运行Git`4f10f08`，镜像`c1e631f3...5bbdd`。scheduler原容器保持healthy且未重启。
- 本scope关闭，不重跑、不把90降到80。下一步另立零收益后继，优先研究“少一项硬门+连续质量分数”
  或“两阶段触发/排序”，先解决三门乘法式压缩，再申请效果读取。见
  `docs/TS_V6_ENTRY_QUALITY_PREFLIGHT_ACCEPTANCE_20260817.md`。

## 2026-08-17 · TS-v6-0结果盲操作化附录已冻结

- 在读取任何真实TS-v6特征前，进一步冻结父事件严格子集语义：质量门失败只剔除该父事件，不得在
  同一episode内重新武装、延后确认或创造替代信号日；父事件键须与R3G-1冻结产物精确对账。
- 回踩成交额比固定取首次武装行且分母排除当日；恢复收盘位置和10日涨幅横截面分位固定取父信号
  行。历史不足、无有效区间或横截面不足均fail closed。
- 机器真身`config/ts_v6_entry_quality_operationalization_addendum_v1.yaml`，SHA-256
  `ffa0e1f745853841aa58e0eb0e0efc00142a61523cf4bd1c3f269bb2452f441b`。本附录不改主协议的分位、
  密度门、时间划分或权限，仍为零效果、策略`NOT_EVALUATED`、生产授权none。见
  `docs/TS_V6_ENTRY_QUALITY_OPERATIONALIZATION_ADDENDUM_20260817.md`。

## 2026-08-17 · TS-v6-0入场质量零效果预检协议已冻结

- 用户确认按TS复盘建议继续；下一代只改变`HEALTHY_RETEST_ENTRY_QUALITY`，以回踩缩量、恢复收盘
  位置和10日不过热三个结果盲轴改进入场。父版4周突破/1.5ATR/10日等待/1日确认、市场板块门、
  下一开盘、退出、仓位和风险规则全部不变。
- 2021—2023只用于PIT特征分布、固定L9九点密度和至多一个候选选择；2024—2025只对已选点做事件
  密度pass/fail且不得改选，入场后结果仍未读；2026本节点不读。策略效果尝试增量0。
- 新增真实入口fixture、语义读取标记和最多两个标记前技术release的边界；标记后失败不得同scope
  重跑。该边界只减少无语义读取时的恢复扩散，不放宽结果防火墙或失败留痕。
- 机器真身`config/ts_v6_entry_quality_preflight_v1.yaml`，SHA-256
  `a518862b224b120b04f0a0ab6d1543a7827cbb9c245a3e8806e443c062d7332b`。当前只冻结协议，尚未施工、
  尚未读取真实特征或运行画像；效果仍`NOT_EVALUATED`、生产授权none。见
  `docs/TS_V6_ENTRY_QUALITY_PREFLIGHT_PROTOCOL_20260817.md`。

## 2026-08-17 · TS-v5 R3G-3发现期失败诊断完成

- R2 runner内部双跑一致，最终独立audit总门10/10、三点各9/9 PASS；机器裁决仅为
  `GO_DIAGNOSTIC_COMPUTATION_R3G2_REJECT_UNCHANGED`，R3G-2权威REJECT、策略REJECT、生产none不变。
- 主点费前-3,710.56元、费用1,884.04元、费后-5,594.60元；止损组-48,641.00元压过止盈组
  +41,309.72元，11—15日持有组-16,255.15元。三个冻结点及三成本场景全部为负。
- 主点仅28.06%交易日持仓，全期/持仓日平均仓位2.01%/7.15%；低参与率是规模瓶颈，但当前合并拒单
  原因不能证明信号稀缺或持仓上限是亏损根因。负费前期望未解决前不放大仓位。
- 报告/audit SHA为`118a528c...ca919`/`34cb944a...64b59`；零新增效果尝试，留出期/2026未读。
  下一合法节点是零效果读取的TS-v6单机制预检，不调R3G-2、不追加参数点。见
  `docs/TS_V5_R3G3_DISCOVERY_DIAGNOSTIC_ACCEPTANCE_20260817.md`。

## 2026-08-17 · TS-v5 R3G-3发现期失败诊断协议已冻结

- auditor入口恢复已完成全部检查，但在写JSON时因`numpy.bool_`不可序列化而失败，audit-r3为空。
  runner和该auditor均不重跑；序列化恢复只转原生bool、绑定同一R2三哈希并写独立audit-r4。
- R2 runner 已完成且内部双跑一致；原独立auditor仍在进入函数前因同类CLI映射错误失败，audit输出
  为空。runner不重跑；已另立auditor-only恢复scope，只修参数映射并绑定R2报告/manifest哈希。
- 第一入口恢复在授权后、明细读取前因把父 runner 的审计前`PENDING_INDEPENDENT_AUDIT`错当成最终
  `REJECT`而fail closed；只读父report/audit聚合JSON，未读NAV/orders/trades、未计算诊断，效果尝试0。
  该恢复不重跑；R2只分离runner审计前状态与audit最终状态，绑定旧授权哈希并使用独立输出根。
- 原 runner 唯一调用在进入诊断函数前因 CLI `protocol` 未映射为 `protocol_path` 而失败；输出根为空、
  未读封存数据、未写授权、效果尝试增量0，原入口不重跑。已另立只修参数映射的入口恢复 scope，
  原诊断问题、数据边界和停止条件均不变；恢复仍仅允许一次 runner、内部 replay 与独立 auditor。

- R3G-2 的权威 `REJECT` 与未读留出期保持不变；R3G-3 只解释已封存 2021—2023 发现期为什么
  平均现金接近98%、单笔期望为负，不以诊断挽救旧策略。
- 已在逐订单/逐交易值读取前冻结四类问题、分母、持有期桶和证据分层；明细只允许 first-pass
  discovery 三点的 base 场景，成本邻场景只读聚合 summary，replay/holdout/2026 明细均禁止。
- 下一步施工一次断网 diagnostic runner、一次内部确定性 replay 和一次独立 auditor；新增效果尝试0，
  不运行模型、预测、回测、参数搜索或外部API，不改模拟仓、Web、scheduler或生产。
- 协议：`config/ts_v5_r3g3_discovery_diagnostic_v1.yaml`；说明：
  `docs/TS_V5_R3G3_DISCOVERY_DIAGNOSTIC_PROTOCOL_20260817.md`。

## 2026-08-17 · TS-v5 R3G-2真实效果权威REJECT，留出期未读

- recovery scope`c78d6851...7193a`按用户逐字批准唯一执行；原scope未重跑。runner first/replay与独立
  auditor全部完成，审计9/9 PASS，权威`REJECT_TS_V5_R3G2_DISCOVERY`、策略`REJECT`、生产none。
- 三个冻结点基础净收益为-6.15%/-1.90%/-1.12%，H00906净超额为+19.47%/+23.72%/+24.50%；
  但基础绝对收益、2倍成本和额外10bp场景全部为负。主点DSR概率78.09%，低于95%冻结门；平均现金
  97.99%—98.85%，单笔期望三点均负。
- 首次效果读取消费恰好3个冻结尝试；两遍各38文件、bundle同为`f36bc46f...12a9`，逐文件一致。
  报告/audit SHA为`515e891b...d528`/`79de6dab...046f`。
- 发现期失败后`holdout=null`且产物树无holdout目录；2024—2025和2026结果均未读。原scope与
  recovery scope现均关闭且不得重跑，也不得事后放宽门槛或追加点。
- 本结果只否决当前冻结的BREAKOUT_RETEST实现，不否决TS方向。下一合法节点是零新增效果尝试的结果
  诊断，再决定是否另立有实质机制变化的TS-v6；模拟仓/生产仍未授权。scheduler原容器保持healthy。
  见`docs/TS_V5_R3G2_EFFECT_RECOVERY_ACCEPTANCE_20260817.md`。

## 2026-08-17 · TS-v5 R3G-2效果原scope入口失败，独立恢复scope待新批准

- 原scope`961b62f2...e19db75`在唯一runner进入真实执行函数前因CLI参数映射TypeError失败；该scope已
  消费且永久不得重跑。auditor未调用，真实分数/排名、入场后价格、H00906和留出期均未读，效果尝试0，
  原效果目录只保留失败回执`8bfd0685...58d2`，不能记作策略失败。
- 独立恢复协议只修入口映射并绑定原scope/批准/失败回执/原输出根；协议提交`37b2f78`、实现
  `02da4f4`、最终提交`9e295993...c3d`均已推送。最终镜像`sha256:0081742e...2874c`精确绑定
  scope生成时的`HEAD=origin/main`，938文件快照`3df4ceaa...4ecb`与宿主一致，断网fixture
  18 PASS/1 skip。
- key-only预检报告仍为`3cc735ee...114d0`、`GO_PRE_EFFECT_KEYS_ONLY`、`reused=true`；未读效果且尝试0。
  新recovery scope为`c78d6851...7193a`，文档SHA`698bc010...95245`；approval不存在，恢复效果/审计根
  为空，`execution_authorized=false`。
- 下一步必须由用户对固定恢复动作和新scope再次逐字批准。原scope与recovery scope均不得重跑；
  发现期失败不得读留出期，外网、2026、额外参数、模型训练、模拟仓、Web和生产继续禁止。scheduler
  仍为原容器且healthy。见
  `docs/TS_V5_R3G2_EFFECT_ENTRYPOINT_RECOVERY_PREPARATION_20260817.md`。
- 本段“待新批准”状态已由上方权威REJECT覆盖；recovery scope已执行并关闭。

## 2026-08-17 · TS-v5 R3G-2效果预执行工程完成，待精确批准

- 最终实现提交`3b43b6b...e725bf`、代码快照`9cc5e40a...170278`、不可变镜像
  `sha256:dbf006ec...8a6053`和930文件清单已逐项一致；断网、只读、无宿主数据挂载镜像fixture
  23/23 PASS。
- 键级预检幂等GO：报告`3cc735ee...114d0`；发现期727日/362事件，留出期485日/358事件（352个
  可调度），三个冻结点两期分数键覆盖均100%。分数值、入场后收益、H00906值均未读，效果尝试0。
- 施工中错误Git身份、合成测试宿主隐式依赖、4 GiB临时空间和缺少R3F冻结谱系挂载均在效果读取前
  fail closed并修复；失败证据保留，不构成策略失败。全仓1371 PASS，13个效果模块最大400行。
- 唯一未授权scope为`961b62f2...e19db75`，文档SHA`994a5d71...4ff075`；approval不存在、输出根
  为空，裁决`READY_FOR_EXACT_USER_APPROVAL_NOT_EXECUTED`，策略仍`NOT_EVALUATED`、生产none。
- scheduler保持原容器`183b8c6c5edd`、原镜像和创建时间且healthy。下一步必须由用户逐字批准固定
  动作后才可首次读取3个冻结效果尝试；同scope重跑、外网、2026、额外参数、模拟仓/Web/生产禁止。
  见`docs/TS_V5_R3G2_EFFECT_PREEXECUTION_ENGINEERING_20260817.md`。
- 本段“待批准”状态已由上方入口失败与独立恢复scope覆盖；原scope不再是可执行待办。

## 2026-08-17 · TS-v5 R3G-2效果工程/发布协议已结果前冻结

- 下一节点只允许施工独立runner/auditor、完全synthetic验收、不可变镜像和唯一release scope；真实
  分数值、排名、入场后行情、H00906、收益、回测、实验账本、模拟仓、Web和生产均未授权。
- W7只认entrypoint recovery的权威`GO_W7_SCORE_LINEAGE_DATA_ONLY`真身；原失败scope不删除、不
  改写，也不能被当作可用分数源。
- 结果前补清涨跌停历史档位、20日容量、部分卖出、分批T+1、退出优先级、成本场景独立路径和分区末
  未退出失败关闭；不改变三个点、资金、风险、止盈止损或效果硬门。
- 当前`strategy_effective=NOT_EVALUATED`、`production_authorization=none`。唯一scope推送后仍须用户
  精确授权，才可首次读取三个真实效果尝试。

## 2026-08-17 · TS-v5-R3G-2 W7入口恢复数据门GO

- recovery scope`f61a2365...44b5`按用户逐字批准唯一执行；runner内部first/replay及无Qlib独立auditor
  均完成，权威`GO_W7_SCORE_LINEAGE_DATA_ONLY`。原scope`5d238942...38ad`未重跑。
- W7谱系194,329行、2025-01-02—2025-12-31；两遍bundle均为`5842f87d...2f93`，模型、预测、summary
  与manifest逐内容一致。runner report/audit SHA-256为`d3c51f89...274d`/`d5cd43c3...276d`。
- 只读取允许的W7模型与分数谱系，未读取RankIC、收益、H00906、组合或效果；效果尝试0，策略
  `NOT_EVALUATED`，生产授权none。外网/secret/实验账本/模拟仓/Web/生产变更均为0。
- recovery scope已关闭且不得重跑。下一步若进入TS真实效果，必须另立效果release scope并再次精确
  批准；W7数据GO不自动授权效果。全仓1,356项、架构13项、脱敏manifest逐项复算均PASS，scheduler
  原容器保持healthy。见`docs/TS_V5_R3G2_W7_LINEAGE_RECOVERY_ACCEPTANCE_20260817.md`。

## 2026-08-17 · TS-v5-R3G-2 W7入口恢复scope待精确批准

- 新恢复协议只修runner/auditor CLI参数映射，绑定原scope`5d238942...38ad`、原批准`9f513150...0f28`、
  失败回执`cdfe44d1...99bb`及原lineage/audit文件数0；原scope永久不得重跑。
- 恢复使用独立镜像、独立scope/approval schema和独立输出目录；继承同一W7/provider/双跑/审计合同，
  继续禁止RankIC、收益、H00906、组合、外网、模拟仓、Web和生产。
- 准备提交`8c22834`已推送；恢复镜像`sha256:39a5fa...1398`内18项断网fixture PASS，911个受控文件
  与host逐项一致，快照`a6102897...cda0`。生产scheduler仍为原容器`183b8c6c5edd`且healthy。
- 唯一未授权recovery scope为`f61a2365...44b5`，文档SHA-256为`235bfac2...b395`；没有创建approval或
  recovery输出目录，runner/auditor均未调用，真实Qlib/W7训练/分数/效果新增仍为0。
- 下一步仅可逐字批准动作
  `TS_R3G2_W7_SCORE_LINEAGE_ENTRYPOINT_RECOVERY_ONCE_WITH_REPLAY_AND_INDEPENDENT_AUDIT`；批准前不得执行，
  执行后同scope仍不得重跑。
- 见`docs/TS_V5_R3G2_W7_ENTRYPOINT_RECOVERY_PREPARATION_20260817.md`。

## 2026-08-17 · TS-v5-R3G-2 W7原scope入口失败封存

- 原scope`5d238942...38ad`已按用户批准创建一次runner容器，但CLI把`release/approval`错误映射给
  `release_path/approval_path`，在进入`run()`前TypeError；原scope次数已消费且不得重跑，auditor未调用。
- 无`lineage_read_started.json`，真实Qlib、W7模型/分数、RankIC、收益、基准、组合均未读；策略效果尝试
  仍为0，不能记作策略失败。Git忽略失败receipt SHA-256为`cdfe44d1...99bb`。
- runner和auditor两个入口已做最小参数映射修复，并增加直接调用两个`main()`的回归测试；修复与失败
  已由`54fc96a`封存。后续恢复准备已另立新镜像与scope；再次取得用户精确批准前不读W7。
  见`docs/TS_V5_R3G2_W7_ENTRYPOINT_FAILURE_20260817.md`。

## 2026-08-17 · TS-v5-R3G-2 W7谱系预执行工程完成

- 2025 W7已完成结果盲工程入口，但尚未训练：严格继承M6干净Alpha158/LightGBM与t+11成熟度口径，
  只允许模型和`datetime/instrument/score`产物，不读测试标签、RankIC、收益、基准或组合。
- first pass/replay、write-once、失败封存、精确scope/approval和无Qlib独立auditor均已完成；W7失败仍
  不计策略效果尝试。7类职责拆分后生产模块最大227行，没有增长既有热点文件。
- 专项23项、全仓1348项、架构门13项、Ruff、Compose解析和diff-check已PASS；release协议/Compose哈希为
  `4fef44db...98f0`/`fa258ea4...5c54`。
- 首个镜像候选虽通过10项合成fixture，但host/image门发现通用Dockerfile漏复制12个受控根文件，已
  fail closed；该候选未生成scope、未读真实W7。修复提交`205af847`的最终镜像
  `sha256:4daccf51...2117`已重新通过10项fixture和906个host/image受控文件逐项哈希核验。
- 唯一未授权release scope为`5d238942...38ad`；当前裁决
  `READY_FOR_EXACT_USER_APPROVAL_NOT_EXECUTED`。外网/secret/真实训练/效果/模拟仓/生产仍为0；取得用户
  精确批准后才可真实训练W7。见
  `docs/TS_V5_R3G2_W7_PREEXECUTION_ENGINEERING_20260817.md`。

## 2026-08-17 · TS-v5-R3G-2真实效果协议结果前冻结

- 唯一效果族固定为R3G-1机械锁定的`BREAKOUT_RETEST`主点与两个邻居，首次效果读取合计3次尝试；
  邻居只检验局部稳定性，不能替换主点，不得新增点、机制或事后调参。
- 时间角色固定为2021—2023发现效果、2024—2025条件留出、2026部分年度仅监控。发现门失败时留出
  收益必须保持未读；2026因无冻结W8分数谱系，不读分数或效果，也不允许沿用W7。
- 旧P1 Alpha158缓存早于M6标签成熟度纠错，明确禁止用于本次效果。2021—2024复用M6干净W2—W6，
  2025只允许按同一Alpha158/LightGBM/seed及t+11 purge配方新建W7；W7谱系阶段不读RankIC或收益。
- 50万元、最多7票、单票10%/两批各5%、总仓70%、行业30%、风险/容量/真实税费、结构止损、
  1.5R与20%较近止盈、15日退出和H00906超额口径均已冻结；历史GO仍不授权模拟仓或生产。
- 配置SHA为`c3aa5a2b...72bf`，当前只完成协议与合同测试，效果`NOT_EVALUATED`、生产授权none。
  下一步施工断网W7谱系和效果执行器/独立审计；首次真实效果读取前仍须冻结唯一release scope并取得
  用户明确批准。见`docs/TS_V5_R3G2_EFFECT_PROTOCOL_20260817.md`。

## 2026-08-14 · TS-v5-R3G-2前置H00906基准谱系数据门GO

- 官方`H00906`全收益基准派生日表覆盖2019-01-02—2026-08-11共1845个SSE开市日；raw 1846行中
  唯一额外`20190101`为open/high/low全空、close有效的请求起点锚，按结果未知R5澄清留raw不入派生。
  排除后缺失/额外日期、重复键、无效close和OHLC冲突均0。
- 唯一断网评价裁决`GO_H00906_LINEAGE_DATA_GATE_ONLY`，独立audit 15/15 PASS；实现Git
  `7c0bb7a`、代码快照`ffb8f9e1...1b07`、派生日表/报告/manifest/audit哈希分别为
  `464a72c1...efa6`/`04f4accb...885a`/`71beb606...455b`/`af4078e0...eab1`。
- Tushare/secret读取0、策略效果尝试0、新网络请求0；策略仍`NOT_EVALUATED`、生产授权none。
  scheduler保持原容器/镜像/创建时间且healthy。下一合法节点须另立R3G-2效果协议，只允许R3G-1
  已机械锁定的3个`BREAKOUT_RETEST`点进入，不自动授权效果、模拟仓或生产。见
  `docs/TS_V5_R3G2_BENCHMARK_LINEAGE_ACCEPTANCE_20260814.md`。

## 2026-08-14 · TS-v5-R3G-2前置H00906基准谱系协议冻结

- 下一合法节点收窄为结果盲H00906总收益基准数据门；现行TS时间角色仍是2021—2023发现选择、
  2024—2025冻结稳定性、2026截至8月11日仅观察。采集从2019开始只为兼容旧TS-v3冻结基准合同，
  不把2019—2020重新用于现行选参。
- 权威源固定为中证指数官方事实表与`indexCode=H00906`历史行情接口；一次事实表请求、两次相同历史
  请求须在写入前一致。禁止用`000906`价格指数、本地股息代理或无授权第三方值替代；本次不读Tushare
  token或其他secret。
- 该节点只允许不可变采集、SSE开市日完整性门、一次评价与一次独立audit；候选收益、Alpha158数值、
  参数比较、模型/回测、模拟仓、Web、scheduler和生产仍禁止。通过也只允许另立R3G-2效果协议，策略
  仍`NOT_EVALUATED`、生产授权none。见
  `docs/TS_V5_R3G2_BENCHMARK_LINEAGE_PROTOCOL_20260814.md`。
- 首轮镜像构建在容器/请求/读取前因BuildKit把本地digest引用解析为Docker Hub拉取而失败；零scope
  消耗。恢复只改用已核验本地标签并把精确父镜像ID写入label和测试，协议与数据门不变。见
  `docs/TS_V5_R3G2_BENCHMARK_IMAGE_RECOVERY_20260814.md`。
- 首次真实网络容器在事实表TLS握手阶段失败，完整HTTP响应、历史请求、文件写入、数据门评价均为0；
  原网络scope关闭。R1只把固定三份公开bytes传输移到宿主，随后Docker断网评价和审计；不读secret、
  不换来源或门槛。见`docs/TS_V5_R3G2_BENCHMARK_TRANSPORT_RECOVERY_R1_20260814.md`。
- R1首次宿主传输因`raw/`未预建以curl 23失败，文件落盘、历史请求和评价仍为0；R1关闭。R2只新增
  项目内目录存在/可写/三目标为空的请求前硬门，其他三请求和权限不变。见
  `docs/TS_V5_R3G2_BENCHMARK_TRANSPORT_RECOVERY_R2_20260814.md`。
- R2三份官方raw成功固化且双历史物理哈希一致；首轮断网评价因规范化key排序后仍按位置重命名造成
  字段错位，在任何派生写入前失败。R3只改为16字段显式名称映射并加乱序对抗测试，零新网络。见
  `docs/TS_V5_R3G2_BENCHMARK_EVALUATION_RECOVERY_R3_20260814.md`。
- R3字段映射正确后质量门只剩官方接口的`20190101`非交易日起点锚：1846 raw行对1845开市日，缺失/
  重复/无效close均0，派生仍未写。R4因“OHLC全空”与“close为正”的字面矛盾未实施；R5在结果未知时
  只澄清为open/high/low全空、close有限且为正，边界锚留raw不入派生日表，排除后日期须与SSE
  日历全等；零新网络。见`docs/TS_V5_R3G2_BENCHMARK_BOUNDARY_ANCHOR_R5_20260814.md`。

## 2026-08-13 · TS-v5-R3G-1近期密度R2部分GO

- R3G-1覆盖2021—2026但按角色分离：2021—2023只做发现选择，2024—2025冻结验证，2026截至
  8月11日仅观察且不选参、不改判；六年不得合并。原R3G-0的2019—2021是v4继承文案，不是数据只能
  到2021。
- 首轮431点全零在封存后查明为公共执行投影缺陷：缺`raw_open`且`has_bar`取错来源；原profile/event/
  audit哈希永久保留，但旧`STOP_NO_RECENT_DENSE_MECHANISM`降为
  `INVALIDATED_BY_COMMON_EXECUTION_PROJECTION_DEFECT`，不再是密度结论。
- R2只修这两个字段并强化缺字段fail-closed；唯一断网画像生成5,683行事件，独立audit 21/21 PASS。
  六机制只有`BREAKOUT_RETEST`通过：81点中41点过发现门，机械锚点+两个邻居均过2024—2025冻结门；
  其余五机制本批STOP。权威`PARTIAL_GO_DENSE_MECHANISMS_ONLY`，策略仍`NOT_EVALUATED`、生产授权none。
- 正式镜像`3b81e501...a42d9`、Git`5afc08f`、代码快照`7c0c8cfa...c23f`；profile/events/audit哈希
  `9ab1719d...7a67`/`2e68af1c...d08a`/`40cfb62e...0964`。手工错录SHA镜像在运行前拦截并永久
  标provisional，随后增加HEAD/origin/build自动一致性和manifest门。
- 下一合法节点须先闭合H00906全收益谱系，再另立R3G-2结果前效果协议；只允许已机械冻结的突破回踩
  三点，不自动授权收益读取、回测、模拟仓或生产。见
  `docs/TS_V5_R3G1_RECENT_DENSITY_RECOVERY_R2_ACCEPTANCE_20260813.md`。

## 2026-08-13 · TS-v5-R3G-0六机制可执行语义工程门GO

- 主scope `3a066c13...45bb`以提交`c7da5ef`先行推送；量纲与确认公式歧义在实现前分别以`a12c208`、
  `4f83994`加注，不删除/修补候选，不改参数或阈值。最终实现/断网构建/非有限特征防线提交为
  `21d25ad`/`7cb4993`/`f0d1005`，均已推送。
- 六候选从R3F不可变content重新编译，fingerprint/signature完全一致且唯一；有效参数点
  81/75/81/81/32/81，共431。六条正常合成路径和16类对抗路径全PASS；候选登记不含LLM自由文本、
  reasoning、证券、行情或结果。
- 权威`GO_R3G_DENSITY_SCOPE_PROPOSAL_ONLY`；本节点DeepSeek/外网/secret/行情/密度/收益/Alpha158分数/
  模型/回测均为0，TS-v5效果尝试仍为0，策略`NOT_EVALUATED`、生产授权`none`。
- 最终断网镜像`34da009d...c5e6`、代码快照`8e068eea...d308`；registry/report/audit哈希为
  `9e51a58e...eaf4`/`e2fe2e11...fc6a`/`a9f32f96...5579`，独立audit 13项PASS，幂等复跑三哈希不变。
  全仓1292 PASS、架构13 PASS；五模块170/106/280/251/299行。scheduler原容器`183b8c6c5edd`
  和原镜像持续healthy。见`docs/TS_V5_R3G_EXECUTABLE_SEMANTICS_ENGINEERING_ACCEPTANCE_20260813.md`。
- 该下一节点已由上方R3G-1完成并显式覆盖为2021—2026三段角色；本段2019—2021仅保留为当时继承
  文案，不再代表当前待办或现行时间口径。

## 2026-08-13 · TS-v5-R3F本地绑定proposal真实合同金丝雀GO

- 用户批准后，scope `1a45898c...ee61`、实现`2031df8`、独立镜像`f3ccf7df...6efd`和execution
  release `da758d6d...7ab6`依次在真实调用前冻结并推送；release提交为`e1e8f31`。R3C/R3D/R3E旧
  合同、回答、账本和裁决均未改写。
- 唯一真实容器按固定六机制串行取得6/6完成响应；外部请求6、每席sequence 1、HTTP 200为6，重试、
  递补、计费不确定和第7次调用均为0。实际费用`$0.010779967`，prompt/completion tokens为
  18,825/3,486。
- 六份回答均`parse/schema PASS`且语义唯一，本地authority编译和原候选validator 6/6通过，权威
  `GO_BOUND_PROPOSAL_CANARY_ONLY`。这只证明结构化候选合同可用；参数搜索/回测未运行，策略效果仍
  `NOT_EVALUATED`，生产授权`none`。
- 断网无密钥独立审计13项PASS；断网全只读幂等复核新增调用0。主报告/audit/两个脱敏账本哈希为
  `a742ddc5...54f5`/`9cd37447...3aa9`/`ccf7155c...7d98`/`3839d57f...0121`。scheduler仍为原容器
  `183b8c6c5edd`且healthy。见`docs/TS_V5_R3F_LLM_CANARY_ACCEPTANCE_20260813.md`。
- 本scope已关闭，不递补或第7次调用。下一合法节点为结果前另立R3G发现期评价协议：登记六候选、
  去重并冻结发现期/事件密度/参数预算/成本/多重检验后，才可授权本地读取行情和效果；不直接进入
  模拟仓或生产。

## 2026-08-13 · TS-v5-R3E本地绑定proposal合同工程门完成

- 结果前scope `30185aa4...ec691`与v3合同先以提交`863f7d2`推送，随后实现`aee51dc`及完整可见投影
  修正`e1ebfa4`推送；旧v2
  proposal合同/编译器、最终候选validator和R3C/R3D证据均保持冻结哈希不变。
- v3把attempt mode、父候选和搜索点数移出LLM响应：请求显式携带本地批准的`INDEPENDENT`权威，编译器
  唯一注入lineage；证据mode只从已编译候选派生。搜索点按1—5槽机械分配7/7/5/3/2，对应搜索积
  7/49/125/81/32，均不超过196。
- 六机制合成proposal全部通过原候选validator，48/48个对抗样例fail closed；R3C六份封存回答断网只读
  重放仍为0录取、0修补。正式工程报告`095ebb49...7f73`、独立audit`e7c6c47d...5a9e`，二次运行哈希
  不变，audit全部PASS。
- 权威`GO_R3F_LIVE_CANARY_SCOPE_PROPOSAL_ONLY`：只说明本地合同缺陷已关闭，可以另提R3F小批金丝雀
  scope；当前DeepSeek调用、secret读取、行情/收益、参数搜索/回测、模拟仓、Web和生产仍为0，策略效果
  `NOT_EVALUATED`。scheduler原容器`183b8c6c5edd`持续healthy。见
  `docs/TS_V5_R3E_BOUND_PROPOSAL_ENGINEERING_ACCEPTANCE_20260813.md`。

## 2026-08-13 · TS-v5-R3D离线诊断发现本地授权绑定缺陷并停止

- 结果前scope `cbfba18e...fb6090`和实现提交`555ccdf`先后推送；随后仅在`network=none`专用镜像中
  只读六份R3C content，不使用reasoning，不调用LLM、不读行情/收益、不修补候选。
- 六个批准席位均为`INDEPENDENT`，但请求Schema同时允许两种lineage且未传`assigned_attempt_mode`；
  六份回答都选择`ADVERSARIAL_REVISION`，runner却统一按`INDEPENDENT`记账。权威根因为
  `APPROVED_INDEPENDENT_SLOT_MODE_NOT_BOUND_IN_REQUEST_OR_RUNNER`，裁
  `STOP_LOCAL_IMPLEMENTATION_DEFECT`。
- 次级字段错误为搜索积超196占5/6、文本安全2/6、父哈希2/6、缺必填字段1/6；因首要本地缺陷，
  “是否值得新live批”的次级门未评价。独立audit 12项PASS，断网幂等复跑报告/audit与R3C原账本哈希
  不变；scheduler原身份健康。
- 下一合法目标仅为R3E零API合同恢复：把批准mode确定性绑定到request/schema/compiler/账本并机械分配
  合法搜索积；保持validator、196上限和全部研究边界不变。R3E不是新调用授权。见
  `docs/TS_V5_R3D_OFFLINE_PROPOSAL_DIAGNOSTIC_ACCEPTANCE_20260813.md`。

## 2026-08-13 · TS-v5-R3C六机制合同金丝雀权威停止

- 用户精确批准scope `234621cf...953ae`后，execution release提交`ad77847`先行推送；无密钥断网
  preflight确认终版镜像/代码快照、六请求束、两个空专属账本和原scheduler身份全部一致。
- 唯一真实容器串行取得恰好6/6份完成响应，六机制各1份；HTTP 200为6、重试/递补/第7次调用/计费
  不确定均为0，实际费用`$0.012032535`。六份content均可解析JSON，但严格proposal Schema或确定性
  编译合同全部FAIL，有效唯一候选0，权威`STOP_NO_VALID_CANDIDATES`。
- 断网无密钥独立审计11项全部PASS；断网全只读复跑新增调用0，release、两账本、主报告和审计报告
  哈希前后不变。未发送或读取证券、行情、收益、持仓，未运行参数搜索、回测、模拟仓、Web或生产；
  scheduler保持原容器健康。
- 本scope永久关闭，不得人工修补、递补或第7次调用。策略效果仍`NOT_EVALUATED`、生产授权`none`；若
  继续，应先另立零API/零行情R3D离线匿名失败诊断，保持冻结validator不变。见
  `docs/TS_V5_R3C_LLM_CANARY_ACCEPTANCE_20260813.md`。

## 2026-08-13 · TS-v5-R3C六机制合同金丝雀预执行门完成

- scope提交`c8bb9ed`先于实现推送，冻结六机制各1份独立响应、无递补/第7次调用、最坏费用
  0.051156美元和0.15美元硬熔断；唯一scope SHA为`234621cf...953ae`。
- 六请求bundle `f10e5e41...b6ff`、proposal分类/确定性编译、复用transport/标准账本/统一费用、独立
  audit和结果前release门均已完成；MockTransport六席、幂等复用和离线复算PASS。实现`a2f215d`、
  路径与manifest加固`3b85077`均已推送。
- 首个加固镜像因40位Git build-arg手工转录错误永久标为provisional；它只有断网/无secret预检，API与
  费用0。终版镜像`sha256:0c07a2eb...b92a`已用真实完整HEAD重建并逐字段核对；无
  release时即使注入哨兵密钥也退出码2。全仓1246、架构13项PASS，scheduler原镜像连续运行且healthy。
- 权威`READY_FOR_EXPLICIT_LIVE_APPROVAL`：当前API调用、secret读取和费用仍为0。须用户逐字批准唯一
  scope、恰好6响应和0.15美元后，才可冻结execution release；效果/回测/模拟仓/生产仍禁止。见
  `docs/TS_V5_R3C_LLM_CANARY_PREEXECUTION_ACCEPTANCE_20260813.md`。

## 2026-08-13 · TS-v5-R3B机制专属合同投影工程门完成

- R3A确认的模型侧合同投影缺口已闭合：六机制分别生成proposal Schema与精确projection，LLM只填写
  研究语义和边界内选择；reference/measure、两个强制取消规则及全部必需features由同源编译器确定性
  补齐，终产物仍必须通过字节不变的冻结`MechanismCandidate`。
- 六个最小proposal全部编译，21条规则/机制均有投影或确定性来源，42/42个对抗样例fail closed；独立
  audit完整重算PASS，二次运行write-once哈希不变。权威
  `GO_NEW_LIVE_CANARY_SCOPE_PROPOSAL_ONLY`，不是新调用授权或策略有效性结论。
- 外部调用、secret/行情/收益读取、旧R2候选修补、参数搜索、回测、模拟仓、Web和生产均为0；策略仍
  `NOT_EVALUATED`、生产授权`none`。如继续须另立小批live canary scope/release并获用户明确批准。
  见`docs/TS_V5_R3B_CONTRACT_PROJECTION_ENGINEERING_ACCEPTANCE_20260813.md`。

## 2026-08-13 · TS-v5-R3A离线合同诊断完成

- 结果盲scope `9f82d89f...e48e4d1`在展开四份R2 content前先行推送；随后只读四份不可变响应，
  未使用reasoning、未调用LLM、未读行情/收益，未修补候选或回测。
- 四份共同主因是`INCOMPLETE_LLM_FACING_CONTRACT_PROJECTION`：4/4均违反只存在于本地自定义validator、
  未完整投影到模型可见Schema/candidate limits的规则；仅第2份另违反可见的长度和Feature枚举。
  JSON Schema表达缺口4、提示合同缺口4、模型可见规则不服从1、validator缺陷0。
- 权威`GO_R3B_CONTRACT_PROJECTION_RECOVERY_ONLY`：保持validator不变，下一步应以同源机制专属约束投影
  和确定性编译器补齐强制取消规则/required features，LLM只填研究语义和边界内选择。不是新调用授权；
  R2四份仍无效且不得修补录取。见
  `docs/TS_V5_R3A_OFFLINE_CONTRACT_DIAGNOSTIC_ACCEPTANCE_20260813.md`。

## 2026-08-13 · TS-v5-R2四响应合同金丝雀权威停止

- 用户精确批准scope `e2d7218f...e1a8ef`后，结果前实现`d077ca4`、独立镜像、空账本和execution
  release依次冻结并推送；一次transport SHA手工录入错误在零调用/零密钥阶段由独立提交留痕纠正。
- 唯一真实批次串行取得恰好4/4份完成响应，外部调用4、重试0、递补0、第五次调用0；实际费用
  `$0.006332411`，无计费不确定性。四份content均为JSON，但严格候选Schema全部FAIL，因此有效候选0，
  权威`STOP_NO_VALID_CANDIDATES`；不得补发，不读取策略效果，不运行参数搜索或回测。
- 断网无密钥独立审计逐请求、逐哈希、逐响应重分类和费用复算PASS；断网幂等复跑新增调用0且四类证据
  哈希不变。未读/未发证券、行情、持仓、收益、首批响应或reasoning，生产scheduler原身份健康。
- 本scope永久关闭；若继续须先离线匿名分析Schema失败机制，再另立新scope和用户批准。
  `candidate_effectiveness=NOT_EVALUATED / production_authorization=none`。见
  `docs/TS_V5_R2_LLM_CANARY_ACCEPTANCE_20260813.md`。

## 2026-08-13 · TS-v5持续演化研究治理冻结，工程开工但外部研究未授权

- TS-v5-R2四响应合同金丝雀预执行门已`GO_PREEXECUTION_ONLY`：scope提交`89da7a5`先行推送，唯一
  scope SHA-256为`e2d7218f...a1a8ef`；固定波动自适应/周结构分位/突破回踩/均线恢复四个独立席位，
  无反方、无递补、无第五调用，最坏费用0.034104美元、硬上限0.10美元。实现提交`5cb8ff8`只新增157行
  scope/请求束预检，复用v2响应画像和原请求安全门；4请求束SHA-256为`0068357f...e489b`。全仓1175、
  架构13项通过；正确镜像`sha256:510c0a99...819de`在断网、只读根、非root、无secret条件下同结果PASS。
  首次镜像构建曾手工传错1字符Git哈希，该镜像未运行、未入release且已由正确身份镜像取代。当前API
  调用、secret读取和费用均为0；须用户逐字批准scope哈希后才可另立live release。见
  `docs/TS_V5_R2_LLM_CANARY_PREEXECUTION_ACCEPTANCE_20260813.md`。

- 首批真实DeepSeek机制研究已完成并权威`STOP_NO_VALID_CANDIDATES`：12/12完成响应（6独立+6反方），
  串行、外部调用12、实际费用0.03012781美元、幂等复跑调用0；12份均因provider结束原因非`stop`
  而计为无效，Schema合法候选0。原始报告误以“响应齐全”给出`GO_CANDIDATES_ONLY`，报告保持不可变，
  独立断网audit后追加纠正；禁止补发、复用本approval、参数搜索、回测、模拟仓、Web或生产。TS策略族
  不因本批停止。见`docs/TS_V5_LLM_FIRST_BATCH_ACCEPTANCE_20260813.md`。

- TS-v5-R1响应合同恢复工程门已`GO_RESPONSE_CONTRACT_ENGINEERING_ONLY`：首批12份不可变envelope只读
  复核为12/12 `finish_reason=length`、12/12恰好用满1800 completion tokens、12/12最终content为空
  且reasoning非空，根因是思考阶段耗尽固定输出预算。协议提交`815212d`先于实现提交`97aba0d`推送；
  v2仅显式关闭thinking并移除reasoning_effort，1800上限、候选Schema、提示、六机制和发送边界均不变。
  `length`仍永久失败，只有`stop+非空JSON object+严格Schema`可进入候选。全仓1172、架构13项通过；
  独立镜像`sha256:0bd9e9b4...d09d2`在断网、只读根、无secret条件下复核PASS。当前外部调用/费用新增0，
  不授权补发、参数搜索、回测、模拟仓、Web或生产；新批仍须新scope和用户批准。见
  `docs/TS_V5_LLM_RESPONSE_CONTRACT_RECOVERY_ACCEPTANCE_20260813.md`。

- 用户已明确批准v1 scope
  `9947e1bebc10d5da32df63ff462a8c8e9403a12986dbfef0a891f69956325a88`执行首批恰好12个
  DeepSeek完成响应和0.50美元单批熔断。该明确批准晚于预算v2，因此v1恢复控制本批，v2只保留5美元
  总预算背景且不得扩大本批。当前先施工并验收最小协调器/证据/独立audit，未读取secret、未联网；
  实现提交推送并冻结绑定release后才可真实执行。见
  `docs/TS_V5_LLM_EXECUTION_PROTOCOL_20260813.md`。
- 执行前实现经轻量provider合同抽离与架构棘轮复核后以`9d979c9`推送，专用最小镜像和内容快照已
  重新生成；正式release现绑定该提交、镜像ID、
  代码快照、请求束和两份空专属账本。下一步须先推送release并通过无secret Docker preflight，之后才
  能读取项目内DeepSeek密钥并执行唯一批次。
- v1 release的两次无密钥preflight分别暴露专属目录未创建和旧D1重型导入链；两次均在secret、TLS、
  provider调用和账本写入前停止。v1保持原样并由v2显式记录为`FAILED_BEFORE_SECRET_NETWORK_OR_PROVIDER_CALL`；
  v2只绑定轻量provider修复后的`4e5cb60`和新镜像，研究scope/提示/12响应/0.50美元均不变。

- 用户纠偏TS不能因具体规则失败就停止；TS现正式定义为长期策略研究族，只有用户明确退役才关闭。
  v3/v4固定百分比结论原样保留，只停止具体版本，不停止“强市场—强板块—强个股—右侧波段”方向。
- 新生命周期分为探索沙箱、候选冻结、验证、锁定历史测试、独立模拟前瞻和生产评审。探索允许利用
  发现期反馈持续改版，但所有候选、参数评价、重复和失败均永久计数；逻辑改版与参数优化分离，封存期
  不得用于失败后的替补选择。
- 首轮机制限定为波动自适应回调、周结构分位、突破回踩、均线恢复、收缩扩张和相对强度回调六类。
  DeepSeek定位为候选生成/批判/语义复核，不裁决收益；本地程序负责数据、参数搜索、回测、统计、去重
  和所有权威门。候选合同、六机制枚举、参数/复杂度边界、语义去重、受限提示、TS专用窄传输适配与
  CLI已完成；专项22、
  全仓1157、架构13项通过，离线preflight为PASS，provider/行情效果/secret读取均为0。
- 当前停在`READY_FOR_BOUNDED_LLM_RESEARCH_APPROVAL`；尚未授权真实DeepSeek调用、行情/收益、回测、
  模拟仓、Web或生产。用户已将TS-v5持续研究总费用硬上限提高到5.00美元，但这不是自动调用授权；
  首批仍固定恰好12响应、串行和0.50美元单批上限，后续每批仍须另立scope并明确批准。v1在零调用、
  零secret读取时由预算v2显式取代；v2当前`execution_authorized=false`，仍须用户按新哈希批准后才能
  生成执行release。见
  `docs/ADR_0006_TS_EVOLUTIONARY_RESEARCH_LANE.md`、
  `docs/TS_V5_EVOLUTIONARY_RESEARCH_PROTOCOL_20260813.md`和
  `docs/TS_V5_EVOLUTIONARY_RESEARCH_ENGINEERING_ACCEPTANCE_20260813.md`、
  `docs/TS_V5_LLM_RESEARCH_SCOPE_PROPOSAL_20260813.md`和
  `docs/TS_V5_LLM_RESEARCH_BUDGET_ADDENDUM_20260813.md`。

## 2026-08-13 · TS-v4B-R1结果盲密度门STOP，固定百分比参数区域关闭

- R1在结果未知时只修DuckDB Parquet写出边界并绑定新镜像；最终镜像内专项21项通过。唯一断网真实
  画像和唯一独立audit已经消费，原失败scope及R1 scope均不得重跑。
- 2019—2021发现期四臂1.5%/2.5%/3.5%/4.0%分别只有5/5/4/4个合法事件、4/4/3/3个信号日；
  2019年全部为0，四臂均未达到30事件、20信号日和逐年5事件，且没有相邻通过对。Alpha158仅投影键，
  覆盖均100%、重复0，未读分数或排名。
- 机器裁决`STOP_NO_DENSE_PARAMETER_REGION`，独立audit 18/18 PASS。策略效果尝试仍为0、
  `NOT_EVALUATED`、生产授权none；未读收益/基准点位，未联网、读密钥、训练、回测、建模拟仓或改
  Web/生产。固定百分比网格不得按已见数量扩展或降门槛；若继续TS须另立具有新研究含义的波动自适应/
  结构分位版本，任何效果前仍须闭合H00906全收益谱系。见
  `docs/TS_V4_DENSITY_PREFLIGHT_RECOVERY_R1_ACCEPTANCE_20260813.md`。

## 2026-08-12 · TS-v4B首次画像写出前失败，R1单点恢复已冻结

- 已推送实现`eec7315`和镜像`sha256:7a14fc…e560`通过全仓1130项、架构13项和镜像专项16项；唯一
  真实画像在第一份Parquet写出前因DuckDB COPY参数绑定把`20190102`当输出路径而失败。事件/日报/
  报告/audit均未写出、结果值未暴露，scheduler保持原容器healthy；原scope永久不重跑。
- R1只把“同一COPY内混合日期与路径参数”改为“relation先绑定日期、再显式write_parquet”，输出改到
  独立R1目录；四臂、输入、状态机、日期purge、密度阈值和结果防火墙全部不变。须新增真实写出
  fixture后重新固定已推送镜像身份，再运行唯一一次R1画像与独立audit。
- 该失败不是策略或密度结论；收益、Alpha分数、H00906点位、外网、密钥、模型、回测、模拟仓、Web和
  生产仍未授权。见`docs/TS_V4_DENSITY_PREFLIGHT_RECOVERY_R1_PROTOCOL_20260812.md`。

## 2026-08-12 · TS-v4B一次性结果盲密度预检已在真实运行前冻结

- v4B只在2019—2021发现期画像1.5%/2.5%/3.5%/4.0%四臂；每段末尾按v4A删除最后16个官方
  信号日。每臂须同时达到30个合法事件、20个不同信号日、2019—2021每年各5个，且Alpha158事件键
  无重复并100%覆盖；至少一对相邻参数通过才可继续，否则机械停止。
- 只复用v3 R4结果盲状态内核并参数化触达线；画像/独立audit各仅一次。收益、Alpha分数、H00906点位、
  模型、回测、外网、密钥、模拟仓、Web和生产仍禁止。四臂永久计四次策略尝试，效果尝试仍为0。
- 下一步是在合成fixture、镜像身份与结果防火墙通过后，用已推送实现运行唯一一次断网真实画像；画像
  后不得改阈值或扩参数。见`docs/TS_V4_DENSITY_PREFLIGHT_RELEASE_PROTOCOL_20260812.md`。

## 2026-08-12 · TS-v4A继续研究协议冻结，尚未授权读取收益

- 用户裁定TS不能因v3精确基线样本不足而放下，允许调整合理参数以寻找相对更好的扣费收益。v4首轮只
  改“上一完整周VWAP回调深度”一个变量，固定1.5%/2.5%/3.5%/4.0%四臂；恢复、止损、止盈、15日、
  两批仓位、市场/板块、容量和执行规则全部继承，禁止再扩网格。
- 时间严格分为2019—2021发现、2022—2023验证、2024锁定历史测试；每段末做16个信号日成熟purge。
  2024的市场环境已用于既有压力讨论，因此不冒充完全未知样本外，最终仍只认自然前瞻。
- 先做只读发现期密度门；只有至少一对相邻参数各达到30事件/20信号日/每年5事件且Alpha键100%覆盖，
  才能另行授权四臂发现期效果。选择要求相邻参数平台、全四臂计N、DSR>=0.95，验证或测试失败后禁止
  换第二名。
- H00906全收益序列仍须在任何效果前单独恢复并审计，不得用价格指数或本地代理。当前收益、Alpha158
  分数、基准点位、画像、回测、模拟仓、Web、生产、外网和密钥均未授权。见
  `docs/TS_V4_PARAMETER_RESEARCH_PROTOCOL_20260812.md`。

## 2026-08-12 · TS-1A-R4结果盲回调状态样本门STOP，策略效果未评估

- R4协议和操作化附录先于真实画像冻结并推送；结果前固定上一完整周VWAP下4%触达、同周恢复确认、
  紧邻下一开盘、结构止损距离严格小于15%，以及2019—2024至少60条/40个信号日、每年不少于3条且
  至少四年各不少于8条的样本门，真实运行后未改写任何门槛。
- 唯一断网画像形成23个确认事件：10个合法、13个因下一开盘高于周锚点拒绝。2019—2024只有8个
  合法事件、5个不同信号日，年度为2020/2021/2023/2024各3/1/3/1，四项样本门全部失败，机器裁决
  `STOP_INSUFFICIENT_TRUE_EVENTS`。
- Alpha158只读事件键，8/8覆盖、重复0、未读分数或排名。R3 manifest元数据无显式H00906身份，基准
  门另为`BLOCKED_BENCHMARK_DATA`，未以价格指数或本地代理替代。
- 独立audit `PASS`，产物、行数、年度/状态计数和禁读字段全部复算一致。效果尝试0、策略仍
  `NOT_EVALUATED`、生产授权none；未联网、读密钥、训练、回测、建模拟仓或改Web/生产。
- 该结论不推翻R3数据门GO，也不等于所有TS方向无效；只停止当前精确基线，禁止按已见数量放宽规则。
  若未来继续须另立具有新研究含义的版本并登记新尝试，不能同scope重跑。当前回到R2-1自然前瞻主线。
  见`docs/TS_V3_PULLBACK_STATE_PREFLIGHT_ACCEPTANCE_20260812.md`。

## 2026-08-12 · TS-1B效果协议冻结前复核STOP，须先闭合回调状态与全收益基准

- 结果盲复核确认 R3 的 832 行实现只要求日线恢复形态，没有要求当周先触达事前回调线；因此它们不是
  可直接进入效果协议的“回调后恢复事件”。2019—2024 的 414 个恢复候选中，154 个在下一开盘的
  结构止损距离严格小于15%，但该数仍只是上界，不能据此冻结最低交易数。
- R3 输入已绑定中证800价格指数`000906.SH`，尚未绑定基线要求的中证800全收益指数 H00906；真实
  效果前必须取得可审计谱系，否则`BLOCKED_BENCHMARK_DATA`，不得构造代理或静默降级。
- 本次裁决`STOP_BEFORE_FREEZE`不推翻R3数据门GO，也不是策略REJECT；收益/MAE/MFE、Alpha158分数、
  训练、回测、外网、模拟仓、Web和生产均为0，策略仍`NOT_EVALUATED`。
- 下一合法节点收窄为`TS-1A-R4`：先冻结唯一回调触达、恢复、结构止损/上移、止盈和次日合法开盘
  口径，再做一次序列化结果盲匿名画像与独立audit，同时只做H00906基准谱系预检。见
  `docs/TS_V3_EFFECT_PREFREEZE_REVIEW_20260812.md`和
  `config/ts_v3_effect_prefreeze_review_v1.yaml`。

## 2026-08-12 · TS-1A-R3结果盲恢复GO，允许另立TS v3冻结协议

- 用户精确批准 release scope `380503cb...7256` 后，R3 建立唯一 claim 并完成固定3个 Tushare
  `index_daily`请求：创业板指全历史2,576行、科创50尾段12行、中证800缺口1行；实际3次传输尝试，
  无重试、无密钥输出，同 scope 已消费且禁止重跑。
- 三个追加式批次的`operator`及audit schema因旧常量仍标R2；R3 release/claim/receipt、协议哈希、
  批次和审计绑定均正确，故不改数据裁决。原文件不回写，终版文档披露缺陷，代码只修未来名称并锁定
  回归测试。
- 断网真实画像裁决`GO_TS_V3_FREEZE`，独立audit `PASS`。三指数冻结范围内官方开市日缺失/重复/冲突
  均为0；PIT中证800合法成员日2,060,710，真实bar 2,028,944加独立不交易31,766实现100%解释，
  无法解释缺口、生命周期冲突、重复/冲突键和`.BJ`均为0；申万L1覆盖99.2539%通过冻结门槛。
- 既有Alpha158缓存只读事件键：缓存范围内414/414候选键匹配，418个范围外事件禁止用当前模型回填；
  分数、排名及候选后收益均未读取。匿名规则形成832个候选、331个有候选日，832个次日开盘均可执行，
  最长连续空候选136日。
- 一个结果前风险必须进入下一协议：止损距离中位约17.99%，535/832不低于15%。下一节点须先冻结
  过宽止损拒绝、按止损距离缩仓、单票/组合风险以及唯一退出和效果口径，不能看收益后调参。
- 策略效果尝试仍为0，`strategy_effective=NOT_EVALUATED`，生产授权none；未训练、回测、推荐、模拟仓、
  Web或生产。下一合法动作仅另立并复核TS v3结果前退出与效果协议。见
  `docs/TS_V3_DATA_GATE_RECOVERY_R3_ACCEPTANCE_20260812.md`。

## 2026-08-12 · TS-1A-R3三指数完整性恢复施工记录

- R1 数据恢复协议和操作化附录已先后冻结，但在 release、claim、密钥读取、provider 调用和真实画像
  全部为 0 时，只读键级复核发现科创50指数历史仅到 2026-07-24，短于研究截止日 2026-08-11。
  R1 因此永久记 `SUPERSEDED_BEFORE_EXECUTION_BY_R2`，不是一次失败尝试，也没有消耗授权。
- R2 结果前固定两个且仅两个 Tushare 请求：`399006.SZ` 2016-01-01—2026-08-11 全历史，以及
  `000688.SH` 2026-07-25—2026-08-11 缺失尾段。两响应必须都完成语义校验后才允许提交；三条指数
  各自在冻结起点后的官方开市日缺失、重复、冲突必须为 0。见
  `docs/TS_V3_DATA_GATE_RECOVERY_R2_PROTOCOL_20260812.md`。
- R2 仍在零 release/claim/provider/画像时，统一日历 anti-join 又确认中证800缺 2026-07-15 单日；
  因此 R2 同样在执行前由 R3 继任。R3 最终固定三请求：上述创业板全历史、科创50尾段及中证800
  2026-07-15 单日，三响应必须全部校验后才提交；三指数冻结全范围日历差必须统一为0。见
  `docs/TS_V3_DATA_GATE_RECOVERY_R3_PROTOCOL_20260812.md`。
- 结果前实施附录进一步明确：上一有效高点只由日线+复权构造，不受上一日市值/行业/ST过滤影响；
  TS-1A-R2 对 Alpha158 只读 `ts_code/trade_date` 做事件键覆盖，禁止读取分数或排名。见
  `docs/TS_V3_DATA_GATE_RECOVERY_R2_OPERATIONALIZATION_20260812.md`。
- 当时只完成离线模块、完全合成端到端 fixture与三段短命Docker边界；该执行前状态已由上方R3正式
  验收继任，候选后收益仍从未读取。
- R3实现提交`cbf7f0a43848398c245628c2761c4b9b4edc5be4`已推送；全仓1,091、架构13、R3专项12、
  Ruff/compileall/Compose/脱敏均PASS。精确release scope为
  `380503cb57169032627703103c034d997f6c51afb759fc315b0c56426f697256`，绑定代码快照
  `4faa4cee...a169`、当时ingest ledger物理SHA `d5d54986...c940`和上述三请求；之后已按该scope唯一执行。

## 2026-08-12 · TS-1A结果盲数据门双阻断，策略效果未评估

- TS-1A按冻结协议唯一真实运行完成：外网/DeepSeek/provider调用0、效果尝试0、生产变更0；独立audit
  PASS，但权威裁决为`MULTIPLE_BLOCKS`：`BLOCKED_MARKET_RULE + BLOCKED_DATA`。这不是策略
  REJECT，不得进入TS-1B、回测、模拟仓或Web。
- 市场门缺`399006.SZ`创业板指历史；冻结映射禁止用中证800替代。个股门2,060,800个PIT中证800
  成员日中，日线或主源全天停牌解释覆盖99.99539%，仍有95日不满足硬门0。
- 结果盲键级诊断确认95日不是同一种问题：90日落在7只证券的`delist_date`及之后；余下5个单日洞
  已有项目内Baostock `trade_status=0`证据。v1漏把`stock_basic`右开退市区间与Baostock状态列为
  required sources，故必须保留BLOCKED，不得用运行后发现静默补合同。
- 其余质量证据良好：`.BJ=0`、重复/冲突键0、复权/市值/成交额在有bar日覆盖100%、申万L1覆盖
  99.2539%；既有Alpha158 OOS缓存1,164,697行存在，但事件键覆盖因上游阻断未评价。
- 下一合法节点仅`TS-1A-R1`结果盲数据合同恢复：先冻结`stock_basic`/Baostock解释口径，再经用户精确
  授权补采`399006.SZ`，断网完成全部候选漏斗画像。不得把“补完数据”表述为策略有效；见
  `docs/TS_V3_DATA_GATE_ACCEPTANCE_20260812.md`。

## 2026-08-12 · TS升级为v3强板块—强个股—右侧波段方向

- 用户确认将“月线右侧趋势许可、周线回撤入场、日线真实执行、短周期规则退出”作为重点旁线；正式
  编号`TS`（Trend Swing），定位为趋势内均值回归/波段策略，不预称无风险或稳定套利。
- 优先级固定为生产/R2-1主线 > TS重点旁线 > RF及普通研究扩张；TS必须使用独立策略、身份、证据、
  账本和未来模拟账户，不覆盖中证800 Alpha158主策略。
- 联网资料支持研究中期趋势、移动平均和波动归一化，但A股动量/反转/成交量证据不统一；固定
  3%—5%买点、5%—10%止盈以及“触线即成交”均在读取TS收益前作废，缩量与10日涨幅继续只作后续
  单变量诊断。
- v2解决v1的接飞刀、无市场状态、无候选优先级、固定仓位和止损伪成交问题：月线同时要求中证800与
  个股`close>SMA6`且`SMA6`上升；周线冻结VWAP/ATR20，价格触达`VWAP-1R`只进入观察，随后须日线
  `close>前日high`、阳线且指数`close>SMA20`，再于下一官方交易日合法开盘区间买入。
- 用户在结果读取前进一步冻结v2.1组合意图：单票两批合计上限10%，第一批最多5%；第二批仅在持仓
  盈利、收盘重新站上冻结周锚且指数仍许可后，于下一合法开盘加仓，禁止下跌补仓或第三批。正常持仓
  3—7只、硬上限7只，总名义仓位上限70%；信号不足允许少于3只并持有现金。
- 同期严格OOS Alpha158分数只决定稀缺仓位优先级，不改变触发；缺合法历史分数链直接阻断。两批合计
  单票0.5%计划风险、组合3%风险、行业30%和20日中位成交额5%容量约束继续有效；每周约5日刷新候选，
  第5/10日只留复核快照，第15个交易日硬退出，`+1.5R`止盈和`-1R`风险退出可提前发生。
- Alpha158足以作为TS首版排序基线，但未被认定为最终充分：它覆盖成熟日频量价族，却不直接表示
  TS月/周/日事件路径，且原约10日收益标签与TS条件入场/最长15日退出不完全一致。TS-1A须结果盲核验
  OOS分数覆盖、成熟时钟与标签适配；后续如挖新因子，优先缩量和10日过热，一次一个机制并先证明相对
  Alpha158非重复，禁止把多个新因子一次性混入v2.1救回失败基线。
- 用户进一步确认v3方向：先要求大盘/主要市场不创新低，再选择相对走强的热点板块；板块内股票市值
  不低于200亿元、完整周成交额不低于50亿元，单日30亿元放量暂作加分；至少三根完整月K线支持连续
  两月高点提高，最近三根完整周K线低点不下移，再由日线寻找回调后转强买点。
- v3继承两批各最多5%、单票10%、3—7只、总仓位70%、风险预算、T+1、真实开盘、容量和允许长期空仓。
  初始止损暂定冻结上周低点下浮2%，以后只能上移。v3覆盖统一中证800/SMA20市场许可、SMA6月线许可、
  `VWAP-1R`唯一入口和固定ATR止损，但板块强度、连续两周波动与放量仍须结果盲量化，尚不授权效果。
- 下一合法动作仅v3 TS-1A结果盲量化与数据门：冻结市场/板块映射，画像板块强度、波动、放量、
  月周日字段、OOS分数谱系、状态漏斗和容量；不授权收益、
  MAE/MFE、参数网格、训练、回测、Web、模拟账户或生产。见
  `docs/TS_0_TREND_SWING_STRATEGY_DESIGN_BASELINE_20260812.md`。
- TS策略—产品交付路线已整理：后台未来以原子快照输出具体股票、两批计划买点、结构止损、盈利/时间
  退出、原因、状态和证据；Web只读展示且不得重算或补推荐。首版反馈采用稳定反馈编号和复制模板，
  反馈只进入追加式`OBSERVE/PROPOSE`，不能回写当天信号或历史计划；页面直接写反馈须另立安全ADR。
  见`docs/TS_V3_STRATEGY_PRODUCT_PLAN_20260812.md`和`WEB_QUERY_CONTRACTS.md`的P-WEB-08提案。

## 2026-08-12 · Docker旧镜像受控清理完成

- 经用户明确批准，删除41个仅属于筛微且未被容器使用的旧镜像标签：Web测试/构建、已淘汰scheduler/
  开发预检、明确标记provisional/wrong-git/unreadable/missing的M6失败构建，以及已被终版替代的M7
  中间镜像；其中40个为独立镜像，1个旧scheduler标签与保留回滚镜像共用内容。
- Docker镜像总数由90降至50，镜像占用由143.8GB降至103.7GB，约释放40.1GB。当前scheduler、Web、
  research-control、上一版scheduler回滚镜像、权威研究复算镜像、M7终版归档镜像均保留。
- 筛微scheduler/Web/research-control和枢衡Web共5个运行容器全部healthy；未删除容器、卷或构建缓存，
  未触碰枢衡及其他项目镜像。Build Cache仍为145.5GB，其中45.63GB当前可回收，需另行授权才清理。

## 2026-08-12 · RF-0A中证800单机制结果盲准备GO，正式研究仍未授权

- R2-1自然前瞻继续作为主目标；等待期允许推进不读效果的数据、身份和协议准备，但不得用准备工作
  提前启动DeepSeek、候选、训练或回测。
- 只读盘点确认三份既有LLM账本共104次尝试、70行非空公式、63个唯一公式哈希；通用动量/反转/
  波动/流动性/量价主题已较拥挤，而历史非空公式对`open`引用为0。G1账本现有29个版本、21个
  “研究族+精确公式”身份，正式准入仍为0。
- 选择“隔夜信息吸收与日内反转状态”作为唯一后续机制问题；Alpha158已包含`OPEN0`、`KMID`和K线
  位置等特征，故本方向重复风险高，必须证明联合状态在语义/AST、暴露、IC残差和组合净结果五层均
  有增量，不能把开收盘差改名当新因子。
- 数据仅裁为`FIT_FOR_PREPARATION`：PIT中证800、开盘/收盘字段和既有时钟可复用，但尚缺open/前收盘
  专项目标字段画像。下一可执行节点仅RF-0B结果盲数据与身份预检；正式8响应小批须等R2-1检查点后
  另立协议并获用户授权。见`docs/RF_0A_CSI800_SINGLE_MECHANISM_PREPARATION_20260812.md`。
- 本轮未使用发现/封存效果，未调用DeepSeek/provider，未生成候选、训练、回测或修改生产/Web；七类
  自然账本保持既有未提交追加状态。

## 2026-08-10 · 自然跑批证据归档至第6个live-dual日

- 20260810日增量`ce0f5efb9a12`、20260807→20260810次日开盘对账`3e0ff7f87562`、影子信号
  `78deaf15086e`均PASS；S1—S9 PASS、S10 NOT_APPLICABLE，`.BJ=0`，今日信号
  `rebalance_due=false`。飞书日增量、对账、信号及两个模拟账户的开始/完成通知均首次投递PASS。
- Top30账户`85727fc5931b0c0c53b9`与Top20账户`6a0e70008d58316cb4bf`均为Docker scheduler自然
  FORWARD、订单/成交0、会计和新鲜度PASS；生产镜像内独立重放与前瞻验收均PASS，两个账户的
  `bse_event_count=0`。R2-1主序列因此由5日推进为6个`LIVE_DUAL_FORWARD`日，仍为0次自然调仓；
  首次调仓核验仍预计20260814，20日/2次门仍最早预计20260828。
- 本次一并归档20260805—20260810尚未提交的七个自然账本末尾追加，共228行、删除0；账本追加门
  25 PASS，调度/影子/模拟仓/通知专项92 PASS，架构门13 PASS，全仓1,069 PASS。新增行不含凭据、
  绝对本地路径或`.BJ`。未修改生产代码、模型、门禁、调仓规则或服务，未启动新因子、ETF策略或
  DeepSeek研究批。

## 2026-08-10 · LLM因子与策略研究工厂治理基线固定

- 用户确认长期采用LLM作为知识侦察、因子挖掘、策略研究、结果盲反方审查和研究记忆；确定性代码、
  冻结协议、独立audit与真实前瞻负责裁决，LLM不获准改门槛、读封存结果后调参或直接上线。
- 因子与策略为并行分支：策略可在不新增因子时只改变一个模型/组合变量；中证800研究与现有主策略
  使用独立身份、产物和账本，好的新策略建立独立模拟账户而非覆盖主策略。
- R2-1后首批默认中证800/一个机制/8响应/最多3候选/机械Top1/Top2，连续最多3个小批后强制复盘；
  失败、重复均计N，不补位，不沿用旧D1模型/价格/余额。
- 长期自动化确定性执行、审计、投影和已批准模拟账户，不自动授权、调门槛或生产发布；高配置电脑未来
  只作为隔离research-worker，至少3个真实批次证明复用后才评审队列/并发Worker。
- 当前仅固定`FROZEN_DESIGN_BASELINE_NOT_EXECUTION_AUTHORIZED`；R2-1前代码、DeepSeek、候选、效果、
  Web执行、模拟账户和生产变更均为0，七个自然账本未触碰。见
  `docs/LLM_RESEARCH_FACTORY_GOVERNANCE_BASELINE_20260810.md`。

## 2026-08-09 · Web 1.1.2 前瞻分层与当前路线修正 GO

- Web 已停止把 Top20 的10个协议`FORWARD`全部称为自然前瞻；后端权威分层为协议10日/1次调仓、
  受控追赶5日/1次、Top30/Top20同日自然5日/0次，R2-1仍为`NOT_DUE`（门槛20日+2次自然调仓）。
- 总览独立展示 Top30 单账户12个自然观察日与双账户共同检查点；模拟组合逐日显示证据层，当前5日只
  展精确表不画趋势，不给优胜、效果、风险调整指标或生产切换结论。
- 策略工厂保留不可变v3历史快照，并以路径+哈希绑定的overlay显示20260809真实路线
  `COURSE_CORRECTION_AND_OBSERVE`；当前只积累R2-1证据，M7候选/效果均为0，新增研究暂停。
- 新增模块最大399行并纳入架构棘轮，`types.ts`保持719行；Web仅使用白名单配置和单文件只读证据挂载，
  无写API、secret、Docker socket或项目根挂载。
- 架构13、全仓1,069、Web单元33、五视口69（另11项按场景跳过）、真实桌面7和移动7均PASS；最终
  Web镜像`30ee550b...0b421`，query/UI healthy且仅UI绑定`127.0.0.1:8080`。
- scheduler仍为原容器`183b8c6c...23dd3`/原镜像`722f63de...13b76`且healthy，research-control亦未
  重启；七个自然账本未暂存。工程裁决仅`GO_LOCAL_READ_ONLY`，策略仍`NOT_EVALUATED`、生产none。
  见`docs/WEB_1_1_2_TRUTH_CORRECTION_ACCEPTANCE_20260809.md`。

## 2026-08-09 · R2-1A自然前瞻检查点合同冻结并补正FORWARD分层

- 详细核对发现`d0d99cf`复盘把协议FORWARD与双账户同日自然运行混称：20260727—31的Top20由
  20260803受控追赶产生。历史`mode=FORWARD`合法且不改写，但不能并入live-dual主检查点。
- 当前分层固定为：协议FORWARD 10日/1次调仓；其中受控追赶5日/1次；真正双账户同日自然FORWARD为
  20260803—07共5日/0次调仓。旧以10日/1次直接作为自然门起算基数的口径显式作废。
- `r2-1-forward-checkpoint-v1`冻结共同状态锚点20260731、live-dual起点20260803、两账户/策略SHA、
  同日生成/同信号/同快照/100%日历覆盖/重放/会计/新鲜度/`.BJ=0`门及固定描述公式。
- 首次到期仍要求20个live-dual日+2次自然调仓；预计20260814形成第一次live-dual调仓，最早20260828
  同时形成第二次调仓和20日门。只允许`NOT_DUE/BLOCKED_EVIDENCE/OBSERVED_WITH_EXECUTION_WARN/
  CHECKPOINT_OBSERVED`，禁止优胜、效果GO/REJECT、生产切换、年化、Sharpe、IR或显著性。
- 本节点新增研究尝试0、未读取新增日期效果，仅复核既有mode/时间/身份；生产/Web/代码变更0，七个
  自然账本未暂存。见
  `docs/R2_1_FORWARD_CHECKPOINT_PROTOCOL_20260809.md`。

## 2026-08-09 · 第二次阶段路线复盘裁决收紧并转自然前瞻

- 主裁决`COURSE_CORRECTION_AND_OBSERVE`：平台整体方向正确，但8月6日后局部重现“恢复工程增长快于
  权威结果”的偏移；81个提交、342个tracked文件变化和41,260行文本净增，只形成M6一个新增归因结论，
  M6-3 Top20效果仍未评价，M7停在候选前数据NO-GO。
- 生产真身仍健康：截至20260807日增量17/17 PASS、次日对账16/16 PASS；Top30/Top20协议FORWARD
  为10日/1次，其中live-dual自然证据仅5日/0次调仓；正式实验账本864行但准入0。
- 立即停止M6-R4、M7-R4/R5；M5/M2/P4/G8、旧LLM批、新股票池/因子、队列/Worker/Web写能力和无目标
  重构继续暂停。不能用空档期制造开发任务。
- 下一主目标`R2-1 FORWARD_EVIDENCE_CHECKPOINT`不新增代码：预计20260814核验第一次live-dual调仓，
  若自然链路连续，最早20260828同时取得20个live-dual日和第二次调仓；只比较净值/基准/回撤/换手/费用/现金/成交证据，
  不作短样本年化、Sharpe或生产切换。
- A1-3B继续等待异机灾备，不阻塞自然前瞻。异常才做有证据的最小修复；无异常时保持系统运行就是正确
  施工。见`docs/PLATFORM_ROUTE_REVIEW_20260809.md`。

## 2026-08-09 · A1-3A M7本地归档恢复PASS，远端耐久性未就绪

- M7终局annotated tag `m7-moneyflow-recovery-final-20260809`已推送到`origin`，精确指向
  `49e9d740...98c7`，建立可远端恢复的代码锚点且禁止移动tag。
- 冻结arm64镜像`5b15e23f...b3da`已导出到项目内Git忽略只读tar，SHA-256为
  `d4f8e1e7...546d`；当前Docker引擎load回同一image ID，断网/只读/零项目挂载synthetic fixture PASS，
  外网和真实密钥读取0。
- M7终局真实执行证据复核为3,480文件/237,604,601 bytes，报告、manifest、audit哈希均与终局验收一致；
  未重跑provider/evaluator/auditor，未读取效果或生成新研究尝试。
- 裁决`LOCAL_ARCHIVE_REHEARSAL_PASS_REMOTE_DURABILITY_NOT_READY`：镜像和Git忽略证据仍无异机副本，也未
  在全新Docker引擎或另一台主机恢复，故不是灾备完成；`SAFE_DELETE_NOW=[]`、A1-3B未授权、删除0。
- scheduler保持`183b8c6c5edd`/`722f63de...13b76`/healthy且未重启；七个自然账本未暂存。下一步等待
  用户指定远程服务器或私有registry，再做异机恢复门；见`docs/ADR_A1_3A_M7_ARCHIVE_READINESS_20260809.md`。

## 2026-08-09 · A1-2活跃/归档/删除候选只读复核完成

- 当前tracked code 683文件/136,013行，核心Python 354文件/73,711行；较A1-0增长14,660行，但新增
  `>400`生产模块0、循环依赖仍0、唯一`src -> tools`冻结债务未扩大，代码结构尚未失控。
- A1-0后全部tracked文本净增20,379行，其中M7为153文件/18,632行；70个M7源码模块均小于400行且
  无外部生产import，已形成结构合格但关闭后的历史证据岛。
- `SAFE_DELETE_NOW=[]`：M7/M6仍承担唯一runner/auditor/批准/镜像复算职责，缺专用Git tag、远端镜像
  可恢复证据、归档ADR和逐文件退出清单；config、manifest、失败/NO-GO文档永久保护。
- M7可在归档PASS后评审退出当前主干的源码/测试/构建上界为105文件/14,660行，M6上界89文件/14,347
  行；二者均不是已批准删除清单，不设强制减行KPI。
- 下一建议仅A1-3A M7归档就绪ADR/tag/隔离恢复演练，删除0；须用户新授权。未改生产代码、未删文件、
  未运行数据/研究/生产，七个自然账本保持未暂存。见
  `docs/A1_2_ACTIVE_ARCHIVE_DELETE_INVENTORY_20260809.md`。

## 2026-08-09 · M7-0R3-P2真实网络恢复权威NO-GO，M7停止在候选前

- 用户精确批准scope`a701e9ce...cb73`后，四角色各唯一运行一次：75次Baostock状态、541次Tushare
  全市场moneyflow、541次单票单日moneyflow，共1,157次provider调用/传输尝试/不可变receipt，语义
  重试0；专用token副本使用后立即删除，`.env`未挂载、未修改或输出。
- 轨A的527个唯一状态键全部被独立确认未交易，908成员行闭合、冲突0、未决0；轨B的541个键在全市场
  262.1万行响应中仍全部缺失，541次单票单日响应也全部为空，恢复0、内容冲突0。
- 断网evaluator内部双算和独立auditor均PASS，权威`NO_GO_M7_EVIDENCE_RECOVERY_INCOMPLETE`；候选/效果/
  尝试0，策略`NOT_EVALUATED`、生产none。报告`94a3b093...7e3a`、audit`f870534a...6604`。
- 发现旧半年度segment校验与真实规模标签不一致，附加误报1,449行；轨B两项独立硬门仍失败，故不影响
  NO-GO，按同scope禁重跑规则仅留档、不改写报告或重算。
- 本scope关闭；按路线复盘硬停止规则不立M7 R4/R5、不算调整覆盖率、不进入八候选。下一主线为只读
  A1-2活跃/归档/删除候选清单，实际删除/重构仍须新目标和用户复核。scheduler原身份healthy且未重启。
  见`docs/M7_MONEYFLOW_EVIDENCE_RECOVERY_NETWORK_EXECUTION_ACCEPTANCE_20260809.md`。

## 2026-08-09 · M7-0R3-P2最终网络release就绪，停在精确批准前

- 最终scope`a701e9ce...cb73`绑定Git`2741a09`、代码束`a65cb9fa...9a24`、arm64镜像
  `5b15e23f...b3da`、计划manifest`dcc2a78d...f43`及四角色内容寻址挂载；最终断网mock fixture PASS。
- 精确上限为75次状态窗口、541次全市场moneyflow、541次单票单日moneyflow，共1,157个provider请求，
  最坏3,471次传输尝试；语义空响应不重试、已claim失败不重试、同scope不得重跑。
- 当前`approval_recorded/execution/network/provider/secret=false`，批准envelope和专用token文件未创建，
  真实调用仍为0；scheduler原容器/镜像healthy且未重启，七个自然账本未暂存。
- 只有用户绑定完整scope并批准动作`M7_MONEYFLOW_EVIDENCE_RECOVERY_ONCE`后才可执行；不得复用历史批准。
  见`docs/M7_MONEYFLOW_EVIDENCE_RECOVERY_NETWORK_RELEASE_ACCEPTANCE_20260809.md`。

## 2026-08-09 · M7-0R3-P2精确请求计划及独立审计GO，待最终网络scope

- 用户绑定恢复scope`3a5d201b...9592f`后，唯一断网auditor恢复PASS：75个状态窗口精确覆盖527键，
  541个全市场及541个单票单日请求精确覆盖资金流双形态；audit`4f63bfe8...7dd5`。
- 首次`/plans`挂载basename错误的FAIL永久保留且无产物；恢复只改为`/plans/<plan_id>`，同镜像、输入、
  算法和阈值不变，scope已关闭。provider/网络/secret/资金流数值/研究尝试仍为0。
- 聚合计划manifest`dcc2a78d...f43`已逐字节归档；同类检查发现四个未来真实角色也使用`/plans`，已在
  最终scope前统一修为内容寻址路径并加回归，未触发真实调用。
- 下一步只提交推送归档和挂载修复、重建最终镜像并生成精确网络scope，再停下等用户批准；不得直接
  联网或计算调整覆盖率。见
  `docs/M7_MONEYFLOW_EVIDENCE_RECOVERY_REQUEST_PLAN_ACCEPTANCE_20260809.md`。

## 2026-08-09 · M7-0R3-P2请求计划审计首次FAIL，挂载恢复scope待批准

- 真实请求计划已唯一生成且provider/网络/secret/资金流数值读取均为0；独立auditor首次调用因计划目录
  被挂成`/plans`、不满足内容寻址basename等于plan ID的自校验而fail-closed，未生成审计PASS产物。
- 只读分段诊断确认manifest、日历、plan ID、两轨目标身份、三份计划文件物理/逻辑身份及527/541键
  覆盖均PASS；故障属于执行挂载合同，不是数据或计划裁决，首次FAIL永久保留。
- 已冻结一次性挂载恢复scope：只把plan挂载改为保留内容寻址basename，Git/镜像/输入/算法/阈值不变，
  `network=none`且不挂载secret/生产目录；当前`execution_authorized=false`。提交推送并给出scope SHA后须
  用户绑定动作`M7_REQUEST_PLAN_INDEPENDENT_AUDIT_MOUNT_RECOVERY_ONCE`批准，若再失败则永久关闭。
  见`docs/M7_MONEYFLOW_REQUEST_PLAN_AUDIT_MOUNT_RECOVERY_20260809.md`。

## 2026-08-09 · M7-0R3-P2网络恢复release工程GO，停在真实请求计划前

- P2新能力已拆入独立`m7_moneyflow_network_recovery`扩展包，冻结旧包逐字不变；旧P1代码束回归哈希
  `17997e655...26d0`继续成立，避免新施工污染历史release。
- 已实现离线精确计划、四角色窄挂载、单独token文件、claim-before-provider、三次传输上限、write-once
  batch、离线evaluator/auditor与精确scope/approval契约；最大模块377行。
- 断网Docker fixture GO，全仓1,059、架构13及Ruff/compileall/pip/Compose/脱敏门PASS；scheduler
  healthy且未重启，7个自然账本未暂存。
- 真实键请求计划、provider、网络、`.env`/token、资金流数值仍为0；实现先推送，之后才允许一次断网
  真实请求计划，并在最终scope生成后停下等批准。见
  `docs/M7_MONEYFLOW_EVIDENCE_RECOVERY_NETWORK_ENGINEERING_ACCEPTANCE_20260809.md`。

## 2026-08-09 · M7-0R3-P1真实key-only投影GO，scope关闭

- 用户精确批准scope`9aca0457...81614`后，断网projector唯一完成：冻结lineage core
  `df5de3990428...eeca`匹配，轨A 908成员行/527去重源键，轨B 541/541；重复、PIT逆序、`.BJ`和两轨
  intended-grain交集均为0，内部replay PASS。
- 独立DuckDB auditor唯一完成，两轨内容哈希与主算逐项相同；report/manifest/audit分别为
  `a029072b...eac4`/`d8dba2e...6fa6`/`8356c5b3...d6f2`，双角色claim已封存且禁止重试。
- 用户明确“同scope不得重跑”，故没有启动第二个真实容器；不可重入由真实claim、loader前原子claim和
  同镜像真实规模合成二次调用门证明。一次探针请求在容器创建前被权限审查拒绝，产物哈希零变化。
- 数值读取/provider/网络/调整覆盖率/候选/效果/尝试均为0；聚合manifest脱敏，scheduler原身份healthy，
  七个自然账本未挂载未写；专项23、架构13、全仓1,043 PASS。权威仅
  `GO_M7_RECOVERY_TARGET_PROJECTION_ONLY`，原M7/R2 NO-GO不变。
  下一步如继续须基于527/541去重键另立精确网络release并再次批准；见
  `docs/M7_MONEYFLOW_RECOVERY_TARGET_PROJECTION_EXECUTION_ACCEPTANCE_20260809.md`。

## 2026-08-09 · M7-0R3-P1精确release就绪，停在scope批准前

- 已推送实现`23f06b2`，最终代码束`17997e65...26d0`和arm64镜像`ea77e171...d007`完成断网合成
  复验；release精确绑定v2协议、R2输入束/core、代码根、命令、挂载和资源。
- scope`9aca04576362455af66c5426bd0b4b6211d7edecc8b141de5ecee96ae5781614`当前明确
  `execution_authorized=false`；approval、真实目标、projector/auditor claim均不存在。
- 真实证券键/资金流数值/provider/外网/候选/效果/尝试仍为0，scheduler原容器和镜像healthy且未重启。
  只有用户绑定完整scope和动作另行批准后，才允许projector/auditor各唯一运行一次；见
  `docs/M7_MONEYFLOW_RECOVERY_TARGET_PROJECTION_RELEASE_ACCEPTANCE_20260809.md`。

## 2026-08-09 · M7-0R3-P1目标投影工程GO，待生成精确release

- v1在零真实读取的工程测试中发现R2 core身份转录错误；原文永久保留且从未执行。v2只把core纠正为
  report/audit/execution manifest一致的`df5de3990428...eeca`，已先于实现独立推送。
- key-only projector、独立DuckDB auditor、双日期PIT口径、write-once Parquet/manifest/audit、双角色
  pre-read claim和精确release/approval合同已完成；6个新增模块最大259行，不引入新依赖或服务。
- 真实规模合成轨A 908/轨B 541逐集合一致，重复调用在loader前停止；专用断网只读非root容器PASS。
  专项终版19、架构13、全仓1,039 PASS，Ruff/compileall/pip/Compose/脱敏门均PASS；scheduler未重启。
- 权威仅`GO_M7_RECOVERY_TARGET_PROJECTION_ENGINEERING_ONLY`；真实证券键/数值/provider/网络/尝试仍为0。
  下一步必须先推送实现、重建镜像并生成精确scope，再等用户绑定SHA批准；不得直接运行真实投影。见
  `docs/M7_MONEYFLOW_RECOVERY_TARGET_PROJECTION_ENGINEERING_ACCEPTANCE_20260809.md`。

## 2026-08-09 · M7-0R3真实恢复release前置工程GO，停在离线目标投影前

- 结果前构建合同提交`e43bee4`已先推送；新增目标投影、依赖注入provider、隔离批次、读取校验、断网
  evaluator、独立auditor、四角色release、封存与fixture九个窄模块，最大201行，不改冻结主审实现。
- 合成真实规模投影908/541，批次绑定release/request/schema/行数/内容哈希；重复request在provider前
  停止、批次重复写和篡改失败关闭，evaluator内部双跑与DuckDB独立审计完全一致。
- 不可执行synthetic scope`cac367d0...421d`，断网只读Docker报告`87abea55...0d12`、审计
  `faea8b8f...2878`；全仓1,026、架构13 PASS，scheduler原容器/镜像healthy且未重启。
- 权威只裁`GO_M7_RECOVERY_RELEASE_ENGINEERING_ONLY`；真实键/数值/provider/凭据/外网/生产均为0，
  原M7/R2 NO-GO不变。下一步须新批准一次断网key-only目标投影，之后才可生成并另批精确网络scope。
  见`docs/M7_MONEYFLOW_RECOVERY_RELEASE_ENGINEERING_ACCEPTANCE_20260809.md`。

## 2026-08-09 · M7-0R3双轨恢复synthetic工程门GO，停在真实release前

- synthetic工程合同提交`48a9a0a`先于实现推送；新增8个窄职责模块，最大文件低于400行，未修改
  通用S1/Baostock/P1资金流合同或R2主审实现，未新增常驻服务、外部依赖、账本或公共schema。
- 908/541真实规模合成输入完成主Pandas与独立DuckDB逐项复算；13场景覆盖完整GO、状态冲突/缺失、
  双形态缺失/冲突、重复/`.BJ`、6000行饱和、批次损坏、重复claim、3次传输上限和语义不重试。
  clean core`8250b211...cf25f`，场景bundle`8915a9e0...64ca50`。
- 一次性Docker fixture断网、非root、只读根、无项目/.env/data/ledger/logs/socket挂载并PASS；真实provider
  调用0、真实证券键/资金流数值读取0、调整覆盖率/候选/效果/尝试0，策略NOT_EVALUATED、生产none。
- 权威工程裁决`GO_M7_EVIDENCE_RECOVERY_ENGINEERING_ONLY`，原M7/R2 NO-GO不变。下一步若继续须另立
  真实recovery release目标；真实输入适配实现推送并生成精确scope、用户新批准前不得联网或读真实键/
  数值。见`docs/M7_MONEYFLOW_EVIDENCE_RECOVERY_ENGINEERING_ACCEPTANCE_20260809.md`。

## 2026-08-09 · M7-0R3双轨证据恢复协议冻结，停在工程施工前

- 结果已知：R2 的908条“主源全天停牌但无独立确认”和541条“daily存在但主moneyflow缺键”逐字写入
  协议；原M7/R2两项NO-GO、三池、PIT、隔离、分母及99.5%/99%/95%门槛均不改写。
- 轨A只用既有Baostock状态源对精确908键补独立证据，不改通用S1计划器；轨B只用同语义Tushare
  `moneyflow`，逐去重键要求“按日全市场/按票单日”两形态规范20字段一致。THS/DC、零填充、日线反推、
  相邻日推断和单边择值全部禁止。
- 未来最坏调用上限冻结为Baostock 908、Tushare 1,082、合计1,990，串行且先claim；本节点实际调用0，
  未读真实证券键、token或资金流数值，未计算调整覆盖率，候选/效果/尝试0，生产none。
- 暂不引入上交所公告网页运行时解析器：先验证现有独立源的最小补救；若仍有剩余，须另立source ADR和
  协议。当前只完成protocol-only，下一目标须另批synthetic-only工程门；真实采集还须实现推送、精确
  release scope和用户新批准。见`docs/M7_MONEYFLOW_EVIDENCE_RECOVERY_PROTOCOL_20260809.md`。

## 2026-08-09 · M7-0R2真实缺口谱系权威NO-GO，scope关闭

- 用户精确批准scope`9b5e40ec...c0cae`后，live proposal完整性复算PASS；断网runner和独立DuckDB
  auditor各唯一执行一次，恰留两个pre-read claim，同身份重试为false。run ID`1e78e7c...54ea4`。
- 原M7 757,636成员行中的2,615条缺口完整落入10类：1,157条隔离日、541条daily存在但moneyflow
  缺键、9条独立确认未交易、908条只有主源全天停牌而缺独立确认；分区差0、冲突0，但未决908。
- 六门5 PASS/1 FAIL，`unresolved_row_count_zero`独立失败；Pandas内部回放和DuckDB独立复算core均为
  `df5de399...eeca`，audit PASS。权威裁决`NO_GO_M7_GAP_LINEAGE_INCOMPLETE`。
- 资金流/daily数值列读取0，未计算调整覆盖率，候选/效果/尝试0，策略NOT_EVALUATED、生产none；原M7
  `NO_GO_M7_0_DATA_COMPATIBILITY`不变。scope关闭，不进入候选。未来若继续须以新协议补独立交易状态
  证据并处理541条已确认交易缺键，不得重跑或复用本approval。见
  `docs/M7_MONEYFLOW_GAP_LINEAGE_EXECUTION_ACCEPTANCE_20260809.md`。

## 2026-08-08 · M7-0R1恢复前工程门GO，停在缺口谱系协议前

- 结果已知的R1协议明确冻结`result_blind=false`，提交`cdcb0c0`先于实现推送；v1权威NO-GO、四个
  半年失败、旧scope和99.5%/99%/95%门槛全部原样保留，同scope未重跑。
- successor主路径允许全A资金流源`.SH/.SZ`，独立DuckDB复算一致；M3成员仍只收`.SH`，`.BJ`和非法
  格式失败关闭。v1三组fixture规范SHA逐字不变，历史默认入口未改判。
- 新pre-read consumption原语以五字段身份原子独占消费runner/auditor角色；合成测试证明第二次调用及
  首次loader失败后的再次调用都在语义loader前停止。真实successor入口尚未施工，不夸大为release GO。
- 专项20、全仓974、架构13 PASS，Ruff/compileall/pip check/diff-check通过；真实键/数值/缺口读取0，
  候选/效果/尝试0，生产none，scheduler未重启。下一步须另立M7缺口谱系协议、release和新精确批准，
  不得复用v1 approval。见`docs/M7_MONEYFLOW_RECOVERY_ENGINEERING_ACCEPTANCE_20260808.md`。

## 2026-08-08 · M7-0真实键级数据门权威NO-GO，scope关闭

- 用户精确批准scope`f4710068...b24e1`后，live proposal完整性复算PASS；21:58后唯一断网runner与
  独立DuckDB auditor均完成，scope不得重跑。run ID`54529f2c...032d`，audit`d0abc5d1...dac7`。
- 14个硬门12 PASS/2 FAIL：三池总体覆盖99.6105%/99.7107%/99.7325%，但全池2021H2、2022H1、
  2023H1及中盘池2022H1共4个半年单元低于99%，最低98.5452%，独立足以裁NO-GO。
- 同时发现非改判实现缺陷：主/审实现都用SH-only正则检查全A股source，致3,620,544行被标malformed；
  该计数不是可信数据域诊断，但半年门独立失败，修正也不会改变本次NO-GO。同scope不修不重跑。
- write-once还不能在语义读取前机器阻止同scope再调用；本次runner/auditor各唯一调用一次，但successor
  必须先补pre-read consumption gate，并用合成二次调用验证，不得在本scope上重跑测试。
- 权威`NO_GO_M7_0_DATA_COMPATIBILITY`只阻断当前P1键直接进入M7候选，不是策略REJECT；候选/效果/尝试
  增量0，`strategy_effective=NOT_EVALUATED`、生产none。M7-0关闭，不进入八候选。若未来继续须另立
  早期半年缺口谱系恢复协议和新scope。见
  `docs/M7_STAR_CUSTOM_POOL_MONEYFLOW_DATA_GATE_EXECUTION_ACCEPTANCE_20260808.md`。

## 2026-08-08 · M7-0真实键级数据门release就绪，停在精确批准前

- 最终scope`f47100687e...b24e1`绑定已推送Git`2aabf207...ea0d`、代码bundle`fc0a341d...dcf0a`、
  metadata manifest`8a133388...0e27a`、arm64镜像`893e90f4...c616`、命令/挂载/资源和独立auditor；
  release scope物理SHA为`31446aff...b6466`。
- 最终镜像断网非root合成fixture再次PASS；approval、内容寻址输入束、正式runner/auditor输出均不存在，
  真实证券键/资金流数值读取0，候选/效果/研究尝试0，生产none。
- 批准入口已绑定SHA`8f1842ab...eb52`，未来会先复算live proposal SQLite完整证据图，校验仍为
  `REVIEW_REQUIRED`/seq2/head`da38d05a...b1f0a`且未过期；不能用手填字段冒充批准。
- 只有用户逐字绑定完整scope并批准动作`M7_STAR_CUSTOM_POOL_MONEYFLOW_DATA_GATE_ONCE`，才可物化
  输入束并唯一运行一次断网真实键级门；同scope不得重跑。见
  `docs/M7_STAR_CUSTOM_POOL_MONEYFLOW_DATA_GATE_RELEASE_ACCEPTANCE_20260808.md`。

## 2026-08-08 · M7-0键级数据门工程前置GO，待推送后生成精确release

- metadata-only inventory 已锁定P1完整目录2,563批/10,614,438行和M3成员779,271行；M7选择范围为
  1,328个源日→1,328个feature日，范围内3个隔离源日。manifest canonical SHA为`8a133388...0e27a`，
  全程只读账本索引、JSON、文件哈希和Parquet footer，真实证券键/资金流数值行读取仍为0。
- 新增独立M7包、键级reader、Pandas主计算、DuckDB独立audit、write-once sealing、精确release/
  approval合同及approval后输入束物化；host-side批准入口还会复算live proposal证据图并验证状态/序号/
  head，避免手填批准绕过。15模块共2,359行、最大300行，不新增服务/队列/schema/账本。
- clean/重复键/稀疏覆盖三类合成门分别正确GO/NO-GO/NO-GO；runner replay与独立audit一致。全仓959
  PASS、架构13 PASS，断网非root provisional镜像fixture PASS；scheduler仍为原容器/原镜像healthy。
- 本节点裁决仅`GO_ENGINEERING_PREREQUISITES_ONLY`，不是数据GO或策略有效。下一步须先提交推送本
  实现，再从该Git重建镜像并生成精确release scope；用户绑定完整scope批准前不得读取真实证券键。
  见`docs/M7_STAR_CUSTOM_POOL_MONEYFLOW_DATA_GATE_ENGINEERING_ACCEPTANCE_20260808.md`。

## 2026-08-08 · M7-0三自建科创池资金流键级兼容协议已结果前冻结

- 只冻结`moneyflow`源键与M3三池成员PIT的兼容性数据门：主池为科创板全市场自建PIT池，迁移池为
  中盘/小盘自建PIT池；三者均不得包装为官方科创指数。本批候选、评价单元、效果和研究尝试增量均为0。
- 锁定2021-01-04—2026-06-30 feature域、前一SSE交易日可用时钟、P1整日隔离不填充及三池总体/
  半年/逐日覆盖门；未来只允许`GO_M7_0_DATA_COMPATIBILITY_ONLY`或`NO_GO_M7_0_DATA_COMPATIBILITY`，
  禁止partial-pool GO和结果后放宽阈值。
- 机器合同`config/m7_star_custom_pool_moneyflow_data_v1.yaml` SHA为`b629ba91...e164e`；proposal
  export物理SHA为`99368c40...cf582`，规范proposal SHA按控制面算法复核为`67e16748...faeb8`。
- 本节点只投影并核验既有元数据，没有读取资金流证券键或数值、标签、收益、候选、模型、回测、外网或
  生产。下一合法动作是在本协议推送后施工metadata-only inventory、窄runner/auditor、合成fixture、
  一次性Docker镜像和精确release scope；真实证券键仍须用户绑定该scope另行批准。
- 协议冻结提交`0ec4725d...a0398`已先推送；protocol scope canonical SHA为`3b137d0b...d59b`，
  envelope物理SHA为`15723129...3f78`。scope只开放下一阶段零真实数据施工，真实数据门执行仍为false。

## 2026-08-08 · M5-1B三自建科创池资金流提案已提交人工复核

- 通过既有本机M5控制面建立提案`4d3007db221e9d63e9d0be742f3e64493085dac48c7a9c5ca37de7bd6d589a65`：
  主池为科创板全市场PIT研究池，迁移比较池为中盘/小盘PIT研究池；家族为资金流，固定最多8个
  确定性候选和24个跨池评价单元，provider调用与费用均为0，七日有效。
- 提案于`2026-08-08T12:05:02+08:00`创建、`12:05:57+08:00`提交，当前`REVIEW_REQUIRED`、事件
  序号2；proposal request SHA为`05caa719...ba88c`，M5目录完整性复核返回2份提案且本提案只剩取消动作。
- 资金流主域只登记计划尝试背景由`N=18`至`N=26`；`actual_research_attempt_increment=0`。本节点未读
  真实资金流或证券清单，未运行数据门、候选、标签、效果、模型、回测、DeepSeek、前瞻或生产。
- 提案将于`2026-08-15T12:05:02+08:00`到期。下一合法动作是结果前冻结独立数据兼容性协议，先复用
  M3成员PIT和P1`moneyflow-quality-v2`，只裁`GO_DATA_ONLY/NO_GO_DATA`；真实读取及执行仍须另行授权。
  生产scheduler保持原容器`183b8c6c5edd`、原镜像`722f63de...13b76`且healthy，未重启。

## 2026-08-08 · A1-1C M3身份合同解环完成，A1首次检查点关闭

- `M3DiscoveryIdentity`具体dataclass继续留在原data模块，公开模块身份、8字段顺序和位置参数构造不变；
  M3合同新增只读结构端口，release只依赖该端口，不再反向导入data实现。
- 全仓Python循环由1降至0；contract/data/release分别为376/295/257行，全部低于400行软上限，并由
  A1-1C版本化架构增补和机器测试锁定。
- M3协议、release配置、输入snapshot、CLI、候选、费用、24次历史响应、研究结果和账本均未修改；
  未读取`.env`、未调用DeepSeek、未运行数据/研究/生产、未重启scheduler，七个自然账本保持未暂存。
- A1-1B/C完成，A1首次整理检查点到此关闭；A1-1A唯一`src -> tools`债务因冻结历史复算继续隔离，
  等版本化successor再处理。见`docs/A1_M3_DISCOVERY_IDENTITY_CONTRACT_ACCEPTANCE_20260808.md`。

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
# 2026-08-09 · M7-0R3-P2精确网络恢复release协议冻结，停在离线请求计划前

- 冻结 `m7-moneyflow-evidence-recovery-network-release-v1`，只授权离线读取P1封存的527/541去重
  源键、生成不可变请求计划、实现四角色隔离执行壳、构建镜像与生成精确release scope。
- 当前外网、provider、`.env`/token读取、资金流数值、调整覆盖率、候选、效果、模型、回测、前瞻、
  模拟仓和生产均未授权；最终scope必须另获逐字批准。
- 旧恢复协议原样保留；其predecessor core的`d915...`转录错误由本协议显式纠正为已由P1执行确认的
  `df5de3990428...eeca`，不改旧文件或原M7/R2 NO-GO。
- 协议SHA为`3b487b9a58ae7a376cc640899277885897372cac643118290ab59057cf0cf9d3`；见
  `docs/M7_MONEYFLOW_EVIDENCE_RECOVERY_NETWORK_RELEASE_PROTOCOL_20260809.md`。

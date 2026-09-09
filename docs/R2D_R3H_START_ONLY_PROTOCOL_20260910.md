# R2D-R3H：20260909元数据核验后的start-only冻结

状态：ENGINEERING_FROZEN / LIMITED_VALIDATION_ACCEPTED / LOCAL_COMMIT_AUTHORIZED / SCOPE_NOT_AUTHORIZED / PRODUCTION_NOT_AUTHORIZED。
本节点只允许配置、合成测试、文档施工及本地提交；不推送、不生成scope、不改变生产。

## 本次受限交付裁决

用户在获知R2D专项96项、架构13项及静态检查通过，全仓38项真实业务读取被保护器拒绝并
中止、尚未暂存/提交/推送后，对“接受上述受限验证，仅本地提交这五份工程文件，继续禁止
真实业务及密钥读取”的请求回复“继续”。据此接受本次相称范围交付并授权本地提交。
这是一项仅限本次五文件工程交付的明确裁决，不将失败/未执行项改写为PASS，不修改常设测试门，
不授权真实业务/密钥读取、网络、scope生成或任何生产动作。下方批准前阻断及失败记录保留。
本提交只包含本协议、R3H配置及测试、STATE、ROADMAP；之后唯一下一节点为确切提交的推送及
origin/main定向同步授权，尚不执行预检或启动。

## 证据与结论边界

2026-09-09 20:11:50 UTC+8，用户批准的单次自然闭环只读核验完成：
20260909 daily=1、shadow=1、paper=2，全部PASS，operator均为docker-scheduler。
双账户最新PASS执行日均为20260909、信号日20260908、freshness=PASS；实际产物SHA、
FORWARD mode和九项身份均匹配。shadow与双账户代码仍为旧生产
4e5244b6b02739dd209a9b01ea715c43ed9a874a7014156e20cf364f06a82708。
该核验不提取效果、不重放paper、不核验通知，不能写成新候选首日验收或策略有效。

release current仍为候选97d8c05e...7553 / b64ae11...5ebe，previous仍为旧生产。
state SHA：c879228f6514b3a07c0d1a6efec0c68832d0feab7444821e9376de1bfd86c454。
audit SHA：4524d2d0af6d57dbf1fad6c57dcb623f62eb39f63930d278c26999f895e1eea1。
audit 34条、哈希链PASS，末事件PROMOTE_PASS，记录时间2026-09-03T12:53:26.697482+00:00；
末记录SHA：aca0245b0e59e19612a2fd332dcb10188f0cfbfcd4eb5211f1167587819f477d。
本次投影未核验schema_version与git_head字段，不将未投影字段的空值解释成源文件缺失。

health为noop / 20260909，updated_at=2026-09-09T12:07:27.553739+00:00。
标准目录.release/r2d-execution-scopes与.release/r2d-executions均不存在；
仅据此报告未发现R3G标准scope/执行记录，不推断所有可能旁路均未活动。
R3G的20260909 19:00截止已过，不补做、不覆盖、不顺延、不复用scope。
本次没有Docker检查，不能用本次账本或历史Docker观察代替实时容器合同验证。

双账户产物身份（只记录已核验元数据，不附业务产物）：

- model_baseline：run_id=cade641d5ded43af3437；
  artifact_path=data/paper/model_baseline/runs/20260909-84a516a096fb.json；
  SHA=00e2c98b29dd19268f46d76093c7dc4f08487b20ebc8649b5fbe5650cf420b35。
- model_top20：run_id=8df57077c9785e712467；
  artifact_path=data/paper/model_top20/runs/20260909-84a516a096fb.json；
  SHA=48283e6cb188aeadc1f539885effee707ae9036b401a8e0e97bd2f516dfcdbf1。

## 冻结配置与复用边界

配置：config/r2d_scheduler_release_guard_r3h_start_v1.yaml。
SHA-256：8e348eb851654aec9653164827f71ec80a2fe3f3d4421e95e344f72d27e330f6。

完全继承R3G的候选、expected_running_release、四挂载、R3A封存fixture、13组件控制器、
prepare禁用与全部门槛。controller_source_head仍为69f0d913ebd60126ebe8d2f190053329858a45d6；
组件SHA仍为f88f44a791e630c4d57dcd79f9c7a3684b263bf64a935e9f5829ed53a3d3f998。
不改生产源码、不重建候选、不重跑fixture、不重复已完成的Phase A。

唯一配置差异为guard_id、目标日、旧生产noop日期、最新FORWARD日期与上述两份产物哈希：

- target_trade_date=20260910；Asia/Shanghai 16:40（含）—19:00（不含）；
- 必须是20260910当天16:00后自然形成的noop / 20260909；
- 20260910 daily/shadow/paper全部尝试（包括失败或部分尝试）计数必须均为0；
- 两账户最新PASS/FORWARD必须仍绑定20260909及旧生产代码，实际字节哈希与身份一致；
- 未来心跳或超过3600秒的心跳失败；身份漂移、任一门失败或跨窗口即停，不重试、不降门。

期望结果是冻结一个可测试、失败关闭的后继协议，不是证明明天的门已满足。
直接复用既有Schema、readiness规划器、时间门及单次执行合同，不新建计算或生产依赖，
不引入ADR级别的接口/部署改变。纯合成测试验证允许差异、边界时刻、旧日/上午心跳、
任一目标日尝试、Phase A及旧execute入口拒绝、文件哈希和文档绑定。
历史R3G配置与协议字节保留；新协议不用时保持未授权，不以rollback修改生产或删除历史。

## 独立日历、Docker和执行合同

独立日历：
data/control/r2d-calendar-evidence/c9916944c6865cf4e1e6b15af7ac90a54d2275320d25353873071f08d892b114/day.txt。
20:11核验SHA=c9916944c6865cf4e1e6b15af7ac90a54d2275320d25353873071f08d892b114，
日期有序唯一、20260909在册、之后首个交易日20260910。工程阶段不再次读取原始日历。
未来获准使用时重新校验该SHA；这是scope生成前显式操作人检查，不是新增执行Schema字段，
也不替代release_metadata.load_plan的权威trade_cal/readiness元数据规划。

20260908历史Docker观察的Compose project为shaiwei_init，预期旧容器ID为
7a55151d4d5d686b01fbf26c76432754302358b2faa653eac21ca07ee78780c4。
未来预检须在同一精确容器重新核验project、镜像/发布标签、healthy、restart=0、只读根、
三个项目bind及shaiwei_runtime_locks_v1四挂载；禁止猜测、扫描其他项目或修配置绕门。
正确标签为io.shaiwei.code_snapshot_sha256、org.opencontainers.image.revision、
io.shaiwei.lock_authority，外加获准的Compose project标签。

ExecutionScope继续绑定协议路径/字节SHA/全文、最终HEAD与本地origin/main、state/audit、
旧容器、Compose project、FORBID_AFTER_DISPATCH与3600秒新鲜度。claim原子单次消费、
派发前MAY_HAVE_WRITTEN屏障及不可覆盖receipt保持不变，派发后禁止自动回滚。
无--execute入口也需要真实scope；本工程不调用该入口、不伪造批准文件或执行回执。

## 交付、停止点与后续精确授权

开工本地HEAD与origin/main均为93c4002de8739896436e8da15a74bebf213b94e1。
这只是本地引用，不冒充本次远端实时查询；上轮推送成功记录不授权本轮网络。
本地交付仅本配置、测试、本文、STATE、ROADMAP五份工程文件；七份自然账本增量、
既有未跟踪底稿和测试临时产物不暂存、不回写。测试临时输出使用项目内新建唯一目录。

批准前曾因全仓门受禁读边界阻断而停在本地提交之前，当时待裁决为：
是否接受下述96项R2D专项、13项架构及静态检查作为本次仅五份
配置/测试/文档的相称范围交付，允许本地提交；这不放宽生产数据或密钥读取权限，不修改常设门。
该裁决现已取得，依据见上文。本地提交后，再按确切提交另行取得向
git@github.com:qiang0723/shaiwei.git 的origin/main推送及定向同步该引用的授权。
完成工程先行推送后，才另批20260910窗口内一次scope生成与无--execute预检。
读取清单须明确包括协议字节、控制器Git/13组件/R3A证据、release/audit、health三字段、
目标日三类计数、最新双账户身份及产物字节白名单、独立日历、权威readiness元数据及定向Docker。
仅准不可覆盖写一份scope；不得写approval/claim/barrier/receipt。任一失败或跨窗口即停。
若没有在窗口内完成，不能复用本协议或临时延长日期，须重新报告自然现场并另立协议。

预检PASS后报告真实scope SHA及精确start边界，等待独立逐字批准。
实际start涉及Compose按部署配置读取env_file、容器内健康检查及生产常驻进程；
未来生产批准必须明确覆盖这些调用，不可拿禁止Compose/docker exec/凭据读取的只读授权启动。

候选首自然日全门验收前R2D保持开放，G1不施工。随后固定为G1正控、Style Attribution v1、
W7、100/300/500/1000万元；R2-1R1自然累积不阻塞G1。既定G1/Style内容要求与g1-v1阈值不变。

## 验证记录

受保护R2D专项两组85+11=96 PASS（其中R3H新增16项），架构13 PASS；Ruff、五文件差异格式、
配置SHA与文档绑定、旧R3G配置/文档/测试逐字节保持、五文件无密钥凭据形状扫描PASS。
凭据形状扫描不等于真实密钥值比较；不宣称密钥比较已通过。

本次发现既有测试保护器只拒绝生产写入、真实.env读取及socket连接，不拒绝真实业务文件读取。
因此在本次唯一.test-tmp/r3h-validation.tFyHaT/guard中追加调用级保护器，保留原防护，
并拒绝真实data/ledger/logs/.release文件读取、Git show业务blob、Docker及Git网络命令。
这是额外测试防线，不是不可绕过的系统沙箱；未改既有生产源码或常设测试保护器。

make test显式排除83项：真实.env密钥比对1项，以及
test_ledger_append_only.py中的test_head_index_worktree_prefix_chain与
test_parent_to_head_committed_prefix各41项。其余运行仍出现38项保护拒绝；
已人工中止该轮，不移除保护器、不把失败转为skip或伪称PASS。中止汇总为
38 failed、495 passed、83 deselected、1 warning，67.73秒，KeyboardInterrupt / 非零退出。
这不是完整全仓结果，也不能与专项通过数相加。

失败涉及deepseek传输账本表头、fundamental_dynamics_recovery封存manifest、G8账本、
账本历史例外、D1/M1/M3封存输入和审查记录；错误为真实业务文件或Git业务blob读取被拒绝。
这些测试名称含live/preflight不表示执行了真实调用；其真实输入读取已在保护器处被阻断。
不把本次保护拒绝裁定为R3H逻辑回归，也不以旧回归PASS替代本次未完成的全仓门。

合成产物和临时保护器保留在本次唯一.test-tmp目录，未纳入五文件交付。
批准前验证记录结束时未暂存、未提交、未推送；没有真实scope、Docker、外网、生产动作或新增效果读取。

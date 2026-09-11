# R2D-R3I：20260910元数据核验后的start-only冻结

状态：ENGINEERING_FROZEN / LIMITED_VALIDATION_PASSED /
SCOPE_NOT_AUTHORIZED / PRODUCTION_NOT_AUTHORIZED。

## 本次授权与开工边界

用户在获知20260910只读核验结果后，对“仅施工配置、合成测试和文档，沿用已披露的受限验证
方式并本地提交；不推送、不生成scope、不改变生产”回复“继续”。本次仅交付新配置、测试、
本文、STATE、ROADMAP五文件。受限验证为R2D合成专项、架构、Ruff、格式、哈希和无密钥静态扫描；
不重跑依赖真实业务输入的全仓测试或真实.env密钥比较，不将未执行项冒称PASS，不修改常设门。
R3H的38项禁读保护拒绝及全仓中止记录保留，不回写、不将旧结果冒充本轮验证。

本次权威输入是2026-09-11 00:13:59 UTC+8单次授权核验的元数据与已推送R3H工程字节。
仅机械推进自然日期与两份FORWARD哈希；复用既有Schema、时间门、readiness与单次执行合同，
不改生产源码或新增依赖/接口/部署边界，无需新ADR。缺证据或任一身份漂移失败关闭。
旧协议、候选、fixture、账本与未跟踪底稿不覆盖；回退本工程不涉及生产rollback。

## 已核验事实及限制

20260910 daily=1、shadow=1、paper=2，均PASS、operator=docker-scheduler。
shadow和双账户代码仍为旧生产
4e5244b6b02739dd209a9b01ea715c43ed9a874a7014156e20cf364f06a82708。
两账户最新PASS执行日20260910、信号日20260909、freshness=PASS；
产物实际SHA、FORWARD mode与九项身份匹配。这不是paper独立重放、通知验收、候选首日或策略有效性结论。

- model_baseline：run_id=7077c7cb8336e1f68851；
  artifact_path=data/paper/model_baseline/runs/20260910-5851f158e604.json；
  SHA=5be99ab10a196ef0a1a555ce3b76dc3b74a7fcba932180291fd77a6d631fa503。
- model_top20：run_id=573c672627d66f3b3a45；
  artifact_path=data/paper/model_top20/runs/20260910-5851f158e604.json；
  SHA=81995ebe9e371495cc3cad8267c2b168e9af8c0de5ffd2a447a94ce3a9b3db7b。

release current仍为候选97d8c05e...7553 / b64ae11...5ebe，previous仍为旧生产；
current git_head=df44cabe44635b3c6be8e40188140fb54f5ff9a0，
previous git_head=210af4dab33c85b38c05b28f56c176b7970c41db。
state schema_version=shaiwei-scheduler-release-state-v1，
SHA=c879228f6514b3a07c0d1a6efec0c68832d0feab7444821e9376de1bfd86c454。
audit SHA=4524d2d0af6d57dbf1fad6c57dcb623f62eb39f63930d278c26999f895e1eea1；
34条、链PASS，末事件PROMOTE_PASS，时间2026-09-03T12:53:26.697482+00:00，
末记录SHA=aca0245b0e59e19612a2fd332dcb10188f0cfbfcd4eb5211f1167587819f477d。
current锁authority为docker-named-volume-v1；previous该字段未存储，不将缺失字段伪称已验证标签。

health=status noop、detail 20260910、updated_at=2026-09-10T16:04:49.712401+00:00。
这是9月11日00:04的心跳，不满足当日16:00后的启动门。
.release/r2d-execution-scopes及.release/r2d-executions均不存在；
只说明未发现R3H标准执行记录，不证明所有旁路均未活动。本次未调用Docker、未核验真实运行容器。
R3H的9月10日19:00窗口及其授权已失效，不补做、不顺延、不复用；Phase A不重复。

独立日历：
data/control/r2d-calendar-evidence/c9916944c6865cf4e1e6b15af7ac90a54d2275320d25353873071f08d892b114/day.txt。
本次哈希匹配c9916944c6865cf4e1e6b15af7ac90a54d2275320d25353873071f08d892b114，
日期有序唯一，20260910在册、之后首交易日20260911。工程阶段不再读取日历或其他生产数据。
以后每次获准使用均复验SHA；独立副本不替代权威trade_cal/readiness规划。

## R3I冻结合同

配置：config/r2d_scheduler_release_guard_r3i_start_v1.yaml。
SHA-256：9b91890a56f559570333d41c85e68b2653a714c7221ace0880e221ac1f7f5060。

相对R3H仅改变guard_id、target_trade_date、legacy noop日期、两账户FORWARD日期及SHA：

- target_trade_date=20260911，Asia/Shanghai 16:40（含）—19:00（不含）；
- 20260911当天16:00后自然形成的noop / 20260910，心跳非未来且年龄不超过3600秒；
- 20260911 daily/shadow/paper全部尝试（含失败和部分尝试）计数均为0；
- 两账户最新PASS/FORWARD仍为20260910，旧生产代码及实际字节哈希/身份与本协议绑定一致。

候选、expected_running_release、四挂载、R3A封存证据、prepare禁用及其余门完全继承R3H。
controller_source_head=69f0d913ebd60126ebe8d2f190053329858a45d6；
13组件SHA=f88f44a791e630c4d57dcd79f9c7a3684b263bf64a935e9f5829ed53a3d3f998。
候选不重建、fixture不重跑。纯合成测试检查允许差异、六个窗口边界、旧日/上午/错误日期心跳、
任一目标尝试、Phase A及旧execute入口拒绝、配置与文档哈希绑定。
本协议不是当天门已满足的证明，也不是scope或启动授权。

## 未来scope与生产授权边界

历史20260908观察的Compose project为shaiwei_init，预期旧容器
7a55151d4d5d686b01fbf26c76432754302358b2faa653eac21ca07ee78780c4。
未来须在获准预检中重新定向核验精确容器、镜像、healthy、restart=0、只读根和四挂载；
不得用历史观察代替现场、猜测project或扫描其他项目。
三个发布标签为io.shaiwei.code_snapshot_sha256、org.opencontainers.image.revision、
io.shaiwei.lock_authority，另核验Compose project。四挂载为项目data/ledger/logs bind及
shaiwei_runtime_locks_v1命名锁卷，目标和源的冻结门均保持。

scope继续绑定最终协议路径/SHA/全文、HEAD/本地origin/main、state/audit、旧容器、Compose project、
FORBID_AFTER_DISPATCH与3600秒新鲜度；独立日历校验仍是生成前显式操作人门，不新增Schema字段。
原子单次claim、派发前MAY_HAVE_WRITTEN屏障、不可覆盖receipt与派发后禁止自动回滚保持。
无--execute预检也需要scope；本工程不调用该入口、不创建approval/claim/barrier/receipt。
失败或跨窗口即停止，不重试、不降门、不自动延长协议。旧scope及历史失败证据永久保留。

当前HEAD与本地origin/main均为1886754d057a335f7ade57c96569a5dd3a338bc4；
这只是本地引用复核，R3H此前已获准推送，本次没有联网。本节点停在本地提交完成。
下一节点先另批确切新提交到git@github.com:qiang0723/shaiwei.git的main及定向同步origin/main。
先行推送后，再另批20260911窗口内一次scope生成和无--execute预检，精确读取清单须包含：
协议/Git/13组件/R3A、release/audit、health三字段、目标日三类计数、最新双账户身份与产物字节
白名单、独立日历、daily配置/采集元数据/trade_cal等权威readiness输入及定向Docker元数据。
仅准不可覆盖写一份scope；不得写批准文件、claim、barrier或receipt。

预检PASS后报告真实scope SHA，再取得独立逐字start授权。实际start涉及Compose按部署配置
读取env_file、容器内健康检查及生产常驻进程，必须明确批准实际调用边界；
禁止拿无密钥、无Compose、无docker exec的只读授权执行start。
本次不读.env/环境变量、不联网、不调用DeepSeek、不输出效果、不做任何生产变更。

候选首自然日全门验收前R2D不关闭、G1不施工。后续主线固定为G1正控、Style Attribution v1、
W7、100/300/500/1000万元，R2-1R1自然累积不阻塞G1。既定G1/Style内容要求与g1-v1阈值不变。

## 验证记录

受保护R2D专项112 PASS（含新增R3I 16项），1.20秒；make architecture-check 13 PASS，
2.78秒；Ruff、五文件格式和凭据形状扫描、配置/文档哈希绑定、旧R3H配置/测试/协议字节保持PASS。
13组件身份由专项重新计算并匹配冻结SHA，生产源码无变更。
沿用本次已明确授权的受限方式，没有运行make test全仓业务读取或真实.env密钥比对；
不宣称全仓通过，也不把凭据形状扫描等同真实密钥值比较。
测试使用既有.test-tmp/r3h-validation.tFyHaT/guard额外禁读保护器，本次新输出隔离在
.test-tmp/r3i-validation.vbBPaM，所有历史临时文件和自然账本增量保留，不纳入提交。
本次只交付五文件及本地提交；没有网络、Docker、真实scope、生产动作或新增效果读取。

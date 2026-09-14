# R2D-R3J：20260914元数据补验后的start-only冻结

状态：ENGINEERING_FROZEN / LIMITED_VALIDATION_PASSED /
SCOPE_NOT_AUTHORIZED / PRODUCTION_NOT_AUTHORIZED。

## 授权、复用与交付边界

用户获知9月11日/14日账本及最新双账户核验结果后，对“仅施工五份配置/测试/文档，
沿用受限验证并本地提交，不推送、不生成scope、不改变生产”回复“继续”。
本次只交付新配置、新合成测试、本文、STATE、ROADMAP；不再读取生产数据。
受限验证为R2D合成专项、架构、Ruff、格式、哈希和无密钥静态扫描，不运行真实业务/密钥全仓检查。
用户已明确接受本次范围，不把未执行项改为PASS，不修改常设门或旧失败记录。

权威输入为下述已完成授权核验与已推送R3I工程字节；只机械更新自然日期及两份FORWARD哈希。
既有Schema、时间门、readiness和单次执行合同直接复用，不改生产源码、依赖、接口或部署。
无新增ADR级变化。缺证据、漂移或任一门失败即停止；历史协议与所有失败证据保留。
撤销本工程不涉及生产rollback。候选不重建、R3A fixture不重跑、已完成Phase A不重复。

## 2026-09-14核验事实与限制

初次整合命令因完整解析CSV可能接触效果列而被安全审查拒绝，未启动、未读取。
没有绕过拒绝：先在20:19:13 UTC+8完成不涉及账本的获准检查；随后用户补充明确允许
程序读取三份CSV完整字节供解析（会接触效果列原始字节），仅使用/输出获准元数据，
并读取定位的两份最新PASS产物仅验哈希、FORWARD和身份。20:20:45补验完成。
以上是两个时间点的观察，不冒充原子快照；未重复已完成子项，没有效果分析/输出或原文落盘。
该一次性补充读取许可不自动延伸到未来预检或工程测试。

release current仍为候选97d8c05e...7553 / b64ae11...5ebe，previous仍为旧生产。
state SHA=c879228f6514b3a07c0d1a6efec0c68832d0feab7444821e9376de1bfd86c454；
audit SHA=4524d2d0af6d57dbf1fad6c57dcb623f62eb39f63930d278c26999f895e1eea1。
审计链34条PASS，末事件PROMOTE_PASS，记录时间2026-09-03T12:53:26.697482+00:00，
末记录SHA=aca0245b0e59e19612a2fd332dcb10188f0cfbfcd4eb5211f1167587819f477d。
health为noop / 20260914，updated_at=2026-09-14T12:16:55.202240+00:00；
它不能替代9月15日16:00后的新鲜边界。.release/r2d-execution-scopes及
.release/r2d-executions均不存在，仅说明未发现标准执行记录，不证明所有旁路无活动。
R3I窗口与授权已过期，不补做、不顺延、不复用。本次未调用Docker，实时容器合同仍待单独核验。

20260911与20260914均为daily=1、shadow=1、paper=2，账本状态PASS、operator=docker-scheduler。
shadow及双账户仍属旧代码4e5244b6b02739dd209a9b01ea715c43ed9a874a7014156e20cf364f06a82708。
20260911仅核验账本元数据，没有读取该日两份产物；其完成时间在北京时间9月12日05:05/05:23，
本次不诊断延迟原因，也不据PASS声称时效或通知验收通过。
实际读取的两份产物均为最新20260914 PASS，信号日20260911，freshness=PASS；
实际SHA、FORWARD mode、九项身份与账本匹配：

- model_baseline：run_id=e9a7b7355779083bf95c；
  artifact_path=data/paper/model_baseline/runs/20260914-95a2b8884a4d.json；
  SHA=9566327f116b84f15fee27353e9424fe48656333fef0ad397aea10796a654e7e。
- model_top20：run_id=b0ea7462da7c385fab74；
  artifact_path=data/paper/model_top20/runs/20260914-95a2b8884a4d.json；
  SHA=ee0a56d6c425920703f423d82630bf9975dd6e27a5c14936d11e41374b255fb1。

这些结果不等于paper独立重放、通知验收、候选首个自然交易日验收或策略有效性结论。
独立日历：
data/control/r2d-calendar-evidence/c9916944c6865cf4e1e6b15af7ac90a54d2275320d25353873071f08d892b114/day.txt
哈希匹配同名SHA、日期有序唯一、两目标日在册，20260914后首个交易日为20260915。
未来使用须复验SHA，副本不能替代权威trade_cal/readiness规划；工程阶段不再次读取。

## R3J冻结合同

配置：config/r2d_scheduler_release_guard_r3j_start_v1.yaml。
SHA-256：5372a6ff4549cade08d2371dd0560d1b63e40e91e8c9ebf108a93f524e6389c1。

相对R3I仅改变guard_id、target_trade_date、legacy noop日期、双账户FORWARD日期及SHA：

- target_trade_date=20260915，Asia/Shanghai 16:40（含）—19:00（不含）；
- 必须是20260915当天16:00后自然形成的noop / 20260914；
- 心跳非未来且年龄不超过3600秒；目标日daily/shadow/paper全部尝试（含失败/部分尝试）均为0；
- 两账户最新PASS/FORWARD仍须为20260914，实际字节哈希、旧代码及全部身份与本协议一致。

候选、expected_running_release、四挂载、R3A封存证据、prepare禁用和其他门完全继承R3I。
controller_source_head=69f0d913ebd60126ebe8d2f190053329858a45d6；
13组件SHA=f88f44a791e630c4d57dcd79f9c7a3684b263bf64a935e9f5829ed53a3d3f998。
合成测试覆盖允许差异、窗口端点/前后日期、上午/前日/错误detail、任一目标尝试、
Phase A及旧execute入口拒绝、配置和文档哈希绑定。本工程不是未来门已满足的证明。

## 唯一后继节点及未授权事项

开工本地HEAD与origin/main均f8003c976d32ec02d2094dddaf9f557ff62ed4ec；这是本地引用，
不是本次实时远端查询。R3I此前已推送；本轮不联网。本节点停在相称验证及本地提交完成。
之后先另批确切新提交向git@github.com:qiang0723/shaiwei.git的main推送及定向同步origin/main。
先行推送后才另批20260915窗口内一次scope生成及无--execute预检，任一失败或跨窗口即停、不重试。

未来读取授权须精确覆盖协议/Git/13组件/R3A、release/audit、health三字段、目标日三类计数、
双账户最新PASS及实际产物字节、独立日历、daily配置/采集元数据/trade_cal等readiness输入。
三份CSV以及readiness所需采集CSV的完整字节读取若不可避免，必须事先明确批准；
只准使用元数据白名单，禁止效果分析/输出、原文落盘，不复用本次已消费的补验许可。

Docker须另批定向核验，历史Compose project为shaiwei_init，预期旧容器为
7a55151d4d5d686b01fbf26c76432754302358b2faa653eac21ca07ee78780c4，
这些是20260908观察，不代替新检查。须核验精确容器/镜像、healthy、restart=0、只读根、
三项目bind加shaiwei_runtime_locks_v1四挂载、project及三个正确发布标签：
io.shaiwei.code_snapshot_sha256、org.opencontainers.image.revision、io.shaiwei.lock_authority。
不得扫描其他项目、猜测project或改配置绕门。

scope须绑定协议路径/SHA/全文、最终HEAD/本地origin/main、state/audit、旧容器、Compose project、
FORBID_AFTER_DISPATCH与3600秒新鲜度。独立日历仍是生成前显式操作人检查，不新增Schema字段。
仅准不可覆盖写一份scope；无--execute也需真实scope，本工程不调用它。
approval/原子单次claim/MAY_HAVE_WRITTEN屏障/receipt属于后续独立授权；禁止派发后自动回滚。
预检PASS后报告scope SHA并等待独立逐字start批准。实际start涉及Compose部署env_file、
容器内健康检查及生产常驻进程，须另批实际调用边界，不能沿用只读授权。

本次不读.env/环境变量，不调用Docker/DeepSeek，不生成scope，不推送或改变生产。
自然账本、三份既有校准底稿和全部测试临时文件保持，不暂存无关文件。
R2D首自然日全门验收前不关闭、不施工G1；后续G1正控→Style Attribution v1→W7→
100/300/500/1000万元顺序不变。R2-1R1自然累积不阻塞G1，既定G1/Style要求及g1-v1门槛不变。

## 验证记录

受保护R2D专项128 PASS（含R3J新增16项），0.97秒；make architecture-check 13 PASS，
2.22秒；Ruff、五文件格式/凭据形状、配置与文档哈希绑定、旧R3I配置/测试/协议字节保持PASS。
13组件SHA经专项重新计算匹配冻结身份，生产源码未改。
本次按用户批准执行相称验证，不运行make test全仓真实业务读取或真实.env密钥值比较，
不宣称全仓通过，凭据形状扫描不替代真实密钥值比较；R3H历史失败记录保持。
沿用既有.test-tmp/r3h-validation.tFyHaT/guard禁读保护器，本次输出隔离在
.test-tmp/r3j-validation.JuRI1a。测试临时文件及原有账本/底稿保留，不纳入提交。
本次只交付五份工程文件及本地提交，没有新生产数据读取、网络、Docker、scope或生产动作。

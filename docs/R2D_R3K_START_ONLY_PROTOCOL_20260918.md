# R2D-R3K：20260917元数据核验后的start-only冻结

状态：ENGINEERING_FROZEN / LIMITED_VALIDATION_PASSED /
SCOPE_NOT_AUTHORIZED / PRODUCTION_NOT_AUTHORIZED。

## 授权、结果目标与复用边界

用户于2026-09-18对“R3K五文件冻结、隔离测试及本地提交；不推送、不读生产证据、
不生成scope、不改变生产”明确回复“批准”。仅交付新配置、新合成测试、本文、STATE、ROADMAP。
验证为已披露的受限范围：R2D合成专项、架构、Ruff、差异格式、哈希及凭据形状静态扫描；
不运行全仓真实业务/密钥检查，不将未执行项标为PASS，不放宽常设门或删除旧失败记录。

结果目标仅为冻结20260918候选start-only输入，供后续独立授权预检使用，不宣称生产GO。
权威输入为本会话9月17日20:45已获准完成的一次元数据核验及已交付R3J工程字节。
仅机械改变日期及双账户产物哈希，复用Schema、时间门、readiness、单次执行与失败关闭合同。
不改生产源码、依赖、公共接口、部署或权威计算，无新增ADR级变化，不复制生产实现。
候选不重建、R3A fixture不重跑、已完成Phase A不重复。历史协议与失败证据保留。
撤销本工程不涉及生产rollback；缺证据、漂移、任一门失败或过期均停止，不重试、不顺延。

## 2026-09-17 20:45核验事实与限制

当次授权从用户确认起30分钟内仅一次只读核验，实际读取发生于
2026-09-17T12:45:01.742698+00:00至12:45:01.999998+00:00；许可已消费，不延伸到本次施工。
三份CSV完整字节仅供解析元数据白名单，两份最新PASS产物仅验证哈希、FORWARD和九项身份。
没有效果提取/输出、生产写入或外网；以下为短时间顺序观察，不冒充原子快照。

release current仍为候选97d8c05e...7553 / b64ae11...5ebe，previous仍为旧生产4e5244b6...2708。
state SHA=c879228f6514b3a07c0d1a6efec0c68832d0feab7444821e9376de1bfd86c454；
audit SHA=4524d2d0af6d57dbf1fad6c57dcb623f62eb39f63930d278c26999f895e1eea1。
审计链34条PASS，末事件PROMOTE_PASS，时间2026-09-03T12:53:26.697482+00:00，
末记录SHA=aca0245b0e59e19612a2fd332dcb10188f0cfbfcd4eb5211f1167587819f477d。
health为noop / 20260917，updated_at=2026-09-17T12:43:58.624336+00:00，
不能替代9月18日16:00后新鲜边界。标准scope与execution目录不存在，仅说明未发现标准记录。

20260917 daily=1、shadow=1、paper=2，全部PASS、operator=docker-scheduler。
daily run=933a0f06c07e；shadow run=47b8eba02d62；shadow和paper仍属旧生产代码。
双账户最新PASS均execution=20260917、signal=20260916、freshness=PASS；实际SHA、
FORWARD mode及九项身份与账本匹配：

- model_baseline：run_id=09c10da39bc8143a3c3f；
  artifact_path=data/paper/model_baseline/runs/20260917-9b41a779060e.json；
  SHA=a49f9f94983a338fbb2df03e789eed0121f7cd3472d96826c46a0e55c549a707。
- model_top20：run_id=5b55a77044bd31c10007；
  artifact_path=data/paper/model_top20/runs/20260917-9b41a779060e.json；
  SHA=516fdde3636fd0739e48132af6a336e6bc4675c60bd60997f15243687b58efd5。

Docker定向核验：Compose project=shaiwei_init，旧容器
7a55151d4d5d686b01fbf26c76432754302358b2faa653eac21ca07ee78780c4，
image_id=sha256:722f63de15932cb2698e82db7c0140f02921f27f126e1c0235ca62e0a1213b76，
running=true、healthy、restart=0、readonly_root=true；data/ledger/logs三项目bind和
shaiwei_runtime_locks_v1至/run/shaiwei-locks共四个可写挂载。旧容器/镜像代码及revision匹配；
io.shaiwei.lock_authority实际缺失（null），不能写成观察到legacy-bind-flock-v0。
配置中的legacy值沿用既有兼容语义，不新增标签或修改旧镜像。候选镜像ID、代码、revision及
docker-named-volume-v1标签匹配，但未运行；历史观察不能代替9月18日现场门。

独立日历：
data/control/r2d-calendar-evidence/c9916944c6865cf4e1e6b15af7ac90a54d2275320d25353873071f08d892b114/day.txt
实际SHA匹配同名哈希、日期有序唯一、20260917在册，其后首个交易日20260918。
未来使用前须复验SHA；副本不替代权威trade_cal/readiness，本次工程不再读取。
没有paper独立重放或通知验收，不构成候选首自然日验收或策略有效性结论。
R3J的9月15日窗口已过期；原定9月17日的定时请求于9月18日唤醒后因日期不符停止，未顺延执行。

## R3K冻结合同

配置：config/r2d_scheduler_release_guard_r3k_start_v1.yaml。
SHA-256：fc4a28504ca8deccc1f044b8adc10dabfb0a1a83b6bf95b12c4b81bc563e0bc3。
相对R3J仅改变guard_id、target_trade_date、legacy noop日期、双账户FORWARD日期及SHA：

- target_trade_date=20260918，Asia/Shanghai 16:40（含）—19:00（不含）；
- 必须是20260918当天16:00后自然形成的noop / 20260917；
- 心跳非未来且年龄不超过3600秒；目标日daily/shadow/paper全部尝试（含失败/部分尝试）均为0；
- 两账户最新PASS/FORWARD仍须为20260917，实际字节哈希、旧代码及全部身份匹配。

候选、expected_running_release、四挂载、R3A封存证据、prepare禁用和其他门完全继承R3J。
controller_source_head=69f0d913ebd60126ebe8d2f190053329858a45d6；
13组件SHA=f88f44a791e630c4d57dcd79f9c7a3684b263bf64a935e9f5829ed53a3d3f998。
合成测试覆盖允许差异、时间端点/前后日期、上午/前日/错误detail、任一目标尝试拒绝、
Phase A及旧execute入口拒绝、配置与文档哈希绑定。不以合成PASS证明今天真实门已满足。

## 唯一后继节点及未授权事项

开工HEAD与本地origin/main均ac9cf3141ea25146185b3153392bf5f9ddcdd2fb；本轮未联网，
这是本地引用观察，不冒充实时远端查询。本工程停在验证及本地提交。先另批确切提交向
git@github.com:qiang0723/shaiwei.git的main推送及定向同步origin/main，再另批窗口内
一次scope生成与无--execute只读预检。跨过19:00即停止，不自动顺延到下一交易日。

未来读取授权须覆盖协议/Git/13组件/R3A、release/audit、health三字段、目标日三类计数、
双账户最新PASS及两份产物字节、独立日历、daily配置/采集元数据/trade_cal等readiness输入。
三份CSV及readiness所需采集CSV完整字节解析若不可避免，须先明确批准；仅使用/输出元数据，
禁止效果分析/输出、原文落盘，不能复用昨晚已消费许可。只读预检也不在本次工程授权内。
Docker另批精确容器/镜像ID、running/healthy/restart、只读根、四挂载、Compose project及
io.shaiwei.code_snapshot_sha256、org.opencontainers.image.revision、io.shaiwei.lock_authority；
不扫描其他项目，不读.env/环境变量，不用Compose解析或docker exec代替定向字段。

scope须绑定协议路径/SHA/全文、最终HEAD/本地origin/main、state/audit、旧容器、Compose project、
FORBID_AFTER_DISPATCH与3600秒新鲜度；仅准不可覆盖一份，独立日历仍是生成前操作人显式检查，
不新增Schema字段。无--execute也需真实scope，本次不调用。approval、原子claim、
MAY_HAVE_WRITTEN屏障与receipt属于后续独立授权，禁止派发后自动回滚。
预检PASS才报告scope SHA并申请独立逐字start批准。实际start的Compose env_file、
容器内健康检查与常驻进程须另批实际边界，不能沿用工程或只读授权。

## 主线与验证记录

R2D生产切换及候选首自然日全门验收关闭后，才进入G1正控、Style Attribution v1、W7、
100/300/500/1000万元资金梯度；R2-1R1的20日/2次调仓可后台累积，不阻塞G1。
G1须含两层A/B、五路实验、两种噪声、传递链、Top30重合/Jaccard、NOT_FOR_ADMISSION旁路、
公开因子先验与误放率边界，g1-v1门槛不变。Style须含市场β、规模/价值盈利/反转/流动性/
波动/行业、双臂及转换器暴露差，绑定合法clean_lgbm_control_v1。本次均不开工。

受保护R2D专项144 PASS（含R3K新增16项），0.94秒；make architecture-check 13 PASS，
1.97秒；Ruff、五文件UTF-8/换行/空白/凭据形状、配置与文档哈希绑定均PASS。
旧R3J配置/测试/协议字节保持，STATE/ROADMAP历史正文原样保留；13组件身份经专项重新计算匹配。
生产源码未改。上述为相称工程验证，不是全仓或真实生产验收。
沿用.test-tmp/r3h-validation.tFyHaT/guard调用级禁读保护器，
测试输出隔离于.test-tmp/r3k-validation.2BrV1I；既有临时文件、自然账本和三份校准底稿保留。
不运行make test全仓真实业务检查或真实.env密钥值比较，不宣称全仓通过；凭据形状扫描
不替代真实密钥值比较。R3H历史失败记录保留，只提交五份工程文件，不暂存其他文件。

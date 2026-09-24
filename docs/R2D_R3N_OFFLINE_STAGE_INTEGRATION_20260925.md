# R2D-R3N：离线入口编排与持久化阶段核心

开工：2026-09-24；验证：2026-09-25。
状态：OFFLINE_CORE_SYNTHETIC_PASS / LIVE_ENTRYPOINT_WIRING_NOT_IMPLEMENTED /
PRODUCTION_NOT_AUTHORIZED / LIMITED_DELIVERY_ACCEPTED。

## 本轮结果与授权

用户在获知 R3N 仅限项目内代码、协议和隔离测试，不读生产数据、不联网、不构建镜像、不切换
生产后询问“可以继续吗”，本轮据此推进该离线工程。未生成或消费真实 scope/审批/claim，
未读取 .env、秘密、环境变量或真实 data/ledger/logs/.release 内容，没有外网和 Docker 调用。

R3M 提交647082accc530d6a28d264e0bd69e474d23c749f已于9月24日按单独批准推送/定向同步。
开工本地HEAD与origin/main均为该值；本轮未联网查实时远端。七份自然账本增量、既有临时目录
与三份校准底稿保留。最近已批准的生产观察仍是9月17日，不能由工程测试推断9月25日状态。

本轮九份工程文件：ADR 0013、本文、三个新源码模块、两个新测试模块、STATE、ROADMAP。
R3L/R3M、旧13控制器组件、生产scheduler/release/CLI、Compose、配置和冻结判据均不改。
这次交付是R3N的离线核心，不是已完成真实全入口接线，也不是生产可运行的新镜像。

## 实际实现，不再只是内存布尔模拟

ADR 0013先于代码落盘，版本r2d-candidate-offline-v1，模式只能为OFFLINE_FIXTURE_ONLY。

- r2d_candidate_contract.py（145行）：严格Schema、阶段链重放、合法阶段迁移和稳定错误码。
- r2d_candidate_store.py（109行）：真正保存/重开测试SQLite数据库，计划绑定、追加事件、
  BEGIN IMMEDIATE与expected-head比较，显式一次创建；文件缺失/损坏/已存在不重建或覆盖。
- r2d_candidate_runner.py（150行）：注入只读元数据和合成业务端口，入口停放、延迟工厂、
  每阶段前重新验身份/时间/计数/独立回执、等待数据续接、未知写入阻断。

调用入口run_offline_tick接收ingress、CandidatePlan、OfflineStageStore、MetadataPort、
BusinessPort工厂与显式clock。没有secret/config加载、隐式时钟、网络、Docker或真实业务import。
六类入口scheduler/daily/shadow/paper/verify/acceptance均经过离线入口判定；仅scheduler能
进入完整编排，其余独立调用在元数据读取/业务工厂之前拒绝，未知入口同样拒绝。

重要区别：现有真实scheduler及裸CLI**没有接到这个适配器**，它们仍是旧实现。测试只能证明
调用本适配器的六类路由被门控，不能证明旧容器/宿主进程或现有命令无法绕过。上线前必须完成
真实接线及全writer隔离证明，不得把“离线全入口”改称“生产全入口”。

SQLite适配器只允许项目.test-tmp下已有专用目录，拒绝生产目录、顶层.test-tmp、路径穿越、
符号链接及数据库硬链接；固定文件名r3n-stages.sqlite3。测试数据库并非真实生产claim。
其事务只处理本地同一数据库，不接入旧锁、不替代Docker named-volume锁权威；不读取锁环境。

## 首日阶段与有条件续接

初次claim前调用原R3M rehearse_first_day，不把过期切换窗口用于新切换，也不修改原门。
持久化CLAIM唯一；READINESS每次入口调用最多执行一次，明确WAITING_SOURCE即返回，
不会进入DAILY/shadow/paper。上限由合成计划显式给出，不静默重试、sleep、改日或追加批准。

正式顺序为DAILY→SHADOW→baseline执行/verify/acceptance→top20执行/verify/acceptance
→FINAL_ACCEPTANCE。最终双账户验收独立存在，不能仅凭两条paper PASS宣告完成。
每一阶段都是先事务提交BEGIN，再构造/调用业务端口，合格回执返回后才事务提交END。
回执绑定计划SHA、首日、阶段、BEGIN SHA和非敏感证据SHA；任一错配均阻断并保留BEGIN。

续接不是绕过R3M对手填CLAIMED的拒绝。本新合同只接受重放有效的追加链及独立元数据：

1. CLAIM已持久化但无BEGIN，证明本适配器尚未派发；新鲜复核通过后可进入首阶段。
2. END已持久化，独立阶段回执与计数逐项匹配，才能从下一阶段继续，不重跑完成阶段。
3. WAITING_SOURCE的END已提交且业务尝试仍为0，才可在同一首日、同一claim及预算内再探测。
4. BEGIN存在但无END，一律MAY_HAVE_WRITTEN，即使中断发生在工厂调用之前也不自动重跑。
5. END应答丢失后不能直接补写或重跑；重新打开数据库，独立对账后按已完成前缀续接。

每次阶段前，元数据观察时间必须不早于最近持久化事件、非未来且3600秒内；计划/候选身份、
停放fixture、首日日历、交接窗口、独占所有权和全入口证明须匹配。正式尝试计数必须与完成前缀
严格一致，无额外或遗漏；独立证明不能用journal自身END替代。事件必须发生在冻结首日合法
派发时刻之后，禁止跨首日自动补跑。完成结果只为OFFLINE_FIRST_DAY_COMPLETE，权限恒false。

## 验证证据与边界

新增96项：入口/编排69项，存储及故障/并发27项；与原310项R2D/旧readiness合成回归合计
406 PASS（2.47秒），make architecture-check 13 PASS，Ruff PASS。
首轮存储测试出现14条Ruff F811夹具导入告警，已改为显式fixture重导出并重检通过；行为测试
没有因此放宽断言或跳过。复核还将所有端口异常（包括自定义StageError）统一转换为稳定错误码，
新增四项原文不泄漏对抗。未执行的全仓/真实业务检查不标PASS。

覆盖每一阶段的端口中断、END提交前/后故障、CLAIM/BEGIN提交前后中断、等待源限次续接、
每阶段身份重验、独立证据/计数漂移、未来/倒退时序、损坏/截断链、路径逃逸和计划错配。
测试业务回执独立保存在合成世界中，不以journal行反向伪造已完成业务。
两个真实测试子进程竞争同一CLAIM或BEGIN，仅一个提交；另有两个测试子进程在BEGIN提交
前/后直接退出而不清理连接，重开数据库后分别验证可继续/未知态阻断。未操作任何生产进程。

SQLite进程退出测试不是断电测试，也不是Docker共享卷隔离、真实业务exactly-once或恶意管理员
防篡改证明。追加链不是数字签名；无外部可信锚时，不能检测管理员协同重写数据库和独立证据。
路径检查不是针对恶意并发替换目录的完整OS安全边界；该适配器只供受控本地fixture，不得直接部署。

测试使用已审阅的R3H保护器，并由适配器额外限制SQLite路径。pytest输出位于
.test-tmp/r3n-validation.6GdVLo；各次专用数据库位于新建.test-tmp/r3n-fixture.*目录，全部保留。
禁止自动插件、pytest缓存及字节码；不清理原有文件，不暂存任何测试数据库。

工程SHA256：

| 文件 | SHA256 |
| --- | --- |
| r2d_candidate_contract.py | 81f905aa87e3ffedad9b23e72c32b3832a63f20d24553813969ba4b6fc0a0f00 |
| r2d_candidate_store.py | ea13790899a2a836ab9d9d2b3d9d3e5b735e5358d869442af502a63de484515d |
| r2d_candidate_runner.py | 66d49863914219401dab38d96edb82f2955f472ec8f90870707af5699a514053 |
| test_r2d_candidate_runner.py | 9d37aa9200c6c083afcc4eabe22f3bda24e7a09a2b2906e790ac6e2fbc257f78 |
| test_r2d_candidate_store.py | 7e1aaa08822c75a37946d267c6efa25c2e181902b57ebada8585849077329902 |

R3L与R3M源码/测试SHA均与已推送记录一致；九文件新增内容静态脱敏、空白、diff、工程哈希及
模块/函数预算检查PASS，HEAD未变、暂存区为空。静态脱敏只查凭据形状，不读取真实密钥。
未运行make test全仓业务/真实密钥比较；旧R3M受限交付确认不能自动扩大为本轮九文件豁免。
本轮暂不暂存或提交，待用户接受本次受限验证并批准本地交付；确切提交推送仍须另批。

## 唯一下一节点与仍未完成事项

首次交付时下一节点为R3N九文件受限验证交付确认（已由下节关闭）。交付/推送后，下一工程仍属R3N：真实候选入口接线、
只读白名单元数据与现有日期权威适配、生产持久化后端选择及离线装配测试。先证明这些连接，再
另批真实Docker fixture、新候选构建和生产核验/切换；不是下一步就能start。
本轮未完成旧writer排空、OS全入口隔离、发布state/audit CAS迁移或新候选首自然日验收。

R2D仍开放；随后G1正控→Style Attribution v1→W7→100/300/500/1000万元顺序不变。
R2-1R1自然累积不阻塞R2D关闭后的G1。两层A/B、五路实验、两种噪声、传递链、Top30重合/
Jaccard、NOT_FOR_ADMISSION、公开因子先验/误放率边界及g1-v1不变；Style的市场β、
规模/价值盈利/反转/流动性/波动/行业、双臂及转换器暴露差与合法clean_lgbm_control_v1不变。

## 2026-09-25 受限交付确认

用户在获知406项合成回归、13项架构及静态检查通过，真实scheduler/CLI尚未接线且未跑
全仓真实业务/密钥检查后，对“接受本次受限验证，仅批准九文件本地提交；推送与生产另批”
回复“继续”。本节关闭前述交付待裁决点，不修改常设门，不将未执行项或旧失败改为PASS。
前述未暂存/未提交文字保留为首次交付历史，不新增任何生产读取、效果、秘密、网络或Docker权限。

提交前五份源码/测试SHA与上表一致；受保护回归406 PASS（2.46秒）、架构13 PASS（2.13秒）、
Ruff PASS，输出在.test-tmp/r3n-delivery.O7AtiA，专用合成数据库保留于.test-tmp/r3n-fixture.*。
仅交付本文、ADR 0013、三个源码、两个测试、STATE和ROADMAP；不暂存数据库、账本或已有底稿。
本地交付后另批确切提交推送及origin/main定向同步，不自行联网。真实入口、生产后端及部署
证明仍未完成，R2D候选首自然日仍未验收；后继按前述主线与权限继续。

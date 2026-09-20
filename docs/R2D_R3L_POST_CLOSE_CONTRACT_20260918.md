# R2D-R3L：自然闭环后宽窗口纯合同工程

日期：2026-09-18；交付确认：2026-09-20。状态：CONTRACT_SYNTHETIC_PASS / LIMITED_DELIVERY_ACCEPTED /
LIVE_ADAPTER_NOT_IMPLEMENTED / PRODUCTION_NOT_AUTHORIZED。

## 本轮授权与六文件边界

用户表示时间不灵活，并同意“先冻结并测试自然任务完成后、宽窗口内切换的新合同，生产另批”。
本轮只做ADR、纯内存合同、合成测试、本文及STATE/ROADMAP六文件；没有任何新生产证据读取、
Docker、外网、scope、批准文件、claim、receipt、候选构建、fixture运行或生产动作。
R3K此前已单独获准推送，开工HEAD/本地origin/main均ca550e9c0e43afd99140c31aac9828588ac7f069。
本轮不重复推送、不宣称查询了实时远端。旧R3K时间窗已过期，不以新设计续期旧批准。
新模块仅为合同工程，不是已接入的start入口。生产改造与新候选身份迁移仍未授权。

## 为什么不能只延长19:00

工程只读确认三个不同限制：

1. r2d_authorized_start强制同日窗口、prior-day noop和目标日零尝试；
2. release.release_start_readiness要求跨代码存在更新的合法交易日；
3. pipeline.scheduler即使daily NOOP也进入shadow、paper、独立verify和acceptance。

所以“收盘后行情不变”并不证明旧进程无写入，也不证明新候选启动后不会触碰旧日链路。
不能绕过readiness或在旧scope上仅修改截止时刻。本轮保留旧门的拒绝行为并用合成回归验证。
旧生产锁后端、health/noop、两个静态计数快照不能替代覆盖所有写入入口的排空与fence证明。

## 新合同：把三类日期/时刻分开

决策见docs/ADR_0011_R2D_POST_CLOSE_WINDOW_20260918.md。
新增src/shaiwei/r2d_post_close_contract.py（235行），不导入runtime/config/release/Docker，
没有文件或环境读取、隐式当前时钟、CLI或生产适配器。调用者必须显式传入经验证的元数据及now。

- closed_trade_date：已经完成并封存的旧版本交易日。
- not_before / expires_at：带时区的绝对授权时段，左闭右开，一次最长24小时，可跨午夜。
- first_candidate_trade_date：冻结日历中closed之后首个合法交易日，不能以自然日+1代替。
- next_dispatch_not_before：来自冻结调度语义的该首日最早派发时刻；窗口不得跨过此边界。
- 模式POST_CLOSE_PARKED：候选在首个合法新交易日可运行前保持业务停放，不重跑关闭日。

24小时是本新合同方案的显式上限，不是现在授予的24小时生产权限。示例里的9月21日、
16:00等仅为合成测试数据，不是新生产日期/窗口或当前调度配置的声明。
不会自动顺延、跨日期改scope、循环重试或将过期批准续用。
纯合同以CONTRACT_VALID_NOT_FOR_EXECUTION输出，production_authorized恒false。

## 输入合同与失败关闭

ReleaseBinding精确绑定候选镜像ID/代码、旧代码/容器、state/audit/calendar/controller SHA、
HEAD与origin_main，拒绝同代码或未同步Git。证据必须与冻结绑定完全相同。
双账户恰为model_baseline/model_top20，最新PASS/FORWARD、Docker operator、freshness、
实际哈希/身份已验证标记、执行日、旧代码及两份冻结artifact SHA必须匹配。

daily/shadow各自必须PASS且日期等于关闭日，shadow代码必须等于旧版本。
闭环计数保守限定daily/shadow/paper全部尝试1/1/2，首日全部尝试0，积压日期为空。
存在多次/失败/部分尝试不能只筛PASS后假装满足；未来如需别的计数合同必须显式修订。
同时要求独立重放和通知验收证据，计数和latest PASS不替代完整闭环。
观察和心跳均不能来自未来且年龄<=3600秒；账户完成<=周期完成<=心跳<=观察<=检查时间。

旧写入入口必须ALL_WRITERS_FENCED_AND_DRAINED、fence持续持有、在途writer=0，绑定排空报告SHA。
候选必须有PARKED_UNTIL_FIRST_ELIGIBLE_DATE能力，能力fixture SHA与协议精确绑定。
本模块只验证输入合同一致性，不自行验证报告字节、来源、签名、真实排空或候选行为。
任意64位字符串或手填PASS并不是有效证据；未来适配器要先验来源/字节/哈希链再构造输入，
不能用model_construct或未经校验的model_copy跳过Schema。没有能力证明即不能走真实路径。

字段缺失、额外字段、字符串冒充布尔、布尔冒充计数、日期错误、窗口超长/越派发边界、
账户缺失/重复、BACKFILL、任何身份漂移或不完整闭环均失败关闭。
新合同保持FORBID_AFTER_DISPATCH与3600秒新鲜度，不授权任何自动rollback。

## 尚未具备的能力与唯一后继

当前候选未证明停放/下界能力，旧生产也未证明全入口可靠排空。
因此本轮没有实现“现在晚上随时可以启动”，不能调用release.start_current或复用旧执行scope。
后继R3M应先完成结果盲停放/排空适配设计，决定候选级改造、新镜像及发布身份迁移边界，
再施工synthetic适配；构建、新候选fixture、生产读取与生产切换必须分别取得明确授权。
若不能安全解决所有旧写入入口的竞态，返回BLOCKED，不能以宿主扫描或健康灯替代。

真实执行路径未来须保留精确scope批准、单次原子claim、最终变更前复验、MAY_HAVE_WRITTEN、
派发后失败/未知禁止自动回滚。新Schema与旧r2d-execution-scope-v1明确分离，不改旧批准文本。
宽窗口允许工程提前交付、证据和scope准备好后由用户在方便时批准；可设计一次精确批准覆盖
该窗口内已列明的复核和一次动作，但必须在未来协议中写清读取次数、动作和失败退出边界，
不能据本次笼统同意自行生成生产批准，也不承诺定时机制一定准点唤醒。

## 合成验收与交付限制

新增76项纯合同对抗；原R2D 144项及3项旧release readiness合成测试一起223 PASS（1.10秒）。
覆盖24小时/跨午夜/周末首日、精确起止边界、时区等价、未来/过期心跳、闭环因果顺序、
任一首日尝试、积压、身份漂移、缺排空/停放证明、弱化证明、自填额外授权、账户错配与BACKFILL。
make architecture-check 13 PASS（2.10秒）；Ruff PASS。
合同SHA=d1c7b18068cbda3a0654e520ab7f4e8382a480a0b311e2aeba34499da0f88680；
测试SHA=fb1aecc9ac4f483ae9f706947c18e9fe94957c0ccfb4534d7576df48db98dbfa。
测试沿用.test-tmp/r3h-validation.tFyHaT/guard禁读保护器，输出隔离于
.test-tmp/r3l-validation.8C57pr，禁止真实data/ledger/logs/.release读取、秘密读取、
生产写入、Docker和网络。既有临时文件不清理，七份账本增量和三份校准底稿保留。

本次没有运行make test全仓真实业务或真实.env密钥比较，不宣称全仓通过。
静态凭据形状扫描不替代真实密钥比较。此前R3K五文件受限提交裁决不自动扩大为新模块交付豁免；
9月18日首次交付停在工程与合成验证完成，尚未暂存/提交，需要确认接受相称验证后再本地提交；
网络推送另批，不为通过全仓检查新增生产/密钥读取权限。R3H旧失败记录保持。

## 2026-09-20 受限交付批准

用户在获知223项合成回归、13项架构及静态检查通过、全仓真实业务/密钥检查未运行后，
对“接受本次受限验证并仅批准六文件本地提交，不含推送或生产动作”明确回复“确认”。
本条关闭上述交付待裁决点，不修改常设门，不将未执行项或历史失败改为PASS。
提交前源码/测试哈希与9月18日记录一致，受保护回归223 PASS（0.99秒）、
make architecture-check 13 PASS（2.03秒）、Ruff PASS；复核输出隔离于
.test-tmp/r3l-delivery.hLqEso。仅交付六份工程文件；生产读取、网络、Docker及生产动作均为0。
本地交付后仍须另批确切提交推送；后继R3M停放/排空适配设计不包含在本次提交确认内。

R2D仍未关闭，G1未开工；后继主线仍是G1正控→Style Attribution v1→W7→
100/300/500/1000万元，R2-1R1自然累积不阻塞G1。既有G1/Style要求及g1-v1门槛完全不变。

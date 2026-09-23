# R2D-R3M：候选停放与旧任务排空适配设计、纯合成演练

日期：2026-09-23。状态：DESIGN_SYNTHETIC_PASS / LIVE_ADAPTER_NOT_IMPLEMENTED /
PRODUCTION_NOT_AUTHORIZED / LIMITED_DELIVERY_ACCEPTED。

## 结果与授权范围

用户接受“先做 R3M 设计、协议和合成验证，不读新生产数据、不构建镜像、不联网、不改生产”，
回复“继续做吧”。本轮仅六份工程文件：本文、ADR 0012、r2d_parking_rehearsal.py、对应测试、
STATE.md 和 docs/ROADMAP.md。没有 scope/批准/claim/屏障/receipt 生成或消费。

R3L 提交 3b0df7dca3df56796ce1f3f47b764adf94a1df4d 此前已按单独批准推送并同步引用。
本轮只核对本地 HEAD 与 origin/main 均为该值；未联网，不能把本地引用称作实时远端查询。
七份自然运行账本增量、既有测试目录和三份校准底稿保留且不暂存。没有读取它们的业务内容。
最近获准现场记录仍是9月17日；本轮没有核验9月23日生产身份、数据更新或自然闭环。

## 已明确的实施边界

ADR 0012 在参考实现之前建立。只查工程源码确认：

- 旧生产版本的停止信号处理意图是结束当前同步周期后退出；它不是进程树已排空的运行证明。
  health=stopped 还可能伴随非零退出码，不能单字段验收。
- Compose YAML 文本的30秒宽限可能不足；不执行 Compose 解析、stop 或 Docker 查询，也不采用
  超时强杀方案。未来重启策略变化、隔离入口和停止信号均须纳入精确生产授权。
- daily NOOP 前可刷新日历，NOOP 后 scheduler 仍进入 shadow/paper；停放必须在业务入口之前。
- market_source_ready 本身可能联网/写原始批次，不能冒充只读停放门。首日 claim 与源就绪探测
  是不同阶段；本轮 WOULD_CLAIM_FIRST_DAY 只表示模拟可进入 claim，不表示源就绪或允许直接执行。

“宽窗口”不等于取消3600秒证据新鲜度：必须在窗口内完成一次有效切换，首日可以晚于切换窗口。
旧日期 scope 不续期，操作窗口过期不得新增切换动作；周末停放也不得伪造新鲜旧心跳。

## 参考实现及调用入口

src/shaiwei/r2d_parking_rehearsal.py 共250行，纯内存、严格不可变模型、显式 now。
只依赖 Pydantic 和冻结 R3L 纯合同，没有 I/O、时钟读取、runtime/secret/Docker/网络或生产 CLI。
没有将此模块导入 scheduler、release 或任何常驻入口。两入口：

1. rehearse_handoff(plan, closed, witness, now=...)：验证排空阶段次序和身份，然后调用原
   assess_post_close；返回 WOULD_HANDOFF_PARKED，不执行任何动作。
2. rehearse_first_day(plan, observed, now=...)：模拟停放/首日 claim 路由；只返回 PARKED、
   WOULD_CLAIM_FIRST_DAY 或 FIRST_DAY_ACCEPTED_NO_REPLAY，不执行 claim、行情探测或业务函数。

所有结果 production_authorized=false。错误为 ContractViolation 稳定原因码，不回显证据内容；
Schema 缺失/额外字段/错误类型先由 Pydantic 拒绝。拒绝不能由调用者转成自动重试或默认通过。
不得用 model_construct 或未校验的 model_copy 绕过 Schema；本轮类型不是安全凭据或签名。

RehearsalPlan 精确绑定 R3L、旧运行/已准备/新停放三个不同镜像与代码身份、旧 writer 清单、
清单/排空 fixture/闭环摘要哈希。新候选不能只换镜像标签而沿用没有停放能力的准备候选代码。
DrainWitness 要求逐个唯一清单成员的退出证据，屏障≤首变更≤入口隔离≤停止请求≤退出≤最终核验；
未知 writer、遗留子进程、运行中、非零退出、重启、强杀、fixture/闭环/发布身份漂移均阻断。
旧 noop 带原始时间留档，必须在首变更之前；最终 closed 观察必须在退出核验之后，R3L 新鲜度、
1/1/2闭环计数、首日零尝试、无积压、双账户、重放与通知原门全保留。

FirstDayObservation 要求已核验交接、全入口停放、独占所有权和能力身份；交接完成时刻必须在
原切换窗口内且不晚于观察。首次派发日期沿用冻结日历，不自动+1。首日之前只模拟 PARKED；
首日仅唯一缺失日期、零尝试可提出 claim；错过自然首日、旧日/多日积压、已 claim 或未知状态
均阻断。完整首日验收后不再提出首日 claim；本模块不实现后续常驻运行授权。

上述布尔、SHA 和时间都是**合成输入合同**，不是已核验的真实来源。真正适配器必须独立核验
字节、哈希链、OS/Docker 实况及精确授权；任意手填 PASS 或 SHA 不能用于生产。
合成 claim 路由测试不是“真实 scheduler 已保证零副作用”的证据。

## 发布谱系与未解决的真实证明

未来期望 current=新停放候选、previous=经核验实际运行的旧生产；已准备但未运行的候选保留为
历史，不得普通 promote 后挤占 previous，也不能重复旧 Phase A。输出只是期望值，没有写 state。
新镜像、revision、锁权威、全入口隔离、fixture、新 scope、最终 CAS/审计一致性均尚未实施。

必须覆盖所有旧写入者和新入口；旧代码不配合新维护锁，因此只拿宿主锁或只看 health 不成立。
实际退出/子进程/重启抑制/无宿主与未知 writer 的证明，需要后继受控 fixture 和精确现场权限。
隔离或退出超时则停止并保留证据，不强杀、不自动恢复旧服务；未来维护可能造成服务暂停，须明确告知。

首日 claim 后 WAITING_SOURCE 的阶段记录与安全续接、候选崩溃、原子 claim、部分 state/audit
提交恢复、全入口旁路阻断都须在后继真实代码集成的离线故障注入中证明。本轮未实现，不冒充上线GO。
本设计没有放宽旧 release_start_readiness，也没有接入绕过旧门的 start_current 调用。

## 合成验证与交付限制

最终新增87项纯合成测试 + 原R3L/既有R2D与三项旧readiness回归223项，合计310 PASS（1.11秒）。
覆盖所有阶段的身份/时序/退出/重复清单/未来与过期证据/严格类型/零尝试/错过首日等失败路径。
最终文档落盘后13项架构测试再次 PASS（2.12秒），Ruff、diff、六文件新增内容静态脱敏/空白
与工程哈希检查 PASS；最长函数39行，暂存区为空。静态脱敏只查凭据形状，不读取真实密钥。
测试用例里的日期、哈希、容器全部合成，不是新的生产目标日或批准时段。

源码 SHA256：c7bf2f593b8c805b567187d7bb520da76c48cf91695a9fda0269956d2f8fc354。
测试 SHA256：af96ead21c21a0cf32c9920adf479eed1fb981a251a20b1baf74aa61dbe08a00。
R3L源码/测试哈希仍为 d1c7b180...f88680 / fb1aecc9...8dbfa，与冻结记录一致。
旧13组件、生产 scheduler/release、Compose、R3L及其他冻结门不改。

复用已审阅 .test-tmp/r3h-validation.tFyHaT/guard/sitecustomize.py 及 tests/r2d_safety/
保护器，禁止真实 data/ledger/logs/.release 读取、秘密读取、生产写入、Docker 和网络。
只在 .test-tmp/r3m-validation.4LgY06 内输出，禁用 pytest 自动插件/缓存与字节码。

未运行 make test 全仓真实业务/密钥校验，静态凭据形状检查不能替代真实密钥比较，不宣称全仓PASS。
R3L 的受限交付批准不自动扩大到 R3M。本轮六文件尚不暂存/提交；需用户接受本次相称验证并批准
仅本地交付，再按确切提交另批推送。不得为补齐交付门自行读取真实业务或密钥。

## 唯一下一节点与主线

首次交付时下一节点：R3M 六文件的受限验证交付确认（已由下节确认关闭）。交付/推送完成后进入 R3N 全入口停放与持久化
阶段端口的离线集成、故障注入；不能又改一个生产日期配置而假装停放/排空能力已具备。
真实 Docker fixture/镜像构建/生产证据/切换另批，未批准前不执行。

R2D 仍开放；候选首次自然交易日完整验收后才关闭。随后立即冻结施工 G1 正控，再 Style
Attribution v1、W7、100/300/500/1000万元；R2-1R1自然20日/2次调仓后台累积不阻塞G1。
G1 两层A/B、五路、两类噪声、传递链、Top30重合/Jaccard、NOT_FOR_ADMISSION、公开因子先验
和误放率边界全部保留，不修改g1-v1。Style 的市场β、规模/价值盈利/反转/流动性/波动/行业、
双臂/转换器暴露差和 clean_lgbm_control_v1 身份要求不变。

## 2026-09-23 受限交付确认

用户在获知310项合成回归、13项架构及静态检查通过，且未运行全仓真实业务/密钥检查后，
对“接受本次受限验证，仅批准本地提交六份工程文件；推送和生产另批”回复“继续吧”。
本节仅关闭前述交付待裁决点，不新增数据/效果/密钥读取、网络、scope、Docker或生产权限。
前述尚未暂存/提交的文字保留为首次交付历史，不将未执行检查或历史失败改为PASS。

提交前源码/测试哈希与上文一致；受保护R2D回归310 PASS（1.18秒）、架构13 PASS（2.41秒）、
Ruff PASS，输出仅在.test-tmp/r3m-delivery.JX7klh。六文件新增内容另做静态脱敏及diff检查。
只提交本文、ADR 0012、纯模拟、对应测试、STATE和ROADMAP；旧生产源码、七份自然账本及
既有未跟踪文件保留。未运行真实业务全仓/真实密钥比较，不宣称全仓通过。
本地交付后先另批确切提交推送及origin/main定向同步，不自行联网；R3N及真实适配按前述边界推进。

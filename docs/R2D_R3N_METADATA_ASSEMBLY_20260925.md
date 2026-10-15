# R2D-R3N：白名单元数据与日期权威离线装配

日期：2026-09-25。状态：OFFLINE_ASSEMBLY_SYNTHETIC_PASS /
LIVE_ENTRYPOINT_WIRING_NOT_IMPLEMENTED / LIMITED_DELIVERY_PENDING / PRODUCTION_NOT_AUTHORIZED。

## 本步结果与精确范围

上一轮九文件提交 d426238d7994bc1298544328264280e872624f6d 已获独立批准推送至
git@github.com:qiang0723/shaiwei.git 的 main 并定向同步；当时 HEAD/origin/main 均为该提交。
本步及恢复检查仅核对本地引用，未再联网。最近获准的真实生产观察仍为9月17日，不能由
本轮合成测试、Git状态或账本文件名推断9月25日生产运行和数据是否更新。

本步在用户“继续”后实现离线元数据装配；中途发生下述检查范围失误，已暂停、告知用户，
用户再次“继续”仅确认工程复核与记录收尾，未授权提交、推送、生产读取或生产操作。

本轮仅八份工程文件：

- STATE.md、docs/ROADMAP.md。
- docs/ADR_0014_R2D_OFFLINE_METADATA_ASSEMBLY_20260925.md、本文。
- src/shaiwei/r2d_candidate_metadata.py、src/shaiwei/r2d_candidate_app.py。
- tests/test_r2d_candidate_metadata.py、tests/test_r2d_candidate_metadata_boundaries.py。

ADR 0014 先于新增实现。R3L/R3M/R3N原核心、旧控制器、生产scheduler/CLI、daily规划函数、
release_metadata、配置和Compose不改；不修改架构或研究判据。七份自然账本增量、原有
未跟踪校准底稿和测试证据均保留，不暂存、不清理。

## 实际新增能力

元数据适配器242行，装配入口25行。没有新依赖或服务，没有生产默认路径、命令行注册、
环境开关或配置加载；run_fixture_candidate只打开已有离线阶段库，不隐式创建或修复。
独立daily/shadow/paper/verify/acceptance及未知入口在读取快照/打开阶段库前被拒绝。
业务端口仍为测试注入，只有原R3N在BEGIN持久化后调用工厂；停放不claim、不构造业务对象。

固定r3n-metadata.json以严格版本化Schema保存一份合成快照：规格哈希、真实采集时刻、
合成身份/隔离证明、五种CSV白名单、独立阶段回执和完整首日验收标记。此处“真实采集时刻”
指显式输入的观察时间不被适配器改写为调用时间，不意味着读取了真实生产证据。
规格绑定CandidatePlan及显式规划参数。读取限定项目.test-tmp专用目录，拒绝目录/文件软链、
硬链和路径穿越；上限2MiB，读取前后核对inode/设备/大小/mtime/ctime，重复JSON键拒绝。

日历CSV字节哈希须匹配计划；日期有效、排序唯一、开市位合法，从bootstrap到首日连续覆盖，
首个后继交易日须确实等于冻结首日。不是将自然日+1当交易日，也不跳过缺失的休市日记录。
五种CSV严格限制字段，不读取/输出收益、持仓、指标、行情或任何效果列。

eligible/pending/watermark直接调用既有daily.build_plan；提供只读内存文件协议及合成DataFrame，
不传磁盘默认路径，不复制规划算法。现有release_metadata.load_plan底层有全局路径解析，
因此本步不调用它；该判断仅来自源码，不是对线上数据的读取或漏洞利用。
ready时分与冻结首日dispatch一致；规划会保留旧日期缺口，不用后续PASS掩盖未完成日期。

三类目标日尝试数从全部对应行计算，失败不被过滤成零尝试。shadow/paper校验候选代码；
两个paper账户与独立PAPER阶段回执逐项对应，不能用相同总次数代替baseline/top20身份。
claim只取持久化库claimed标记，不用END重新制造外部阶段回执。丢失独立回执、身份漂移、
旧/未来观察、重复账户、错误日期或内容都失败关闭；异常原文不出边界。

## 验证与失败记录

- 第一轮新增测试64 PASS；Ruff发现1条E731（lambda赋值），改为具名局部函数后通过。
- 补齐边界测试后合并回归493 PASS（4.23秒），但出现6条旧multiprocessing测试的
  多线程进程fork弃用警告。未将警告屏蔽或删除旧测试。
- 恢复复核时加强路径测试：不仅要求稳定拒绝错误码，还计数断言零Path.open；避免异常
  被适配器脱敏后掩盖实际读取尝试。生产代码未因此改变。
- 新元数据87 PASS（1.89秒）、旧R2D/readiness406 PASS（2.49秒），分别启动独立受保护
  pytest进程，均无警告；总计仍493，不把同一测试的重复运行当新增证据量。
- make architecture-check 13 PASS（2.31秒），Ruff PASS。两新增源码各<=400行，函数预算
  与依赖方向另做工程静态复核；无热点增长、权威日期算法复制或新业务入口调用。
- 文档收尾后架构再次13 PASS（2.17秒）；八文件精确路径diff、静态凭据形状、冲突标记、
  新文件空白/换行检查PASS。两个源码最长函数分别29/13物理行，原R3N三个核心SHA不变。
  静态凭据形状检查不读取真实秘密，不替代未运行的全仓/真实密钥检查。

测试复用已审阅R3H保护器：禁止真实业务文件读取、生产写入、.env、网络、Docker等。
关闭自动pytest插件、缓存和字节码；输出/基准目录为.test-tmp/r3n-metadata-validation.qDRLzs，
分进程最终目录final-legacy与final-metadata；专用r3n-fixture目录保留，不提交测试数据库。
测试中实际调用的是原build_plan与真实测试SQLite，业务/身份/隔离证明仍为合成，不能冒充
实际交易效果、全writer隔离、发布身份认证或首日生产验收。

## 检查范围失误、暂停与恢复

前次收尾错误执行了没有路径限定的git diff --check，Git也检查了已有账本改动，输出
ledger/ingest_batches.csv的CRLF转换提示。未输出账本行或效果，未修改、暂存账本，
未联网或操作生产；但这超出已声明的仅工程文件检查边界，不能宣称本步从未触及账本读取。
发现后停止并告知用户；用户回复“继续”，确认仅工程复核与记录收尾，提交/推送仍另批。
没有以该回复追认新的生产读取权限，也不为证明未变而重读/哈希账本内容。
恢复后所有diff/静态内容检查必须传入精确工程白名单；Git status只用于保留文件清单。
此事件和前述Ruff/fork警告均保留，不改写为全程无异常。

## 工程字节身份

| 文件 | 行数 | SHA256 |
| --- | ---: | --- |
| r2d_candidate_metadata.py | 242 | c58fa44aa688e4ae1eedc27e553d354b92fe03998d0e3326ca3295a5afb513fd |
| r2d_candidate_app.py | 25 | 0d5ba4135e98f3d95431b498173266c7ae3607d52ea31736e09f9750bb8f3267 |
| test_r2d_candidate_metadata.py | 275 | 332d4465ef96cd715860739dd1da3c7d7cd5a1c255a94bee3a9c0c2f7a1d9aed |
| test_r2d_candidate_metadata_boundaries.py | 165 | 167acaabe42df1664be122991683c3b929eb394678e689262c812f2744ea88cd |

## 交付限制与唯一下一节点

本轮未运行会读取真实业务/密钥的make test全仓检查；不标全仓PASS，也不沿用上一轮
九文件受限交付豁免。当前只做八文件工程收尾，未暂存、提交或推送。
唯一下一节点：用户接受本轮493项合成回归、13项架构及静态检查的受限证据和未跑项，
批准仅八文件本地提交；随后精确提交推送另批。

这一步补上了文件元数据投影和离线装配，仍未接生产scheduler/裸CLI，不能称作真实全入口
改造完成。生产持久化后端、独立证据采集/认证、OS级旧writer排空/全入口隔离、Docker真实
fixture、新候选镜像、发布state/audit CAS与候选首自然日验收仍缺失。
后继仍属R3N真实候选入口与后端适配；若需扩大部署/存储权限，先冻结精确协议并另获批准。
当前不start、不promote、不生成/消费真实scope，不用合成证明关闭R2D或抢先启动G1。

主线R2D关闭→G1正控→Style Attribution v1→W7→100/300/500/1000万元不变。
G1保留两层A/B、五路实验、两种噪声、传递链、Top30重合/Jaccard、NOT_FOR_ADMISSION、
公开因子先验及误放率边界，g1-v1门槛不变。Style保留市场β、规模/价值盈利/反转/流动性/
波动/行业、双臂与转换器暴露差及合法clean_lgbm_control_v1身份。
R2-1R1自然累积不阻塞R2D关闭后的G1；旁线不改变上述主线。

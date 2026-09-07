# R2D发布守卫安全合同工程记录（2026-09-07）

## 用户交付批准（2026-09-07）

用户在获知2010项受保护回归通过、真实.env密钥比对未执行及尚未提交推送后明确回复“批准”，
同意本次以受保护回归＋无密钥静态扫描交付并提交推送工程补丁。本次例外不等同实际密钥值比对
通过，不修改全仓常设规则。提交仅含19份工程/测试/文档文件，不含自然账本、原有未跟踪底稿、
测试临时产物；不授权生产、真实preflight、scope、候选build或密钥读取。以下为批准前工程记录。

状态：实现与受保护回归完成，待用户裁决无密钥交付门；尚未暂存、提交或推送。
不是生产验收，不授权真实预检、scope生成、启动或回滚。
依据：docs/ASTRA_PROJECT_REVIEW_FOLLOWUP_20260907.md 与 ADR 0010。

## 本次边界

仅修改宿主发布控制器、合成测试和工程文档。未运行Docker、生产preflight、真实fixture、
候选build、真实scope生成/消费、DeepSeek或效果分析；不读真实.env。
旧Phase A完成事实及所有历史协议/哈希/回执不覆盖。未实时核验今日生产，历史健康记录不冒充当前状态。
原有七份自然运行ledger改动与三份未跟踪校准文件不暂存、不回写。
测试临时文件放在项目.test-tmp，不作为业务证据。

## 修复对应

- 回滚：旧R2D execute接口失败关闭；新的start-only入口不调用旧自动恢复逻辑。
  启动派发前持久化MAY_HAVE_WRITTEN屏障；未知/失败仅留回执，禁止自动回滚。
  这不是候选真实首次写入证明，也不替代首个自然交易日验收。
- 授权：版本化scope绑定协议字节SHA与全文、HEAD/本地origin、控制器、镜像、旧容器ID、
  Compose项目、state/audit哈希、窗口和动作；逐字批准摘要校验；完整scope随claim持久化。
  原子不可覆盖claim、统一线程/进程锁、不可覆盖终态回执；崩溃留claim即不可重试。
  批准文件是受信操作人转录，不是数字签名，不能由代理自行伪造用户批准。
- 无密钥预检：readiness只用daily配置Schema与原规划器；镜像只查询三个白名单标签；
  Docker标签查容器，不在preflight解析Compose或新建候选容器。
- 身份/时间：旧容器精确ID、重启0、只读根、三bind源及命名锁卷；FORWARD实际字节哈希、
  类别与身份白名单；日历与paper产物路径约束；未来或超过3600秒心跳拒绝。
  最终mutation前复验协议、Git、候选、state/audit、旧容器、自然边界和真实时钟。
- 锁：复用storage.interprocess_lock，新增唯一local-only发布资源，不新增直接flock旁路，
  不修改既有生产锁资源、调度器、模型或g1-v1阈值。
- 底层release原语仍是受信操作人接口，本补丁不声称约束任意宿主代码执行者。
  真正执行阶段Compose仍会按部署配置读取env_file；未来生产授权必须明确覆盖此边界，
  不因本次“无密钥preflight工程”自动获得凭据读取或启动授权。

## 验证与未完成门

- 最终受保护make test：2010 PASS、1 deselected、17项既有弃用/未来行为警告，208.14秒。
- 发布合同定向回归：133 PASS；测试输出隔离修正：27 PASS，末次声明修正后11 PASS。
- make architecture-check：13 PASS；本次变更Ruff、git diff --check和无密钥形状扫描PASS。
- 当前本地HEAD与本地origin/main均为243006091f618f6aeed4f41913d4213cba372147；
  本次未联网确认远端，未提交本工程。
- 控制器13组件SHA256：f88f44a791e630c4d57dcd79f9c7a3684b263bf64a935e9f5829ed53a3d3f998。
全仓首轮：1999通过、2失败、1项明确未执行。两失败分别为新增直接flock违反自发现门，
以及旧canary测试假定系统临时目录在项目外；已修复为复用统一锁、注入合成项目根。
canary生产代码与研究判据不变，不调用provider。
保护器首轮1991 PASS、18 setup errors、1 deselected：两份旧M6测试在固定data测试目录建/删合成
输出，被保护器阻止。现已改为项目.test-tmp内唯一TemporaryDirectory，避免删除已有固定测试目录。
首轮未保护测试执行过这两个既有合成夹具的建/清理流程，不冒称完全未触碰data树；没有真实策略
运行、效果评价或自然账本写入。生产数据与测试输出以后明确隔离。
真实.env比对测试test_secret_hygiene.py因用户禁读边界明确不执行，不宣称完整make test验收通过；
另做不读取密钥的形状/跟踪范围扫描，但它不能替代实际密钥值比对。
tests/r2d_safety/sitecustomize.py是仅显式启用的测试保护器，限制测试进程写真实ledger/data/logs/release/运行锁，拒绝真实.env读取及网络连接；
它仅是额外测试防线，不是生产沙箱，也不是不可绕过的操作系统安全边界。

受保护回归复跑命令（先确保.test-tmp存在，不用于生产）：

```sh
PYTHONPATH="$PWD/tests/r2d_safety:$PWD/src" \
PYTHON_DOTENV_DISABLED=1 FEISHU_ALERTS_ENABLED=0 \
TUSHARE_TOKEN='' FEISHU_WEBHOOK_URL='' FEISHU_SIGNING_SECRET='' \
TMPDIR="$PWD/.test-tmp" SHAIWEI_LOCK_ROOT="$PWD/.test-tmp/test-locks" \
PYTEST_ADDOPTS='--basetemp=.test-tmp/r2d-suite-clean --deselect=tests/test_secret_hygiene.py::test_local_secrets_and_generated_data_are_not_tracked --tb=short' \
make test
```

basetemp是可清理的本次合成目录；不得替换成业务目录。真实密钥比对排除显式保留。
如果需要重跑且希望保留本轮合成产物，先使用新的basetemp目录名。

## 唯一下一节点

先完成工程交付门；禁读密钥与仓库全套测试纪律的冲突须明确裁决，不静默豁免。
之后才可申请一次有精确读取边界的生产元数据核验，核实真实自然日与控制器身份，
另立当前有效日期的start-only协议/scope并取得逐字授权。
控制器清单为13个文件：原六个R2D组件，加release.py、release_metadata.py、
r2d_execution_contract.py、r2d_metadata_environment.py、r2d_authorized_start.py、
storage/interprocess_lock.py、storage/lock_resources.py。
旧组件哈希随工程变更失效，不能修改旧冻结配置来假装身份连续，也不能复用旧scope。
候选首自然日验收、R2D正式关闭后才进入G1正控；随后Style Attribution v1、W7和资金梯度，
R2-1R1自然积累不阻塞G1。

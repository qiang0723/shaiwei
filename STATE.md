# STATE — 筛微施工状态（git 为真身，会话记忆为草稿）

> 每会话开工先读本文件；收工必更新「当前进度」与「待答点」。改判旧口径须显式作废并注明日期。

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

## 当前阶段
阶段 0（基线）已完成；阶段 1 已完成有界 GP 预演和 `p1-moneyflow-v1` 首个正式数据增强家族，二者均按冻结 `g1-v1` 结论 REJECT，正式因子库仍为 0 插入。锁竞争修复后当前代码版本连续三次完整“信号 → 下一交易日开盘对账”已于 2026-07-22 完成 3/3，核心任务验收 PASS、通知通道 WARN；同日完成飞书通知健壮性修复。P0.5 模拟组合的工程、Docker 接入、四日 BACKFILL 和 2026-07-23 首个自然 `FORWARD` 已全部 PASS，当前进入持续前瞻观察。P3-3B 已完成因子与实验的不可变安全投影、五组类型化查询及 HTTP 后端；P3-3C 因子工厂与 P3-4B 模型/回测页面均已完成，Web 1.0 七类本机只读页面全部可用。P4-0 科创100源采集PASS，但官方历史成员谱系NO-GO，已停在P4-1前且未评价策略效果。

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

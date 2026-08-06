# ADR-0003：M5 全局数据失败必须先封存、再审计、后裁决

- 状态：`ACCEPTED_FOR_RECOVERY_PROTOCOL_FREEZE`
- 日期：2026-08-06
- 决策范围：M5-2B 全局源身份冲突的诊断、失败产物、独立审计与新 case 恢复
- 不授权：真实数据读取、冲突修数、标签/效果、模型、回测、DeepSeek、外部采集、工程门、Web、生产或 scheduler 修改

## 1. 问题与结果目标

M5-2B release v3 的唯一真实断网 runner 在合并普通/VIP 资产负债表时发现相同冻结来源身份对应不同
业务字段，并以 exit code 2 失败。数据源确有待解释冲突，但实现还暴露了第二个问题：协议已经把源身份
冲突定义为全局数据 NO-GO，runner 却在封存规范化失败报告之前抛错，导致 auditor 没有输入，registry
只能记录 `STOPPED`，无法得到经审计的 `BLOCKED_DATA`。

本 ADR 的结果目标不是让数据“过门”，而是让全局坏数据也形成完整、确定、脱敏、可独立复算的负面
证据。未来新 case 再遇冲突时，应封存 canonical 失败报告，由独立 auditor 重读同一冻结输入复算；
只有 audit PASS 后，registrar 才能记录正常的 `DATA_GATE_RECORDED / NO_GO`。

## 2. 已有真身与不可触碰边界

- 旧 case `223414f4…0a78` 已在 event 10 终止；event SHA 为 `e0ca4594…b9b3bd`。旧事件、数据库、
  ledger、release v3、输入束和零输出事实不得删除、补造或回写。
- 原研究协议的八个候选、三个股票池、24 单元、公式、方向、PIT、548 日陈旧度、覆盖门槛、尝试
  `N=14/20` 与效果测试 0 全部不变。
- 既有 registry v1 四表、事件哈希链、幂等 receipt 和 outbox 已通过真实留痕，不需要迁表或改 schema。
- 当前没有获准再次读取真实财务语义，也没有获准把普通接口或 VIP 接口指定为冲突时的优先真身。

## 3. 方案比较

### A. 普通接口或 VIP 固定优先，冲突行继续计算

实现简单，但源优先级在看见冲突后才提出，可能静默改变 PIT 值；没有公告版本或权威修订证据时，任意
选边都不是数据治理。拒绝。

### B. 冲突仍抛异常，新增可重试运行事件

能诚实表达工程失败，但把协议已定义的数据完整性问题降为运行异常，无法形成 DATA NO-GO；重试还会
再次读取真实数据而没有新增证据。拒绝。

### C. 两种 write-once 结果模式，共用独立审计与正常 DATA 裁决

正常输入继续生成 feature panel 和 24 单元质量报告；全局源冲突不选择任何冲突记录、不计算候选，
但生成脱敏冲突报告、全局失败数据报告和 run manifest。auditor 使用独立实现重读同一输入，复算冲突
类别、计数和承诺哈希；通过后以全 24 单元 FAIL、八候选全部 rejected、批级 NO-GO 进入
`BLOCKED_DATA`。选择本方案。

## 4. 决策

### 4.1 新 protocol scope 与新 case

恢复必须形成新的 `protocol_scope_sha256`。case ID 继续按 ADR-0002 的
`proposal_id + protocol_scope_sha256` 规则派生，因此旧 STOPPED case 不迁移、不复活。相同 proposal
只有在新 DATA approval 时仍为 `REVIEW_REQUIRED` 且未到期才可使用；否则建立新提案，禁止延长到期日。

新 case 继续使用 registry v1 四表和原合法主链，不增加 `FAILED` 捷径：

`... → DATA_GATE_RUNNING → DATA_GATE_RECORDED(NO_GO) → BLOCKED_DATA`

registry 只接收审计后的 8×3 简化矩阵和两个证据 SHA，不接收原始证券、日期或财务值。

### 4.2 来源身份与值比较

身份仍为 `(ts_code, f_ann_date, end_date, report_type, update_flag)`；表内业务字段仍由原冻结协议定义。
比较顺序固定：

1. 对普通和 VIP 各自保留来源标签，规范化身份中的字符串和日期；
2. 业务值只做确定性数值规范化：空值归一为 NULL，数值按精确有限值比较，`1` 与 `1.0` 等价；禁止
   容差、四舍五入、缩尾、填零或插值；
3. 分别识别同 API 内完全重复、同 API 内冲突，以及普通/VIP 交叉重叠完全一致或冲突；
4. 完全重复可内容无损折叠；任何冲突组不选边、不进入 PIT 计算，并触发批级全局失败。

诊断报告允许保存表名、冲突类别、字段名、聚合计数及 canonical 冲突集合 SHA；禁止保存或提交
`ts_code`、公告日、报告期、update flag、原始/规范化财务值或可逆行级载荷。完整本地承诺哈希只用于
auditor 对同一输入复算，不授权导出业务数据。

### 4.3 两种输出模式

runner 的 `outcome_kind` 只能是：

- `NORMAL_DATA_MATRIX`：原 feature panel、data report、run manifest；
- `GLOBAL_DATA_FAILURE`：`source_conflict_report.json`、`data_gate_report.json`、
  `run_manifest.json`，明确 feature panel 为 `NOT_CREATED_GLOBAL_FAILURE`。

全局失败报告固定：`source_identity_conflicts > 0`、24 个协议顺序单元全部 `FAIL`、
`eligible_candidate_ids=[]`、八候选全部 rejected、verdict 为
`NO_GO_M5_2_DATA_PREEXECUTION`。覆盖率、相关性和候选值统一标 `NOT_COMPUTED_GLOBAL_FAILURE`，不得用
0 或空数组伪装成实际计算结果。

成功 GO 返回 exit 0；已封存且可审计的 DATA NO-GO 返回 exit 3；控制身份、I/O、未知异常或无法封存
的运行故障返回 exit 2，且不得登记数据结论。退出码本身不授权 registrar，audit PASS 仍是唯一前置。

### 4.4 独立 auditor

auditor 不导入 runner 的冲突分类或候选计算实现。它独立读取冻结 allowlist，按本 ADR 重写来源分组和
精确值比较，核对：输入/release/approval/code 身份、outcome kind、文件集合、物理/规范哈希、冲突
类别与计数、冲突集合承诺、零原始字段泄漏、全 24 单元 FAIL 和 NO-GO 投影。任一差异 audit FAIL，
registrar 不写 `DATA_GATE_RECORDED`。

### 4.5 权限与运行边界

本 ADR 与恢复协议只授权后续实现和纯合成 fixture。真实冲突诊断、真实 runner/auditor、正式新 case
初始化和 gate 事件仍为 false。实现提交与镜像必须先推送，输入 manifest/bundle、四个窄挂载、资源和
命令形成新的 release scope；用户只可针对该完整 SHA 批准一次断网真实 DATA_GATE。

## 5. 迁移、回滚与兼容

- registry schema v1 零迁移；旧库继续按旧事件语义重放，新 case 使用新 protocol scope。
- 原研究配置继续是唯一公式/PIT/门槛真身；恢复配置只增加数据失败证据语义，不复制或改写研究公式。
- release v1/v2/v3、旧 build v1 和旧 case 永久保留；新实现不得让历史 verify 失败。
- 回滚只停止新 runner/auditor，保留协议、release、case、产物和负面证据；生产、Web 和 M5-1 不变。

## 6. 验收与复审触发器

施工至少用纯合成 fixture 覆盖：完全重复无损折叠、普通内冲突、VIP 内冲突、普通/VIP 交叉冲突、
NULL/数值规范化、报告泄漏、双跑字节一致、auditor 独立重算、manifest 篡改、全 24 FAIL 投影、registry
NO-GO 和旧 STOPPED case 重放。任何真实读数、冲突选边、源修订、公式/门槛变化、registry schema
迁移或效果读取都必须另立协议或 release，不得夹带。

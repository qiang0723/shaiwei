# M5-2B-R2 财报来源版本谱系恢复协议冻结验收

- 日期：2026-08-06（UTC+8）
- 状态：`GO_SOURCE_LINEAGE_PROTOCOL_ONLY`
- protocol scope：`96c4f996f2641e6b18c26d8228ee72712b2670d70fe0cdedf95c99cd2e463ccd`
- 派生新 case ID：`6b6c849f4ded89f631e1af8127f0e7321898aa7f4ce0c2630806fc8c8ef7be16`
- 结果前协议提交：`ccc799b073520f04954fcb0da9e9d7ea0052b144`（scope 生成前已推送）

## 1. 裁决

R2 版本谱系恢复协议已冻结，可进入“纯合成实现 + 独立审计 fixture + 断网 release 构建”节点。本裁决
不授权读取真实财务语义、诊断 23 个真实冲突组、获取外部证据、建立正式新 case、写 gate 事件、运行
真实 lineage feasibility，或进入 PIT、候选、标签、效果、模型、回测和生产。

R1 case 继续保持 `BLOCKED_DATA / NOT_EVALUATED / production none`。R2 使用相同 proposal 与新 scope
派生独立 case；旧 release、产物、audit、event 6 和裁决均不迁移、不改写、不重跑。

## 2. 关键方法修正

1. 明确分开 `f_ann_date`、权威修订生效时间和本地抓取时间；
2. 本地 `ingest_time` 只能证明观察下界，不能回填更早历史；
3. 相同五字段身份内的相同 `update_flag` 不能给不同值排序；
4. 历史链至少需要带版本身份与生效时点的 provider 证据，或法披/交易所/发行人一手材料；
5. 只有本地观察证据的版本只能标为 future-only，不得通过冻结历史门；
6. 禁止 latest wins、普通/VIP 优先、非空/多数值优先、容差、删样本或按效果选源；
7. 先运行断网 lineage feasibility；确需联网补证时另立采集协议，不能和数据门混跑。

## 3. 数据质量裁决边界

R2 的通过标签 `GO_M5_2_SOURCE_LINEAGE_RECOVERABLE` 只表示所有冲突组具备唯一、完整、可按形成日使用
的版本链，仍须另立 DATA_GATE。任一冲突组缺权威时点、存在分叉、链缺口或仅有本地观察，均为
`NO_GO_M5_2_SOURCE_LINEAGE_PREEXECUTION → BLOCKED_DATA`；策略继续 `NOT_EVALUATED`。

公开产物只允许表级证据等级/处置/原因计数和不可逆 commitment。证券代码、公告与报告期、report
type、update flag、财务值、候选值、请求参数和绝对路径不得提交。

## 4. 机器合同与架构

- ADR：`docs/ADR_0004_M5_STATEMENT_VERSION_LINEAGE.md`；
- 协议：`docs/M5_DYNAMIC_FUNDAMENTAL_SOURCE_LINEAGE_RECOVERY_PROTOCOL_20260806.md`；
- 机器恢复合同：`config/m5_dynamic_fundamental_source_lineage_recovery_v3.yaml`；
- protocol scope：`config/m5_dynamic_fundamental_source_lineage_recovery_protocol_scope_v3.json`，物理 SHA
  `9156b92f545d79a8de1478f1fd3d0ab6191c26caa80568fb9b51ffb708fcf8ba`；
- construction-only build：`config/m5_dynamic_fundamental_source_lineage_build_v3.yaml`。

未来职责拆为 observation 合同、值 commitment、纯 lineage builder、只读证据适配、脱敏投影、薄
runner 与不导入主构造器的独立 auditor。新生产模块常态不超过 400 行；不增长既有热点，不修改 R1
分类语义、registry schema、Web 或生产服务。

## 5. 验证与下一动作

协议机器测试、scope/case/冻结文件哈希测试、架构门、Ruff、diff-check 和凭据扫描全部通过后方可提交。
当前下一合法任务仅是按 build v3 施工纯合成版本谱系实现，完成双跑确定性、篡改、泄漏和旧 case 重放
fixture，再推送实现并生成完整 release scope。

用户必须对未来 release scope 的精确 SHA 单独批准；旧 v4 批准不迁移。批准时 proposal 必须仍为
`REVIEW_REQUIRED` 且未超过 `2026-08-12T10:48:16+00:00`；若过期则新建 proposal，禁止续签旧批准。

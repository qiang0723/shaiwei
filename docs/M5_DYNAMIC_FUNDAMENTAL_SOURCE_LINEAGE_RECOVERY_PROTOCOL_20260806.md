# M5-2B-R2 财报来源版本谱系恢复协议（结果前冻结）

- 协议 ID：`m5-dynamic-fundamental-source-lineage-recovery-v3`
- 冻结时间：2026-08-06 12:03（UTC+8）
- 机器真身：`config/m5_dynamic_fundamental_source_lineage_recovery_v3.yaml`
- 架构裁决：`docs/ADR_0004_M5_STATEMENT_VERSION_LINEAGE.md`
- 当前阶段：`SOURCE_LINEAGE_PROTOCOL_ONLY_NO_REAL_READ`

## 1. 本目标

本节点只冻结 R1 数据 NO-GO 之后的版本谱系恢复规则。它把 23 个冲突组视为待证明的源版本问题，先
判断本地不可变批次和未来权威证据能否构造合法历史链；不读取真实财务语义、不查看冲突证券/日期/值、
不选择普通/VIP、不运行 PIT、候选、覆盖、标签、效果、模型或回测。

本协议的成功只表示“具备另立数据门的条件”，不表示 M5 数据已 GO，更不表示因子或策略有效。

## 2. 冻结事实与继承

- R1 release v4 scope `8858912f…6f65` 已唯一执行；case `a2539149…2068` 的 event 6 为
  `DATA_GATE_RECORDED → BLOCKED_DATA`，永久保留。
- R1 权威发现为 23 个冲突组：balancesheet 8、cashflow 15、income 0；24/24 单元未计算并 FAIL，
  strategy `NOT_EVALUATED`、production `none`。
- 原八式、三池、24 单元、公式、方向、PIT、548 日陈旧度、覆盖门槛、未来窗、尝试 `N=14/20` 与
  effect test 0 原样继承。R2 不增加研究尝试。

## 3. 证据等级与时间语义

版本证据分四级：

1. `E0_VALUE_VARIANT_ONLY`：只知道相同五字段身份有不同值；不能排序；
2. `E1_LOCAL_OBSERVATION`：绑定不可变 batch 和 `local_observed_at`；只能证明本地首次/再次观察；
3. `E2_PROVIDER_DECLARED_VERSION`：源明确给出可区分版本的发布/修订生效时点、版本身份和不可变证据；
4. `E3_AUTHORITATIVE_PRIMARY_DOCUMENT`：交易所/法披平台/发行人法定公告等一手材料，能绑定版本内容、
   发布时间与修订关系。

历史 `PIT_VERSION_CHAIN_RESOLVED` 至少需要 E2 或 E3。`f_ann_date` 继续定义财报行的初次公告可用日，
但同一五字段身份内的不同值必须另有 `provider_revision_effective_at`；相同 `update_flag` 不构成顺序。
`local_observed_at` 只能作为未来下界，不得回推到更早形成日。

## 4. 冻结的处置规则

每个冲突身份组按 ADR-0004 的六种互斥处置归类。历史恢复 GO 必须同时满足：

- 每个不同 `value_version_sha256` 有 E2/E3 证据；
- 版本有效区间唯一、连续、无重叠分叉；
- 任何 formation date 只能命中一个当时已知版本；
- 证据与版本链由独立 auditor 复算一致；
- 不改变研究公式、样本、股票池或门槛。

latest batch、VIP/普通优先、update flag 大小、非空率、多数值、数值容差和删除冲突组全部禁止。
只有 E1 的版本可标记 `FORWARD_ONLY_OBSERVED_VERSION`，不能进入冻结历史门。

## 5. 未来实现与产物

下一施工节点只允许纯合成实现：

- 纯 `version commitment` 规范化器；
- 纯 `lineage builder` 与处置器；
- 独立 audit 实现；
- 脱敏 `source_lineage_report.json`、`lineage_gate_report.json`、`run_manifest.json` 的 write-once 封存；
- 新 case 的 registry v1 状态投影与幂等 fixture。

公开报告只含表级证据等级/处置计数、未解决原因计数、链 commitment 和 authority；不得包含证券代码、
公告/报告日期、report type、update flag、原值、规范化值、候选值、URL 查询参数、绝对路径或行级载荷。

## 6. 运行分层与裁决

未来 release 必须先做断网 `LINEAGE_FEASIBILITY`，输入为冻结本地批次与单独封存的权威证据束；不允许
同轮联网补证。裁决：

- 全部历史链完整：`GO_M5_2_SOURCE_LINEAGE_RECOVERABLE`；仅允许另立 DATA_GATE；
- 任一链不完整或只有本地观察：`NO_GO_M5_2_SOURCE_LINEAGE_PREEXECUTION`，状态 `BLOCKED_DATA`；
- 身份、I/O 或封存失败：`STOPPED`，不得登记数据结论。

本轮新 protocol scope 派生新 case；R1 case 不迁移、不复活。runner 裁决必须经独立 audit PASS 后才能
登记；退出码不单独构成权威。

## 7. 外部证据边界

本协议不授权网络或 provider。若纯本地 feasibility 证明缺 E2/E3，必须另立
`AUTHORITATIVE_EVIDENCE_ACQUISITION` 协议，预先冻结来源 allowlist、字段、调用次数、预算、凭据边界、
限速、不可变原件和失败语义。采集与 DATA_GATE 不得合并，抓到的“当前值”也不得回填历史。

## 8. 下一授权与停止线

协议 scope 冻结后，只能施工并推送版本谱系实现与纯合成 fixture，再构建内容寻址的断网 release。
只有用户明确批准该未来 release scope SHA，且 proposal 仍合法，才允许一次真实
`LINEAGE_FEASIBILITY`。旧 v4 批准不迁移。

出现以下任一情况立即停止：真实财务语义读取、真实冲突诊断、外网或凭据使用、原始批次改写、冲突
选边、候选/PIT/标签/效果/模型/回测、旧 case 改写、Web/scheduler/生产触碰，或用 E0/E1 声称历史
版本完整。

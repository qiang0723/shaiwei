# M5-2B-R1 全局数据失败恢复协议冻结验收

- 日期：2026-08-06（UTC+8）
- 状态：`GO_RECOVERY_PROTOCOL_ONLY`
- protocol scope：`6f99c0dfdc5cd75df9bf769fb65318feb4e8e7140082a9dfb924a88a3bb0dc49`
- 派生新 case ID：`a2539149d588a0c19f9cb73331f19a66df63e301df03f56fbb2c8e5c74672068`
- 结果前协议提交：`c0eb26bdc7e25e50e67e7d4acfbf0460f3c05b6e`（scope 生成前已推送）

## 1. 裁决

M5-2B-R1 恢复协议已冻结，可进入“实现 + 纯合成 fixture + release 构建”节点。本裁决不授权真实财务
读取、真实冲突诊断、正式新 case 初始化、gate 事件、runner/auditor 真实运行或任何研究效果。

旧 v3 case 保持 `STOPPED / NOT_EVALUATED / production none`。新 case 由相同 proposal 与新的
protocol scope 派生，身份不同；registry v1 四表零迁移，旧事件仍须逐字重放通过。

## 2. 冻结的关键修正

1. 来源冲突分为普通内、VIP 内、普通/VIP 交叉三类冲突，以及三类完全一致重复/重叠；
2. NULL 与精确有限数值规范化后比较，禁止容差、四舍五入、填补或来源优先级；
3. 完全重复只作无损折叠，任一冲突不选边并触发全局数据失败；
4. 全局失败也必须 write-once 生成 conflict report、data report 和 run manifest；不生成 feature panel；
5. 24 单元全部 FAIL、eligible 为空、八候选全部 rejected，批裁决为 DATA NO-GO；
6. auditor 用独立实现复算聚合计数与冲突集合承诺，audit PASS 后 registrar 才能写
   `DATA_GATE_RECORDED → BLOCKED_DATA`；
7. runner exit 3 仅表示已封存 NO-GO，不是单独权威；未封存故障仍 exit 2 且不能记录数据结论。

## 3. 继承与未变化

原研究配置 SHA 仍为 `ce5cb639…96b79`；八式、三池、24 单元、公式、方向、PIT、548 日陈旧度、覆盖
门槛、未来窗、尝试 `N=14/20` 和 effect test 0 全部未变。没有新增候选、选参、补位或按已知冲突
调整研究含义。

旧 case `223414f4…0a78`、release v3 `49fdc6e7…e05830`、event 10
`e0ca4594…b9b3bd` 和零输出事实均被新 scope 绑定但不迁移、不改写、不重跑。

## 4. 机器合同与架构

- ADR：`docs/ADR_0003_M5_GLOBAL_DATA_FAILURE_EVIDENCE.md`；
- 恢复协议：`docs/M5_DYNAMIC_FUNDAMENTAL_DATA_GATE_RECOVERY_PROTOCOL_20260806.md`；
- 机器恢复合同：`config/m5_dynamic_fundamental_data_gate_recovery_v2.yaml`；
- protocol scope：`config/m5_dynamic_fundamental_data_gate_recovery_protocol_scope_v2.json`，物理 SHA
  `a5bcb1a21e9ea2dbe7c2536014511c4ef3b89fcbc9c4ea3dcb4fae6da0890179`；
- construction-only build v2：`config/m5_dynamic_fundamental_data_gate_build_v2.yaml`。

实现职责预先拆分为纯 source classifier、纯 failure projection、薄 runner 编排、独立 audit classifier
与薄 auditor 编排；新增模块常态不超过 400 行，不向 Web/生产反向依赖，不修改 registry schema。

## 5. 权限与下一动作

当前所有真实读写、外部网络、凭据、provider、标签、效果、模型、回测、工程门、Web、scheduler 和
生产权限仍为 false/0/none。下一合法任务仅是按 build v2 施工恢复实现和完全合成对抗 fixture，提交
推送后构建不可变断网镜像与 metadata-only 输入束，生成新的完整 release scope。

用户仍须对该未来 release scope 的完整 SHA 单独批准；旧批准不迁移。批准时 proposal 必须仍为
`REVIEW_REQUIRED` 且早于 `2026-08-12T10:48:16+00:00`，否则停止并建立新提案。

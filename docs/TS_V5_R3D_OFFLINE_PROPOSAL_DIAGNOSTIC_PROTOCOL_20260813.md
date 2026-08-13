# TS-v5-R3D 六响应离线 proposal 失败诊断协议

日期：2026-08-13（UTC+8）

状态：`RESULT_BLIND_DIAGNOSTIC_FROZEN`

## 目标

只读复核R3C六份不可变JSON响应，查清通用分类
`PROPOSAL_SCHEMA_OR_COMPILER_INVALID`背后的具体规则，并判断是否存在集中、可机械修复的接口问题，
从而决定“是否值得先做工程恢复，再申请新的小批调用”。本目标不修补或录取旧响应，不评价机制收益。

## 结果前输入与顺序

在展开六份content前，本协议与
`config/ts_v5_r3d_offline_proposal_diagnostic_v1.yaml`先冻结R3B proposal合同/编译器、原候选validator、
R3C scope/release/账本/报告/audit、六份request/raw/manifest的逐项哈希。协议提交并推送后，才允许
在项目内断网只读展开content；reasoning始终禁止使用。

## 四层诊断

1. `PROPOSAL_JSON_SCHEMA`：核心JSON Schema可表达的类型、必填、额外字段、枚举、长度与数量规则。
2. `MECHANISM_PROJECTION`：请求中`x-ts-mechanism-projection`已经明示的参数域、精确范围、唯一性、
   搜索积和lineage规则。
3. `DETERMINISTIC_COMPILER`：响应满足已发送合同，却仍在确定性编译器中失败。
4. `FINAL_CANDIDATE_VALIDATOR`：确定性产物违反字节不变的最终候选合同。

报告只保存匿名序号、机制、字段路径、规则ID、错误类型和计数，不复制原回答正文、reasoning、证券、
行情或收益。允许在内存中逐层验证，但不得保存修补或标准化后的候选。

## 结果前裁决

- 任一响应满足全部已发送合同但仍在编译器/最终validator失败，裁
  `STOP_LOCAL_IMPLEMENTATION_DEFECT`，先修本地实现，不开新调用。
- 只有同时满足以下条件，才裁`GO_R3E_CONTRACT_RECOVERY_ENGINEERING_ONLY`：六份都能归因于已发送的
  可见合同；本地缺陷0；同一首要规则至少覆盖4/6；首要规则总数不超过3；恢复不放宽validator、参数
  或研究边界，并能在新调用前由合成/对抗fixture证明。
- 其他情形裁`STOP_NEW_LIVE_BATCH_NOT_JUSTIFIED`，说明当前接口失败过于分散，继续付费调用没有证据。

无论哪个结果，都不直接授权DeepSeek调用。即使工程恢复值得做，也必须另立R3E协议、先完成零API
工程验收，未来新调用再用新scope、release和用户明确批准。

## 禁区

外网、任何secret/LLM调用、行情/证券/收益、参数搜索、回测、模拟仓、Web和生产全部为0；R3C六份原始
响应、账本和裁决保持不可变，scheduler不得修改或重启。

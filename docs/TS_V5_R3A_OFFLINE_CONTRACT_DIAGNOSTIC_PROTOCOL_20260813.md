# TS-v5-R3A 四响应失败的离线合同诊断协议

日期：2026-08-13（UTC+8）

状态：`RESULT_BLIND_DIAGNOSTIC_FROZEN`

## 目标

只读复核TS-v5-R2四份不可变响应，区分失败究竟来自提示合同缺口、发送给模型的JSON Schema表达不足、
模型违反已显式可见约束，还是本地校验器自身缺陷。输出恢复建议，不修补候选，不读取效果，不调用
DeepSeek。

## 冻结输入与顺序

输入严格绑定R2 scope、release、两账本、主报告、独立audit及四份raw envelope的SHA-256，完整清单见
`config/ts_v5_r3a_offline_contract_diagnostic_v1.yaml`。本协议在逐字段展开响应正文前冻结；旧产物保持
字节不变。

## 方法

1. 用冻结的`MechanismCandidate`重新得到结构化Pydantic错误，只保存字段路径、错误类型和约束类别。
2. 对每条失败规则分别检查：模型收到的JSON Schema是否能表达、system prompt或candidate limits是否
   明文提示、规则是否只存在于本地自定义validator。
3. 允许在内存中做最小反事实修补，只用于确认后续错误层；修补后的内容不得落入候选库或进入评价。
4. 报告只含匿名序号、机制、错误类别、合同覆盖矩阵和恢复建议，不复制原响应正文或reasoning。
5. 独立入口重新计算输入哈希、诊断结果和裁决；同一scope复跑必须哈希不变。

## 通过与停止

工程PASS要求四份响应均能得到确定、可复算的根因分类，且独立audit通过。该PASS只授权后续另立
`R3B`合同恢复工程协议；不授权任何新LLM调用、参数搜索、回测、模拟仓、Web或生产。如果发现本地
validator缺陷，先停止并走纠错；不得因离线诊断直接把R2无效响应改判为候选。

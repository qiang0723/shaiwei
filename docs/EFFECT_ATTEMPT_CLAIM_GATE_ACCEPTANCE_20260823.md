# A1-5A 真实效果 attempt claim 工程验收

- 日期：2026-08-23（UTC+8）
- 协议：`a1-5a-effect-attempt-claim-gate-v1`
- 裁决：`GO_ENGINEERING_ONLY`
- 生产授权：`none`
- 真实效果读取：`0`
- 真实实验账本追加：`0`

## 1. 交付结果

A1-5A 已建立未来真实效果 runner 可复用的 claim-first 窄门：调用方必须先把确定性尝试行追加到
canonical experiment ledger 并 `fsync`，再写入内容寻址 receipt 并 `fsync`，随后才可调用注入的
effect reader。claim 后无论 receipt、reader 或后续流程是否失败，该尝试均被保守消费；相同 scope
不能借幂等路径重新开放。

本节点只证明工程门可用。八个历史 runner 均保持源码和冻结身份不变；没有读取收益、标签、证券、
持仓或封存效果，没有运行模型、预测或回测，也没有改变 Web、scheduler 或生产身份。

## 2. 实现边界

- `src/shaiwei/ledger.py` 抽出通用确定性 `append_experiment_once`；历史 reconciliation API 保留为
  兼容薄包装，现有调用语义不变。
- `src/shaiwei/research/effect_attempt_claim.py` 独立负责 spec 校验、确定性 ID、claim row、receipt、
  claim-first 编排和独立复核；模块 271 行。
- `config/effect_attempt_claim_gate_v1.yaml` 逐路径、逐 SHA 登记 8 个已关闭旧入口，明确不可回改、
  不可复用旧 scope；未来已接入入口清单仍为空。
- 自发现门要求所有带冻结 effect-start marker 的 tracked runner 与登记表精确相等，避免新入口静默
  旁路；对抗 fixture 覆盖调用顺序、claim 前失败、receipt 失败、reader 失败、重复 scope、篡改和
  敏感字段。

## 3. 失败语义

| 故障点 | reader 调用 | 尝试计数 | 同 scope 重试 |
|---|---:|---:|---:|
| claim 前校验失败 | 0 | 0 | 可修正后另行申请 |
| ledger 已写、receipt 失败 | 0 | 1 | 禁止 |
| receipt 已写、reader 失败 | 1 | 1 | 禁止 |
| 相同 experiment ID 或 receipt 已存在 | 0 | 不新增 | 禁止 |

ledger 与 receipt 不是跨文件事务；本门有意选择“可能在极窄窗口多计一次、绝不漏计已读效果”的
保守顺序。最终策略裁决仍由未来版本化 effect report 与独立 auditor 表达，不回写 claim row。

## 4. 验证证据

- claim/registry/reconciliation 专项：19 PASS；
- 架构门：13 PASS；
- 全仓：1,781 PASS，17 条既有第三方/未来行为 warning；
- 41 份账本追加门：86 PASS；
- Ruff、compileall、pip check、diff-check：PASS；
- 新生产模块 271 行，`ledger.py` 390 行，均未超过 400 行；
- 脱敏扫描只命中 gate 自身用于拦截凭据的正则字面量，未发现凭据值。

## 5. 下一合法节点

A1-5A 到此结束。下一步只能由 M6-5C 或另一项新真实效果研究另立结果前协议，把本 gate、最小账本
写挂载、terminal report 对 receipt 的引用、独立 auditor 及具体 release scope 一起冻结，再由用户
单独授权。A1-5A 本身不授权真实执行，也不与退市规则、模型或生产变更混做。

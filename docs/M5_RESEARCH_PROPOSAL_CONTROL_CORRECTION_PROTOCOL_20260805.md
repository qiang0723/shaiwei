# M5-1 研究提案控制面冻结口径补正协议

> 补正 ID：`m5-research-proposal-control-correction-v1`
>
> 冻结时间：2026-08-05T17:24:20+08:00
>
> 基础协议：`m5-research-proposal-control-v1`
>
> 权威范围：多重检验作用域、生成方式交叉约束与架构宪法身份绑定

## 1. 裁决

基础协议和 `config/m5_research_proposal_control_v1.yaml` 永久保留，不回写。只施工代码前复核发现，
v1 配置用单一 `prior_related_generation_attempt_count` 同时表达家族、联合探索域和全局敏感性，导致
静态基本面 `12` 不能由绑定的 F1 单独证明，残差家族也丢失“本家族 `N=3`、相关价量背景
`N=273`”双层口径。v1 配置因此标为 `SUPERSEDED_BEFORE_IMPLEMENTATION`，不能作为运行时真身。

本补正只建立 `config/m5_research_proposal_control_v2.yaml`，修复以下三项：

1. 将历史尝试拆成 `primary` 与可选 `sensitivity` 作用域，各自绑定计数和证据；
2. 固定确定性生成与 LLM 意向的次数/费用交叉约束；
3. 将架构宪法精确路径和 SHA-256 纳入机器配置与启动漂移门。

不增加 proposal 字段自由度、状态、命令、审批、Worker、外部调用或任何研究执行授权。基础协议中
create、submit-review、cancel 之外的禁区和所有 false/none 授权继续完整有效。

## 2. 多重检验上下文补正

每个家族必须返回并持久化如下结构：

- `primary.scope_id / prior_attempt_count / evidence_path / evidence_sha256`；
- 可选 `sensitivity.scope_id / prior_attempt_count / evidence_path / evidence_sha256`；
- `planned_increment_policy=GENERATION_ATTEMPT_CAP_COUNTS_ONCE`。

服务端分别派生 `primary_planned_after` 和可选 `sensitivity_planned_after`，均为相应历史 N 加本提案
`generation_attempt_cap`。一个公式跨多个股票池形成多个评价单元时仍只增加一次生成尝试；失败、重复、
语义拒绝或沙箱拒绝也占用计划 N。浏览器不得提供、覆盖或重置这些字段。

| 家族 | primary | sensitivity | 权威证据 |
|---|---:|---:|---|
| 资金流 | `moneyflow_family=18` | 无 | P1 验收 |
| 静态基本面 | `fundamental_static_family=6` | `fundamental_joint_domain=12` | F1 证明本家族 6；F2 证明 F1+F2 联合 12 |
| 动态基本面 | `fundamental_dynamic_family=6` | `fundamental_joint_domain=12` | F2 同时证明动态 6 与联合 12 |
| 量价机制 | `related_price_volume_domain=273` | 无 | M4 冻结协议/验收继承相关价量域 273 |
| 残差与特异风险 | `residual_risk_family=3` | `related_price_volume_domain=273` | M4 冻结协议明确本家族 3 与全局 273 |

这里的 `planned_after` 只是未来复核所需的多重检验背景，不是试验已发生、预算已授权或研究任务已
建立。M5-1 的实际研究尝试增量始终为零。

## 3. 生成方式交叉约束

`DETERMINISTIC_CODE` 必须同时满足：

- `provider_call_intent_count=0`；
- `provider_budget_usd=0.00`；
- `completed_response_target=0`；
- provider 身份为 `NONE_NOT_APPLICABLE`。

`LLM_BOUNDED_DSL` 必须同时满足：

- `provider_call_intent_count=generation_attempt_cap`；
- `completed_response_target=generation_attempt_cap`；
- `0.00 < provider_budget_usd <= 1.00`；
- provider 身份只可为 `TO_BE_REVIEWED_NOT_AUTHORIZED`；
- 每个计划生成尝试至多对应一个完成响应目标，任何失败仍计入计划 N，不补位。

任一交叉字段不一致返回 `CONTRACT_INVALID` 且零写入。以上只描述预算与调用意向；
`provider_spend_authorized=false`、`external_call_authorized=false`、`deepseek_authorized=false` 始终固定，
不能从正预算、提交人工复核或剩余有效期推导真实调用。

## 4. 架构与运行时漂移门

v2 配置必须绑定：

- `docs/ARCHITECTURE_CONSTITUTION.md`，SHA-256
  `d312dd6389dde45528e8360bbb213456bde8c2522f786892a599421821e1804e`；
- 基础协议、补正协议与 ADR 的精确文件身份；
- M5 v2 快照、authority addendum、M1 股票池注册表及每个 multiplicity 证据的精确身份。

`research-control` 启动时在开放 ready 和任何读写 API 前逐项重算；缺文件、哈希漂移、计数作用域不完整、
授权字段不是固定 false/none 或 v1 配置被误选，均 `CONTROL_NOT_READY`。Docker 只读挂载只包含这些
枚举真身，不得通过整仓挂载绕过漂移门。

## 5. 验收门

1. v1 文件字节不变，运行时只接受 v2；
2. 五家族 primary/sensitivity 计数、证据 SHA 和 planned-after 逐项正确；
3. 静态 6/联合 12、残差 3/全局 273 不再被单值压平；
4. 确定性模式的非零调用/费用及 LLM 模式的零调用/零费用全部零写入拒绝；
5. 架构宪法或任一绑定输入漂移时服务不 ready；
6. `approval_authorized`、`provider_spend_authorized` 及基础协议全部执行授权保持 false/none；
7. 不产生研究尝试、provider 调用、结果读取、任务、队列、批准或生产变化。

通过本补正只解除 M5-1 代码施工的合同阻断；终态仍只能是
`GO_M5_PROPOSAL_ONLY_CONTROL_PLANE`，M5-2 继续未授权。

# A1-5A 真实效果 attempt claim 工程协议

- 协议 ID：`a1-5a-effect-attempt-claim-gate-v1`
- 状态：`FROZEN_BEFORE_IMPLEMENTATION`
- 日期：2026-08-23（UTC+8）
- 上游：A1-4C-R1 `GO_LOCAL_READ_ONLY_RELEASED`
- ADR：`docs/ADR_001_EFFECT_ATTEMPT_CLAIM_GATE_20260823.md`

## 1. 本节点要交付的结果

建立一个可由未来真实效果 runner 复用的 claim-first 窄门，并用机器清单封住新入口旁路。A1-5A 成功
只表示工程门可用，不表示任何历史 runner 已迁移，更不授权读取效果、运行模型/回测或改变生产。

## 2. 冻结状态机

```text
PRECHECKED
   ↓ append canonical claim + fsync
LEDGER_CLAIMED
   ↓ write content-addressed receipt + fsync
EFFECT_READ_ALLOWED
   ↓ future runner owns terminal report/failure evidence
TERMINAL_OUTSIDE_CLAIM_ROW
```

- claim 或 receipt 前失败：效果 reader 调用 0；
- ledger claim 后失败：尝试已消费，reader 可以是 0 次，但同 scope 永久关闭；
- reader 调用后失败：尝试已消费，失败证据必须引用 receipt；
- 已存在相同 experiment ID：失败关闭，不返回旧 receipt，不允许同 scope 重跑；
- claim row 永不更新；最终 decision/report 由版本化效果产物和独立 audit 表达。

## 3. 固定 claim 字段

claim row 必须完整填充现有实验账本字段，并固定包含：

- `candidate_source`、`model_or_engine`、`engine_version`、`attempt_family`；
- `release_scope_sha256`、`attempt_ordinal`、`code_sha256`、`data_snapshot_sha256`；
- `status=CLAIMED_BEFORE_EFFECT_READ`、`attempt_consumed=true`、`authoritative=false`；
- `same_scope_retry_authorized=false`、`production_authorization=none`；
- `admitted=false` 与明确的非准入原因。

禁止字段包括效果值、收益、排名、证券、持仓、原始行情、绝对本机路径和任何凭据。

## 4. 实现范围

1. 将现有通用的确定性实验追加能力从“历史 reconciliation”名称中抽出，旧函数保留兼容薄包装；
2. 新增单一职责 `research/effect_attempt_claim.py`，负责 spec 校验、ID/row/receipt 规范化、claim-first
   编排和独立 ledger/receipt 验证；
3. 新增机器注册表，登记全部现存旧效果 runner 的路径、源码 SHA、关闭状态和不可复用边界；
4. 自发现测试要求带标准 effect-start marker 的 tracked runner 与注册表集合相等；
5. synthetic fixture 覆盖正常调用顺序、claim 前失败、receipt 写失败、reader 失败、同 scope 二次调用、
   行/receipt 篡改、敏感字段和 Schema 越界。

## 5. 禁止事项

- 不修改八个历史效果 runner、冻结协议、release scope、镜像或历史产物；
- 不写真实 `ledger/experiments.csv`，不新增真实研究尝试；
- 不读取任何封存效果、标签、收益、证券或持仓；
- 不运行 Qlib、训练、预测、回测、DeepSeek、模拟仓或 scheduler；
- 不读取 `.env`，不访问外网，不改变 Web；
- 不把 A1-5A 工程 GO 表述为 M6-5C、策略有效性或生产授权。

## 6. 验收与下一步

专项、账本追加门、架构、全仓、Ruff、compileall、pip check 和 diff-check 全部通过；新增生产模块不超
400 行，现有热点不增长。完成后唯一下一步是由具体未来效果节点另立迁移协议，把 claim gate、最小
账本写挂载、terminal report 引用和独立 auditor 绑定到最终不可变 runner；未经该协议不得真实执行。

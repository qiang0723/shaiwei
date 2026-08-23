# ADR-001：真实效果读取的 canonical attempt claim 门

- 状态：`ACCEPTED_FOR_A1_5A_ENGINEERING`
- 日期：2026-08-23（UTC+8）
- 决策节点：`A1-5A`

## 问题与结果目标

现有真实效果 runner 通常先在忽略区写 `effect_started` 标记，再读取封存效果；部分冻结 release 又
明确禁止挂载或写入 `ledger/experiments.csv`。M6 Head30 因此出现两次效果读取已消费尝试、但只能
事后补录 canonical ledger 的缺口，并进一步触发过提交基线错位。

目标不是重写已关闭研究，而是让未来任何真实效果入口在读取语义结果前，先以同一 release scope 在
canonical ledger 中持久占用尝试。失败后账本行仍保留，同 scope 不得再读；下游可据此准确计算
研究家族尝试数，且不再依赖事后补账。

## 候选方案

### 方案一：回改全部历史 runner

拒绝。现有入口的协议、镜像、scope 和效果证据均已冻结并关闭；批量回改会制造新的历史实现，无法
解释原执行时没有账本挂载的事实，也会扩大回归面。

### 方案二：效果完成后追加 terminal ledger 行

拒绝。效果读取后到追加账本前若进程崩溃，仍会产生“已看结果但未计尝试”的窗口，这正是当前缺陷。

### 方案三：claim-first，账本 fsync 后才开放效果读取

采用。runner 在构造或调用真实效果 reader 前，先追加一条确定性 scope claim；追加成功并写出
内容寻址 receipt 后，才把 receipt 交给 reader。效果读取或后续计算失败仍消费尝试；在账本写入后、
reader 调用前崩溃也保守计一次并关闭同 scope。该选择可能在极窄故障窗口多计一次未实际看到结果的
尝试，但绝不会少计已读取效果的尝试，符合防过拟合和审计优先原则。

## 合同与边界

- canonical ledger 继续使用现有 `ledger/experiments.csv` Schema，不修改历史行；
- claim 行只表达“尝试已消费且效果读取许可已占用”，不伪装成 terminal 策略裁决；
- deterministic experiment ID 绑定 schema、attempt family、release scope 和 ordinal；
- 同 scope 第二次 claim 无论内容是否相同都失败，不把幂等当作重跑授权；
- receipt 必须绑定完整 ledger row 哈希；独立 verifier 从 ledger 反查唯一行并重算；
- claim 前失败不计尝试；claim 后任何失败均计尝试，恢复必须新 scope、新 ordinal、新授权；
- `admitted=false`，不得污染因子准入；不得包含效果数值、证券、持仓、原始数据或 secret；
- A1-5A 只用临时 synthetic ledger 验证，不写真实账本、不读取效果、不运行回测。

## 迁移、回滚与退出

八个现存真实效果入口登记为 `LEGACY_CLOSED_NO_CANONICAL_CLAIM`，保持源码和历史证据不变，禁止以
原 scope 重跑。机器自发现测试要求所有带冻结 effect-start marker 的 runner 必须进入登记表；未来
新入口只有接入 claim gate 并在 release/Compose 中显式授权最小账本写挂载后才能登记。

A1-5A 的回滚只删除未被任何真实 runner 使用的新模块、注册表和测试；不触碰历史账本。首次真实迁移
点是未来 M6-5C 或其他另立协议的效果 runner，届时必须独立冻结具体 claim row、挂载、receipt 与
auditor 绑定，不能由本 ADR 自动授权。

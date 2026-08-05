# M5-0A 策略工厂跨池评价单元计数补正协议

> 协议 ID：`m5-strategy-factory-count-correction-v1`
>
> 冻结时间：2026-08-05T17:08:00+08:00
>
> 权威范围：M5-0 只读策略工厂中 M3 跨池评价单元计数的追加式补正

## 1. 发现与裁决

M5-0 的冻结目录把 `m3-custom-pools-price-volume-v1` 同时记为 24 次生成尝试和 24 个评价单元。
M3 结果前协议与最终发现验收均明确：24 个响应中的每一个都在三个自建股票池形成一个评价单元，
因此生成尝试是 24，跨池评价单元是 72。

本补正只把该工作包的 `evaluation_unit_count` 从 24 更正为 72。以下事实全部不变：

- `generation_attempt_count=24`，相关价量发现域仍只增加 24 次，累计 `N=270`；
- `candidate_count=24`，`effect_test_count=0`；
- M3-3 仍为 `STOPPED_CONTRACT`，策略仍为 `NOT_EVALUATED`；
- 不读取封存效果，不产生因子、模型、回测、信号、前瞻或生产授权；
- 其余七个工作包、八个股票池、正式因子库 0 和中证800唯一生产策略均不变。

旧目录、旧快照与 M5-0 验收永久保留，不原地改写。旧快照仍证明 M5-0 只读工程闭环，但其中该字段
不再是当前权威的研究 multiplicity 口径。

## 2. 绑定证据

- 基础目录：`config/m5_strategy_factory_v1.yaml`，SHA-256
  `9bcc8053d334bdb66895f688377eb5858393909da3379f7b33e488d4b4e5311b`；
- 旧快照 ID：`b24142867cf6e68b30724dd8d38a4864c2898e995de3bbf89bd2ea02594af9b3`；
- 旧快照文件 SHA-256：`83bb3d46e4fc46d450f3e13496d8ecb10b49ca48f86f3536399ea9503e64bcc3`；
- M3 结果前协议：`docs/M3_MULTI_POOL_FACTOR_PREEXECUTION_PROTOCOL_20260802.md`，SHA-256
  `9200bac34700293b3dd5d823e114a6bca0ca7b4614abd793e0e73ea714910c03`；
- M3 发现验收：`docs/M3_MULTI_POOL_FACTOR_DISCOVERY_ACCEPTANCE_20260802.md`，SHA-256
  `6db71b9ba19cafeb6dabcd590ea30c284a92d753d74903f5bdd463ffe0fc3ec2`。

两份 M3 证据均逐字声明“24 次响应 × 3 个股票池 = 72 个评价单元，但只增加 24 次研究尝试”。

## 3. 允许施工

1. 新增机器可读 addendum，精确绑定基础目录、旧值、新值和两份证据；
2. 通过独立 authority overlay 模块把 addendum 应用于内存中的目录模型；
3. 在新的 `strategy_factory_v2` 内容寻址目录生成新快照和新指针，保留旧目录字节不变；
4. 新快照来源身份同时包含基础目录、addendum、构建器和全部原证据哈希；
5. 只读 Web 切换到新目录，页面显示 M3 生成尝试 24、评价单元 72；
6. 补充 addendum 漂移、非法字段/对象/旧值、新旧目录隔离、双跑幂等和 GET/HEAD-only 回归。

## 4. 禁止事项

- 不修改 `config/m5_strategy_factory_v1.yaml`、旧快照或旧 `latest.json`；
- 不借补正调整任何研究结果、裁决、候选、尝试 N、股票池状态或准入事实；
- 不读取行情、标签、收益、持仓、模型或 `.env`，不访问网络；
- 不启动 research-control、Worker、DeepSeek、回测或生产施工；
- 补正验收通过前，不冻结或实现 M5-1 proposal-only 控制面。

## 5. 通过条件与终态

- 新快照中只有目标字段从 24 变为 72，所有其他业务字段与旧快照一致；
- addendum、基础目录和两份 M3 证据任一哈希漂移均失败关闭；
- 旧目录全树哈希施工前后不变，新目录双跑字节一致；
- Web GET/HEAD、未知参数、写方法拒绝、`.BJ=0`、正式库0、活跃授权任务0全部保持；
- 架构门、全仓测试、Ruff、Compose、脱敏和 scheduler 隔离通过。

唯一允许终态为 `GO_M5_STRATEGY_FACTORY_COUNT_CORRECTION_ONLY`。该终态只解除 M5-1 的历史计数
阻断，不自动授权 M5-1 或任何真实研究。

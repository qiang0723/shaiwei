# M3-3 三自建池机械 Top2 独立审查协议

日期：2026-08-02（UTC+8）

协议：`m3-star-three-pool-price-volume-review-v1`

状态：`M3_3_RESULT_BLIND_REVIEW_PROTOCOL_FROZEN_EXECUTION_NOT_RELEASED`

策略有效性：`NOT_EVALUATED`

生产授权：`none`

## 本阶段只回答什么

M3-2 已机械锁定两条三池候选。M3-3 只审查固定公式能否在不看任何发现指标和封存结果的前提下，
支持一致的数学构造、经济方向、三池共同机制、PIT/数值稳定性和可证伪性。它不生成、修复或替换
公式，不改方向/窗口，不递补第 3 名，不读取 2023—2026 封存结果，也不运行 G1、模型、回测、组合、
信号或生产任务。

固定候选为：

1. `f6fd83e97bad3114`：`Div(EMA($close,5d),EMA($close,20d))`，方向 positive；
2. `ca552f379c62504d`：`Div(WMA($close,5d),WMA($close,20d))`，方向 positive。

候选、顺序、表达式哈希、原始响应和发现证据身份绑定 M3-2 终版 manifest、报告、context、attempt
ledger 与不可变产物。不通过时原式停止，不得递补、改式或追加发现响应。

M3-2 的 `expression_tokens=7` 按 provider 原始表达式计数；规范渲染会补 `$` 与 `d`，若对渲染文本
重新分词可得到不同数量。M3-3 必须从原始响应重放同一审计流程并复用冻结值，不得用重新分词改写
复杂度或机械顺序；公式哈希、AST 节点和最大回看仍须逐项一致。

## 主控污染与唯一审查权

主控在 M3-2 运行和终态核验中已看到批次状态、合格候选数量、机械顺序，以及其中一条候选的部分
发现期排序信息；没有读取 2023—2025 验证、2026 压力/近期、G1、模型、组合或前瞻结果。该污染不
掩盖，具体数值不得写入本文、提示、Git 摘要或对外请求，主控永久退出本批经济裁决。

唯一审查权来自不接收任何发现指标或后续结果的固定 DeepSeek 对抗委员会。它是保守负面筛选：只有
候选四角色均未发现 major/critical 阻断，才可能允许另立 M3-4 验证协议；这仍不是因子有效性结论。

## 固定八份审查与语义合同

每条候选按相同顺序接受四个窄角色，合计恰好 8 个完成响应，串行执行：

1. `construct_and_units`：水平比值、收益含义、量纲、价格尺度、复权和截面可比性；
2. `economic_direction_and_cross_pool_coherence`：positive 方向能否由一个事前机制同时适用于全市场、
   中盘和小盘规则池，而不是公式复述；
3. `pit_and_numerical_stability`：历史窗口、次日开盘、分母、缺失/停牌、有限值与确定性；
4. `redundancy_and_falsifiability`：EMA/WMA 两式是否构成独立可证伪假设或实质冗余。

响应必须先通过严格 JSON schema，再由既有确定性自由文本语义门逐字段检查。正文若建议任何替代
算子、窗口、估计量、方向或变体，出现不同 DSL，声称业绩/准入，或含糊暗示改式，均计入 8 次并
立即停止整批；不得补发。这直接吸收 D1-3A 与 M1-2 “结构字段合规、正文越界”的失败经验。

## 结果前裁决

- 公式身份、复杂度、回看、原始响应和 M3-2 上游哈希必须先通过确定性门；
- 8/8 响应必须同时 schema 有效且语义为 `PASS_SEMANTIC_CONTRACT`，否则
  `STOP_M3_3_REVIEW_CONTRACT`；
- 单候选四角色必须全部 `NO_BLOCKER_FOUND`；任一 major/critical finding 按原式
  `REJECT_REVIEW_BLOCKER`，不修复、不递补；
- 至少一条通过时只能裁定 `GO_FREEZE_M3_4_VALIDATION_PROTOCOL_ONLY`；两条均拒绝时为
  `STOP_M3_FAMILY_BEFORE_VALIDATION`；
- 任一终态都保持 `strategy_effective=NOT_EVALUATED`、`production_authorization=none`。

## 费用、网络与当前授权

未来模型固定 `deepseek-v4-pro`、thinking enabled/high、JSON Output；8 次按 16k 输入、3k 输出、全部
cache miss 预留 `$0.07656`，专项硬熔断 `$0.25`。未用余额不构成执行授权，模型身份或价格变化须在
首次请求前 fail closed。

本协议当前 `execution_authorized=false`。本目标只允许实现断网 fixture、专属空账本和不可变执行
真身，DeepSeek 调用必须在预执行门验收后，另行向用户列明“固定两条公式、非权威假设、公开知识
摘要、四角色问题、恰好 8 次、上限 `$0.25`”并取得明确授权。

未来 API 只允许接收上述结果盲字段；禁止发送发现指标、行情行、证券清单、收益、持仓、本地路径、
日志或凭据。密钥仍只准从项目内 Git 忽略的 `.env` 窄传入一次性 Docker。

## 工程与停止边界

实现应复用已验收的通用语义门和 DeepSeek 传输适配层，但使用独立 M3 合同、schema、证据和 ledger，
不得改变旧 D1/M1/M3-2 证据。预执行容器必须非 root、只读根、`network_mode:none`、无端口和 Docker
socket；输出 provider 调用 0、密钥读取 false、发现指标未读、封存结果未读。

本阶段不修改或重启 scheduler，不施工 Web，也不接任何生产路径。

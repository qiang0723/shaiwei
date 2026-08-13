# TS-v5 DeepSeek 预算补充裁决

日期：2026-08-13（UTC+8）

状态：`PROGRAM_BUDGET_AUTHORIZED_BATCH_EXECUTION_PENDING`

用户已将TS-v5 DeepSeek持续研究总费用硬上限提高到5.00美元。本裁决提高的是研究计划的总预算容量，
不是消费目标，也不自动授权任何一次API调用。未用额度不得自动滚入一次批次；每个后续批次仍须在调用
前冻结发送范围、完成响应数、单批熔断、输入身份和输出边界，并取得用户明确批准。

首次批次的研究含义和安全边界不变：六类机制各1个独立候选和1个同机制反方改版，恰好12个完成响应，
串行运行；全缓存未命中最坏估算仍为0.102312美元，单批硬熔断仍为0.50美元。5.00美元不能被本批一次
性使用。禁止发送证券、原始行情、持仓、订单、信号、效果指标、封存/前瞻/生产结果、路径和任何凭据。

原`config/ts_v5_llm_research_scope_v1.yaml`及其SHA-256
`9947e1bebc10d5da32df63ff462a8c8e9403a12986dbfef0a891f69956325a88`永久保留。它在零provider调用、
零secret读取的状态下由v2在执行前显式取代，不静默改写。

当前机器scope为`config/ts_v5_llm_research_scope_v2.yaml`，SHA-256为
`a7ab6407db4037be53b7496246e4e200ca2a1d8081d4c31fa1de024b9ee32d56`。
总预算授权已经记录，但首批`execution_authorized=false`、`deepseek_api_called=false`；只有用户批准新的
机器scope哈希后，才允许冻结执行release、实现一次性批次协调器并运行首批。行情/收益、参数搜索、
回测、模拟仓、Web和生产均不在本授权内。

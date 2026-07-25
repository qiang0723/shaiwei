# D1 LLM-DSL 首轮 40 次对照协议草案

状态：`D1_2A_PREEXECUTION_FROZEN / D1_2B_NOT_AUTHORIZED`

执行授权：`false`

当前允许：D1-1 控制面，以及 D1-2A 已冻结的提示/知识、受限客户端、费用/传输恢复和断网 Docker 证据

当前禁止：读取 DeepSeek 密钥、DeepSeek 调用、真实候选生成、发现期评价、W1-W6/G1、生产接入

本文件把 D1-0 架构裁决转成 D1-1 至 D1-3 的结果前合同。机器真身为
`config/d1_llm_factor_research_v1.yaml`；两者冲突时必须停止并修订草案，不能在运行中自行解释。

## 1. 研究问题

在中证800、同一 2016-06-01~2018-12-31 有效发现期、同一 OHLCV/VWAP 字段、同一行业/市值
PIT 中性化、同一表达式白名单和同一 G1 下，固定 40 次 DeepSeek 受限 DSL 提案能否产生至少一个
通过全部 G1 的、相对 Alpha158 有扣费增量的候选？

这是“生成方法”研究，不是新数据研究、模型调参研究或生产策略试验。首轮不使用资金流、财务、观象
数值、新股票池或新执行规则。

## 2. 假设与主判

- `H0`：40 次 LLM 尝试后没有候选通过全部 `g1-v1`。
- `H1`：至少一个候选通过全部 `g1-v1`。
- 主判 `GO_BOUNDED_PILOT`：Top2 中至少一名全部 G1 PASS。
- 主判 `PAUSE`：无候选全部 G1 PASS；停止本协议，不调门槛、不补第 41 次、不换模型追结果。

历史 GP 只作冻结参考：最终 40 个表达式中 4 个有效、最佳 `|RankIC|=0.0201422558`，家族总 N 为
166。禁止复制旧候选到新家族或重置 N，以免降低多重检验惩罚。

## 3. 40 次预算与主题

固定五个 DSL 可表达主题，每主题 8 次，顺序不可改变：

1. 趋势/动量；
2. 反转/均值回归；
3. 波动/振幅；
4. 流动性/成交量；
5. 量价交互/状态。

每主题前 4 次为独立提案，后 4 次为有界变异。变异只能看同主题的 parser/sandbox 结果、规范 AST、
覆盖、复杂度和发现期 RankIC；不得看 W1-W6、压力期、G1、前瞻或其他主题结果。无论前 4 次多差，
仍完成该主题 8 次；无论提前出现多强候选，也不因表现提前停止。

一个完成的模型响应只允许一个候选。以下均消耗一次尝试并进入 G1 家族 N：

- 空、截断、schema 错误或包含多个候选；
- 表达式语法错误、白名单/复杂度/回溯/shift 拒绝；
- 与历史 GP、正式因子库或本轮已有候选规范 AST 重复；
- 覆盖不足、RankIC 无效或发现期弱；
- 为修复前述问题而获得的新模型响应。

仅在没有完成响应的连接/5xx/429 情况下允许同请求哈希最多重试两次；如果无法确认服务端是否已经
完成并计费，账本标记 `BILLING_UNCERTAIN` 并在下一请求前 fail closed。

## 4. 模型、输出和费用

- 模型：`deepseek-v4-pro`；thinking 开启；`reasoning_effort=high`；不传无效 temperature。
- 正式 JSON Output；不用 beta strict tools；不给任何工具。
- 串行并发 1；每次输入最多 16k token、输出最多 8k token。
- 40 次全缓存 miss 的计划上限 $0.5568；硬熔断 $0.75。
- 首次请求前重新核对官方模型名和计费；任一价格高于草案、模型返回身份变化、usage 缺失或累计费用
  无法界定时停止，禁止靠估算继续。

API 密钥只从运行时环境变量读取，禁止进入提示词、日志、账本、错误栈、Docker 镜像层、Git 或飞书。
本协议不读取也不验证现有 `.env` 内容；D1-2 启动前只做“变量存在/不存在”的脱敏门。

## 5. 候选 JSON 最小契约

每个响应必须包含且只能包含一名候选的以下语义字段：

```json
{
  "schema_version": "d1-candidate-v1",
  "topic": "trend_momentum",
  "hypothesis": "可被证伪的经济或行为假设",
  "expression": "Mean($close,20)",
  "expected_direction": "positive_or_negative",
  "economic_rationale_draft": "LLM 草稿，非 G1 人工解释",
  "lineage": {
    "mode": "independent_or_mutation",
    "parent_attempt_ids": []
  },
  "known_failure_risks": []
}
```

本地 schema 拒绝额外字段和第二表达式。`expected_direction` 只作预注册记录；权威方向仍按现有 G1
样本内 RankIC 规则冻结，LLM 不得根据 W1-W6 改方向。

## 6. 提示与知识身份

D1-2 前必须冻结并哈希：system prompt、candidate schema、算子/字段说明、五个主题模板、知识源清单、
每条人工摘要、反馈序列化规则、提供方配置和代码快照。

首轮运行中禁止实时网页检索。每条知识必须有 URL、作者/发布者、发布时间、抓取时间、内容哈希、许可
或使用依据、人工摘要哈希。外部正文默认不直接进入提示；含指令性文本、不可确认来源或权利边界不清的
内容进入隔离区。所有知识截至 2026-07-25，历史研究结论必须带“回溯发现”标签。

D1-2A 已冻结机器真身 `config/d1_llm_factor_prompt_v1.yaml` 与
`config/d1_llm_factor_knowledge_v1.json`：五主题各一条一手论文人工摘要进入创意提示，五条
DeepSeek 官方文档只约束模型、价格、请求、响应和重试。前四次独立提案反馈为空；后四次变异必须按
ordinal 携带同主题全部早先 attempt，最多 7 条，不得只挑成功记录。允许/禁止字段和 parent 候选集合
由本地序列化器强制，W1-W6/G1/前瞻字段无法进入请求。

## 7. 确定性执行与安全门

LLM 输出永不 `eval`。执行链固定为：JSON schema → 字符串规范化 → 现有 AlphaGen parser → 算子/
字段/窗口/复杂度白名单 → synthetic future perturbation → 真实发现期因子计算。

D1-1 的一次性研究容器须满足：非 root、只读根、无 Docker socket、固定 CPU/内存/PID/超时、默认
不挂生产模型和信号、只挂项目内 D1 研究区及所需只读数据。mock/synthetic 测试完全断网；真实 D1-2
只允许客户端向冻结 DeepSeek base URL 发请求，模型本身没有工具和网络入口。

## 8. 记账与不可变产物

D1-1 已新增 `ledger/llm_factor_attempts.csv`，一行对应一个预分配 attempt，至少绑定：

- attempt/topic/ordinal/parent；
- protocol、prompt、knowledge、schema、代码和数据快照哈希；
- provider 请求时间、返回模型、结束原因、usage、cache hit/miss 和美元估算；
- 原始响应哈希、解析/沙箱状态、规范 AST、重复对象、失败分类；
- 发现期覆盖与指标产物哈希。

原始请求/响应、reasoning、因子面板和中间结果只留在项目内 `data/research/d1/` Git 忽略区；Git 提交
脱敏 manifest、协议、代码、fixture、测试和必要账本。`ledger/experiments.csv` 继续作为 G1 试验 N 的
权威来源；D1-1 必须证明两个账本一一对应、重复运行不追加第二行、任何碰撞 fail closed。

D1-2A 另新增 `ledger/llm_factor_transports.csv`，以 STARTED/COMPLETED/RETRYABLE_ERROR/
TERMINAL_ERROR/BILLING_UNCERTAIN 事件记录请求传输状态。200 响应必须先落 write-once 项目内产物再
完成事件；悬空 STARTED、读写超时、协议断链或无法解析的 200 均按可能已计费停止，恢复不得自动重发。

## 9. 发现期选择和人工闸

40 次全部终结后，按冻结的方向无关发现强度机械选择 Top2；语法、安全、重复和覆盖失败者不能入选。
Top2 确定后、读取 W1-W6 前，研究者逐名填写不少于 20 字的人工经济解释并判断是否成立：

- 成立：绑定解释哈希，进入 G1；
- 不成立：该名直接失败且不递补；
- 解释不得引用 W1-W6、压力期、未来或前瞻结果。

这一步保留 G1 的“人工可陈述经济含义”，但不允许人工通过不断换名优化历史结果。

## 10. 评价、报告和停止

Top2 使用未经修改的 `g1-v1`。报告必须同时给出：

- 40 次完整漏斗、五主题分层、失败和重复；
- DeepSeek token/成本、缓存状态、模型身份和异常；
- 与 GP 40 个最终候选的生成层描述比较；
- 与旧 GP Top2 的相同组合层指标比较；
- LLM 自己真实 N 下的 DSR/HAC/G1；
- 明确区分 `生成有效`、`历史 G1 PASS`、`前瞻有效`、`生产授权`。

任何 G1 PASS 只允许另立 D1-4 有界前瞻候选；`production_authorization` 继续为 `none`。无 PASS 则
协议 PAUSE，保留所有失败记忆；若未来换模型、开放 Python、接入观象或新数据，必须另立新家族和新
结果前协议，不能把本次第 41 次伪装成延续。

## 11. 分阶段授权点

| 阶段 | 可做 | 不可做 | 进入条件 |
|---|---|---|---|
| D1-0 | 架构/协议/配置 | API、候选、效果 | 本次完成 |
| D1-1 | 控制面、账本、schema、mock、synthetic、Docker 工程门 | 真实 API、真实候选/结果 | 2026-07-25 已完成，工程 GO |
| D1-2A | 提示/知识冻结、真实客户端、费用和传输恢复断网验收 | 密钥、API、行情、G1 | 2026-07-25 已完成，零调用 |
| D1-2B | 40 次生成与发现期评价 | W1-W6/G1、追加预算 | D1-2A 先提交推送，用户确认模型、40 次和 $0.75 |
| D1-3 | 人工闸、Top2 G1 | 改门槛、递补、生产 | D1-2 不可变证据完整，另行授权 |
| D1-4 | 有界低频前瞻研究试运行 | 常设自治、生产控制 | 至少一个 G1 PASS，另立协议 |

## 12. 阶段状态与待确认

D1-1 验收见 `docs/D1_LLM_FACTOR_ENGINEERING_ACCEPTANCE_20260725.md`；D1-2A 已完成官方合同核对、
提示/知识冻结、受限客户端和断网恢复验收，见
`docs/D1_LLM_FACTOR_PREEXECUTION_ACCEPTANCE_20260725.md`。当前仍为零 API、零市场结果和零生产
授权。D1-2B 开始前必须由用户明确确认：

1. 首轮使用 V4 Pro thinking/high，而不是 Flash；
2. 40 次上限及每主题 4 独立 + 4 变异；
3. $0.75 硬费用上限；
4. D1-2A 完成并提交推送后，再决定是否授权 D1-2B；
5. 观象、实时知识雷达、资金流/财务和任意 Python 全部不进入首轮。

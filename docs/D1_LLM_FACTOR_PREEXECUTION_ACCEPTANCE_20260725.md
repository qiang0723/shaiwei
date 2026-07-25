# D1-2A LLM 因子研究真实调用前冻结验收

日期：2026-07-25（UTC+8）

## 1. 裁决

`GO_PREEXECUTION_ONLY / D1_2B_NOT_AUTHORIZED`

- `prompt_contract_frozen=true`
- `knowledge_manifest_frozen=true`
- `official_provider_contract_checked=true`
- `restricted_real_client_implemented=true`
- `transport_recovery_engineering_complete=true`
- `llm_api_calls=0`
- `runtime_deepseek_secret_loaded=false`
- `real_market_data_read=false`
- `market_results_inspected=false`
- `g1_run=false`
- `production_authorization=none`

本裁决只证明首次真实调用前所需的提示、知识身份、费用熔断和传输恢复工程已经冻结并通过断网
验收。它不批准读取 `.env`、调用 DeepSeek、生成真实候选、读取发现期行情、运行 G1、修改生产
scheduler 或把 LLM 接入生产。

## 2. 冻结合同

### 2.1 提示与反馈

`config/d1_llm_factor_prompt_v1.yaml` 冻结以下内容：

- 中文 system prompt 明确 LLM 只是候选假设生成器，不是投资顾问、回测裁判或生产控制器；
- 一个完成响应只能返回一个符合严格 schema 的 JSON 候选，禁止工具、Python、shell、文件、网络、
  环境变量、动态执行和额外字段；
- 趋势/动量、反转/均值回归、波动/振幅、流动性/成交量、量价交互五个主题各有独立目标、问题域和
  禁止解释；
- 前四次独立提案不得读取先前反馈；后四次变异必须按顺序携带同主题全部先前尝试，最多 7 条，
  不得遗漏失败记录或跨主题；
- 反馈只允许 parser/sandbox、规范表达式、重复对象、失败分类、发现期覆盖/RankIC 和复杂度字段；
  W1-W6、压力期、G1、前瞻和生产字段在序列化前 fail closed；
- 变异响应的 parent 必须属于请求内冻结的 `eligible_parent_attempt_ids`，且在不可变尝试账本中确实
  存在于当前尝试之前。

请求固定 `deepseek-v4-pro`、thinking enabled、`reasoning_effort=high`、JSON Object、`stream=false`、
`tools=[]`，不传 temperature；请求还绑定 prompt、knowledge 和 candidate schema 哈希。UTF-8 请求体
使用保守上界阻断超过 16k 输入预算的请求。

### 2.2 知识 manifest

`config/d1_llm_factor_knowledge_v1.json` 共冻结 10 条来源：

- 5 条 DeepSeek 官方执行合同：模型/价格、thinking、JSON Output、响应 schema、错误码；
- 5 条一手研究来源分别服务五个主题：Jegadeesh–Titman、Lehmann、Parkinson、Amihud、
  Lee–Swaminathan。

每条都绑定 URL、作者/发布者、发布时间、检索时间、人工核验事实哈希、使用依据、人工摘要及摘要
哈希。Git 和提示均不保存外部全文；进入提示的只有五条人工摘要，官方 API 文档只约束执行、不参与
创意。所有历史研究结论标记 `retrospective_discovery=true`，不得表述为 2016—2018 当时可得知识。

官方核对来源：

- [DeepSeek Models & Pricing](https://api-docs.deepseek.com/quick_start/pricing)
- [DeepSeek Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode)
- [DeepSeek JSON Output](https://api-docs.deepseek.com/guides/json_mode/)
- [DeepSeek Create Chat Completion](https://api-docs.deepseek.com/api/create-chat-completion)
- [DeepSeek Error Codes](https://api-docs.deepseek.com/quick_start/error_codes/)

本次冻结价格为每百万 token：cache-hit 输入 `$0.003625`、cache-miss 输入 `$0.435`、输出 `$0.87`。
40 次 × 16k 全 miss 输入 × 8k 输出的机械最坏费用仍为 `$0.5568`，低于待用户确认的 `$0.75`
硬熔断。模型、返回身份或任一价格变化都要求在第一请求前修订协议，不能沿用本次核对。

## 3. 真实客户端控制面

`src/shaiwei/research/deepseek_client.py` 已实现 OpenAI 兼容的受限 DeepSeek 适配层，但当前协议
`execution_authorized=false`：

- 未授权时只接受 `httpx.MockTransport`；任何真实 HTTP transport 在创建 client 前被拒绝；
- live factory 在读取环境变量和创建网络 transport 前先核验授权；本次没有读取或验证 `.env`；
- Authorization、响应正文、provider error body 和 response id 不进入错误、账本或 Git；
- 200 响应先写项目内 Git 忽略的 write-once 脱敏产物，再追加 `COMPLETED`，恢复时读取产物而不二次
  请求；
- 响应出现密钥/Webhook 模式时不落原文，只保留源响应哈希、脱敏标记、模型/usage/结束原因；
- 429/500/503 和连接建立失败仅在明确没有完成响应时最多重试两次；
- read/write/协议断链、无法解析的 200、悬空 `STARTED` 均视为 `BILLING_UNCERTAIN`，自动恢复和
  自动重试都被禁止；
- 返回模型不符、usage 缺失/矛盾、累计费用越界或敏感输出均是批次级 fatal，下一次 provider 调用
  前要求人工复核；
- 每个完成响应的实际 usage 计入累计费用；下一请求还必须预留一个 16k miss + 8k output 的最坏
  费用，无法预留即在请求前熔断。

新增空的追加式 `ledger/llm_factor_transports.csv`。每个 transport event 只记录 attempt/request
哈希、序号、状态、HTTP 类别、计费状态、脱敏产物与源响应哈希，不记录请求、响应、密钥或 URL。

## 4. 断网与对抗验收

- 本地全仓：247 passed；既有 FastAPI/Starlette 兼容提醒 1 条，与 D1 无关。
- D1/账本专项：43 passed。
- 断网、非 root、只读根 Docker fixture：PASS；同时验证 candidate/experiment 双账本 1:1、幂等
  重放、prompt/knowledge 哈希、MockTransport 成功恢复、429 后一次恢复、读超时后禁止重发。
- 断网 Docker 对抗：29 passed、2 项仅因镜像不复制 Git ledger 而按计划 deselect；覆盖未授权真实
  transport、环境变量前置拒绝、终端错误脱敏、坏 200、敏感输出、费用门、提示/知识篡改、反馈越界、
  schema/DSL/谱系和双账本。
- Ruff、compileall、`pip check`、Compose config、`git diff --check` 和全仓秘密/忽略边界均 PASS；
  宿主脱敏门只将 `.env` 中已配置秘密与 Git 跟踪文件作不回显比对，client/fixture 未加载密钥。
- Docker fixture 的 `network_mode=none`，无 `.env`、端口、Docker socket、生产数据/账本/模型/信号
  挂载，也没有启动常驻服务。

## 5. 不可变身份

| 证据 | SHA-256 / 身份 |
|---|---|
| 完成态协议 | `68f3f40ea69979f1febfc99ea66b18b3324ea702f02651aafac65b50630f94b5` |
| prompt bundle | `23c56cc58aeaa1d59f1c4ee587debe052e7422949c18553be9937a3ea73942ec` |
| knowledge manifest | `0f1e8ab2461352ce020dcf1873a5d79bfc010b08eea205b6b308e27bc3c23fad` |
| candidate schema | `71617286887eec810735a22651d7ade9d9eb58aa5a3eb1650ee833f9adacf217` |
| control plane | `3c9dfeeceac43ac9f4750b2d18b18885734accd9d71562336fa7bba446555b31` |
| prompt/knowledge validator | `7f762976108667de8c39d082933222cdaee73f73ca613ca4335f5423ea22579a` |
| restricted DeepSeek adapter | `8450c6ff99368278e97606390162437f123e68a88c7707b3b1adb78022bd3fcb` |
| 空 transport 账本 | `212d06350c46b7f3359ce9a90d53224977c231d11501e1e1f4467140d9fe3ad6` |
| research compose | `0f1305af9d6b2148edbd48648569f189bfb054e6579b024f07a08eb96e62c449` |
| Docker 受控代码快照 | `0c6ca3a03b68574a420f764780e05ba2e9868fd2644a46250b537a808e1658aa` |
| Docker 镜像 | `sha256:b5fb1fce8301739064233460ff84d514e4ba87ba6d31da84453643ce0c5f21dc` |
| Docker fixture 产物树 | `ec060ebd57b877740d7e292cfa2725435bef34d174293cc72735c833542f14ad` |

## 6. 生产隔离

施工前后生产 scheduler 均为容器
`fd8e96152b53f3f0d0efdcd6462c2b039aa68c7fb56461b95826709652a5adbb`、镜像内容
`sha256:de87ec740981166b032b394fb256a978acdc8d35e999a369f1debc3466aa0261`，创建时间保持
2026-07-24 20:25:27+08:00，状态 `running/healthy`。本目标没有构建、重启、替换或挂载生产
scheduler。

## 7. 下一授权点

D1-2B 仍未开工。若用户要继续，必须明确批准以下一次性真实研究预算：模型
`deepseek-v4-pro` thinking/high、恰好 40 个完成响应、累计 `$0.75` 硬上限。批准后仍要先建立
独立真实研究发布快照、只做不回显的 secret 存在性门和冻结 API 出口核验，再串行执行生成与发现期
评价；不得读取 W1-W6/G1。D1-2B 完成只产生发现期 Top2，D1-3 人工解释闸和 G1 仍需再次授权。

# M1-2 科创50机械 Top2 独立审查协议

> 日期：2026-08-01（Asia/Shanghai）  
> 协议：`m1-star50-price-volume-review-v1`  
> 状态：`FROZEN_BEFORE_IMPLEMENTATION_AND_REVIEW_RESULTS`  
> 策略有效性：`NOT_EVALUATED`  
> 生产授权：`none`

## 1. 本阶段只回答什么

M1-1 已机械锁定两条科创50候选。M1-2 只审查固定公式能否在不看发现指标和封存结果的条件下，支持
一致的经济解释、PIT/次日开盘时钟、数值稳定性与可证伪性。它不生成新公式、不修公式、不改变方向
或窗口、不读取 2023—2025 封存验证窗、不运行压力期/G1/模型/组合，也不授权模拟仓或生产。

固定候选为：

1. `5c3c30d8b3a01f76`：`Corr(Delta($close,1d),$volume,20d)`，方向 positive；
2. `47f690ef14487a25`：`Div(Sub($close,Mean($close,20d)),Std($close,20d))`，方向 negative。

候选、顺序、表达式哈希和原始响应均绑定 M1-1 终版 manifest、报告、attempt ledger 与不可变产物；
不通过时不得递补第 3 名。

## 2. 盲态污染与独立性

协议冻结前，主窗口为筛选候选行误打印了两条候选的发现期 RankIC 与覆盖率。没有读取 2023—2025
封存验证、压力期、G1、组合、前瞻或生产效果。该污染不掩盖、不把数值写入本文、提示、Git 摘要或
对外请求，但主窗口永久退出本批经济裁决。

本批唯一审查权来自未接收任何发现指标或后续结果的固定 DeepSeek 对抗委员会。它是保守的负面筛选：
只有某候选四角色均未发现 major/critical 阻断，才允许另立 M1-3 验证协议；这不是因子有效性结论。

## 3. 固定八份审查与语义门

每候选按相同顺序接受四个窄角色，合计恰好 8 个完成响应，串行执行：

1. `construct_and_units`：数学构造、量纲、signed/unsigned、绝对价格变化与收益、截面可比性；
2. `economic_direction`：冻结方向是否有一致的事前行为、微观结构或错误定价机制；
3. `pit_and_numerical_stability`：PIT/次日开盘、零分母、缺失/停牌、有限值与确定性；
4. `redundancy_and_falsifiability`：与另一固定式的结构/经济冗余及明确可证伪条件。

响应必须通过严格 JSON schema，再在有效记账前通过既有自由文本语义门。正文若建议替换算子、公式、
窗口或估计量，提出变体，声称业绩/准入，含不同 DSL，或语义含糊，均计入 8 并停止整批；不得补发。
这直接继承 D1-3A “结构字段合规但正文越界”导致权威 STOP 的教训。

## 4. 结果前裁决公式

- 公式身份、复杂度、最大回看、PIT/shift 与上游哈希必须先通过确定性门；
- 8/8 响应必须同时结构有效且语义 `PASS_SEMANTIC_CONTRACT`；否则
  `STOP_M1_2_REVIEW_CONTRACT`；
- 单候选四角色必须全部 `NO_BLOCKER_FOUND`；任一 major/critical finding 将该式按原样
  `REJECT_REVIEW_BLOCKER`，不修复、不递补；
- 至少一条候选通过时，只能裁定 `GO_FREEZE_M1_3_VALIDATION_PROTOCOL_ONLY`；两条均拒绝时为
  `STOP_M1_FAMILY_BEFORE_VALIDATION`；
- 任一终态均保持 `strategy_effective=NOT_EVALUATED`、`production_authorization=none`。

## 5. 费用、网络与秘密

模型固定 `deepseek-v4-pro`、thinking enabled/high、JSON Output。2026-08-01 重新核对官方价格：每
百万 token 缓存命中输入 `$0.003625`、未命中输入 `$0.435`、输出 `$0.87`；8 次按 16k/3k 全未命中
预留 `$0.07656`，专项硬熔断 `$0.25`。官方已提示未来可能引入峰谷 2 倍价格，但尚未公布生效日；
首次调用前价格或模型身份变化即 fail closed，不用硬上限吸收未冻结的新价格。

调用只允许 `https://api.deepseek.com/chat/completions` 且 `trust_env=false`。API 只接收固定公式、方向、
非权威解释、公开知识摘要、角色和 schema；不得发送发现指标、行情行、持仓、收益、本地路径、日志或
凭据。密钥只从项目内 Git 忽略的 `.env` 窄传入一次性 Docker，禁止回显或写入镜像/证据/Git。

官方合同来源：

- https://api-docs.deepseek.com/quick_start/pricing/
- https://api-docs.deepseek.com/api/create-chat-completion/
- https://api-docs.deepseek.com/guides/thinking_mode/

## 6. 工程与停止边界

实现须放入独立 M1 模块，不继续扩大 920 行 D1 旧 runner；review 与 transport 使用 M1 专属追加式
ledger，原 D1 与 M1-1 账本只读。一次性容器须非 root、只读根、无端口、无 Docker socket，只写
M1-2 产物和两份专属 ledger。真实调用前还必须另立执行 release，绑定协议、prompt、语义门、候选
产物、代码、镜像、Git 远端和 `$0.25` 熔断；无密钥断网复跑不得新增请求、账本行或改变哈希。

本阶段不修改或重启 scheduler，不触碰 Top20 8 月 3 日守护，不施工 Web，也不接入任何生产路径。

# TS-v5-R3C 六机制合同金丝雀 scope 协议

日期：2026-08-13（UTC+8）

状态：`AWAITING_EXPLICIT_USER_APPROVAL`

## 目标

R3B只用合成proposal证明了合同可表达、可编译、可失败关闭；R3C的唯一目标是用六个真实但结果盲的
DeepSeek响应验证模型能否遵守新机制专属合同。六种机制各固定一个独立席位，恰好六份完成响应，串行、
无反方、无递补、无第七次调用。每份完成响应无论合法与否都消费其席位。

R3C不是策略研究结果门：不读行情、证券、收益、历史回测、封存验证或前瞻结果，不做参数搜索，不进入
模拟仓、Web或生产。合法proposal只证明合同遵守；即使六席全部合法，也只能进入后续候选冻结评审，
不能表述为候选或TS策略有效。

## 严格终态

- 六份均完成且六份均通过机制专属proposal Schema、确定性编译器和原冻结候选validator：
  `GO_CONTRACT_PROJECTION_CANARY_ONLY`。
- 仅4—5份合法：`STOP_PARTIAL_CONTRACT_COMPLIANCE`。
- 仅1—3份合法：`STOP_WEAK_CONTRACT_COMPLIANCE`。
- 0份合法：`STOP_NO_VALID_CANDIDATES`。
- 任意未完成、计费不确定、身份/账本/请求束不一致均直接停止，不补发。

## 成本与发送边界

沿用2026-08-13已冻结的DeepSeek价格口径和每席最多16000输入/1800输出token，六席全cache miss最坏
费用为0.051156美元，批次硬熔断0.15美元；TS-v5项目5美元余额不能扩张本批或自动授权未来批次。

发送内容仅含冻结proposal system prompt、被分配机制的Schema/projection、产品约束、公开方法摘要、
匿名失败记忆和尝试身份。不得发送行情、证券、持仓、信号、收益、封存结果、原始旧响应/reasoning、
本地路径或任何凭据。

## 开工顺序

本scope协议和配置先行提交并推送。之后只允许零调用地实现六请求bundle、严格分类/编译、复用现有
transport/费用/证据组件的最小runner设计和独立audit fixture；工程与镜像均通过后，再向用户报告唯一
scope SHA-256并取得逐字批准。只有批准后才能冻结绑定实现、镜像、空专属账本和请求bundle的execution
release；release推送及无secret预检通过前不得读取项目内DeepSeek密钥或联网调用。

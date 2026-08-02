# L2-0 因子审查合同 v2 工程协议

日期：2026-08-02（UTC+8）

状态：`RESULT_BEFORE_ENGINEERING_PROTOCOL_FROZEN`

授权上限：仅断网、零密钥、零真实候选的通用审查合同工程门

## 1. 为什么这是下一任务

M1-2 与 M3-3 都没有进入因子验证：前者在自由文本语义门失败，后者在首个响应的服务端结束状态
失败。两批都必须永久停止，不能补发、续跑或用新合同回救；但它们共同证明“结果盲审查委员会”的
输出合同已经成为新因子研究的重复阻断点。继续开新候选批而不先修合同，只会消耗研究次数和费用。

M3-3 的主控窗口没有读取响应叙事。可用的机器事实只有：完成响应 `1/8`、
`completion_tokens=3000`、冻结 `maximum_output_tokens=3000`、失败类
`provider_finish_reason_invalid`。现有合法 schema 同时允许最多 6 个 finding、每个 statement 与
resolution 各 1,000 字符，再加 1,500 字符 summary；因此旧合同从未证明“一个完全合法的最大响应
一定能放入传输上限”。本目标只修复这个工程矛盾与既有自由文本修复泄漏面。

## 2. 官方约束

仅采用 DeepSeek 官方资料作为当前供应商事实：

- thinking 默认开启，也可显式 `disabled`；thinking 模式会额外返回 `reasoning_content`。
- `finish_reason=length` 表示输出达到 `max_tokens` 或上下文限制，内容可能被截断；合法终态仍只接受
  `stop`。
- JSON Output 需要 `response_format=json_object`、提示内明确 JSON，并应合理设置 `max_tokens` 防止
  JSON 截断；官方同时说明 JSON Output 偶尔可能返回空内容，因此空响应必须保持无效且不可补发。

本工程把未来窄审查切换为显式 non-thinking：审查目标是受限分类和可证伪说明，不需要向控制面返回
思维链。若未来要恢复 thinking，必须另立协议重新证明输出预算与费用，不能静默改参数。

## 3. v2 紧凑合同

新 schema 仍保留候选 ID、角色、阻断结论、严重度、类别、简短陈述和可证伪条件，但执行以下收窄：

- summary 最多 320 个 printable ASCII 字符；
- finding 恰为 1—3 个；每条 statement 最多 320 字符、falsification condition 最多 240 字符；
- category 改为冻结枚举；响应禁止重复公式文本，禁止自由格式的 repair/resolution 字段；
- 阻断只能使用 `REJECT_EXACT_EXPRESSION_AS_IS`，无阻断只能使用
  `LATER_FROZEN_VALIDATION_ONLY`；二者都不构成因子效果或准入结论；
- 完整规范 JSON 必须不超过 4,096 bytes，provider `max_tokens=6,000`；显式关闭 thinking，故输出
  预算没有单独的 reasoning token 竞争；
- schema PASS 后仍把所有叙事字段映射到既有、哈希冻结的语义门检查。任何公式/窗口/方向修改、
  变体、不同 DSL、业绩或准入声称、模糊建议仍 fail closed。

## 4. 费用边界

本工程不调用 provider。按 2026-08-02 官方价格作纯算术上限：每次最多 12,000 cache-miss 输入 token
和 6,000 输出 token，对应 `$0.01044`；未来若仍为 8 个响应，示例最坏值 `$0.08352`。这只是未来
release 的预算参考，不是 API 授权；价格或模型变化必须在未来首个请求前重新核对并失败关闭。

## 5. 实现与验收范围

允许新增独立的 v2 schema、最大 payload 证明、旧语义门适配、纯 fixture 预执行入口、测试和断网
Docker profile。不得修改 M1-2、M3-3 的冻结协议、release、执行模块、原始响应、账本、报告或裁决。

工程门至少证明：

1. 可构造的最大合法响应仍小于 4,096 bytes，并小于 6,000 token 的保守字节上界；
2. 角色/候选错误、超长、超数、非 ASCII、结论与严重度不一致、错误 disposition 均 schema FAIL；
3. 修改公式、不同 DSL、业绩/准入声称和模糊替代建议均在语义层 FAIL；
4. 预执行不读取 `.env`、真实候选、发现指标或封存结果，provider 调用为 0；
5. 断网 Docker 与宿主得到同一规范报告和哈希；全仓测试、Ruff、compileall、依赖与 diff-check 通过。

全部通过只允许裁定 `GO_COMPACT_REVIEW_CONTRACT_V2_ENGINEERING_ONLY`。未来任何真实因子审查仍须
建立新的结果前候选协议、不可变 live release 和用户明确调用/费用授权；本目标不授权 M1/M3 重启、
验证、G1、模型、回测、信号或生产。

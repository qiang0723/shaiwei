# TS-v5-R1 LLM 响应合同恢复协议

日期：2026-08-13（UTC+8）

状态：`FROZEN_ENGINEERING_ONLY_NO_LIVE_AUTHORITY`

## 1. 结果目标

修复 TS-v5 首批“思考预算耗尽、最终 JSON 为空”的接口合同问题，使未来独立 release 能在不放宽
候选 Schema、不提高单响应 token 上限的前提下，明确区分完整 JSON、截断、空内容和未知结束原因。
本节点只交付离线工程门；不调用 DeepSeek、不读取密钥、不进入参数搜索、回测、模拟仓、Web或生产。

## 2. 权威根因

首批不可变证据为 12/12 `finish_reason=length`、12/12 `completion_tokens=1800`、12/12 最终
`content` 为空且 `reasoning_content` 非空。DeepSeek 官方文档说明思考内容与最终内容共同受
`max_tokens` 约束，`length` 表示生成超过上限或上下文限制而被截断；JSON Output 文档也要求合理
设置上限并披露空 content 的已知可能性。因此不能把 `length` 改判为成功，也不能把思考正文当候选。

官方依据：

- <https://api-docs.deepseek.com/guides/thinking_mode>
- <https://api-docs.deepseek.com/api/create-chat-completion/>
- <https://api-docs.deepseek.com/guides/json_mode/>

## 3. 单变量恢复设计

未来 v2 请求画像只改变输出模式：显式 `thinking.type=disabled` 并移除 `reasoning_effort`；继续使用
`response_format=json_object`、`max_tokens=1800`、无工具、非流式，以及完全相同的候选 Schema、
六机制、产品约束和发送边界。这样把固定输出预算留给最终 JSON，且不通过扩大预算掩盖合同问题。

终态只接受 `stop + 非空 content + JSON object + 严格候选 Schema`。`length` 永久失败；空内容、
截断、非法 JSON、未知结束原因使用不同错误码。`reasoning_content` 只作不可变审计证据，永不进入候选。

## 4. 架构与兼容

响应画像和终态裁决放入独立纯领域模块；旧 `build_request` 默认行为、首批 release、报告、账本和原始
证据字节不变。未来 live release 必须显式选择 v2，禁止静默切换。新增生产文件以 200 行以内为目标，
不得扩大 `deepseek_client.py` 热点职责，也不复制传输、计费或候选验证。

## 5. 验收与停止点

用合成 fixture 覆盖 `stop/length/空内容/非法 JSON/未知原因`，并用首批 12 份项目内不可变 envelope
只读复核根因计数；验证请求无证券、行情、持仓、收益、路径或秘密。通过全仓测试、架构棘轮、Ruff、
compileall、依赖和脱敏检查后，只能裁定 `GO_RESPONSE_CONTRACT_ENGINEERING_ONLY`。

完成后仍停在新一批执行之前。任何 DeepSeek 调用、费用、响应数量或 live release 均需新的精确 scope
与用户批准，不能复用首批授权或未使用预算。

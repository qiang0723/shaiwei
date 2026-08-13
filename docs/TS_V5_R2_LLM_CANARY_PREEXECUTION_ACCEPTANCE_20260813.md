# TS-v5-R2 四响应合同金丝雀预执行验收

日期：2026-08-13（UTC+8）

权威裁决：`GO_PREEXECUTION_ONLY`

## 冻结范围

- scope先行提交：`89da7a5`；scope SHA-256：
  `e2d7218fc77e918ce3f389263290be6fc5fb15d274ec7affcf75d94e48e1a8ef`。
- 恰好4个独立席位：波动自适应回调、周结构分位、突破回踩、均线恢复；无反方改版、无候选递补、
  无第五次调用。每份完成响应都计数，只有尚无已知完成响应时允许既有传输层有界恢复。
- v2画像固定为`thinking=disabled`、省略`reasoning_effort`、`json_object`、1800 tokens、无工具、
  非流式。原候选Schema、提示、产品约束、六机制总目录和发送边界不变。
- 只有`stop + 非空JSON object + 严格Schema`有效；`length`、空content、非法JSON、未知原因和重复均
  失败关闭。四份合法唯一候选为0则停止，至少1份也只表示合同金丝雀可用，不表示策略有效。

## 费用与数据边界

四席位按每份最多16000输入、1800输出和全cache miss计算，最坏费用0.034104美元；单批硬熔断
0.10美元。TS-v5总额度5美元不扩大本批，也不自动授权任何后续批次。

请求只含冻结提示、严格Schema、产品/复杂度约束、公开方法摘要、匿名失败记忆和席位身份。禁止证券、
行情、持仓、订单、信号、收益、封存结果、本地路径、凭据、首批原始响应和reasoning内容。

## 工程与验证

- 实现提交：`5cb8ff81cbbe80a7d3950bf1917e51b06953c2d4`。新增生产模块
  `v5_canary.py`为157行，只负责固定scope读取和请求束预检；复用v2画像、候选合同和既有安全扫描，
  未复制live runner、传输、计费、账本或候选验证，也未修改808行DeepSeek传输热点。
- 请求数4、机制顺序、独立模式、ordinal 1—4、v2画像和4个唯一请求哈希全部PASS；请求束SHA-256：
  `0068357f586749d97d40660b3bd737f31afedafc3f7b6671c00f4641c4fe489b`。
- 专项12项、全仓1175项、架构13项、Ruff、compileall、pip check和diff-check通过。
- 受控预检镜像：`sha256:510c0a996e482ba9aa29081117f4a1099e93c75e24a9d3b5a4c9a903d86819de`。
  镜像绑定正确完整Git身份，在`network=none`、只读根、非root、无secret条件下输出同一请求束并
  `GO_PREEXECUTION_ONLY`；scheduler保持原容器、原镜像健康。

## 失败留痕与停止点

第一次构建时手工传入的完整Git哈希有1字符错误；该镜像未运行、未进入release、未读取secret或联网，
随后以`git rev-parse HEAD`真身重新构建并通过。错误构建不能作为后续执行证据。

当前DeepSeek调用、secret读取和费用均为0，未读取行情/效果，未参数搜索、回测、模拟仓、Web或生产。
本验收不创建live release，也不授权API。只有用户明确批准上述scope SHA-256、恰好4响应和0.10美元
边界后，才能另立绑定实现、请求束和新镜像的执行release；未批准前必须停止。

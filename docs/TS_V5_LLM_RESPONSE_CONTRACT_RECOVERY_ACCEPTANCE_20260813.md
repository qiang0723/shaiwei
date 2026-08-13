# TS-v5-R1 LLM 响应合同恢复验收

日期：2026-08-13（UTC+8）

权威裁决：`GO_RESPONSE_CONTRACT_ENGINEERING_ONLY`

## 结果

- 首批12份项目内不可变响应 envelope 只读复核为：12/12 `finish_reason=length`、12/12
  `completion_tokens=1800`、12/12最终 `content` 为空、12/12 `reasoning_content` 非空。
- 根因分类为 `OUTPUT_BUDGET_EXHAUSTED_IN_REASONING=12`。这不是候选 Schema 失败，也不能把思考
  正文当候选；首批权威 `STOP_NO_VALID_CANDIDATES` 和所有旧证据保持不变。
- DeepSeek官方规范说明思考内容与最终内容同受`max_tokens`限制，`length`表示输出被截断；JSON Output
  还要求防止JSON被中途截断并披露空content的已知可能性。依据：
  [Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode)、
  [Chat Completion](https://api-docs.deepseek.com/api/create-chat-completion/)、
  [JSON Output](https://api-docs.deepseek.com/guides/json_mode/)。

## 修复边界

- 机器合同 SHA-256：`c254b41e9ab8f37254944cf9f759ae55c77c69f15119e1e87d296e3a0d091a02`。
- 协议先行提交：`815212dfe10b6bcf4173c7ce3fb03fd624c44834`；实现提交：
  `97aba0dd2bd9f38c03e8ac20ecbe4460b19b9889`。
- v2只显式设置`thinking.type=disabled`并移除`reasoning_effort`。`response_format=json_object`、
  `max_tokens=1800`、无工具、非流式、候选Schema、提示、六机制、产品约束和发送边界全部不变。
- 终态仍只接受`stop + 非空content + JSON object + 严格候选Schema`；`length`、空content、非法JSON
  和未知结束原因分别失败关闭。旧v1请求默认和首批release不变，未来release必须显式选择v2。

## 架构与验证

- 新职责拆为119行响应合同模块和124行离线根因审计模块；既有证据模块只增加6行薄接入，未修改
  808行DeepSeek传输热点，未复制传输、计费或候选验证。
- 专项18项、全仓1172项、架构13项、Ruff、compileall、pip check和diff-check全部通过。
- 离线审计报告 SHA-256：`3b6f8420c619a21bfd6a78a0785edb6e0065573212fb7812c7e433da326bf806`；
  两次复跑哈希一致。
- 独立恢复镜像：`sha256:0bd9e9b45f531a26a1ffbaed9d85c6da9c565b43b63ad81702f54b15121d09d2`。
  镜像在`network=none`、只读根、非root、无secret、仅只读挂载12份响应envelope条件下复核PASS。

## 权限与下一节点

本节点没有调用DeepSeek、没有读取secret、行情、证券、持仓、收益或封存结果；没有参数搜索、回测、
模拟仓、Web或生产变更。工程GO不构成候选GO、策略有效或新一批执行授权。

若继续，须另立TS-v5-R2小批live scope，精确冻结响应数、费用、v2合同与停止条件并再次取得用户批准；
不得复用首批approval、不得用5美元总额度自动补发，也不得在新批前进入参数搜索或回测。

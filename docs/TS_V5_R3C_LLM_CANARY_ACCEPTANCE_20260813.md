# TS-v5-R3C 六机制合同金丝雀终版验收

日期：2026-08-13（UTC+8）

权威裁决：`STOP_NO_VALID_CANDIDATES`

## 结论先行

用户精确批准的R3C唯一真实批次已经完成：六种机制各取得1份独立完成响应，共6/6份；没有递补、
第7次调用、重试或计费不确定性，实际费用`0.012032535 USD`，低于`0.15 USD`硬上限。

六份响应均为HTTP 200、`finish_reason=stop`且可解析为JSON，但六份均未通过冻结的机制专属proposal
Schema或确定性编译合同，统一记录为`PROPOSAL_SCHEMA_OR_COMPILER_INVALID`，有效唯一候选为0。因此
本批只能停止，不能人工修补、递补或进入参数搜索/回测。该结论只评价LLM到冻结候选合同的投影能力，
不评价六种机制的收益或TS策略有效性；`candidate_effectiveness=NOT_EVALUATED`，生产授权为`none`。

## 结果前身份与授权

- 唯一批准scope SHA-256：
  `234621cf0280fceca82a8e5f82d6966b27979fde761d68b2508346a2ebd953ae`；恰好6个独立完成响应，
  六机制各1个，串行，无递补/第7次调用，费用硬上限0.15美元。
- execution release提交`ad778470fff393919e90c55b2ab0de8ea8d1b06f`在调用前推送，release
  SHA-256为`849af5f4d761fa323a2bc63123879e0696b14733ca3c03adbf8c881afb64d0da`。
- 终版镜像为
  `sha256:0c07a2eb7142c6e9f4fed8ab7b85b695aac561245325b8b0417ec61efe38b92a`；镜像内Git HEAD
  `9ba7b52bf005dd3e7d0f1c48f398f884a74c9caf`，代码快照
  `227c299691427566080a2204fbb284cdbf4687a6a655bb8ec93771deb2c1695b`。
- 请求束SHA-256：
  `f10e5e41805b711a96001e9e433ccaeb7e86d334cb3bc6b63f7998274449b6ff`。release推送后，断网、
  无密钥、只读根预检PASS：两个R3C专属账本均只有表头，provider调用0、secret读取为false。

## 唯一真实批次

- 机制顺序严格为：波动自适应回调、周结构分位、突破回踩、均线恢复、收缩扩张、相对强度回调；
  attempt序号连续为1—6，transport事件严格为6个`STARTED`和6个`COMPLETED`，每个席位sequence均为1。
- 六个完成事件均为HTTP 200，`FAILED=0`、`BILLING_UNCERTAIN=0`；工具侧终端流先于短命容器结束，
  因此只读核验既有容器与专属账本，没有启动第二容器或复用授权。
- 输入token共19,211，cache hit 0，输出token共4,225；按冻结价格独立重算费用
  `0.012032535 USD`。返回模型字段六份均为`deepseek-v4-pro`。
- 六份content均通过JSON解析；严格proposal Schema/编译分类均FAIL，失败类均为
  `PROPOSAL_SCHEMA_OR_COMPILER_INVALID`。原始回答保存在Git忽略的项目内不可变产物中，未人工改写，
  未把reasoning当候选。

## 独立审计、幂等与隔离

- attempt ledger 6行、transport ledger 12行；SHA-256分别为
  `18d206fe9e1c75e62619c47fb7e1f93d55857806b27b29861a7e240522bee14e`、
  `0da6ea6c23833577fcc4a03e3a7077711beea5e7df23dc022454b1e5f67c9446`。
- 终版报告SHA-256：`c5292c3a1c6b9021ff00222c9fbbdb8c959e1cd5f5b5065757b987ccfc6b47cf`；
  断网独立审计SHA-256：`af532860ece5061d3628307b8b605a4da33d5c9b34e01f86166d11d7d79db597`。
  审计逐请求重建、逐文件哈希、逐响应重分类、费用与权威门复算共11项全部PASS。
- 项目内本批26个文件的排序哈希清单摘要为
  `640493fefdf833537e0039051538e9986d0b357668cf9afc220ec6ccd7d7021b`。
- 断网、无密钥、全部输入只读复跑返回`idempotent_reuse=true`、
  `external_api_calls_this_run=0`；release、两账本、主报告和审计报告哈希前后完全不变。
- 只从项目内`.env`向短命容器注入唯一`DEEPSEEK_API_KEY`，密钥未输出、未写入账本或Git。未发送
  行情、证券清单、收益、持仓或其他凭据；未运行参数搜索、模型、回测、模拟仓、Web或生产。
- scheduler保持原容器`183b8c6c5edd`、原镜像，连续运行且healthy，未重启。

## 停止点

本scope已经消费完毕并永久关闭，不得递补、第7次调用或用未消费预算扩张本批。下一项合理工作是另立
零API、零行情的R3D离线匿名失败诊断，区分proposal Schema字段错误、投影选择越界和确定性编译失败，
同时保持冻结validator不变。任何新的DeepSeek调用仍须新scope、结果前release和用户明确批准；效果、
回测、模拟仓、Web与生产继续禁止。

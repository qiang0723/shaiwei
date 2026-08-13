# TS-v5-R2 四响应合同金丝雀终版验收

日期：2026-08-13（UTC+8）

权威裁决：`STOP_NO_VALID_CANDIDATES`

## 执行身份与边界

- 用户批准 scope SHA-256：
  `e2d7218fc77e918ce3f389263290be6fc5fb15d274ec7affcf75d94e48e1a8ef`；唯一允许4份独立完成响应、
  无反方改版、无递补、无第五次调用，单批硬上限0.10美元。
- 实现提交`d077ca4`已先行推送；执行镜像
  `sha256:95189574de1fc6c0105840d6c55652c46f5810349271f46f401484e3102bcd59`，内嵌代码快照
  `4724bc2593911435594448078e76c78e69d45f45800af04640339bc7da1d5d5c`。
- execution release SHA-256：
  `1ae0a24e6ca221cf71c7cf42318cbd643bcf07281922f485c39f30cf476f036b`。首次release提交中
  transport SHA手工录入错误，发生在零调用/零密钥阶段；错误提交永久保留，随后由独立提交`59a1cb1`
  纠正并推送，终版release通过机器加载。
- 无密钥、`network=none`、只读根预检PASS：专用账本均只有表头，请求束SHA-256
  `0068357f586749d97d40660b3bd737f31afedafc3f7b6671c00f4641c4fe489b`，provider调用0。

## 唯一真实批次

- 串行取得恰好4/4份完成响应：波动自适应回调、周结构分位、突破回踩、均线恢复；每席位只有一次
  HTTP 200完成事件，外部调用总数4，没有重试、递补、第五次调用或计费不确定性。
- 输入token共9,067，输出token共2,999，其中cache hit 512；按冻结价格重算费用
  `0.006332411 USD`，远低于0.10美元硬上限。
- 四份content均为可解析JSON，但严格候选Schema均FAIL：主要涉及取消规则/参数槽越界、经济解释超长、
  required feature枚举不合法和全局候选约束。reasoning未作为候选，也未发送首批原始响应或reasoning。
- 因有效唯一候选为0，权威门为`STOP_NO_VALID_CANDIDATES`；这只说明当前响应合同仍未可靠地产生合规
  TS候选，不评价策略收益，也不等于四种机制无效。不得递补或使用无效内容进入参数搜索/回测。

## 证据、幂等与隔离

- attempt ledger 4行、transport ledger 8行；SHA-256分别为
  `daccc4d9868ea368f64abb450ed8e47ffbe8b579a44cef96e8624d5d51e35ea7`、
  `1959d52dd00512be378aca68fc4dbbfa93a863e25be7a6b27eb5261ad738c983`。
- 终版报告SHA-256：`81a49b252174ea6ba4579e7e48361060099f43377adea4406d0fcca03230d277`；
  断网独立审计SHA-256：`24440b4cc0072ba62b6c569a71abc43f105041a4bbbd19f55254d6029edeb630`，
  审计逐请求重建、逐产物哈希、逐响应重分类和费用复算全部PASS。
- 断网空密钥复跑返回`idempotent_reuse=true / external_api_calls_this_run=0`；release、两账本、主报告、
  审计报告四类哈希均不变。
- 未发送或读取证券、行情、持仓、收益或封存效果；未运行参数搜索、模型、回测、模拟仓、Web或生产。
  scheduler保持原容器`183b8c6c5edd`、原镜像并健康，未重启。

## 停止点

本scope已消费完毕并永久关闭。后续若继续，须先对这4份Schema错误做离线匿名分类，判断是提示合同、
Schema可表达性还是模型服从性问题；任何新调用必须另立新scope和用户批准，不得复用本批余额或补发
第五份。当前`candidate_effectiveness=NOT_EVALUATED / production_authorization=none`。

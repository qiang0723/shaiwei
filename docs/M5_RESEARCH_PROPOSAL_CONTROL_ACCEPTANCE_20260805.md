# M5-1 多股票池研究提案控制面验收

日期：2026-08-05（UTC+8）
裁决：`GO_M5_PROPOSAL_ONLY_CONTROL_PLANE`

## 1. 结论

M5-1 已完成非权威研究提案的本机控制面、Web 工作台和隔离 Docker 服务。用户现在可以创建提案、
提交人工复核或取消；系统不能冻结、批准、发布、排队或运行研究，也不能调用 DeepSeek、读取行情/
标签/封存效果、创建前瞻账户或接入生产。

本裁决只证明“提案意图可被安全、可审计地持久化”。它不是研究协议冻结，不是策略有效性结论，
不是研究执行授权，也不改变中证800仍为唯一生产主策略的事实。

## 2. 冻结身份

- 实现提交：`d8db2046ff81c06cfefa81aa179918b5cac2e8b8`
- M5-1 v2配置：`4113323415bcc512a6eeae6e3f00f823a114d63b604fdb16c85fe4aa94cd94c5`
- 基础协议：`44a3792edc4ae37ca7e92483205257e1dd0d81cdc97664e8a7f91607a14fdbd3`
- 口径补正协议：`1a65fb65b4afa4fd647f0e31ee56e55fa721bcd9b8c016cc84f29bd07fa68662`
- ADR：`007a7e899ca70ad7f7cd96a5590e2f6bfb9bae580d10b424dff71a0112d6cec5`
- 架构宪法：`d312dd6389dde45528e8360bbb213456bde8c2522f786892a599421821e1804e`

首份v1配置与协议永久保留，但v1配置已标记`SUPERSEDED_BEFORE_IMPLEMENTATION`；运行时只接受v2，
并在启动和每次请求前核对全部冻结输入及架构宪法身份。

## 3. 权限与对象边界

- 唯一对象：`NON_AUTHORITATIVE_PROPOSAL`。
- 唯一状态：`DRAFT`、`REVIEW_REQUIRED`、`CANCELLED`。
- 唯一写动作：create、submit-review、cancel。
- 五个可选股票池、三个阻断股票池、五个研究家族及primary/sensitivity multiplicity均由服务端
  冻结真身派生，前端不能另造口径。
- 确定性提案固定provider calls/response target/budget为`0/0/$0`；LLM提案只登记调用上限、完成
  目标和不超过`$1`的预算意向，不产生外部调用或费用授权。
- create只增加一条“计划中的研究尝试上限”登记；当前真实研究尝试增量、provider调用、效果读取、
  模型训练、回测和生产动作均为0。

冻结、批准、发布、排队、运行、重试、Worker、outbox、attempt、artifact或研究ledger端点均不存在。
M5-2不能从`REVIEW_REQUIRED`自动触发，必须另立ADR、结果前协议和用户授权。

## 4. 数据完整性与失败关闭

SQLite v1只包含`proposals`、`proposal_events`和`idempotency_receipts`三表，使用WAL、FULL同步、外键、
busy timeout和`BEGIN IMMEDIATE`。Schema fingerprint覆盖表、列、外键、索引、触发器、视图及SQL。

每次health、读取和写入均执行全库双向重建：

1. 由严格请求与当前冻结authority独立重建canonical proposal；
2. 重放唯一状态机和哈希事件链；
3. 逐proposal核对事件到回执；
4. 再枚举全库回执，反向唯一定位proposal/event，并独立重建历史响应；
5. 精确核对actor、route、幂等键、request SHA、command ID、状态码、时间和逐字节响应。

孤儿、缺失、重复、错配、非法路由、伪响应或离线篡改均返回`CONTROL_NOT_READY`。写事务在取得锁后
先验一次，写入回执后、COMMIT前再验一次；错误正文、状态码或时间会使三表整笔回滚。command ID只能
是`m5cmd-<sha256(Idempotency-Key)>`，浏览器不能把任意文本或秘密写入该字段。

没有静默修改冻结的schema v1；全库双向语义扫描用于补足反向关联约束并保持既有空库兼容。

## 5. Web与Docker隔离

- 浏览器只访问五条冻结proposal路由；Origin必须精确为`http://127.0.0.1:8080`。
- 30分钟HttpOnly/SameSite=strict会话、CSRF、16 KiB请求上限、12次/分钟写限流和稳定幂等恢复已启用。
- 浏览器Authorization和actor头被丢弃；Web代理使用内部随机secret和固定actor hash访问control。
- `research-control`无宿主端口，只连接`control-internal`内部网络；根文件系统只读、非root、capabilities
  全部移除、`no-new-privileges`开启。
- 唯一RW挂载为`data/control/m5/runtime`到控制数据库目录；协议、配置、证据和secret均只读挂载，
  secret来源与RW目录不重叠。服务不挂载`.env`、raw、标签、结果、生产ledger或Docker socket。
- Web UI仍只绑定`127.0.0.1:8080`；页面常驻显示“已提交人工复核；未冻结、未排队、未运行”。

最终控制镜像为`sha256:95c00fb5ff770cfeb1ee35957a4ec88024b061baf46fe9120c64c18943bc22e2`，
Web镜像为`sha256:7e2dc45b3c32ed5cd6f64e1b17789d279c9dd6dc4f3e79eeed3fa1a611bcf7cb`；
`web-query`、`research-control`和`web-ui`均healthy。真实页面`/strategy-factory`返回200，真实proposal
目录返回`count=0`。

运行时权威数据库交付时为proposals/events/receipts=`0/0/0`。预验收曾在旧挂载位置生成一个空的
provisional数据库，仍为`0/0/0`、未使用、未跟踪且不具权威性；未删除它，以保留非破坏性审计边界。

## 6. 验证证据

- 第三方独立审计曾因孤儿回执和首次写入回执未提交前重建给出`NO-GO`；完成全库反向扫描、独立历史
  响应重建和回滚对抗测试后，第四轮最终审计为`GO`。
- Python专项与架构：69 PASS。
- 全仓测试：655 PASS；仅1条既有Starlette/httpx弃用提示。
- 架构宪法：6 PASS；新增生产模块均不超过400行，新增函数不超过冻结复杂度边界。
- 前端单元：32 PASS；TypeScript与production build PASS。
- 五视口fixture：69 PASS / 11 intentional skip（1440/1024/768/390/320）。
- 真实部署：14 PASS，覆盖桌面/移动、CSP、同源零外联、axe、回流、证据口径与性能预算。
- Ruff、compileall、pip check、Compose config、`git diff --check`和新增差异敏感信息扫描均PASS。

生产scheduler施工前后保持同一容器
`183b8c6c5eddac951d9d9b3cfa58c0d38e351d5b94ee1b1d52b9b8059c23dd3b`、同一镜像
`sha256:722f63de15932cb2698e82db7c0140f02921f27f126e1c0235ca62e0a1213b76`、同一创建时间
`2026-08-03T09:39:34.800579793Z`，最终仍为healthy。

## 7. 剩余风险与下一合法动作

- 全库重建为O(proposal + event + receipt)，适合当前本机低频提案量；未来规模显著增长时可另立可信
  checkpoint设计，但不得降低失败关闭语义。
- 任一证据污染会按设计停止整个控制面；当前不提供在线修复接口，只能另立受控离线恢复流程。
- 当前不自动创建任何提案。下一步应由用户在Web明确创建所需池/家族的提案并提交人工复核；是否进入
  M5-2冻结与执行，必须基于具体提案另行裁决。

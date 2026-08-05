# M5-1 多股票池研究提案控制面协议

> 协议 ID：`m5-research-proposal-control-v1`
>
> 冻结时间：2026-08-05T17:18:00+08:00
>
> 权威范围：本机非权威研究提案的创建、提交人工复核与取消

## 1. 裁决

M5-1 建设独立 `research-control`，把 M5-0 浏览器临时草案升级为可持久化、可幂等、可审计操作的
“研究意图提案”。提案不是研究任务、不是冻结协议、不是批准，也不形成研究尝试 N。

唯一允许终态为 `GO_M5_PROPOSAL_ONLY_CONTROL_PLANE`。即使通过，以下授权仍全部为 false/none：协议
冻结、执行 release、Worker 派发、DeepSeek/外部调用、数据采集、真实行情/标签/封存效果读取、模型
训练、回测、模拟仓、前瞻、生产、scheduler 或 Git/Docker 写操作。

## 2. 冻结输入

- 代码起点：`f9e7a39f595517bd853239987b87f4ea38b8479a`；
- M5 v2 快照 ID：`fae1c53c410213e58bd10d938a5854afdd2cce1e3f4c9acd7affb73624c94a6b`；
- M5 v2 快照文件 SHA-256：
  `36f750639f5643a67ac0c2f9eb7505949542a9404edad9ff3d7fb970f7bd6f2b`；
- M5 authority addendum SHA-256：
  `b2ff8baedf878992ebadf2d79f8e38691f8326501e5a9432d821a785c4a6fee6`；
- M1 股票池注册表 SHA-256：
  `964631891a69b4ed2a6c697066a89300910b620d3c71acdf65803248900c4274`；
- 架构宪法 SHA-256：`d312dd6389dde45528e8360bbb213456bde8c2522f786892a599421821e1804e`；
- ADR：`docs/ADR_0001_M5_PROPOSAL_CONTROL_PLANE.md`；
- 三份 M5 专项设计只作设计输入，冲突时以本协议和 ADR 为准。

## 3. Proposal 合同

### 3.1 用户可选择字段

- 股票池：1—3 个、去重、有序，必须来自 v2 快照中五个 `READY` 池；另选唯一 `home_universe_id`，
  其余为 transfer 池；
- 研究家族：资金流、静态基本面、动态基本面、量价机制、残差与特异风险之一；
- 注册假设/证伪规则：只能选择该家族的服务器登记枚举，不接收自由公式、Python、Shell、SQL、路径、
  URL、容器、环境变量或 provider payload；
- 生成方式：`DETERMINISTIC_CODE` 或 `LLM_BOUNDED_DSL`，必须在家族白名单内；
- 生成尝试上限：只允许 8/12/24；候选上限不超过尝试上限；provider 调用意向不超过尝试上限；
- provider 费用意向：精确十进制、0—1 USD；它只是未来预算申请意向，不是授权或预留；
- 有效期：1—14 天；到期后不能 submit，只能 cancel 或重新创建新提案。

### 3.2 服务器派生与固定字段

- 四维身份：精确 universe 版本；factor 为登记家族与
  `TO_BE_GENERATED_WITHIN_BOUNDED_BATCH`；model 与 portfolio 均为 `NONE_NOT_AUTHORIZED`；
- `evaluation_unit_cap = candidate_cap × universe_count`；
- 相关研究历史尝试基线由冻结家族注册表给出，服务计算 planned/after，不能由浏览器重置；
- `evidence_tier=PROPOSAL_ONLY`、`authority_status=NON_AUTHORITATIVE_PROPOSAL`、
  `authoritative_outcome=NOT_EVALUATED`、`production_authorization=none`；
- `stop_on_terminal=true`、`no_budget_carryover=true`；
- 所有第1节未授权能力必须在请求、存储和响应中显式为 false/none，不靠字段缺失表达。

未知字段、重复/阻断池、`.BJ`、不匹配家族/假设/生成方式、超上限、非有限费用、任一授权 true、
过期提交或来源快照漂移全部 422/409 且零写入。

## 4. 状态、事件与幂等

状态只允许：

```text
DRAFT --SUBMITTED_FOR_REVIEW--> REVIEW_REQUIRED
DRAFT --CANCELLED_BY_PROPOSER--> CANCELLED
REVIEW_REQUIRED --CANCELLED_BY_PROPOSER--> CANCELLED
```

create 生成不可编辑的 canonical proposal。需要修改时取消旧提案并创建新提案；M5-1 不提供 PATCH、
DELETE、withdraw-to-draft 或 copy 命令，避免提前建设版本编辑器。

每个写请求必须有 16—128 字符 `Idempotency-Key`；submit/cancel 还必须携带 `command_id`、
`expected_event_seq`、proposal request SHA 和受限 reason code。同 actor+route+key：同请求返回原始响应，
不新增事件；异请求返回 409。旧 seq、错误 SHA、非法状态或两个并发命令只有一个可成功，失败方零写入。

SQLite schema v1 只包含 proposals、proposal_events 和 idempotency_receipts：canonical proposal 与事件
只 INSERT，不 UPDATE/DELETE；只有 proposals 的当前状态/seq 是事务投影缓存。事件含 from/to、actor
hash、command/request/payload/prev/event SHA。数据库启用 foreign keys、WAL、busy timeout、
`BEGIN IMMEDIATE` 和启动 `quick_check`；未知 schema 或损坏失败关闭。

M5-1 没有外部副作用，SQLite 事务是唯一操作态真身，因此本阶段不建设 outbox、研究 ledger、任务
队列、租约、attempt、artifact、approval 或 audit 表。响应丢失通过幂等回执精确重放；进程重启后
状态、事件和回执必须一致。

## 5. API、会话与错误

独立内部 API 统一为：

- `GET /control/v1/research/proposals`；
- `GET /control/v1/research/proposals/{proposal_id}`；
- `POST /control/v1/research/proposals`；
- `POST /control/v1/research/proposals/{proposal_id}/commands/submit-review`；
- `POST /control/v1/research/proposals/{proposal_id}/commands/cancel`。

冻结、批准、release、enqueue、run、retry、delete 等端点物理不存在。create 返回 201，命令事务完成后
返回 200；不使用可能被 UI 误解为“随后会自动执行”的 202。响应必须包含服务器给出的
`available_actions`，前端不得自行推导。

固定错误码：`SESSION_REQUIRED`、`ORIGIN_REJECTED`、`CSRF_REJECTED`、`ROLE_NOT_ALLOWED`、
`PROPOSAL_NOT_FOUND`、`IDEMPOTENCY_CONFLICT`、`STATE_CONFLICT`、`CONTRACT_INVALID`、
`UNIVERSE_NOT_ELIGIBLE`、`RATE_LIMITED`、`CONTROL_NOT_READY`。主视图显示中文原因与合法动作，内部
ID/hash只进入技术详情。

浏览器只通过本机 `web-ui` 精确代理。代理要求精确 loopback Origin、HttpOnly/SameSite严格短会话、
CSRF header、16 KiB请求上限、12次写/分钟；通过仅 web-ui/control 持有的项目内 Docker secret 调用
内部服务。control 无宿主端口、无外网；本机稳定 actor 只表示逻辑 `RESEARCH_PROPOSER`，不冒充多人
认证。MultiCa 和任何远程入口继续禁止。

## 6. Docker与文件边界

- 独立 `Dockerfile.control` / `shaiwei:research-control-v1` / `research-control` service；
- 非 root、只读根、`cap_drop: ALL`、`no-new-privileges`、tmpfs、低 CPU/内存/PID；
- 唯一读写挂载为 `data/control/m5`，只读挂载仅为本协议/配置和精确绑定的 M5 v2 快照；不挂
  `.env`、raw、研究结果、ledger、logs、Docker socket、scheduler 或生产数据；
- `web-query` 不加入 control 网络、不读取数据库、不增加 POST；
- 本地 proxy token 位于 Git 忽略的 `data/control/m5/proxy_token`，不输出、不入日志或镜像。

## 7. Web最小范围

保留策略工厂研究地图；提案区默认空选择，不再默认科创50/量价。只提供：本地编辑预览、保存提案、
提交人工复核、取消，以及提案目录/详情/事件。能力条常驻显示：提案写入允许；协议冻结、执行、外部
调用、效果读取、前瞻与生产均未授权。

提交后的明确文案是“已提交人工复核；未冻结、未排队、未运行”。不得出现任务进度、队列位置、运行
动画、“一键挖掘/最佳策略”或把可建提案解释成策略有效。被阻断的三个池及既有 REJECT/STOP/正式库0
继续在页面保留。

## 8. 故障、安全与验收门

必须验证：

1. 合法 create/submit/cancel 事件与状态；终态不可恢复；
2. 同幂等键重放、异请求冲突、并发旧 seq、响应丢失和重启恢复；
3. 提交前异常全回滚；提交后响应丢失不重复事件；DB busy/损坏/未知版本失败关闭；
4. 阻断池、`.BJ`、未知字段、任意代码/路径/URL、secret形态、授权 true、预算/次数越界零写入；
5. Origin、CSRF、会话、内部 token、限流、body上限和无直接宿主端口；
6. 所有 freeze/release/enqueue/run/delete 路由不存在，P3 POST仍405；
7. 刷新后从 control 真身恢复；UI不得乐观伪造状态；五视口、键盘、焦点、错误摘要和 axe AA 通过；
8. 零 DeepSeek/Tushare/飞书/外网、零研究结果读取、零任务/Worker/approval、零生产变化；
9. 架构门、全仓、前端、真实部署、Ruff、compileall、pip、Compose、脱敏和scheduler隔离全部通过。

通过后停止在 `REVIEW_REQUIRED`。M5-2 必须另立协议和授权，不能由提案、剩余预算或本次 GO 自动
派生。

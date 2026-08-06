# M5-2B-R2 年报行域恢复后真实谱系运行验收

- 验收时间：2026-08-06（UTC+8）
- 批准的 release scope：
  `f7904929991e90a3d4c220cbdaf88818953694803625c41eb3634731e376e2d5`
- 运行终态：`BLOCKED_DATA / LINEAGE_NO_GO_ONLY`
- 谱系裁决：`NO_GO_M5_2_SOURCE_LINEAGE_PREEXECUTION`
- 策略结论：`NOT_EVALUATED`
- 生产授权：`none`

## 1. 结论

用户明确批准上述完整 scope 运行恰好一次断网真实 `LINEAGE_FEASIBILITY`，且不授权外网、权威证据
采集、PIT、候选、效果、模型、回测或生产。新 reader 修复后，唯一 runner 正常读取冻结的年报/type
1/5 行域并 write-once 封存结果；独立 auditor 随后从同一输入重新计算并 PASS。

23 个既有来源身份冲突组全部只能归类为 `FORWARD_ONLY_OBSERVED_VERSION`，可回填历史的
`PIT_VERSION_CHAIN_RESOLVED=0`。因此权威谱系门为 `NO_GO_M5_2_SOURCE_LINEAGE_PREEXECUTION`，新 case
进入 `BLOCKED_DATA`。这说明现有本地批次缺少证明历史修订何时生效的权威版本链，不表示八个动态
基本面候选无效，也不是策略 `REJECT`；候选、效果和模型从未运行。

## 2. 执行前身份与批准

- 当前 `HEAD=origin/main=f345295050f5863aaa5aa15f0433c7de9cb72420`；release 绑定的实现提交
  `213d0a103c9f22b327313bdc568c48eea0a9fff8` 已先推送且仍是当前 HEAD 的祖先。
- release scope 物理 SHA-256：
  `9343fa9cfaa8855739b700fbf244d6597f1f10f070c780f8d973ce11cfdd2933`。
- 输入清单逻辑/物理 SHA-256：
  `bda3f6b86a43a13438acc78bfaf14bce772c9b4d94d221272765ba6f6735d0df` /
  `1e4ea075065d1e5c0d58f40593aa24ce25443b8c696f7032ed04eb7aef795ebf`。
- 镜像：`sha256:5dd12995e4a1dbf8aead28d91aca6a040af7da8c2251f783ff657a7a34212d1a`，
  `linux/arm64`，与 release 一致。
- 提案仍为 `REVIEW_REQUIRED` / event 2，head event SHA-256 为
  `2d6ff1aace167fa6299414773e031adab9ceac09eadd0b789fbb170c41570f5f`，未过
  `2026-08-12T10:48:16+00:00` 到期时点。
- 四个新内容寻址路径执行前均不存在；没有复用半成品或旧 approval。

新 approval envelope 的规范逻辑 SHA-256 为
`75d648294a0eb2d8d805d57e068a042e7e8a86b1d6d43dc1a03643a343ba70fa`，物理 SHA-256 为
`473aafd508091897616d80c6c67d162e5f7496b3473309f51fdf4ef15c2d1602`，绑定新 case
`8000c9e107c100cdb41edace547f5869dddda6807005c142ce2847d9433f49ff` 和 event 4
`3d93e2ad5bd27ff073b5a91222bf7f2bdc9869fb5057f47f4ff87e510874a506`。

## 3. 输入束与隔离

批准后物化 16,856 个文件：16,841 个不可变财报批次和 15 个冻结控制/证据文件；物化阶段只核验
metadata、文件大小、schema 和内容哈希，`semantic_rows_read=false`。bundle manifest 物理 SHA-256 为
`026ec51d034a93301e8d92f10345f9ebc77ae90a9759da82bdeea66ff03e5877`。

唯一 runner 与独立 auditor 均使用同一精确镜像、`network=none`、非 root、只读根、drop ALL
capabilities、no-new-privileges、128 pids 和冻结资源上限；只挂载 release 规定的 input、output、audit
与 registry 四个路径。不挂项目根、`.env`、Docker socket、标签、效果、模型或生产路径。

运行结束后没有遗留 M5 容器；生产 scheduler 仍为原容器 `183b8c6c5edd`、原镜像
`sha256:722f63de15932cb2698e82db7c0140f02921f27f126e1c0235ca62e0a1213b76`、创建时间
`2026-08-03 17:39:34 +0800`，healthy 且未重启。

## 4. 真实聚合结果

- run id：`8ffe2570e740dd84ce8d3ccfc0f75f429488d201cf0088ef54ba715cc9dd1fab`
- 身份组 / 冲突身份组：23 / 23
- 资产负债表：8 组，全部 `FORWARD_ONLY_OBSERVED_VERSION`
- 现金流量表：15 组，全部 `FORWARD_ONLY_OBSERVED_VERSION`
- 利润表：0 组
- `PIT_VERSION_CHAIN_RESOLVED=0`
- 其他 unresolved 类型均为 0；未来证据数为 0
- global lineage commitment：
  `b04ecb18bbede6211d3834d6c65b9839cfc0332625c774216238936bec1fc879`
- `semantic_rows_read=true`，仅发生在获批 runner 与独立 auditor
- provider / 外部调用：0；PIT、feature panel、候选矩阵、标签、效果、训练、回测均未执行

公开报告经过禁止字段递归扫描，不包含证券代码、公告日、报告期、report type、update flag、原值、
规范化值、请求参数或绝对路径。

## 5. 不可变产物与独立审计

runner 封存恰好三件产物，auditor 封存一件报告：

- run manifest SHA-256：
  `905c6454bc69ef9856facd7d84b50c5bd26382a2a83ce6fed69d69b2bbbcd099`
- lineage gate report SHA-256：
  `c481f53bb2e0225f15e71b61bd818f0d9486727ea2f85f71205ae45ed90a7acf`
- source lineage report 物理/规范 SHA-256：
  `dda50de513fe8969de39a9f0c3f90cccdb8545f9f02c59188cb41c58f26767ae` /
  `460be7c7cb6cbe8a46c0cf81e7367dd22c026b20c5e83f210325ae2d523d2255`
- independent audit report SHA-256：
  `e056e41a3473206ebd806e8b917b33e953210ede4b71e15c3ebdfc009ba2ba45`

auditor 不导入 runner 的主谱系构造或 commitment normalizer，重新读取同一冻结输入并逐项复算 23 组、
六类处置、commitment、verdict、产物哈希和授权边界，最终 `status=PASS`。

## 6. Registry、幂等与旧证据保护

新 registry 以旧权威 registry 的 SQLite 一致性备份初始化，旧三条 case 逻辑前缀不变，再追加新 case：

| event | seq | event SHA-256 | 状态 |
|---|---:|---|---|
| `IMPORT` | 1 | `88cf9e6e3f35f5bb3bae9dc72b2d4043c434ad1095aafc4ce6b09f5377e1f99f` | `IMPORTED` |
| `PROTOCOL_FROZEN` | 2 | `a9c04765e7ba368fd44cfed94b6d79f96d01940c81d5156a6549626aea196b99` | `PROTOCOL_FROZEN` |
| `LINEAGE_GATE_RELEASE_READY` | 3 | `bae340c2b09ab9dd7b9b06e7d5248dc5790e5563b6e340de205fdfea48c0bd98` | `LINEAGE_GATE_RELEASE_READY` |
| `LINEAGE_GATE_APPROVED` | 4 | `3d93e2ad5bd27ff073b5a91222bf7f2bdc9869fb5057f47f4ff87e510874a506` | `LINEAGE_GATE_APPROVED` |
| `LINEAGE_GATE_STARTED` | 5 | `c2d20897c43358259d40c6c0524280e25ca91b1380166ec90aa1b5f2b0c1cf0e` | `LINEAGE_GATE_RUNNING` |
| `LINEAGE_GATE_RECORDED` | 6 | `9cfc67deb0d199d969a09f08494644b18c0aed72c0ab68ade4c834f19cba38d8` | `BLOCKED_DATA` |

- 全库：4 cases、28 events、28 receipts、28 outbox；pending outbox 为 0，完整性 PASS。
- event 6 以同一 idempotency key 重放返回同一 event id / SHA，不追加事件。
- outbox 首次发布新 6 条，第二次发布 0。
- 新 registry / gate ledger SHA-256：
  `a21adcaa7ecc57a21e33a79794115c7f001b93666495550aea7a8750ef7b3963` /
  `ac4d79c6e40d4c60c0825e0552e194eaefdae306248ed709b54baf25d8da227f`。
- 上一权威 registry / ledger SHA-256 仍为
  `d2e1b0a3ec243ffaab916b52f11b97ae4788da3f1cfbbd1ef9d9ed189bc82cb4` /
  `da719a370572e045b765cbb2e58214802ffc3887a039ef8928102aeea828e23d`，未被改写。

## 7. 验证与下一边界

- 全仓：812 PASS；仅 1 条既有 Starlette 第三方弃用 warning。
- 架构宪法：6 PASS。
- Ruff、compileall、pip check、git diff check、release/approval/hash/registry integrity：PASS。
- 七个 scheduler 自然账本变更不属于本任务，未暂存、未提交。

本 release 已消费并形成权威 lineage NO-GO，不得重跑、换 source、删除冲突、用 latest/VIP/update flag
排序或把本地观察时间冒充历史生效时间。M5-2C、候选、效果、模型、回测和生产仍被阻断。

若未来继续补足历史版本证据，必须另立结果前协议和精确 release，并明确权威来源、版本/生效时间、
联网边界和失败关闭规则；不能回写本轮证据。按照用户指令，本节点完成后先进行一次只读阶段复盘，
再决定继续、调整、暂停或重排，不自动进入外网补证施工。

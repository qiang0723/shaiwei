# M5-2B-R2 财报谱系年报行域恢复 release 验收

- 验收时间：2026-08-06（UTC+8）
- 当前状态：`SOURCE_LINEAGE_RELEASE_READY_NOT_APPROVED`
- 谱系裁决：`NOT_EXECUTED`
- 策略结论：`NOT_EVALUATED`
- 生产授权：`none`

## 1. 结论

上一 release `b01058b55ff3dd6c06cf0722541214ecbb793de92a3115410c073daab26cf155`
已永久停在 case `6b6c849f...f7be16` 的 event 6 `STOPPED`，不得重跑或改写。本轮只修复已证实的
锚定行域不一致：R2 reader 现在和 R1 冲突基线一样，只允许 `end_date` 为 12 月 31 日且
`report_type` 属于字符串集合 `{1,5}` 的年报行进入 Observation、锚定冲突键和历史 allowlist。

恢复协议提交 `cd13e6a0696f67248f20367e85e6cef85947b602` 先行推送；行域实现提交
`823e8360fed406fe56d2d7797d6d810c03b00ab1` 和断网镜像构造提交
`213d0a103c9f22b327313bdc568c48eea0a9fff8` 随后分别推送。最终形成新的 case、镜像、metadata-only
输入清单和精确 release scope。本验收只说明恢复实现可申请一次真实运行，不表示谱系可行、数据恢复、
候选有效或生产获准。

## 2. 单变量修复与继承边界

- 新增纯领域谓词 `statement_scope.py`；reader 在构造 Observation 前调用，不在下游事后删行。
- 年报 `report_type=5` 和连字符日期可合法进入；季度行、`report_type=2` 等其他报告类型明确排除。
- 合法行缺少冻结身份字段时继续失败关闭，不通过排除规则掩盖数据缺陷。
- 季度冲突、其他报告类型冲突、年报 type 5、连字符年报日期和缺身份行均有对抗测试。
- R1 `source_conflicts.py` 的六类冲突语义、R2 六种谱系处置、独立 auditor、registry schema、八候选、
  三股票池、24 个单元、PIT/覆盖门、尝试 `N=14/20` 均未改变。
- 旧 release、旧 approval、旧输入束、旧 registry、旧 `STOPPED` 事件和零输出/零 audit 事实均未迁移。

协议 scope 为
`0e4ea4ee6c283b9fad28e1b289f146199154a3e2f5c65d5255d2e462cacb20bc`，物理 SHA-256 为
`34836cbec0ca0aae4034650ee2609fb13b20aec1288e5747fdcd5deffe86d222`；新 case 为
`8000c9e107c100cdb41edace547f5869dddda6807005c142ce2847d9433f49ff`。

## 3. 断网镜像与合成工程证据

首次尝试用原数据门 Dockerfile 在 `--network=none` 下重建，因本机 BuildKit 缓存缺少 `duckdb` 依赖而
在 pip 阶段 DNS 失败。该尝试没有开放网络、没有创建新镜像、没有读取真实财务语义。随后从上一份已
验证镜像的精确 digest 派生只叠加恢复代码的专属 Dockerfile，不改变依赖集合：

- 精确 base image：
  `shaiwei:m5-lineage-local@sha256:fe9101f11a54d0b2111c0000ffff5a21d7d72fd86f4300aa30ae7b934119b606`
- 新镜像 / repo digest：
  `sha256:5dd12995e4a1dbf8aead28d91aca6a040af7da8c2251f783ff657a7a34212d1a`
- 平台：`linux/arm64`
- recovery Dockerfile SHA-256：
  `fd8e10b4293016188e637e07c57e311a5616c6a9f69d5d5c22008f57e039ae69`

新镜像以 `network=none`、非 root、只读根、drop ALL capabilities、no-new-privileges、128 pids、无任何
宿主挂载直接运行两遍合成 fixture；两遍 JSON 逐字段一致，`case_count=8`、确定性双跑、独立 audit、
registry 重放和禁止字段篡改均 PASS，`semantic_rows_read=false`、`external_call_count=0`、策略
`NOT_EVALUATED`、生产 `none`。

## 4. 新 metadata-only 输入清单

清单只读取 ingest ledger、Parquet metadata、文件大小和内容哈希，不读取财务列值：

- 逻辑 SHA-256：`bda3f6b86a43a13438acc78bfaf14bce772c9b4d94d221272765ba6f6735d0df`
- 物理 SHA-256：`1e4ea075065d1e5c0d58f40593aa24ce25443b8c696f7032ed04eb7aef795ebf`
- 文件大小：27,755,333 bytes
- R1 锚定批次：16,841
- 截止清单时点的历史批次：16,841
- 权威版本证据：0
- `semantic_rows_read=false`

清单覆盖 income / income_vip / balancesheet / balancesheet_vip / cashflow / cashflow_vip 六类源。锚定与
历史批次当前相同，只说明没有新增可证明历史有效时点的材料；本轮没有据此预判或生成真实谱系结果。

## 5. 新内容寻址 release

- release scope SHA-256：
  `f7904929991e90a3d4c220cbdaf88818953694803625c41eb3634731e376e2d5`
- release 文件物理 SHA-256：
  `9343fa9cfaa8855739b700fbf244d6597f1f10f070c780f8d973ce11cfdd2933`
- code bundle SHA-256：
  `04077847257a63f908a3d6ff77eb27e8b8ee7ec46ecb8cb6fcd489f168e78fb3`
- 实现提交：`213d0a103c9f22b327313bdc568c48eea0a9fff8`
- 提案状态要求：`REVIEW_REQUIRED` / event 2
- 提案到期：`2026-08-12T10:48:16+00:00`

四个挂载全部以新 input manifest SHA 和实现提交前七位内容寻址：只读 input、专属 output、audit 和
registry；不挂项目根、`.env`、Docker socket、标签、效果或模型目录。scope 中只有
`lineage_release_ready=true`；approval、execution、正式 registry 写、真实读取、真实冲突诊断、外部
调用、凭据、PIT、候选、标签、效果、模型和回测授权均为 false，生产为 `none`。

## 6. 验证与生产隔离

- release / recovery 专项：10 PASS。
- 全仓：812 PASS；仅 1 条既有 Starlette 第三方弃用 warning。
- 架构宪法：6 PASS。
- Ruff、compileall、pip check、git diff check：PASS。
- 生产 scheduler 仍为原容器 `183b8c6c5edd`、原镜像
  `sha256:722f63de15932cb2698e82db7c0140f02921f27f126e1c0235ca62e0a1213b76`、创建时间
  `2026-08-03 17:39:34 +0800`，healthy 且未重启。
- 七个 scheduler 自然账本变更不属于本任务，未暂存、未提交。

## 7. 停止线与下一授权

当前没有新 approval envelope、新正式 lineage registry、新内容输入束、真实 runner/auditor 产物或
谱系 verdict。旧 scope 的批准不会自动迁移。只有用户明确批准完整新 scope
`f7904929991e90a3d4c220cbdaf88818953694803625c41eb3634731e376e2d5`，才可物化新输入束并运行恰好一次
断网 `LINEAGE_FEASIBILITY`。

该批准仍不授权外网或权威证据采集，也不授权 PIT、候选、M5-2C、效果、模型、回测、Web、scheduler
或生产；scope 任一字段漂移都使批准失效。

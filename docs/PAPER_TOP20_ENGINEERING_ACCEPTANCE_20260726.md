# Top20 模拟比较账户工程验收

> 验收日：2026-07-26（Asia/Shanghai）
>
> 工程裁决：`GO_ENGINEERING_AND_BACKFILL`
>
> 前瞻状态：`NOT_READY`；策略有效性：`NOT_EVALUATED`
>
> 生产自动化：`BLOCKED_PENDING_CREDENTIAL_ROTATION_AND_RELEASE_WINDOW`

## 1. 冻结与实现身份

任何 Top20 结果出现前，协议、时间纠正和共享账本证据纠正已依次提交并推送：

- `0f24238`：原始结果前协议；
- `4ec339d`：新账户前瞻起点从机械沿用的 7月23日纠正为冻结后的 7月27日；
- `c4ad587`：共享账本从“不可能的整文件不变”纠正为“旧字节完整前缀与 Top30 规范行不变”；
- `cf133d9`：工程实现，先通过本机和 Docker 测试后推送，再生成账户结果。

冻结配置 SHA-256 为 `d09a767ce75ce8ad95c5e2350ab410501cbd8a4d790498731553cadaefbca37e`；
Top20 策略 SHA-256 为 `d11d773bd79719641dc1bbc35976d4899fddb730d0f3673094cb6f20cc7840c8`。
原 Top30 `paper-v1` 策略 SHA-256 仍为
`eaa341b5a3eee94347c7a8453a3e52f1986e3707abfbb6bb69a6d9298c320cc8`。

## 2. 实现边界

- 独立账户 `model_top20`，初始资金 500,000 RMB，基准 `000906.SH`。
- 每份已对账 Top30 manifest 必须恰有 30 个唯一证券、1—30 唯一排名、冻结等权、10日调仓和合法
  source SHA；然后只保留排名1—20并等权为5%。非30只、缺/重排名、重复证券、非等权、错哈希或
  `.BJ` 均 fail closed。
- 投影不生成第二份模型信号；运行产物同时保留原 signal SHA 和独立 projection SHA。
- 基准与 Top20 使用不同账户、策略哈希、状态链、运行身份、通知事件和产物目录。
- scheduler 只有在另一个结果后 release 文件存在且绑定冻结协议哈希时才会串行运行 Top20；本次未生成
  该授权文件，因此当前生产镜像看不到也不会自动启动新账户。

## 3. Docker BACKFILL 结果

Docker 专用操作员 `docker-top20-backfill` 完成以下六个执行日：

`20260717 / 20260720 / 20260721 / 20260722 / 20260723 / 20260724`。

全部 6/6 为 `PASS + BACKFILL`，不得并入前瞻业绩。账户共 160 个事件、20 个订单、18 个成交；首个
调仓目标为20只，受真实交易单位与现金约束后实际持仓18只。截止 2026-07-24 的只读快照为：现金
78,843.07元、持仓市值377,118.81元、净资产455,961.88元、累计费用130.53元。以上数值只用于证明
会计与查询可复算，不构成 Top20 相对 Top30 的策略裁决。

六份产物整树：6 文件、114,892 bytes，tree SHA-256
`dcd8cc219df2340eeb1e555dcb9043377b0bf73bc5d0e872217d9ef3d50f0418`。运行时代码快照统一为
`6846a7f1ac6555548bd72b4b8a473511566a1d493590a77cb2679c284afd282c`；每份投影均为20只、排名1—20、
5%权重且绑定原 signal SHA。Top20 事件 `.BJ=0`。

只读重放返回：`run_count=6 / event_count=160 / order_count=20 / fill_count=18 / status=PASS`。
前瞻裁判返回：`status=NOT_READY / forward_observation_count=0 / replay_status=PASS`，正确拒绝将7月23、
24日的事后建账冒充自然前瞻。飞书 Top20 开始/完成各一次投递 PASS。

## 4. Top30 不变与追加证据

施工前后，`data/paper/model_baseline/` 均为 6 文件、112,047 bytes，tree SHA-256
`1108435f1b9f599363d18d462e518a022a11080692b473aac67ee26f8aade849`。

| 共享账本 | 旧文件 SHA-256 | 新文件 SHA-256 | 旧前缀 | Top30 规范行 | Top20 新行 |
|---|---|---|---|---:|---:|
| accounts | `2069b94f…d2ada` | `6dd76713…9c5b` | PASS | 1，行哈希 `8f8b26d7…8e31` 不变 | 1 |
| events | `2f09bbce…2dc5f` | `97fbce74…ccd1` | PASS | 198，行哈希 `4e1bb585…17d6` 不变 | 160 |
| runs | `8055a16c…aa4c` | `fd0a09a5…17f` | PASS | 6，行哈希 `6b88b7a4…704e` 不变 | 6 |

三份新文件均以原文件完整字节为前缀，只在尾部追加 Top20 行；无重排、覆盖、删除或旧行补填。

第二次运行同一 Docker 入口返回 `NOOP`；账户/事件/运行账本 SHA-256 与六份 Top20 产物整树哈希均
不再变化。

## 5. 测试与生产隔离

- 本机全仓：348 PASS；Ruff、compileall、pip check、`git diff --check` PASS；仅一条既有
  Starlette/httpx 第三方弃用 warning。
- Docker Top20 核心专项：27 PASS；7份真实不可变信号逐份投影 PASS。
- 生产 scheduler 仍为原容器 `fd8e96152b53…a5adbb`、原镜像
  `sha256:de87ec740981…aa0261`、原代码快照 `eb8e752132ac…b7fbd`，创建于 2026-07-24 20:25:27
  UTC+8，健康、未重启、未提升。

## 6. 安全阻断与下一节点

隔离复核时曾错误请求完整 Docker inspect 文档，交互式工具输出包含现有容器环境变量。凭据没有写入
仓库、项目文档、账本、日志或提交，但已出现在本任务工具输出中，按安全原则必须视为已暴露。须由用户
轮换 Tushare 与飞书凭据并只写回项目内被 Git 忽略的 `.env`；后续 Docker 身份检查只允许请求定向
非敏感字段。

在凭据轮换完成、干净终版镜像构建通过且 release readiness 出现新可处理交易日前，不创建 Top20
scheduler release、不提升或重启生产容器。之后的首个自然 `FORWARD` 仍须通过当前代码/策略身份、
Docker operator、新鲜度、`.BJ=0`、独立重放与 Top20 专属飞书开始/完成门。

当前 Web 继续只显示 `model_baseline`。Top20 已可通过冻结 Python/CLI 只读查询；Web 账户切换与同区间
对比应作为独立只读 Web 变更评审，不在短样本为0的状态下仓促展示回填曲线。

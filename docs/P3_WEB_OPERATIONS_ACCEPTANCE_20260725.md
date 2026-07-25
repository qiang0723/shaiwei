# P3-2A 数据质量与系统运行只读查询验收

> 验收日期：2026-07-25（Asia/Shanghai）
>
> 协议：`p3-web-operations-v1`
>
> 结论：`GO_WITH_EVIDENCE_WARN`
>
> 边界：只读后端工程 GO；数据质量/系统运行页面尚未施工，不授权远程开放、写能力、生产变更或
> 将 WARN 改成 PASS。

## 1. 结果前冻结与纠错留痕

实现提交之前已依次提交并推送：

- 主协议：`12e7cbb`；
- 哨兵未哈希绑定补遗：`ed91329`；
- 哨兵时钟语义补遗：`3cf9de8`；
- 通知 schema 代际补遗：`9753532`。

真实实现审计确认两项既有事实：信号/影子账本未保存哨兵报告哈希；2026-07-23 前通知记录没有
稳定 message ID。两项均在实现终版提交前显式留痕，没有合成哈希、ID 或全绿结论。

## 2. 已实现查询

### 2.1 数据质量

`GET/HEAD /api/v1/data-quality` 以最新终态日运行锚定 `as_of`，流式重算截止运行完成时刻的
`ingest_batches` 规范身份链，并验证日增量、PASS 影子、信号、哨兵报告的日期、时钟和代码/数据
身份。

真实验收切片截至 `2026-07-24`：

- 登记批次 69,020，登记行数 45,160,002；
- 重算 `data_snapshot_sha256` 与日运行登记值精确一致；
- 当日市场批次 5、市场行数 15,613；
- S1—S9 PASS、S10 NOT_APPLICABLE、`required_failures=[]`；
- 验证过的市场批次 `.BJ=0`，Web 返回证券 `.BJ=0`；
- 数据结论 `PASS`；
- 哨兵证据 `WARN / IDENTITY_MATCH_UNHASHED`；
- `raw_parquet_rehash_status=NOT_EVALUATED`。

响应不返回 `params_json`、Parquet 路径、异常逐行证券、绝对本地路径或原始记录。批次登记链一致
不被表述为查询时重新哈希 45GB 级原始数据。

### 2.2 系统运行

`GET/HEAD /api/v1/system/runs` 固定展示日增量、哨兵、次日对账、影子信号、模拟仓和独立账本重放。
真实终态为 `WARN`，原因完整保留：

- 日增量 PASS；
- 哨兵 PASS、证据 WARN；
- 次日开盘对账 PASS；
- 影子运行先有 `ForwardQlibError`，随后 PASS，明确 `recovered=true`；
- 模拟仓 PASS；
- 独立重放 6 个账户日、198 个事件 PASS；
- 同日存在核心故障消息 `ce3bfbf96e9ec474`；
- 通知 9 个可寻址消息、11 次尝试、1 次失败、1 个恢复，通知状态 WARN；
- 旧 schema 共 40 条不可寻址记录，只计数、不合成 ID。

release 审计哈希链 PASS，运行前最后一个 `START_PASS` 的代码快照为
`eb8e752132ac1fbe6a9557d26b4c7a65df36f6169d617b6e1e10db88d46b7fbd`，与 PASS 影子一致；
只读根与 `/workspace/data|ledger|logs` 挂载身份已登记。实时 Docker 身份保持
`NOT_EVALUATED`，因为 Web 查询没有 Docker socket。

### 2.3 通知投递

`GET/HEAD /api/v1/notifications/{message_id}` 只接受 16 位小写十六进制 ID，逐次返回当前九字段
脱敏 schema。失败、retryable、恢复和重复投递风险均保留；正文、Webhook、签名、环境变量和原始
业务字段不返回。真实 `ce3bfbf96e9ec474` 查询 PASS。

## 3. API 与 Docker

三个真实容器响应共享同一证据切片，采样 `snapshot_id` 为
`55768e7b0c9072f10268c90f7692fec043794b669294058ae12d1b1171d48fb9`；响应大小分别约
10,086 / 5,551 / 3,918 bytes，均远低于 1 MiB。该 ID 包含可变 scheduler 心跳，只有证据不变时
才保持相同。

终版 Web 镜像内容身份：
`sha256:6c244c9a8be4d44dacb3887822055fa1c9a667b7d1fa61bd6a61a5687da77190`。

`web-query` 保持：

- uid 10001、只读根、`cap_drop=ALL`、`no-new-privileges`；
- 384 MiB、0.75 CPU、128 PID；
- 无宿主端口、无 `.env`、无 Docker socket、无 `data/raw`；
- 新增的 sentinels/releases/scheduler 目录均只读；
- 写账本探针被内核拒绝；
- 真实查询后即时内存约 42.0 MiB。

P3-2A 不修改 P3-1 UI allowlist，因此新端点当前只在内部 query 服务可用；页面与 UI 代理必须在
P3-2B 另立目标后施工。

## 4. 生产隔离

Web 重建前后生产 scheduler 均保持：

- 容器 `fd8e96152b53...`；
- 镜像内容 `sha256:de87ec740981166b032b394fb256a978acdc8d35e999a369f1debc3466aa0261`；
- 代码快照 `eb8e752132ac1fbe6a9557d26b4c7a65df36f6169d617b6e1e10db88d46b7fbd`；
- 创建时间 `2026-07-24T12:25:27.362813588Z`；
- 状态 healthy。

没有启动采集、哨兵、模型、回测或飞书发送，也没有重建、重启或换镜像 scheduler。

## 5. 验证

- P3 查询专项：9 PASS；
- 全仓：277 PASS；
- Ruff：PASS；
- compileall：PASS；
- `pip check`：PASS；
- Compose 展开、GET/HEAD、方法拒绝、响应上限、脱敏、只读挂载和写拒绝探针：PASS；
- 真实批次链、哨兵、release、通知和三 API：PASS；
- 唯一提示仍是 FastAPI TestClient/httpx 上游弃用警告，不为提示擅自升级冻结依赖。

## 6. 下一目标

P3-2B 可在不改后台口径的前提下施工“数据质量”和“系统运行”两个页面，并把三个新端点加入 UI
精确 allowlist。页面必须同时显示数据结论 PASS 与证据 WARN，不得隐藏未哈希绑定、原始文件未重验、
legacy 通知或实时容器身份未评估。

# P3-0 Web 1.0 只读查询后端验收

> 验收日期：2026-07-25（Asia/Shanghai）
>
> 协议：`p3-web-query-v1`
>
> 结论：`GO`
>
> 边界：查询工程 GO，不代表完整 Web 1.0 页面完成，不授权远程开放、交易、在线改参、导出或
> 生产策略变更。

## 1. 结果前冻结

实现前已提交并推送：

- 协议提交：`1e895c013bd4f6c74f688035c1be8d734b551e49`
- 协议：`docs/P3_WEB_QUERY_PROTOCOL_20260725.md`
- 机器配置：`config/p3_web_query_v1.yaml`

冻结先于查询代码、FastAPI、Docker 和任何运行验收。施工未改模型、策略、研究门禁、生产
数据、运行账本或 scheduler 镜像。

## 2. 已实现能力

### 2.1 原子查询

`src/shaiwei/web/query.py` 只读取固定白名单账本、其登记的不可变产物和脱敏通知证据：

- 每次查询读取稳定字节切片并在结束时复核文件集合、大小与修改时间；
- 账本身份、文件 SHA-256、信号内容哈希、模拟组合内容哈希逐项 fail closed；
- 独立重放模拟账户事件、状态链、逐仓状态和会计恒等；
- 证券、信号、对账、持仓和事件任一出现 `.BJ` 立即失败；
- 相同证据产生稳定 `snapshot_id` 和 ETag；
- 不调用 `load()`，不读取 `.env`、原始行情、Parquet、模型文件或 Git 元数据。

当前真实原子快照：

- `as_of=2026-07-24`
- `snapshot_id=1675b728a9a8134ea076f5adc94f2be54053a5aac3df13a7dd4c976d20473347`
- `required_evidence_complete=true`
- 账本重放 `PASS`
- `.BJ=0`
- 综合状态 `WARN`

`WARN` 不是查询失败：2026-07-24 核心影子运行先有一次 `ForwardQlibError` 后 PASS，模拟仓完成
通知也在一次网络失败后第 2 次恢复。查询同时保留核心任务与通知恢复历史，不用最终 PASS
覆盖先前失败。

### 2.2 信号、组合与 FORWARD

- 最新 `2026-07-24` 信号只返回信号时点事实；
- 信号生成前最后一个模拟账户参照日正确固定为 `2026-07-23`；
- 该信号 `rebalance_due=false`，计划交易腿为 0；
- 尚无已登记次日对账，故 `execution_evidence_status=NOT_DUE`、
  `next_execution_date=null`，没有猜测周末后的官方开市日；
- 最新模拟账户日为 `2026-07-24`，逐仓实际权重和未实现盈亏由同一账户日产物确定性投影；
- 最后一个 BACKFILL `2026-07-22` 是唯一 FORWARD 锚点；
- 当前 FORWARD 观察 2 日，只展示专属组合/基准净值、净值差、回撤、费用、换手和现金比例；
- P3-0 未挂载官方交易日历，覆盖率保持 `NOT_EVALUATED`，成熟度保持 `OBSERVING`，年化、
  Sharpe、信息比率继续隐藏。

### 2.3 HTTP

FastAPI 关闭 OpenAPI/Swagger/ReDoc，只开放：

- `GET/HEAD /healthz`
- `GET/HEAD /api/v1/overview`
- `GET/HEAD /api/v1/paper/portfolio`
- `GET/HEAD /api/v1/paper/nav`
- `GET/HEAD /api/v1/paper/forward`
- `GET/HEAD /api/v1/paper/replay`
- `GET/HEAD /api/v1/signals/latest`
- `GET/HEAD /api/v1/signals/reconciliation`

本机验收：

- UI `/`：HTTP 200
- 原子总览：HTTP 200、重放 PASS、FORWARD 2 日、`.BJ=0`
- `/docs`：HTTP 404
- `POST /api/v1/overview`：HTTP 405
- 响应上限 1 MiB，当前页面约 4 KiB
- 当前响应 `Cache-Control: no-store`，不返回绝对路径、异常栈、密钥或原始日志

## 3. Docker 隔离

Web 使用独立 `compose.web.yaml` 和项目名 `shaiwei-web`，两个服务都在显式 `web` profile；
无 profile 时服务列表为空。启动命令必须点名 `web-query web-ui`。

终版镜像：

- `shaiwei:web-v1`
- 内容身份：
  `sha256:1c25025b6cd907bdb2315df8428743b21f47be77986b734a715c8b396c3ae630`
- 依赖使用独立、完全固定的 `requirements.web.lock`

运行隔离：

- `web-query` 无宿主端口，只加入内部网络；
- `web-ui` 无证据挂载，通过内部网络访问 query，另加入回环 bridge；
- 宿主唯一入口为 `127.0.0.1:8080`；
- query 只读挂载 `ledger/`、`data/paper/`、信号、对账和脱敏通知目录；
- UI 不挂载任何生产证据；
- 两容器均为 `uid=10001`、只读根、`cap_drop=ALL`、
  `no-new-privileges`、有界 tmpfs、384 MiB/0.75 CPU/128 PID；
- `.env/.git/docker.sock` 均不存在，环境变量无 token/secret/webhook/api-key；
- 根目录、账本、模拟仓和通知目录写探针全部被内核拒绝。

最初只给 UI 配置 `internal: true` 网络时，Docker Desktop 正确不发布宿主端口。终版按 Docker
官方的混合网络方式调整：query 仅在 internal network，UI 同时加入 internal network 和
回环 bridge；数据服务仍不可从宿主直接访问，UI 只绑定 127.0.0.1。参考
[Docker Compose networking](https://docs.docker.com/compose/how-tos/networking/)。

终版即时资源：

- `web-query`：约 36.7 MiB / 384 MiB
- `web-ui`：约 39.7 MiB / 384 MiB
- scheduler：约 283.8 MiB

## 4. 生产隔离复核

施工前后 scheduler 均为：

- 容器：`fd8e96152b53`
- 镜像：`shaiwei:scheduler-current`
- 镜像内容：
  `sha256:de87ec740981166b032b394fb256a978acdc8d35e999a369f1debc3466aa0261`
- 代码快照：
  `eb8e752132ac1fbe6a9557d26b4c7a65df36f6169d617b6e1e10db88d46b7fbd`
- 状态：`healthy`

Web 构建、重建和网络修复均未启动、停止、重建或换镜像 scheduler。

## 5. 验证

- P3-0 专项：4 PASS
- 全仓：210 PASS
- 脱敏、release 和 append-only 专项：19 PASS
- Ruff：PASS
- compileall：PASS
- `pip check`：PASS
- `git diff --check`：PASS
- Compose 展开、默认关闭、端口、挂载、非 root 和只读写探针：PASS

唯一测试提示是 FastAPI 当前 TestClient 对 httpx 的上游弃用警告，不影响运行；依赖继续固定，
不为消除提示擅自升级。

## 6. 未完成与下一阶段

P3-0 只完成可信查询底座和最小连通性页面。以下仍未施工：

- Web 1.0 正式总览视觉与交互；
- 模拟组合详情页；
- 股票池/信号详情页；
- 实验、数据质量、系统运行和因子工厂 HTTP 查询；
- 官方交易日历覆盖率与达到样本门槛后的年化/风险调整公式；
- 导出、认证、多用户、局域网/公网和远程部署。

建议下一目标为 P3-1：严格复用 P3-0 API，按冻结设计先完成“总览 → 模拟组合 → 股票池/信号”
三个真实页面与浏览器 QA；不得让前端扫描文件、重算研究口径或扩展 Web 后端写权限。

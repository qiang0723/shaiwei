# Top20 单次生产切换守护恢复工程验收 v2

日期：2026-08-01（UTC+8）

协议：`paper-top20-release-guard-20260803`

结果前冻结提交：`b26f126`

## 1. 阶段裁决

机器结论：`GO_ONE_SHOT_RELEASE_GUARD_V2_ENGINEERING_ONLY`。

守护实现已经兼容冻结的 v2 配置，且没有修改候选镜像、发布实现、Compose、scheduler、数据、模型、
信号或门禁。真实整门只读演练已经READY，旧自动任务已删除，新任务已经从周六指向下周一16:05且
只执行一次。本结论不是生产切换完成、不是8月3日跑批PASS，也不是Top20前瞻或策略有效性结论。

## 2. 最小实现

- CLI 默认协议路径由不可再执行的 v1 改为已冻结 v2；v1 配置、协议、验收和 fixture 均原样保留。
- `guard_id` 只接受 `paper-top20-release-guard-YYYYMMDD`，并强制日期后缀等于
  `target_trade_date`，防止复制配置时产生身份与执行日分裂。
- 没有改动 `release.py`、`start_current()`、候选/旧生产身份、16:05—19:00时窗、Git/发布审计/
  容器/FORWARD/readiness门或任何失败关闭语义。
- 独立守护模块为348行，没有继续扩大 `release.py`；测试文件为229行。

## 3. 已完成验证

- 本机 release/guard 专项：32 PASS；既有 v1 全部 fixture 保持通过，新增 v2 默认路径、8月3日
  READY和guard/date错配拒绝测试。
- Docker开发容器专项：32 PASS。
- 全仓：384 PASS，1条既有Starlette第三方弃用warning。
- Ruff、compileall、`pip check`、`git diff --check`、账本append-only和secret hygiene均PASS。
- 2026-08-01周六直接调用生产CLI返回
  `BLOCKED: guard target date does not equal the local date`，退出码2，未访问Docker。
- Docker专项测试前后，生产scheduler均为原镜像`sha256:de87ec74...0261`并保持healthy，未启动或
  重启。

## 4. 真实只读整门演练

- 工程提交`2964ef4`推送并恢复干净工作树后，以2026-08-03 16:05时钟注入、真实其余依赖和
  `execute=false`执行完整守护，返回`READY`、`start_invoked=false`。
- 发布候选四项身份精确等于冻结值；旧scheduler为容器`fd8e9615...adbb`、旧镜像
  `de87ec74...0261`、代码快照`eb8e7521...7fbd`、Git`ecda815...f24`且healthy。
- readiness返回`PASS / CROSS_SNAPSHOT_WITH_NEW_DATA`，唯一新交易日为`20260803`，最新Top30
  执行日为`20260731`且旧代码快照一致。
- 演练没有调用启动，不写发布审计，不运行日增量，不更改生产容器。

## 5. 单次自动任务

- 未触发的旧Codex任务`top20`已删除；其历史身份和未触发事实继续由v1文档与RCA保留。
- 新任务ID：`top20-8-3`；名称：`筛微 Top20 8月3日单次受控切换`。
- 新任务从2026-08-01周六创建，只匹配下一周一16:05 UTC+8一次；本机项目目录固定为
  `/Users/john/Desktop/shaiwei/shaiwei_init`。
- 任务只允许运行一次`make docker-release-guard`；BLOCKED/失败立即停止且不重试、不修复、不绕过；
  STARTED/ALREADY_ACTIVE后只定向检查scheduler状态，不等待或手工触发晚间跑批。

任务创建不等于执行成功。8月3日仍只认新增`START_PASS`、实际候选容器身份以及其后自然整日链路证据。

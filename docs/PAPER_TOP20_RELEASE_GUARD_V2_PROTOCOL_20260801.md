# Top20 单次生产切换守护恢复协议 v2

协议 ID：`paper-top20-release-guard-20260803`

冻结日期：2026-08-01（UTC+8）

目标日期：2026-08-03（本地官方交易日历已确认开市）

## 1. v1永久事实与恢复原因

v1 `paper-top20-release-guard-20260730` 的协议、配置、工程验收和自动任务名称永久保留，不修改、不
覆盖。仓库证据证明2026-07-30计划时点后没有 `START_PASS`，实际 scheduler 在7月30、31日均继续以
旧代码快照运行；Top20保持0个自然FORWARD。

现有证据没有守护命令的结构化输出或发布失败记录，因此权威分类仅为
`AUTOMATION_DISPATCH_NOT_OBSERVED`，Codex应用侧未派发的具体原因`NOT_EVALUATED`。v2不是修复一个
未经证明的守护逻辑缺陷，而是以新的未来日期、最新旧FORWARD锚点和从周六指向下一周一的单次排程
重新取得可执行窗口。

## 2. 唯一允许变化

相对v1只允许：

1. `target_trade_date`由`20260730`改为`20260803`；
2. 最新`model_baseline`执行日由`20260729`改为`20260731`，代码快照仍为旧生产
   `eb8e7521...7fbd`；
3. 删除旧Codex任务`top20`后，从当前周六创建“下一周一16:05、仅一次”的新本机项目任务；不使用
   过去日期锚点，不复用旧任务ID。

候选镜像、旧生产镜像、16:05—19:00窗口、Git/发布链/容器/FORWARD/readiness门、唯一一次
`start_current()`、零build/promote/rollback/手工跑批和所有失败关闭行为逐项不变。

## 3. 冻结身份

唯一候选：

- image：`shaiwei:scheduler-4e5244b6b02739dd`
- image ID：`sha256:722f63de15932cb2698e82db7c0140f02921f27f126e1c0235ca62e0a1213b76`
- 代码快照：`4e5244b6b02739dd209a9b01ea715c43ed9a874a7014156e20cf364f06a82708`
- Git：`210af4dab33c85b38c05b28f56c176b7970c41db`

启动前唯一旧生产：

- image ID：`sha256:de87ec740981166b032b394fb256a978acdc8d35e999a369f1debc3466aa0261`
- 代码快照：`eb8e752132ac1fbe6a9557d26b4c7a65df36f6169d617b6e1e10db88d46b7fbd`
- 最新Top30 PASS执行日：`20260731`

## 4. 日期、时窗与日历门

- 只允许2026-08-03 16:05:00（含）至19:00:00（不含），时区`Asia/Shanghai`。
- 冻结前本地日历计划在8月3日16:05返回watermark `20260731`、eligible target `20260803`、唯一
  missing trade date `20260803`。
- 运行时仍须实时重算；若周末出现新PASS、账本漂移、多日积压、日期变化、工作树不干净、远端不同步、
  容器不健康或候选身份变化，全部在Docker变更前BLOCKED。

## 5. 施工授权

协议提交推送后只允许：

- 让`GuardProtocol.guard_id`接受严格日期格式，而不是只接受旧单一ID；
- 将生产CLI默认配置从v1切换为已冻结v2路径；
- 保留v1 fixture并新增v2默认路径、8月3日边界和最新FORWARD锚点测试；
- 以8月3日时钟注入做真实其余依赖的`execute=false`整门演练；
- 删除旧Codex任务`top20`并创建全新单次任务，随后记录新任务ID。

不得改`release.py`、候选镜像、Compose、scheduler、Top30/Top20协议、数据/模型/信号/门禁、飞书、
Web或研究线路。周末不得调用`--execute`。

## 6. 自动任务边界

- 新任务从2026-08-01周六创建，下一次匹配时间必须是2026-08-03周一16:05 UTC+8，且只执行一次。
- 任务只在`/Users/john/Desktop/shaiwei/shaiwei_init`工作；先读仓库纪律和v2协议，只运行一次
  `make docker-release-guard`。
- BLOCKED或命令失败立即停止，不改代码、不补提交、不重试、不换候选；STARTED/ALREADY_ACTIVE后
  仅定向确认scheduler healthy，不读取环境变量，不等待或手工触发19:30跑批。
- 任务创建不等于执行成功。只有新增`START_PASS`和候选容器身份才能证明切换完成。

## 7. 结果边界

v2工程通过只能标`GO_ONE_SHOT_RELEASE_GUARD_V2_ENGINEERING_ONLY`。8月3日启动成功后仍须等待自然
跑批，独立核验Top30、Top20、`.BJ=0`、S1—S10、飞书与幂等；Top20策略继续
`NOT_EVALUATED`，无实盘授权。16:00早探测候选必须等待Top20首个自然FORWARD通过后的另一交易日。

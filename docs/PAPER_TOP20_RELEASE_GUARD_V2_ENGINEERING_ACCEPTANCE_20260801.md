# Top20 单次生产切换守护恢复工程验收 v2

日期：2026-08-01（UTC+8）

协议：`paper-top20-release-guard-20260803`

结果前冻结提交：`b26f126`

## 1. 阶段裁决

当前阶段结论：`GO_V2_IMPLEMENTATION_VERIFIED_AUTOMATION_PENDING`。

守护实现已经兼容冻结的 v2 配置，且没有修改候选镜像、发布实现、Compose、scheduler、数据、模型、
信号或门禁。本结论尚不代表自动任务已创建，也不代表生产已经切换；完成真实整门只读演练并替换旧
自动任务后，才可升级为最终工程结论。

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

## 4. 待最终闭环

1. 工程提交推送、工作树干净且`HEAD=origin/main`后，以2026-08-03 16:05时钟注入，针对真实
   Git、发布审计、候选、旧scheduler、Top30账本和日历执行`execute=false`整门演练；
2. 删除未触发的旧任务`top20`，新建从本周六指向下周一16:05且只运行一次的本机项目任务；
3. 将新任务ID、演练输出和最终生产未变证据追加到本文及`STATE.md`并推送。

完成上述三项前，不得表述为周一切换已安排完成。

# Top20 单次生产切换守护工程验收

日期：2026-07-29（UTC+8）

协议：`paper-top20-release-guard-20260730`

结果前冻结提交：`c619697`

## 1. 裁决

机器结论：`GO_ONE_SHOT_RELEASE_GUARD_ENGINEERING_ONLY`。

守护工程已具备在 2026-07-30 16:05—19:00 UTC+8 对唯一 Top20 候选执行一次受控启动的能力。
本结论不是生产切换完成、不是当日跑批 PASS、不是 Top20 前瞻验收，也不是策略有效性结论。

## 2. 实现边界

- 新增独立 `shaiwei.release_guard` 模块，342 行；没有向已超过常态规模的 `release.py` 继续加入新职责。
- 配置以 Pydantic 严格模型解析，未知字段拒绝，候选/旧生产/FORWARD 身份和布尔权限均不可静默放宽。
- CLI 默认只检查；只有显式 `--execute` 才可能调用既有 `start_current()`。
- 生产 CLI 不提供时间覆盖参数，测试时钟只能通过 Python 内部依赖注入进入 fixture。
- Git、Docker、账本、readiness 和启动通过窄环境适配层进入；fixture 全部替换适配层，不触碰真实服务。
- Docker 只定向读取容器 ID、image ID、health、运行时代码快照和 Git 身份；未请求或输出环境变量。
- 阻断路径不写发布审计、不发飞书、不改 release 指针、不运行日增量，也不自动 build/promote/rollback。
- 已激活的精确候选返回 `ALREADY_ACTIVE`，不重启第二次。

## 3. 覆盖的失败关闭场景

30 个 release/guard 专项测试覆盖：

- 错误日期、16:05 前、19:00 后；
- 工作树脏、`HEAD != origin/main`、发布审计非 PASS；
- promoted current、候选运行时身份、旧容器 image/snapshot/Git/health 漂移；
- 最新 Top30 执行日或代码快照漂移；
- readiness 模式错误或出现多个新交易日；
- dry-run 零启动、execute 唯一一次启动、候选已激活幂等；
- 定向 Docker inspect 不请求 `.Config.Env`。

所有前置失败均断言 `start_calls == 0`。

## 4. 真实只读复核

- 本地官方交易日历在 2026-07-30 16:05 返回 watermark `20260729`、eligible target `20260730`、
  唯一 missing trade date `20260730`。
- 发布审计链 22 条 PASS，tip SHA-256 `48b40297...4d9c`。
- promoted current 与冻结候选四项身份精确一致：image ID `722f63de...3b76`、代码快照
  `4e5244b6...2708`、Git `210af4d...f3`。
- 当前 scheduler 仍为容器 `fd8e9615...adbb`、旧 image ID `de87ec74...0261`、旧代码快照
  `eb8e7521...7fbd`、Git `ecda815...f24`，状态 healthy。
- 首次真实定向复核暴露 Docker format 分隔符兼容问题；守护在生产变更前返回 BLOCKED。实现随后改用
  明确 `|` 分隔并以真实容器复核通过，失败尝试未启动、重启或修改 scheduler。
- 2026-07-29 实时时钟调用守护返回 `BLOCKED: guard target date does not equal the local date`，证明今晚
  不会提前执行。
- 工程提交推送并恢复干净工作树后，以明日16:05时钟注入、真实其余依赖执行完整只读门，返回
  `READY`、唯一新交易日`20260730`、最新旧快照执行日`20260729`和`start_invoked=false`。

## 5. 测试

- 全仓：382 PASS，1 条既有 Starlette 第三方弃用 warning。
- 本机 release/guard 专项：30 PASS。
- Docker 开发容器专项：30 PASS。
- Ruff、compileall、`git diff --check` PASS。
- 容器专项前后生产 scheduler 的容器、镜像、创建周期和 healthy 状态不变。

## 6. 自动执行安排

Codex 本机项目一次性自动任务`top20`已安排在 2026-07-30 16:05 UTC+8 唤醒，只运行：

```text
make docker-release-guard
```

自动化不得改代码、补提交、重试到过期时点或绕过 BLOCKED。成功启动后仍需等待候选按冻结 19:30
口径自然跑批，并在当日晚间另作 Top30/Top20 完整验收。

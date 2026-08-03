# 日增量早探测下游静默等待补正协议

> 日期：2026-08-03（Asia/Shanghai）
>
> 协议：`p0-daily-early-readiness-notification-recovery-v1`
>
> 状态：`FROZEN_AFTER_INCIDENT_BEFORE_IMPLEMENTATION`

## 1. 已知事实与问题边界

本协议不是盲预注册。2026-08-03 Top20 生产候选在 17:39 启动后、19:31 当日数据到达前，scheduler
连续 7 次发送 `daily_scheduler_cycle_failed`，稳定消息 ID 均为 `ce3bfbf96e9ec474`。每次失败均发生
在日增量返回后继续执行旧影子/模拟仓验收时：旧 `FORWARD` 产物属于旧代码快照，当前验收按设计拒绝
把它冒充当前受控快照。

19:31 数据到达后，原链路自动完成日增量、影子、Top30 和 Top20 并恢复 PASS；没有日增量 FAIL
账本、人工补跑、修数或容器重启。证据见
`docs/PAPER_TOP20_FORWARD_ACCEPTANCE_20260803.md`。

`p0-daily-early-readiness-v1` 已冻结“16:00—19:29 来源未齐返回 `WAITING_SOURCE`，零业务写入、零失败
通知、health 仅记录脱敏状态和目标日期”。现有日增量函数满足该语义，但 scheduler 无条件继续影子和
模拟仓，形成下游通知缺口。本补正只闭合这一处编排语义，不改原数据或策略协议。

## 2. 冻结补正

1. 当且仅当 `daily.run_once()` 返回 `status=WAITING_SOURCE` 时，scheduler 本轮必须：
   - 写入 `health.status=waiting_source` 和脱敏目标日期；
   - 不调用影子周期；
   - 不调用 Top30/Top20 模拟仓、重放或前瞻验收；
   - 不发送 `daily_scheduler_cycle_failed` 或其他业务通知；
   - 正常等待下一次 15 分钟轮询，不进入 degraded。
2. 当日五类输入通过探测并由正式路径返回 `PASS` 后，继续执行原影子、信号、Top30、Top20、重放和
   验收顺序，不得减少任何下游门禁。
3. 北京时间 19:30 起，日增量不再返回来源静默等待；正式请求或后续任何异常仍必须按原逻辑写失败
   证据、发送飞书并使 scheduler degraded。
4. `NOOP`、历史缺口补采、锁竞争和真正异常的语义保持不变；本补正不得把代码快照不一致在一般路径
   上降级为忽略，也不得修改 `paper_forward_acceptance` 的失败关闭门。
5. 不修改数据源、请求字段、完整性门、`.BJ` 排除、S1—S10、信号、模型、Top30/Top20 策略、账户、
   模拟成交、账本 schema、发布挂载或通知重试规则。

## 3. 验收门

- 单元测试必须从 scheduler 顶层证明 `WAITING_SOURCE` 时 shadow/paper 调用均为 0、通知为 0、返回码
  为 0，health 状态序列包含 `waiting_source` 与目标日期。
- 既有测试继续证明来源就绪进入正式路径、19:30恢复失败关闭、历史缺口不静默等待。
- 全仓 `make test`、Ruff、`compileall`、`pip check`、三套 Compose 解析、`git diff --check` 和脱敏门
  全部通过。
- 构建新的不可变 scheduler 候选并在断网、只读根、最小挂载条件下执行相关 fixture；不得覆盖当前
  生产镜像、current 标签或运行容器。
- 代码与候选通过只能裁决 `GO_EARLY_READINESS_NOTIFICATION_RECOVERY_ENGINEERING_ONLY`；真实生产
  仍须等待后续另一新交易日窗口，按既有 release guard 单独提升并观察首次探测、首次就绪、整日
  PASS、`.BJ=0`、两账户、通知、重放与幂等。

## 4. 非目标

- 不把今晚 7 次告警从账本或报告删除，也不改写既有 `PASS_WITH_NOTIFICATION_WARN`；
- 不宣称单日即可证明 16:00—17:00 稳定完成率；
- 不在 2026-08-03 晚间切换或重启生产；
- 不借机修改纸面账户、策略参数、模型、Web 或研究计划；
- 不对 `NOOP` 做宽泛静默，避免掩盖非交易日或发布门禁之外的快照问题。

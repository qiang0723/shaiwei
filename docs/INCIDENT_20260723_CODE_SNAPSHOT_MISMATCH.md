# 2026-07-23 生产代码快照失配事件与隔离门禁

## 结论

2026-07-23 日周期两次在 `paper_forward_acceptance` 阶段失败，错误均为 FORWARD 产物代码快照与
当前受控代码不一致。scheduler 随后恢复 PASS，生产数据、信号和账户账本未发现被人工改写；但现有
证据无法还原当时具体漂移文件，因此根因只能裁定为：**生产 scheduler 直接挂载开发工作树，使开发
受控文件变化能够改变运行时快照**。不得把恢复后 PASS 当作防复发措施。

证据边界：

- 两次 `daily_scheduler_cycle_failed` 留痕位于 `logs/notifications/feishu_20260723.jsonl`；
- 失败点均为 “FORWARD artifact code snapshot is not current controlled code”；
- 当前 scheduler 已恢复健康；
- 未发现可证明某个具体文件是当时漂移源的不可变证据，因此不作臆测归因。

## 影响

- 当日核心数据采集与已有不可变产物未被证明损坏；
- 每日周期在最终模拟仓验收处失败并触发飞书告警；
- 若继续让生产容器挂载整个开发仓库，未来 P2、Web 或其他 `src/config/tests/compose` 施工仍可能让
  scheduler 在无发布动作时改变代码身份。

## 恢复与本次验证

恢复后 scheduler 重新 PASS。P1 施工全程只改 `tools/p1_moneyflow/`、文档和脱敏研究 ledger，
生产代码快照持续保持
`261f58b858dbc46d49ffb9f623e8868dcb10891cc2dadd2292728da6de7eb4fa`；这证明隔离研究目录可以避免
再次触发快照漂移，但不解决生产与未来开发目录的结构性耦合。

## 强制门禁（P2 / Web 后端施工前）

后续必须另立目标实现并验收以下边界：

1. scheduler 使用不可变发布镜像或独立 release checkout，代码不得从开发工作树整仓可写挂载；
2. 只显式挂载运行必需的数据、日志和追加式 ledger，代码与配置只读且绑定镜像 digest/发布快照；
3. 开发任务使用独立 profile/容器，不得共享生产代码目录或 Docker socket；
4. 发布前验证镜像内 `code_snapshot_sha256` 等于批准值，失败即不启动；
5. 保留当前和上一发布快照及回滚证据，发布/回滚均写结构化记录；
6. 以一次模拟开发改动证明 scheduler 快照不变，再以受控发布证明快照只在发布动作后改变。

在该门禁通过前：P2 与 Web 后端不得修改或启动生产 `src/config/tests/compose` 路径；Web 只允许继续
文档、视觉原型和不接真实数据的设计工作。

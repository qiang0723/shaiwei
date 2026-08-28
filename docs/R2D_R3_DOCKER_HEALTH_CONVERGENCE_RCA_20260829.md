# R2D-R3 Docker 健康状态收敛竞态 RCA 与恢复协议

## 1. 裁决

`R2D-R2` scope `a2e66d95dc13d3ea71d9068a880d9074300955c82a553fa867c985bfa2b729d5`
已于 2026-08-28 唯一执行中关闭，永久不得重跑。事件属于发布观测竞态，不是候选镜像身份、named-volume
锁、行情数据、模型或策略结果失败。

当前终态为 `BLOCKED_RECOVERED_OLD_PRODUCTION / R2D_R3_ENGINEERING_ONLY`。本文只授权
RCA、代码、测试和恢复工程，不授权 build、fixture 实跑、promote、start、restart、业务跑批、密钥、
外网、Web、模型或策略改动。

## 2. 不可变证据

发布审计链证明两次底层动作均真实成功：

- 16:41:32，候选 `b7565001...aa72` 写入 `START_PASS`，记录
  `613b8dda...0080`；镜像、代码快照、Git、只读根、named-volume 锁和四挂载全部精确匹配。
- 16:42:14，旧生产 `722f63de...13b76` 写入 `START_PASS`，随后写入
  `ROLLBACK_PASS` `329caa37...a75b`。
- 上层守卫最终返回：`RESUME_START failed and previous release restoration also failed:
  previous release restoration did not recover the healthy scheduler`。
- 候选在回滚前留下 5 条 append-only 时间线，止于 16:41:34
  `DAILY_COLLECTION STARTED`；不得删除、补造或解释为完整候选自然周期。
- 旧生产随后自然形成 20260828 daily PASS，以及 Top30/Top20 两账户 PASS；当前 release
  `current` 仍为旧生产，scheduler healthy。它们不计入候选稳定性。

旧错误包装丢失了首次 `_verify_active` 的内层消息，因此首次误判只能做高置信控制流重建，不能伪称
拥有原始报错。第二次恢复误判由上列 `START_PASS/ROLLBACK_PASS` 与紧随其后的上层失败直接证明。

## 3. 根因

`release._wait_scheduler_contract` 原实现只等待：

1. 镜像、代码快照、Git、只读根和挂载合同通过；
2. 容器内 `python -m shaiwei.pipeline.scheduler --healthcheck` 返回 0。

它没有等待 Docker 自身 `.State.Health.Status` 从 `starting` 收敛到 `healthy`。Compose 的
启动健康探测节拍为 10 秒，而守卫在 `start_current()` 返回后立即二次读取 Docker health 元数据，
因此可能把已经通过内部健康检查的同一容器误判为未健康并触发回滚；回滚后同一竞态再次发生。

## 4. R2D-R3 唯一工程变化

1. `_container_contract` 同时要求 Docker health 元数据精确等于 `healthy`；
2. 原有 60 秒 `_wait_scheduler_contract` 继续轮询，只有“Docker health + 内部 healthcheck”均通过
   才写 `START_PASS`；
3. 镜像 ID、代码快照、Git、只读根、挂载和锁 authority 门全部保持，不增加宽松兜底；
4. 守卫错误必须同时保留首次启动错误和恢复错误，后续 RCA 不再丢失首因；
5. 单元回归覆盖 `starting → healthy`，并证明未收敛前不会读取运行身份或写 `START_PASS`。

## 5. 下一执行节点前的强制门

R2D-R3 代码提交后会形成新代码快照，旧候选不得直接复用为后继生产候选。下一节点必须另立精确
build/fixture scope，并在用户逐字批准后：

- 恰好构建一个内容寻址候选；
- 用同一候选、同一 Compose 启动入口、同一四挂载和真实 Docker health 元数据运行一次断网 daemon
  路径彩排，显式观测至少一次 `starting` 后收敛为 `healthy`；
- 验证成功路径不触发 rollback，故障路径仍能恢复旧生产；
- 将镜像、scope、彩排报告、审计链和代码身份逐哈希绑定。

彩排全绿后仍不得直接启动生产，须基于新的自然交易日边界另立一次性 start scope。R2D-R2 以及本
RCA 中 20260828 的短暂候选运行均不得被复用为后继授权或稳定性次数。

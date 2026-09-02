# R2D-R3C 过期窗口恢复协议

## 目标

R2D-R3B 的 Phase A 与 Phase B 在未批准、未执行的状态下分别于 2026-08-30 和 2026-08-31 过期。
本恢复节点只重新绑定新的自然交易日边界，不重建候选、不重跑 R3A fixture、不复用旧 scope，也不
改变任何发布、健康、锁、账户或首日验收门。

## 永久保留的前序事实

- R3B Phase A scope `c4074e54aea3253a4798f73755c1a37207ec4bfb249e932c4352305c68c5f795`
  的 `approval_recorded=false`；它未执行、未消费生产 mutation，现永久标记为过期且不得复用。
- R3B Phase B 未生成独立 scope，候选从未因 R3B 启动。
- 候选继续固定为 `shaiwei:scheduler-97d8c05eab2a1e8c`，镜像 ID
  `sha256:b64ae11b76c4005876781085c1bdfa08dc500153cd5645594de2fb90b7cc5ebe`，不得重建。
- R3A 恢复 scope `49a322aefb9039126c7590f0b07d60fcad3f1398fa7f2ca6412e52dc3d427017`
  六门 PASS；report/tree/receipt 继续按原哈希封存，不得重跑。
- 当前 release 与运行容器仍是旧生产 `4e5244b6...2708` / `722f63de...13b76`；R3C 不把旧生产
  在等待期间形成的自然账本增量视为漂移或清理对象。

## 新自然边界

本地冻结交易日历 `data/qlib_forward/versions/4e5244b6b027-39d8fe9d34d9/calendars/day.txt`
（SHA-256 `c9916944c6865cf4e1e6b15af7ac90a54d2275320d25353873071f08d892b114`）确认
20260902 与 20260903 均为开市日。

### Phase A 前置闭环

20260902 旧生产必须自然完成且全部满足：

- daily、shadow、Top30、Top20 均为 PASS，操作身份仍为 `docker-scheduler`；
- 双账户执行日、信号、reconciliation、数据/代码快照、policy 与不可变产物哈希相互闭合；
- `.BJ=0`、重放/会计/新鲜度和既有通知门通过；
- Docker 旧生产仍 healthy、重启次数和运行身份无异常；
- release state/audit、候选、R3A 证据和控制器组件无漂移。

任一项不成立时停止，不得手工跑批、补账、顺延同一 scope 或用 20260901 旧产物代替。

### Phase A：只提升、不启动

只有上述自然闭环完成后，才允许生成新的机器 config 与精确 scope。它必须逐哈希绑定 20260902 最新
双账户产物、届时 Git HEAD/origin 跟踪引用、release state/audit、旧生产、候选和 R3A 证据。建议执行
窗口为 20260902 20:45—23:30 UTC+8；窗口过期即 scope 失效。

用户逐字批准精确 scope 后，唯一允许的生产动作是一次 `promote_no_start`。执行后 current 必须为
候选、previous 必须为旧生产，旧容器保持原身份和 healthy。不得 start/restart、读取密钥、访问外网、
运行业务或回填。

### Phase B：下一自然边界启动

Phase A 成功不授权 Phase B。20260903 16:40—19:00 UTC+8 只能在另立 config、另立 scope、另获逐字
批准后执行一次 `start_current`。除继承全部身份门外，还必须满足：

- 旧容器在 20260903 16:00 后形成新鲜 `noop / 20260902`；
- 20260903 daily/shadow/paper 全状态记录均为 0；
- readiness 为 `CROSS_SNAPSHOT_WITH_NEW_DATA` 且唯一日期为 20260903；
- 双账户最新 FORWARD 仍精确绑定 20260902 自然产物；
- candidate、四挂载、named-volume lock authority、R3A 证据及 Phase A 后 release state 无漂移。

启动后只核验候选身份、四挂载和 healthy，业务等待自然调度。候选首个自然交易日的 daily、shadow、
双账户、重放、`.BJ=0`、通知和 timeline 全门通过前，R2D 不得正式关闭。

## 授权与停止点

本协议只授权协议、机器 config/scope 生成器的必要兼容工程和合成测试；当前不授权任何生产 mutation、
真实效果读取、外网、密钥、DeepSeek、手工跑批、历史回填、候选重建、fixture 重跑或模型/信号/策略/
Web 变更。

当前停止点是等待 20260902 旧生产自然闭环。闭环后先生成并报告 Phase A 的完整 config SHA、scope SHA、
唯一命令、时间窗、前后 release 身份和失败边界；取得用户明确授权前不得执行。

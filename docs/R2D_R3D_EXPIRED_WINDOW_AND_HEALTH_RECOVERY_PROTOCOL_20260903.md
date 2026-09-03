# R2D-R3D 过期窗口与旧生产健康恢复协议

## 目标

R2D-R3C Phase A 在未生成新 config/scope、未批准、未执行的状态下于 2026-09-02 23:30 过期，
因此原定 2026-09-03 Phase B 不再成立。本节点只把两阶段切换重新绑定到下一组自然交易日边界，并
把 2026-09-03 观察到的旧生产健康短暂失收敛纳入前置门；不重建候选、不重跑 R3A fixture、不复用
任何旧 scope，也不改变发布、锁、账户或首日验收语义。

## 永久保留的前序事实

- R3B Phase A scope `c4074e54aea3253a4798f73755c1a37207ec4bfb249e932c4352305c68c5f795`
  未获批准、未消费生产 mutation，永久过期且不得复用。
- R3C 只冻结了恢复协议；没有生成后继 config/scope，没有 promote/start/restart，故其 Phase A 已过期，
  Phase B 没有独立授权基础。
- 候选继续固定为 `shaiwei:scheduler-97d8c05eab2a1e8c`，镜像 ID
  `sha256:b64ae11b76c4005876781085c1bdfa08dc500153cd5645594de2fb90b7cc5ebe`；不得重建。
- R3A 恢复 scope `49a322aefb9039126c7590f0b07d60fcad3f1398fa7f2ca6412e52dc3d427017`
  六门 PASS，封存 report/tree/receipt 不重跑、不改写。
- release current 和运行容器仍绑定旧生产代码快照 `4e5244b6...2708`、镜像 ID
  `722f63de...13b76`；等待期间形成的自然数据、日志和追加式账本全部保留。

## 20260903 健康观察

2026-09-03 12:26 UTC+8 定向只读检查显示旧 scheduler 容器仍在运行、重启次数为 0、只读根与
`/workspace/data`、`/workspace/ledger`、`/workspace/logs`、`/run/shaiwei-locks` 四挂载完整，但 Docker
health 为 `unhealthy`；最近五次 healthcheck 均因心跳超过既有 3600 秒陈旧门而退出 1，未输出错误。
容器主进程仍存活，最近完整业务日志止于 10:59 的 `noop / 20260902`。12:29 旧进程在无人工动作下
重新写入同一 `noop / 20260902` 心跳，容器未重启。

该观察只能说明心跳已自然恢复一次，不能提前宣告 Docker health 收敛，更不能作为放宽陈旧阈值、
手工触发业务或绕过旧生产健康门的理由。原始健康记录与日志保持不改。

## 新自然边界

冻结交易日历
`data/qlib_forward/versions/4e5244b6b027-39d8fe9d34d9/calendars/day.txt`
（SHA-256 `c9916944c6865cf4e1e6b15af7ac90a54d2275320d25353873071f08d892b114`）确认
20260903、20260904 均为开市日。

### Phase A 前置闭环

20260903 旧生产必须自然完成且全部满足：

- daily、shadow、Top30、Top20 均为 PASS，操作身份仍为 `docker-scheduler`；
- 双账户执行日、信号、reconciliation、数据/代码快照、policy 与不可变产物哈希相互闭合；
- `.BJ=0`、重放/会计/新鲜度和既有通知门通过；
- Docker health 已按原 healthcheck 自然收敛为 `healthy`，重启次数仍为 0，运行身份、四挂载和
  named-volume lock authority 无漂移；不得用手工改写 health 文件或放宽 3600 秒门取得健康；
- release state/audit、候选、R3A 证据和控制器组件无漂移。

任一项不成立即停止。不得 restart、手工跑批、补账、顺延同一 scope，或用 20260902 产物替代。

### Phase A：只提升、不启动

只有上述自然闭环完成后，才允许机械生成新的机器 config 和精确 scope。它必须逐哈希绑定 20260903
最新双账户产物、届时 Git HEAD/origin 跟踪引用、release state/audit、旧生产、候选、R3A 证据和本协议。
建议执行窗口为 20260903 20:45—23:30 UTC+8；窗口过期即 scope 失效。

用户逐字批准精确 scope 后，唯一允许的生产动作是一次 `promote_no_start`。执行后 current 必须为
候选、previous 必须为旧生产，旧容器保持原身份和 healthy。不得 start/restart、读取密钥、访问业务
外网、运行业务或回填。

### Phase B：下一自然边界启动

Phase A 成功不授权 Phase B。20260904 16:40—19:00 UTC+8 只能在另立 config、另立 scope、另获逐字
批准后执行一次 `start_current`。除继承全部身份门外，还必须满足：

- 旧容器在 20260904 16:00 后形成新鲜 `noop / 20260903`；
- 20260904 daily/shadow/paper 全状态记录均为 0；
- readiness 为 `CROSS_SNAPSHOT_WITH_NEW_DATA` 且唯一日期为 20260904；
- 双账户最新 FORWARD 仍精确绑定 20260903 自然产物；
- candidate、四挂载、named-volume lock authority、R3A 证据及 Phase A 后 release state 无漂移。

启动后只核验候选身份、四挂载和 healthy，业务等待自然调度。候选首个自然交易日的 daily、shadow、
双账户、重放、`.BJ=0`、通知和 timeline 全门通过前，R2D 不得正式关闭。

## 授权与停止点

本协议只授权文档和后续机械 config/scope 生成所需的普通工程；当前不授权任何生产 mutation、真实效果
读取、外网、密钥、DeepSeek、手工跑批、历史回填、候选重建、fixture 重跑或模型/信号/策略/Web 变更。

当前停止点是等待 20260903 旧生产自然闭环及 Docker health 按原门持续收敛。闭环后先生成并报告
Phase A 的完整 config SHA、scope SHA、唯一命令、时间窗、前后 release 身份和失败边界；取得用户
明确授权前不得执行。

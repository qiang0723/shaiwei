# R2D-R1 旧生产 19:30 截止时钟证据恢复协议

## 1. 已知事实与原 scope 终态

R2D Phase A 已于 2026-08-25 唯一完成，release state 为 `current=候选 / previous=旧生产`，候选没有
启动，旧 scheduler 容器继续健康运行。原 release scope
`4145d6018a1cb38f48432677dce1e68558cdaf48ad5c3e81d12f7067eac58292` 的 Phase B 固定窗口为
2026-08-26 16:05—19:00，并要求旧容器在窗口内写出 `waiting_source / 20260826`。

2026-08-26 结果盲核对旧镜像实物确认：旧生产 snapshot `4e5244b6...2708` 的
`daily.ready_hour/minute` 为 19:30。它在 19:30 前只会把当日视为尚未到期并持续写
`noop / 20260825`，不可能在 19:00 前形成协议要求的当日 `waiting_source`。因此原 Phase B 是一个
不可满足的证据门，不是数据源故障、锁失败或候选失败。

原 scope 于 19:00 过期，Phase B mutation 为 0，永久不得重用、改日期或补造 `waiting_source`。
Phase A 的已完成状态保留，不重复 promote。

## 2. 2026-08-26 自然周期边界

旧生产在自身 19:30 时钟下完成 20260826 自然周期：

- daily PASS：5 批、15,649 行，数据快照 `1cf30882...fd615`，实际原始批次 `.BJ=0`；
- shadow PASS：S1—S9 PASS、S10 NOT_APPLICABLE，信号 `c6b44522...6786b`；
- `model_baseline` / `model_top20` 均 PASS，产物分别为 `8d15c3aa...fd36c` /
  `d64083f5...86ac`；
- 日增量、影子、两个模拟账户的开始/完成飞书通知全部 PASS；
- 旧生产代码快照保持 `4e5244b6...2708`，候选没有启动。

这证明本次恢复只涉及发布证据合同，不涉及修复业务周期。

## 3. 唯一恢复变量

后继只替换旧容器“不进入目标日写路径”的证明方式：

1. 目标日改为下一官方交易日 20260827，窗口保持 16:05—19:00；
2. 旧容器必须仍是冻结的 healthy legacy 身份；release state 必须仍为
   `current=候选 / previous=旧生产`；
3. 旧健康文件必须在 20260827 当日 16:00 后新鲜写出 `noop / 20260826`；
4. daily、shadow 和两个 paper 账本中 20260827 行数必须均为 0；
5. 现有 cross-snapshot readiness 必须只暴露 `[20260827]`；
6. 上述五门同时成立才允许一次 `start_current`。候选启动后的首个自然周期继续承担 timeline、锁、
   daily、shadow、双账户、通知、幂等和 `.BJ=0` 完整验收。

该组合等价证明“旧容器尚未进入 20260827，候选是唯一有资格消费该日的 writer”。它不要求旧镜像
产生其代码路径在该时钟下不可能产生的状态，也不降低新日期唯一性、身份、四挂载或首日验收门。

## 4. 保持不变

- 候选镜像、image ID、Git、代码快照和 named-volume authority 不变；
- R2C-R1 10/10 fixture 及 report/tree/receipt/scope 哈希不变，不重建、不重跑；
- Phase A 不重复；旧容器与候选绝不并行；
- 启动失败仍只允许候选完全停止后顺序恢复旧容器；候选首次真实业务写入后自动旧版回滚关闭；
- Top30/Top20策略、模型、信号、数据口径、门禁、Web、模拟仓规则均不改；
- 本节点不读取策略效果，也不产生策略有效性结论。

## 5. 当前授权与停止点

本协议只授权恢复源码、测试、配置、文档和零生产本地验证。不授权 build、fixture、promote、restart、
`start_current`、手工跑批、历史回填、密钥、外网或生产业务。

实现完成并推送后，必须用最终控制器 HEAD/组件哈希、20260826 最新双账户产物、候选/旧生产身份和
20260827 窗口生成新的精确 release scope。用户未逐字批准该新 scope 前必须停止。

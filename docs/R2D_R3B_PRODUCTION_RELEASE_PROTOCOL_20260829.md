# R2D-R3B 生产切换协议

## 目标

在不重建候选、不重跑 R3A fixture、不手工跑批的前提下，把已通过真实健康收敛彩排的 named-volume scheduler 候选分两阶段切换：2026-08-30 仅 promote-no-start，2026-08-31 在旧生产自然边界和所有身份门通过后才允许 start-current 一次。

## 结果前冻结事实

- 下一交易日为 20260831；20260828 旧生产自然周期已完成 daily、shadow、Top30/Top20、哨兵和通知 PASS，`.BJ=0`、零人工修数；
- 候选固定为 `shaiwei:scheduler-97d8c05eab2a1e8c`，镜像 ID `sha256:b64ae11b...c5ebe`，不得重建；
- R3A 恢复 scope `49a322aef...27017` 六门 PASS，report/tree/receipt 均按 SHA-256 封存，不得重跑；
- 旧生产固定为 `shaiwei:scheduler-4e5244b6b02739dd`，当前 healthy；
- 控制器基础提交 `38827399b2b4c58198aa3c043f76a33a2e704408` 已先推送，六组件 SHA-256=`e8e7f091...68a5b`。

## Phase A：只提升、不启动

协议：`config/r2d_scheduler_release_guard_r3b_prepare_v1.yaml`，SHA-256=`79207190...d6d80`。

仅允许 20260830 20:45—23:30 UTC+8 在精确 scope 和用户批准后执行一次 `promote_no_start`。必须先校验 pushed controlled tree、控制器六组件、R3A 封存证据、候选运行身份、旧生产 healthy/三挂载及 release pre-prepare state。执行后 current 必须等于候选、previous 必须等于旧生产，旧 scheduler 容器必须保持原身份和 healthy。不得 start/restart、读密钥、访问外网或运行业务。

## Phase B：自然边界后启动

协议：`config/r2d_scheduler_release_guard_r3b_start_v1.yaml`，SHA-256=`48dca016...bace`。

仅允许 20260831 16:40—19:00 UTC+8，且需另立新 scope、另获用户批准。除 Phase A 后精确 release state 外，还必须同时满足：

- 旧 scheduler healthy；20260831 16:00 后形成新鲜 `noop / 20260830`；
- 20260831 daily/shadow/paper 全状态记录均为 0；
- readiness=`CROSS_SNAPSHOT_WITH_NEW_DATA` 且唯一日期为 20260831；
- 双账户最新 FORWARD 仍精确绑定 20260828 产物；
- 候选、R3A 证据、控制器、四挂载和 named-volume 锁 authority 均无漂移。

任一门失败、窗口过期、scope 已消费或身份漂移，均不得重跑、顺延、补造或手工跑批。启动后只核验候选身份、四挂载和 healthy；业务只能等待自然调度。失败恢复继续使用既有顺序回滚边界。

## 授权隔离

两个阶段使用独立 scope。批准 Phase A 不等于批准 Phase B；本协议施工和推送不等于任何生产 mutation 授权。两阶段均不授权候选重建、fixture 重跑、历史回填、模型/信号/策略/Web 改动或读取密钥。

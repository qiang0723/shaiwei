# Top20 模拟账户首个自然 FORWARD 验收（2026-08-03，UTC+8）

协议：`paper-top20-forward-acceptance-20260803`

## 1. 权威结论

2026-08-03 19:30 自然跑批完成后，Top30 基线账户与 Top20 比较账户的日增量、影子、信号、
模拟仓、重放和机器验收链路均通过。Top20 首个由受控生产 scheduler 自然生成的 `FORWARD`
账户日裁决为 **PASS_WITH_NOTIFICATION_WARN**：核心业务链路 PASS，发布切换期通知 WARN。

WARN 来自新 scheduler 在当日新数据到达前，对旧代码快照生成的 2026-07-31 模拟仓产物执行当前
快照验收，连续 7 次按失败关闭发出同一稳定消息 ID 的告警。19:31 新数据到达后，scheduler 无人工
干预地完成追赶、影子和两账户运行并恢复 PASS；正式日跑批账本没有追加 FAIL，账本和产物没有人工
修数。该告警必须保留，不能把本次表述为“全链路无告警”。

本结论只证明 Top20 账户完成首次自然生产闭环，不证明 Top20 优于 Top30，也不构成策略有效、实盘
交易或真实委托授权。Top20 机器账本中的 6 个 `FORWARD` 包含本次生产切换时对 2026-07-27—31 的
受控追赶；只有 2026-08-03 是本候选首次由常驻生产 scheduler 自然生成的账户日。

## 2. 生产身份与日增量

| 对象 | 权威证据 |
|---|---|
| scheduler 容器 | `183b8c6c5eddac951d9d9b3cfa58c0d38e351d5b94ee1b1d52b9b8059c23dd3b` |
| scheduler 镜像 | `sha256:722f63de15932cb2698e82db7c0140f02921f27f126e1c0235ca62e0a1213b76` |
| 镜像 Git | `210af4dab33c85b38c05b28f56c176b7970c41db` |
| 受控代码快照 | `4e5244b6b02739dd209a9b01ea715c43ed9a874a7014156e20cf364f06a82708` |
| 数据快照 | `399c97edb546d3e6d7bb375633cdc8f2fd1f435a2affa7ae06392a8ef7e3a4c9` |
| 日增量运行 | `0e17435bc0fa` / `20260803` / `PASS` |
| 运行时间 | `2026-08-03 19:32:09—19:32:12 +08:00` |
| operator | `docker-scheduler` |

- 日增量正式统计为 5 个市场批次、15,621 行；加上三份证券状态刷新，当日实际新增 8 个不可变
  原始 Parquet、21,158 行。
- 逐文件重算行数与内容 SHA-256 均一致；实际新增原始记录 `.BJ=0`。
- scheduler 提交前仍为同一容器和镜像，状态 `healthy`；根文件系统只读，挂载仍仅为
  `/workspace/data`、`/workspace/ledger`、`/workspace/logs`。

## 3. 哨兵、影子、信号与次日对账

- 哨兵产物 `logs/sentinels/20260803T114804.213885Z.json`，物理 SHA-256 为
  `89516fa3f03613ee946010ec5cf6f4610b5d7bb8222bb4205091442b433695bb`；S1—S9 全部 `PASS`，
  S10 为 `NOT_APPLICABLE`，必需失败数为 0。
- 影子运行 `f5debc8cd2e4` 为 `PASS`，代码/数据快照与本次生产身份一致，信号准时且
  `rebalance_due=false`。
- 新信号 `data/shadow/signals/20260803-4e5244b6b027-399c97edb546.json` 的物理 SHA-256 为
  `7b17103ac55f11cccbd13e0e79ffcad1c979d90a3fe93c1a8f258765badc2db9`；800 个分数、30 个目标、
  `.BJ=0`，冻结策略仍为 Top30、10 日调仓。
- `20260731 → 20260803` 次日开盘对账为 `PASS`，产物
  `data/shadow/reconciliations/20260731-20260803-3ce150eec9d4.json`，SHA-256 为
  `da7e2a64e4d7408b6ca01334491bf1f6bfbcb77771765e1e393f2f2b2e389227`。
- 本日不是调仓日，因此 30 个目标观察行没有交易腿，换手与预计成本均为 0；这不是“30 个目标均
  不可成交”。目标平均绝对开盘偏差为 `1.215002887%`。

## 4. 两个模拟账户

| 指标 | Top30 `model_baseline` | Top20 `model_top20` |
|---|---:|---:|
| 初始资金 | 500,000 RMB | 500,000 RMB |
| 当前模式 | FORWARD | FORWARD |
| 实际持仓数 | 22 | 17 |
| 当日订单/成交 | 0 / 0 | 0 / 0 |
| 净资产 | 457,426.77 RMB | 447,669.22 RMB |
| 归一化净值 | 0.91485354 | 0.89533844 |
| 基准净值 | 0.964785935 | 0.964785935 |
| 会计恒等差 | 0.00 RMB | 0.00 RMB |
| 重放运行数 | 12 | 12 |
| 模式计数 | BACKFILL 4 / FORWARD 8 | BACKFILL 6 / FORWARD 6 |
| 重放结果 | PASS | PASS |
| 机器验收 | PASS | PASS |

- Top30 产物 `data/paper/model_baseline/runs/20260803-3ce150eec9d4.json`，SHA-256 为
  `ff8ddb0beb9e468611bdc527e3c0ee8c4dda08da3bef4ebd043328e91f671235`，策略 SHA-256 为
  `eaa341b5a3eee94347c7a8453a3e52f1986e3707abfbb6bb69a6d9298c320cc8`。
- Top20 产物 `data/paper/model_top20/runs/20260803-3ce150eec9d4.json`，SHA-256 为
  `f0c4eae56bd4f90bd3ea5578c014f8a024d2df9aa796b38e60b56e5de2c326fc`，策略 SHA-256 为
  `d11d773bd79719641dc1bbc35976d4899fddb730d0f3673094cb6f20cc7840c8`。
- Top20 仅将同一份不可变 Top30 信号按原排名投影为前 20 并等权到 5%；投影 SHA-256 为
  `ecb5bc2d50f2f04f412716ef8b51ea8211cf69beae2e47322cbe8de6eac4068a`。它不是新模型，也没有
  改写 Top30 账户。
- 两账户价格日期新鲜、`.BJ=0`，净资产严格等于现金加持仓市值；只读重放、快照和验收没有写入
  账户或覆盖产物。

## 5. 通知、恢复与幂等

- `logs/notifications/feishu_20260803.jsonl` 最终 SHA-256 为
  `9060d1dabf58fadfa9da4838f30059582968636e5db52f5f9775aeb3c3fa3abd`；日增量追赶开始/完成、
  影子对账、信号生成、Top30 开始/完成和 Top20 开始/完成均在首个投递尝试 `PASS`。
- 17:39:51—19:16:35 之间共有 7 条 `daily_scheduler_cycle_failed`，稳定消息 ID 均为
  `ce3bfbf96e9ec474`，飞书投递均 `PASS`。原因均为旧 `FORWARD` 产物代码快照不等于当前受控
  快照；系统按失败关闭，没有把旧产物冒充当前验收结果。
- 19:31 新数据到达后，系统自动完成追赶和恢复；日增量、影子和两账户最终均 PASS，没有人工补跑、
  修数、删除失败证据或重启 scheduler。
- 完整链路自动运行后，再次调用两账户只读重放、快照和验收均为 PASS，模拟仓产物及共享账本哈希
  不变，证明查询和验收幂等；没有通过重复业务写入来制造通过结果。

## 6. 追加账本证据

本次相对启动前只发生追加：日增量 1 行、采集批次 8 行、影子运行 1 行、影子对账 1 行、实验/信号
登记 1 行、模拟仓运行 7 行和模拟仓事件 205 行，删除均为 0。新增日增量、影子、对账和模拟仓 operator
均为 `docker-scheduler`，新增采集批次 operator 均为 `automation`，没有人工 operator。

| 账本 | 最终 SHA-256 |
|---|---|
| `daily_runs.csv` | `4f6f4430292883c590dca9bad45013b995c06bc0f7c36de651d0b5c4a9510926` |
| `ingest_batches.csv` | `6ed71ac3d487d02a6541b21d7abbfa14c0ed1763d026ac9f0654d3fafa6c1404` |
| `shadow_runs.csv` | `6ec7cb39193fcae879ff8360ca4eebb874e2846798ec9e75a8fdcb0bab7e9aea` |
| `shadow_reconciliations.csv` | `f321814e0e4cdafe4c83f7ace74d9fb4bb9989295ecce68d7735726c4d36ac0f` |
| `experiments.csv` | `4df226bc21a026621c8b327cb032f04fbd7899bec18b576043f18360ecf447e6` |
| `paper_events.csv` | `1be96c17853bf7816bad295f3920347fb17f1d78ed8e0ec69a440141c08073ce` |
| `paper_runs.csv` | `a6ddd5b167875154e3ae607edbb5b44f57c16e233c5716e30dcd6c0281dfc68c` |

## 7. 验收边界与下一步

- 全仓测试 `537 passed`；最终交付另执行 Ruff、`compileall`、`pip check`、Compose 解析、
  `git diff --check` 和脱敏检查。
- 本次不修改 `src/`、`config/`、模型、信号、门禁、Docker 配置或生产数据，只提交自然运行追加的
  正式审计账本与验收/状态文档。
- Top20 进入持续 `FORWARD` 观察；一个自然生产日只证明工程闭环，Web 必须继续显示
  `OBSERVING`，不得展示 Top20 优胜结论或年化、Sharpe、信息比率。
- P0-E 16:00 早探测候选现在满足“Top20 首次自然生产切换验收通过”这一前置条件，但仍须在后续
  **另一新交易日**单独受控提升并观察真实完成时点，不在本次验收中连带施工。
- 发布切换期的跨快照告警另列为后续调度健壮性观察项；在形成独立协议和测试证据前，不宣称
  16:00 候选已经自动消除该告警。

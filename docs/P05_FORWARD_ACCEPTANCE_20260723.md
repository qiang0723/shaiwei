# P0.5 模拟组合首个自然 FORWARD 验收（2026-07-23）

## 结论

`model_baseline` 已由常驻 Docker scheduler 自然完成 `20260722` 信号到
`20260723` 官方开盘/收盘证据的首个 `FORWARD` 账户日，P0.5 的工程与运行闭环结论为
**PASS**。

本结论证明信号、真实交易约束、订单/成交、持仓、现金、公司行为、费用、净值、
追加式账本、只读查询、重放、通知、幂等和异常恢复已经形成可持续闭环。当前只有
1 个 `FORWARD` 账户日，**不证明策略具有稳定 Alpha，也不得据此展示年化、Sharpe、
信息比率或策略有效性结论**。

## 冻结身份

| 对象 | 身份 |
|---|---|
| 账户 | `model_baseline`，初始资金 `500,000.00 RMB` |
| 基准 | 中证800 `000906.SH` |
| 执行策略 | `paper-v1` |
| 策略 SHA-256 | `eaa341b5a3eee94347c7a8453a3e52f1986e3707abfbb6bb69a6d9298c320cc8` |
| P0.5 受控代码快照 | `261f58b858dbc46d49ffb9f623e8868dcb10891cc2dadd2292728da6de7eb4fa` |
| 信号 SHA-256 | `3eef24f0d52ce08a220ea2be20ec37df9d8b0f2a577f322c607660851f7fd512` |
| 执行日数据快照 | `b7ef9171e848bad0fed0f892914bd82daac0d2e219f3482c0f308db07f696ab9` |
| 运行 ID | `a2d9e565973a4569e06c` |
| 运行产物 | `data/paper/model_baseline/runs/20260723-3eef24f0d52c.json` |
| 产物 SHA-256 | `fa39ea42988c90ad218f73bc8a8816b3806526448e46f499e9819317fadeef9f` |

## 时间与无未来数据

- `20260722` 信号于 `2026-07-22T11:45:43Z` 生成，早于任何 `20260723`
  行情入账。
- 冻结交易日历确认 `20260723` 是 `20260722` 后首个官方开市日。
- `20260723` 日增量于 `11:45:03Z` 完成，模拟仓运行于
  `11:54:19Z` 至 `11:54:22Z`；运行只引用精确日期的未复权日行情、
  停牌、基准和上一交易日信号。
- 每个持仓的估值 `price_date` 均为 `20260723`，`stale_trade_days=0`；
  没有未来日期、前填成交或事后追价。

## 数据、门禁与次日对账

- 日增量运行 `3b1d955b7c2f`：5 个市场批次、15,616 行，整日 `PASS`，
  operator 为 `docker-scheduler`。
- 加上三份 `stock_basic` 刷新，当日实际新增 8 个原始 Parquet、
  21,151 行；逐文件行数与 SHA-256 重算均一致，实际 `.BJ` 行数为 0。
- S1-S9 全部 `PASS`，S10 在开发环境为 `NOT_APPLICABLE`，必需失败数为 0。
- 影子对账产物
  `data/shadow/reconciliations/20260722-20260723-3eef24f0d52c.json`
  SHA-256 为
  `db7c5d544dd934e0148ffc2a96c07884a6f6f7db4a1250755b37de2b5faff038`。
- 本日为非调仓日，30 个目标观察行相对上一目标没有交易腿，因此
  `trade_count=0`、`executable_count=0`、换手与预计成本均为 0；
  这不是“30 个订单全部不可成交”。目标证券平均绝对开盘偏差为
  `1.3238039%`。

## 账户与会计

首个 `FORWARD` 日没有新订单、成交或公司行为，系统追加 22 条持仓、
1 条现金和 1 条 NAV 事件，共 24 条；序号严格为 1–24，全部 operator
为 `docker-scheduler`。

| 指标 | 2026-07-23 |
|---|---:|
| 实际持仓 | 22 只 |
| 现金 | 180,557.98 RMB |
| 持仓市值 | 298,225.30 RMB |
| 净资产 | 478,783.28 RMB |
| 归一化净值 | 0.95756656 |
| 中证800基准净值 | 1.0046598752 |
| 回撤 | -4.243344% |
| 当日费用 | 0.00 RMB |
| 累计费用 | 113.22 RMB |
| 累计现金分红 | 32.00 RMB |
| 会计恒等差 | 0.00 RMB |

账户与事件中 `.BJ` 均为 0。净资产严格等于现金加持仓市值；目标权重没有
被拿来覆盖实际持仓。

## 重放、查询与机器裁判

- `paper-verify` 从账户、事件和运行账本独立重放 5 个账户日、174 个事件、
  30 个历史订单和 22 笔历史成交，结果 `PASS`；模式为
  `BACKFILL=4/FORWARD=1`。
- 三份账本 SHA-256：
  - accounts：
    `2069b94f2a94da4feae1e15b490607cfa749ea2180ed1b3108f301a6c74d2ada`
  - events：
    `a679aa9884ef72cc13a1b24c73eb20ddc7482d3a3f873ed5dd50165726d47a39`
  - runs：
    `1790778144d4a1a4d128e4647c41edfcdf81e4d50473b4848ceb37cf5034f661`
- `snapshot` 返回 `mode=FORWARD/freshness_status=PASS`；
  `nav` 返回 `forward_status=PASS/forward_observation_count=1`。
- `paper-acceptance` 对代码/策略身份、Docker operator、新鲜度、
  `.BJ=0`、账本重放和飞书开始/完成证据 fail closed 后返回 `PASS`。

这些只读查询不连接券商、不写生产状态，也不允许 Web 自行重算账户真身。

## 飞书、恢复与幂等

- `paper_cycle_started` 与 `paper_cycle_completed` 均在第 1 次尝试投递
  `PASS`，使用不同且稳定的脱敏消息 ID。
- 同一自然周期中，日增量完成和影子对账通知各在第 1 次遭遇
  `NETWORK_TimeoutError`，第 2 次以同一消息 ID 自动恢复为 `PASS`，
  `recovered=true`；失败尝试没有被覆盖。
- `logs/notifications/feishu_20260723.jsonl` 共 9 行，SHA-256 为
  `0cefaf6ee973c017a81a7fecc01434ba056228c7751221943c3dee7274012592`。
- 受控重复执行完整 Docker scheduler 返回影子 `NOOP`、模拟仓 `NOOP`、
  重放 `PASS`、验收 `PASS`。重复前后 8 类运行/账本文件以及通知、信号、
  对账和模拟仓产物的行数与 SHA-256 全部不变。
- 人工中断 fixture 已覆盖“产物写完、首条事件已追加后失败”的恢复路径：
  原 FAIL 保留，下一轮幂等补齐为 PASS，第三轮 NOOP。自然通知重试与该
  事件级 fixture 共同覆盖外部通道和追加式账本两类恢复。

## 目标逐项裁决

| 目标要求 | 权威证据 | 结论 |
|---|---|---|
| 500,000 RMB 初始资金与冻结策略 | `paper_accounts.csv`、策略文档/哈希 | PASS |
| 下一官方交易日与真实开盘约束 | 交易日历、精确日期行情、对账产物 | PASS |
| 订单/成交/持仓/现金/公司行为/NAV 追加式账本 | 三份账本、5 份不可变运行产物 | PASS |
| 可独立重放与会计恒等 | `paper-verify`、恒等差 0.00 | PASS |
| 无未来数据 | 信号/采集/执行时间链与日期闸门 | PASS |
| `.BJ` 排除 | 原始批次、事件、持仓、机器裁判均为 0 | PASS |
| 只读查询契约 | snapshot/orders/nav/verify/acceptance | PASS |
| Docker 日任务与飞书守护 | scheduler operator、健康状态、通知账本 | PASS |
| 幂等与异常恢复 | Docker NOOP 哈希复核、恢复 fixture、自然重试 | PASS |
| 脱敏、测试、提交与远端同步 | 见最终交付检查 | PASS |

## 最终交付检查

- 全量测试：184 项 PASS。
- Docker P0.5/scheduler 专项：17 项 PASS。
- 脱敏与账本追加约束专项：11 项 PASS。
- Ruff、`compileall`、`pip check`、`git diff --check` 全部通过。
- 没有修改 `src/`、`config/`、模型、门禁、生产调度配置或 Docker 服务；
  本次只提交自然运行追加的正式账本和验收/状态文档。
- scheduler 提交前保持 `healthy`，受控重复运行后内存约 401 MiB，
  没有重启生产容器。

## 结果边界与下一步

P0.5 从本日起进入持续 `FORWARD` 观察，后续交易日由现有 scheduler 自动
追加，无需另开一次性施工任务。一天观察仅完成工程验收；Web 应显示
`OBSERVING`，不能把全账户 BACKFILL 初始化净值冒充 FORWARD 业绩。

后台下一独立工作包可进入 P1“每日主力资金流候选验证”；Web 原型和查询
适配层必须另立目标，并继续保持只读、隔离和证据优先。

# P2-2 科创50正式历史效果验收（2026-07-25，UTC+8）

## 1. 机器裁决

`p2-star50-effect-v1` 的终态为：

| 字段 | 结论 |
|---|---|
| `strategy_results_inspected` | `true` |
| `historical_effect_gate` | `NO_GO` |
| `strategy_effective` | `REJECT` |
| `production_authorization` | `none` |

该结论不改写 `p2-star50-protocol-v1` 的数据 NO-GO、v2 官方谱系数据门 GO 或 P2-1 工程 GO，
也不表示 P2 整体工程失败。它表示本次冻结的 Alpha158/LightGBM/Top10 科创50历史基线停止：不调
门槛、不换 seed、不追加变体、不生成生产信号、不改模拟仓或 scheduler。

`historical_effect_gate` 使用 `NO_GO` 而不是 `REJECT`，是因为冻结前没有找到能同时提供 2023–2025
基础成本日净收益与逐日持仓权重的合法 CSI800 OOS 真身，分散化组按协议为 `NOT_EVALUABLE`。即使
将来另立协议补齐对照，本次三窗、成本和回撤门也已独立失败，因此 `strategy_effective=REJECT` 不依赖
分散化缺口。

## 2. 结果前冻结、P2-1 审计附录与输入绑定

真实 handler/model/backtest 前完成并推送独立冻结提交：

- commit：`ed5b1b0d59bd18186ef99c9844123af473897fcb`；
- protocol：`docs/P2_STAR50_EFFECT_PROTOCOL_20260725.md`；
- config SHA-256：`6fb1141f8801c88e6ba10a2358e54cac309a2e856e49992fbc90ca1c798aa32c`；
- CSI800 schema/hash inventory SHA-256：
  `a1c940272bc94aeec9b85a9d35b4148fac3548f0da563a3d660b15ad8d825002`；
- P2-1 时间字段附录 SHA-256：
  `2c44510f326342e6efa138aac7e559bc8d0ffff350f45dbf56e8cf9e885dd0e3`。

P2-1 旧账本的 `finished_at/evaluated_at` 实为协议冻结时间；旧行、manifest、代码和报告均未修改或
重算。P2-2 新账本分列 `protocol_frozen_at`、真实 UTC `run_started_at/run_finished_at/evaluated_at`。
实际唯一运行始于 `2026-07-24T17:02:12.929813+00:00`，结束并裁决于
`2026-07-24T17:03:00.134461+00:00`。

运行前和确定性复核前均逐项重哈希 P2-1 manifest/quality/report、三份数据、qlib 内容树/build
identity 及 official-lineage-v2 五项输入，全部与协议一致；没有重建 P2-1 或 v2。合并输入身份
SHA-256 为 `b43a7fa3e77f89e7854cc826aff4f4c6e0b77b700380026a2dbf4de753c63a1c`，训练代码身份为
`8ede986d4921edb357d58320f0f4c8fd7dd893ee94abc5bf2136a41816062659`。

## 3. 训练与资源

运行环境为 Python 3.11.15、qlib 0.9.7、LightGBM 4.6.0，单线程、seed 42、deterministic、
force-col-wise。early stopping 只看冻结 valid，三个冻结模型分别在第 1/1/2 轮取得最佳 valid；没有
用 test 调参或重训。

| 模型 | train / valid / test / pressure 行 | 模型 SHA-256 | fit 秒 | 容器进程峰值 RSS* |
|---|---:|---|---:|---:|
| STAR-W1 | 23,500 / 6,250 / 12,100 / 1,750 | `497e4803...017ad` | 0.98 | 912,072 KiB |
| STAR-W2 | 30,150 / 6,200 / 12,100 / 1,400 | `6746f3ea...b168` | 1.08 | 1,146,972 KiB |
| STAR-W3 | 30,050 / 6,250 / 12,150 / 5,800 | `af86823d...0b866` | 1.13 | 1,228,456 KiB |

\* `ru_maxrss` 为进程生命周期累计峰值，不是单模型增量；总入口墙钟约 47 秒。qlib 输出的可选
CatBoost/XGBoost 缺失提示和 pandas `SettingWithCopyWarning` 未改变冻结 LightGBM 通路或结果。

## 4. 三窗口与成本硬门

各窗均满足至少 220 日和 20 次调仓，但基础成本净超额全部为负：

| 窗口 | 日数 / 调仓 | 基础净超额 | 1.5x | 2x | 双边额外 10bp | 策略净回撤 |
|---|---:|---:|---:|---:|---:|---:|
| STAR-W1 (2023) | 242 / 25 | -4.8517% | -3.7410% | -4.2624% | -4.2043% | 27.0302% |
| STAR-W2 (2024) | 242 / 25 | -32.7332% | -33.2374% | -33.7386% | -33.6766% | 36.1279% |
| STAR-W3 (2025) | 243 / 25 | -7.7358% | -8.5482% | -9.3548% | -9.2653% | 15.1690% |

机器门：

- 样本/调仓：PASS；
- 基础成本正超额窗口：0/3，要求至少 2/3，FAIL；
- 727 日 pooled 基础净超额：-50.3960%，要求 `>0`，FAIL；
- pooled 2x：-51.9819%，要求 `>=0`，FAIL；
- pooled 双边额外 10bp：-51.7926%，要求 `>=0`，FAIL；
- 1.5x pooled 为 -50.3310%，只作冻结诊断，不替代硬门。

各成本场景按各自现金、最低费用和整数股约束独立执行，因路径/取整差异，1.5x pooled 略好于 1.0x；
它不具备单调性，且协议本就只将 1.5x 作为诊断。2x 和额外滑点两项冻结硬门均明确失败。

## 5. 压力期与回撤硬门

最大回撤均从各段独立现金起点的基础成本策略净 NAV 峰谷计算，不使用超额 NAV：

| 压力期 | 冻结模型 | 日数 / 调仓 | 净超额 | 策略净回撤 | 20% 门 |
|---|---|---:|---:|---:|---|
| star_2023_drawdown | W1 | 35 / 4 | +2.2813% | 9.8055% | PASS |
| microcap_2024 | W2 | 28 / 3 | -2.1944% | 26.8259% | FAIL |
| volume_price_2026h1 | W3、不重训 | 116 / 12 | -70.3596% | 26.4489% | FAIL |

测试窗 W1/W2 也分别以 27.0302%/36.1279% 超过 20%；六段“任一失败即失败”的回撤总门 FAIL。

## 6. 分散化、执行诊断与风险

冻结 inventory 只读盘点的 Stage0 是汇总、P1 日表缺基础策略日收益和持仓、predictions 不是执行后
组合、shadow/paper 只覆盖 2026 前瞻。因此 weighted overlap、return correlation 和 Euler risk
contribution 均未计算，没有临时造代理；分散化组为 `NOT_EVALUABLE`，按协议使总门 NO-GO。

基础场景三个测试窗共 893 笔交易，持仓和交易 `.BJ=0`，每次目标选择均为 10 名。协议把单名 10%、
Top3 30% 和行业 30% 操作化为调仓时 10% 目标及每行业最多 3 名；两次调仓之间不作日内/日频强制
再平衡。独立诊断显示价格漂移后每日实际最大单名权重 14.4938%、Top3 最大 37.7301%。这不改变本次
REJECT，但说明若未来研究要求“每个交易日实际权重”也不得越线，必须另立协议和执行器，不能回写
本次规则或结果。

## 7. 确定性、幂等与不可变证据

第二遍以完全相同输入、代码、seed 和规则重新训练并执行。除含真实运行时间的 metadata 外，54 组
model/prediction/daily NAV/trade/holding 文件逐内容一致；四项机器比较均为 true：model、execution、
pooled NAV、holding bundle。主要哈希为：

| 证据 | SHA-256 |
|---|---|
| 本地 effect report | `94c458ae908e77af7808e27a41de2b386e920ad910c05a24718de621896f5ce9` |
| tracked manifest | `c12b9404899b94873b7923e20920b02e1a795fc0d75b8fc60d863327f7bf64cd` |
| model bundle | `4b087b1254abd943bf34f31896eb794700eaccc7274328ba68a96f915fee024a` |
| prediction bundle | `0a79e6e47def633c8d87ec86dcfe9303b40771b8f163f77a389f80cf7a6ffa0b` |
| NAV/execution bundle | `16b65b5bffae0c24ecdf18dcc596e303620cb6aa20aadb3317916b5c4475fb80` |
| holding bundle | `3d46f2c032665145a167b21f4c0cd22f22ff2c6a273fd0dac0861cf7dad04b8b` |
| run ledger | `13492b897448921be0308708572ccf9452c150600f078b0572a57f6d32e2c4ce` |
| admission ledger | `454aeacf58c7e35899de15934f49c4f4e95715025bef8ba6133727d3c6db897f` |

终版入口再次调用时直接复用报告，不训练、不回测；调用前后上述 report/manifest/两 ledger 哈希逐项
不变，两个 ledger 均仍只有 1 行。Git 忽略结果目录共 115 个文件、1,551,575 bytes；它保存模型、
预测、逐日 NAV、交易和持仓用于复算，未进入 Git。

## 8. 隔离与停工

P2-2 没有修改生产 compose、scheduler 镜像/配置、CSI800 provider/model/signal/gate、共享 qlib、
前瞻 qlib、生产账本、模拟仓或生产信号。提交只含脱敏 manifest、P2 专属 ledger、测试和文档；原始/
派生业务数据、模型、预测、排名、持仓、交易、日志和凭据均保持 Git 忽略。该基线在 P2-2 停止，
不得根据结果追加变体。

终版验证为：Docker P2 专项 18 passed、Docker 全仓 198 passed、Ruff All checks passed、compileall
通过、`pip check` 无损坏依赖、`git diff --check` 通过；manifest/report/ledger 哈希互证、结果目录 Git
忽略和脱敏扫描通过。生产容器仍为不可变镜像 `shaiwei:scheduler-current`，`Up 5 hours (healthy)`。

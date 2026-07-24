# P2-2C 科创50历史效果综合方法纠错验收（2026-07-25）

## 结论

P2-2C 的权威历史裁决为：

- `original_p2_2_model_valid=false`；
- `original_p2_2_execution_valid=false`；
- `results_known_before_correction=true`；
- `model_retrained=true`、`predictions_recomputed=true`；
- `authoritative_historical_effect_gate=NO_GO`；
- `strategy_effective=REJECT`；
- `production_authorization=none`。

这次结论来自结果前推送的冻结提交
`c6fbbaf0f4720ae5be821d75cca11cfcb3628897`，只修复标签成熟 purge、open/prior-close 时钟和买卖双向
5% 容量。它不是新策略变体，也不宣称结果未知：原 P2-2 结果及主控 open-clock-only 敏感性已可见。

纠错后 standalone 历史门仍明确失败：三窗基础成本净超额全部为负，727 日 pooled 在基础、1.5x、2x
和额外双边 10bp 下全部为负；W1/W2/W3 测试窗最大回撤均超过 20%，microcap_2024 压力期也超过
20%。同期 CSI800 合法日收益+持仓真身仍缺失，分散化门 `NOT_EVALUABLE`。因此本冻结基线正式停止，
不调门槛、不追加变体、不进入前瞻或生产。

该 REJECT 不推翻 v1 数据 NO-GO、official-lineage-v2 数据 GO 或 P2-1 工程 GO；中证800仍是唯一生产
主策略。

## 1. 时间顺序与不可变边界

1. 原 P2-2 freeze/final 为 `ed5b1b0d...` / `13d219dee...`；其数值可复算但方法裁决已由独立附录失效。
2. 冻结前只复算旧缺陷、schema、日历和哈希；没有创建 corrected handler/model/prediction/result。
3. P2-2C 协议、失效附录、输入审计、实现、fixtures 和空专属账本先提交并推送为 `c6fbbaf0...`。
4. 入口随后重新核验 `HEAD=origin/main`、工作树干净、全部 P2-1/v2/原 P2-2/qlib 哈希一致和 scheduler
   healthy，才在一次性 Docker 容器串行执行 first pass 与 deterministic replay。
5. 真实产物只写 Git 忽略的
   `data/research/star50/p2-star50-effect-correction-v1/`；没有写生产 compose/镜像、CSI800、共享/前瞻
   qlib、生产模型/信号/账本或模拟仓。

原 P2-2 目录仍为 115 文件、1,551,575 bytes，canonical tree SHA-256 保持
`98637864c9e341f1af413c300e922b9e80a02589c5fc91fec8eadb315bd5f3a6`；原 report、manifest 和两账本
逐哈希未变。

## 2. 标签成熟纠错

机器直接从官方 benchmark 日历推导端点并在训练 metadata 记录：

| 窗口 | effective train | effective valid | test（不移动） | train/valid feature rows |
|---|---|---|---|---:|
| W1 | 2020-07-23~2022-06-15 | 2022-07-01~2022-12-15 | 2023 原窗 | 22,950 / 5,700 |
| W2 | 2021-01-01~2023-06-13 | 2023-07-01~2023-12-14 | 2024 原窗 | 29,600 / 5,650 |
| W3 | 2022-01-01~2024-06-13 | 2024-07-01~2024-12-16 | 2025 原窗 | 29,500 / 5,700 |

三窗 `handler_fit_end_time` 分别严格等于 2022-06-15、2023-06-13、2024-06-13。purge 后 train/valid
最大标签成熟日分别不晚于各自原段末，valid 成熟日严格早于首个 test 交易日；反向 fixture 证明原
未 purge 的 train/valid 均越界。模型仍是 Alpha158 + LightGBM seed42 和相同超参数；test 起点、压力
映射、early stopping 规则均未变化。

## 3. 开盘时钟与双向容量

运行前独立重现旧缺陷：2023~2026H1 全市场 close/open flags 差异 buy/sell 为 283/35，官方成员日为
90/3；旧基础场景 893 笔交易中 14 笔卖单超过 5%，最大 11.3037996634%。首成员日前有效 bar 最短
74 个交易日，128 只历史成员无缺首 bar，`.BJ=0`。

纠错执行器只用执行日 raw open/pre_close/tick 和 raw_volume 判断成交，缺 open 的 `nav_open` 只用
前一交易日 close；当日 close 和旧 flags 不参与开盘决定。所有当前 holdings 均进入卖出流动性集合；
不足 15 个有效 amount 或 median 无效时不得卖出，部分卖出后保留并在后续调仓重试。

三测试窗基础场景共 909 笔：买 495、卖 414；买卖超容量均为 0，最大买/卖 capacity utilization 为
0.999998479 / 0.999999955。84 个窗口内股票存在跨多个信号日的卖出，证明未卖完持仓走后续调仓重试。
四成本场景及三压力期合计 3,856 笔，买卖超容量仍均为 0。W2 基础场景有 7 次开盘限价阻断，W3 有
1 次无效 execution bar 阻断；均保留真实仓位路径。

## 4. 独立效果复算

不调用项目裁判函数，直接从 first-pass daily/trade/holding Parquet 逐窗复合重算：

| 窗口 | 交易日 / 调仓 | 基础净超额 | 1.5x | 2x | 额外双边10bp | 策略最大回撤 |
|---|---:|---:|---:|---:|---:|---:|
| STAR-W1 | 242 / 25 | -8.5092% | -9.0281% | -9.5437% | -9.4821% | 30.2019% |
| STAR-W2 | 242 / 25 | -19.2534% | -19.8713% | -20.4852% | -20.4227% | 31.8114% |
| STAR-W3 | 243 / 25 | -23.8656% | -24.5317% | -25.1937% | -25.1237% | 22.1532% |

727 日 pooled：基础 -52.9687%、1.5x -54.5946%、2x -56.1902%、额外双边 10bp -56.0171%。
正基础净超额窗口为 0/3；观察日和调仓数门通过，window/cost 门失败。

压力期独立复算：

| 压力期 | 交易日 / 调仓 | 基础净超额 | 策略最大回撤 | 20%门 |
|---|---:|---:|---:|---:|
| star_2023_drawdown | 35 / 4 | +0.9129% | 11.2164% | PASS |
| microcap_2024 | 28 / 3 | +1.4770% | 20.5921% | FAIL |
| volume_price_2026h1 | 116 / 12 | -53.4054% | 15.5337% | PASS |

任一测试窗或压力期回撤超过 20% 即失败；三个测试窗和 microcap_2024 已触发，所以 drawdown gate
失败。分散化继续因合法 CSI800 对照缺失而 `NOT_EVALUABLE`，未造临时代理。

## 5. 确定性、哈希与账本

两遍共有 54 份可比 model/prediction/daily/trade/holding 文件，逐文件 SHA-256 全部相同；model、
prediction、NAV、trade、holding、pooled canonical 比较全部 true。训练 metadata 的真实时间和资源字段
不要求逐字相同。

| 证据 | SHA-256 |
|---|---|
| correction protocol | `232e1a4c2effd9f1925e7fb326a88aeb689ee07829a275aa72cea544e0bf2eb5` |
| frozen input manifest identity | `8aca90da0d096e080fbbf5191c7c9be72c5e0b079e04337aec6e67d01434eb41` |
| correction code | `66666772f2a7a46c51a7eda2c9bbc90e018f4a2de6ae1374d1d0d4d4428559f7` |
| corrected model bundle | `577822fcaf6025d49bd3fb8c3d3c8c4e7e5c4c8f5d1f305b6bbd2ba9b3f3028b` |
| corrected prediction bundle | `a21995b98bd7f738f7f5843abea21e531ef9c28e4b458125cd523e017d74529d` |
| corrected NAV bundle | `9e90420d43624c329705804cc90a253f4f1dce211e809a1745a315a0cf58b50c` |
| corrected trade bundle | `13b4d20ce594905f4670b8fd1b62579649c6f8210ac700314e5f3e08324dddd7` |
| corrected holding bundle | `f2c6b1da630309879d90cf431fe9d0470664a71d86df0538dc2ce750aaa0ade4` |
| ignored effect report | `d80d129480914c87448c5fa372d2ed061bbdbd164b5eb65b65a9fe17455b9b75` |
| tracked manifest | `155ca8b4cdda2166118e6f4f0b6247f3b326d86e4b0e24a7d8d930343fb356a8` |
| independent verification | `37a25058e979570d755c1ebf0d480966d9401d67265b57295c554e01345598dd` |
| correction run ledger | `953fd315a0ce198c10a40eca42031e91a7417b46fee9603b942868818c7cf463` |
| correction admission ledger | `a298bb99ff43c4d94ac87addf9edb58ce0fde0b15de4f3886b3c40eeb716ec86` |

专属账本各 1 行，分列 `protocol_frozen_at` 与真实 UTC `run_finished_at/evaluated_at`。终版提交推送后将
再次调用入口，必须复用既有报告且两账本行数和上述哈希不变。

## 6. 测试、隔离与风险

结果前：本地全仓 206 passed；Docker P2-2C + 原 P2-2 专项 14 passed；Ruff、compileall、pip check、
diff-check 和凭据扫描通过。终版再次执行同组检查。生产 scheduler 运行镜像、代码快照和配置未改，
运行前后均 healthy；Git 未跟踪 data/logs/.env/模型/预测/NAV/交易/持仓。

保留风险与解释：

- 结果和主控敏感性在纠错前已知，证据属性是审计纠错而非盲样本外发现；
- 合法 CSI800 分散化真身仍缺，不能补造；
- 原冻结的目标约束而非逐日实际权重等 caveat、既有成本路径和后复权研究执行表达均未趁纠错修改；
- qlib `CSRankNorm` 产生第三方 pandas `SettingWithCopyWarning`，但两遍 54 份物理产物完全一致，未形成
  数值或确定性漂移；
- 本次 REJECT 后停止本基线，不以调门槛、换 seed 或追加变体追结果。

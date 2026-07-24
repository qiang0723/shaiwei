# P2-1 科创50独立工程协议（结果前冻结）

冻结时间：2026-07-25 00:00（UTC+8；工作包日期仍记 2026-07-24）

状态：**FROZEN BEFORE REAL DATASET BUILD AND BEFORE ANY REAL STRATEGY RESULT**。

本协议只授权基于 `official-lineage-v2` 的独立数据集、qlib 和 synthetic/fixture 工程闭环。禁止在
真实科创50数据上训练模型、回测、计算 IC/收益/回撤、排名、选股或生成信号；P2-2 才可在新授权下
运行正式效果。机器真身为 `config/p2_star50_engineering_v1.yaml`。

## 1. 上游证据与旧裁决

`p2-star50-protocol-v1` 的 NO-GO 永久保留；`p2-star50-protocol-v2` 的官方成员谱系数据门 GO 已由
主控终验。P2-1 不修改、不删除、不重算任何 v2 报告，只在入口逐文件重哈希并绑定：

| 输入 | SHA-256 |
|---|---|
| v1 配置 | `31cb4bd33e7eaa0bcb3c23f937c52357778cad5704894e79061f32f4909da2d1` |
| v2 配置 | `54e9d49d295c26c19898e716873a333d85f581d02c914c2d4affaa23072c4183` |
| v2 脱敏 manifest | `387514f25d9f883c7ebe84e386ba6dbca4644bb204628004cee4991dc316e112` |
| v2 质量报告 | `51bfe33aa21162007961d9fb0fd8a6fe91d45ce7593bddac7c9ff0c2fda2df93` |
| initial_set.parquet | `fe960ccc0b86592c02d082a7f9fda18bb6032b4c263458850cc7deb709a95d4c` |
| membership_events.parquet | `ee5b6ac2a3ee608067bcca51cc21da152b754ec2b96c52c2be4db184c55cdf6a` |
| daily_membership.parquet | `91e9d48421d2a577176488d792c63f5d33bceee953a4532cdb8a8f6317d82644` |

## 2. 独立身份和隔离

- research family：`p2-star50-engineering-v1`；
- dataset：`star50-official-pit-engineering-v1`；
- qlib instruments：`star50_official_pit_v1`；provider：
  `data/research/star50/p2-star50-engineering-v1/qlib_bin`；
- config/model：`p2-star50-engineering-protocol-v1` /
  `p2-star50-alpha158-lightgbm-engineering-v1`；模型只准 synthetic fixture；
- benchmark：`000688.SH` / `SH000688`；
- signal namespace：`p2-star50-engineering-smoke-v1`，只准 synthetic fixture；
- run/admission ledger：`ledger/p2_star50_engineering_runs.csv` /
  `ledger/p2_star50_engineering_admissions.csv`。

禁止覆盖 `data/qlib_bin`、前瞻 qlib、CSI800 数据集/模型/信号/账本或 scheduler。真实和 synthetic
派生产物均只写入 P2 独立的 Git 忽略目录；Git 只提交配置、工具、fixture、测试、脱敏 manifest、
专属审计 ledger 和验收文档。

## 3. P2-1 新增月度精确覆盖门

v2 冻结报告维持原样。P2-1 输入门把 2020-07~2026-06 的 **72 个预期月份逐项显式枚举**在机器
配置中，并逐月要求：

1. 恰好一个唯一 `trade_date`；
2. 恰好 50 行、50 个唯一 `con_code`、重复主键 0、`.BJ=0`；
3. 在该快照日与 official daily membership 的集合精确一致；
4. 缺失月份 0、额外月份 0。

不能再用总比较数 72 代替月份集合。fixture 必须构造“缺一个月、另一个月增加第二个快照、总快照
数仍为 72”的输入并证明 FAIL。

## 4. official daily membership 唯一真身

`daily_membership.parquet` 是动态 instruments 的唯一真身。逐日主键必须唯一、每天正好 50 只，
成员区间只能由连续交易日压缩得到；禁止使用当前成分、Tushare 权重或未来公告修补。

工程质量门固定检查：

- 成员日在上市日前、退市生效日及以后均为 0；`.BJ=0`；
- 每个成员日必须有行情 bar，或被主源空 `suspend_timing` 的全天停牌解释；日内停牌不能解释缺 bar；
- 每个 bar 必须有唯一、正数 adj_factor；停牌字段保持 NaN，不得零填或前值填充；
- daily_basic 对成员 bar 覆盖至少 95%；申万 L1 行业按 `in_date/out_date` PIT 对齐，覆盖至少 95%；
- ST 只按时点有效名称识别；涨跌停使用科创板 19.5% 阈值和方向性字段；
- 行情、复权、基本面、行业、ST、停牌、涨跌停的覆盖、重复、缺口和哈希全部进入质量报告。

为了计算 Alpha158 滚动特征，允许为“曾经进入官方成员集合的股票”读取策略起点前 100 个 SSE
交易日的股票行情作为 feature warm-up；它不改变 instruments 起点，不生成 2020-07-23 前的标签、
信号或效果，也不使用事后回填的指数成分历史。

## 5. 独立 qlib 工程

qlib calendar、features、benchmark 和 `star50_official_pit_v1.txt` 只能写入 P2 provider。instruments
区间由 official daily membership 压缩生成；同一股票退出后再进入必须保留多段区间。构建采用同目录
staging + 原子切换，整树内容哈希绑定输入数据、协议和代码快照；相同输入复跑必须完整验哈希并复用，
不得覆盖差异缓存。

可以用真实数据构建 qlib 并检查结构、字段、覆盖和哈希；不得从真实 provider 创建 label、训练模型、
预测、回测、排名或信号。

## 6. 冻结模型、组合、窗口和执行口径

以下内容从 v1 原样转录，不在 P2-1 运行真实效果：

- Alpha158 + LightGBM；seed 42；完整超参数见机器配置；标签固定
  `Ref($open,-11)/Ref($open,-1)-1`；
- TopK=10、n_drop=2、每 10 个官方交易日调仓、等权、下一交易日开盘；
- 单股 10%、前三大 30%、申万 L1 单行业 30%、行业覆盖至少 95%；
- 20 日流动性、至少 15 日、中位日成交额 2,000 万元、订单不超过 5%；
- ST 排除、停牌/方向性涨跌停/缺开盘不成交、退市现金实现未建模即失败；科创板 19.5%、一分钱
  容差、首次买入至少 200 股；
- 买 6bp、卖 16bp、最低 5 元；1.5 倍、2 倍成本和双边各加 10bp；
- STAR-W1/W2/W3、三段压力期、效果门、重叠/相关/风险贡献和前瞻门全部保持 v1 原值。

任何真实工程不可能性若要求改变上述口径，必须停下回主控；不得看结果后修改。

## 7. synthetic/fixture 通路

模型、回测和执行器只准消费确定性 synthetic fixture。fixture 不使用真实股票代码、行情、指数或
成员数据，但必须走 dataset → qlib → Alpha158 → LightGBM → TopK/n_drop/10 日调仓 → backtest 的
结构通路。烟测只允许记录阶段 PASS/FAIL、行数、fixture/产物哈希；禁止保存或输出预测值、排名、
选中名称、IC、收益、回撤或其他效果指标。

## 8. P2-1 裁决

终版报告必须独立输出：

- `input_gate_pass`；
- `dataset_complete`；
- `qlib_complete`；
- `pipeline_fixture_pass`；
- `idempotency_pass`；
- `engineering_complete`；
- `strategy_results_inspected=false`；
- `strategy_effective=NOT_EVALUATED`；
- `production_authorization=none`；
- `verdict=GO/NO_GO`。

前六项全部为 true 才允许工程门 GO。GO 只表示可以由主控另立 P2-2；不等于策略有效，更不授权
生产。完成测试、脱敏、Git 同步和 scheduler 健康复核后立即停工回传。

# P2-1 科创50独立工程门验收（2026-07-24，UTC+8）

## 1. 裁决

`p2-star50-engineering-v1` 机器裁决：**GO**，只表示基于 official-lineage-v2 的独立真实数据集、
qlib 和 synthetic 工程通路已闭环。

| 状态 | 结论 |
|---|---|
| `input_gate_pass` | `true` |
| `dataset_complete` | `true` |
| `qlib_complete` | `true` |
| `pipeline_fixture_pass` | `true` |
| `idempotency_pass` | `true` |
| `engineering_complete` | `true` |
| `strategy_results_inspected` | `false` |
| `strategy_effective` | `NOT_EVALUATED` |
| `production_authorization` | `none` |
| `verdict` | `GO` |

该 GO 不代表科创50策略有效，不授权生产，也不自动授权 P2-2。P2-1 没有在真实科创50 provider 上
创建标签、训练模型、预测、计算 IC/收益/回撤、排名、选股、生成信号或运行回测。中证800仍是唯一
生产主策略。

`p2-star50-protocol-v1` 的 NO-GO 和 `p2-star50-protocol-v2` 的官方谱系 GO 均原样保留；P2-1
没有修改或重算 v2 冻结报告。

## 2. 结果前冻结

真实数据集构建前已提交并推送：

- 冻结提交：`00bc030`（`docs: freeze P2 Star50 engineering protocol`）；
- 配置：`config/p2_star50_engineering_v1.yaml`；
- 协议：`docs/P2_STAR50_ENGINEERING_PROTOCOL_20260724.md`；
- 配置 SHA-256：
  `3e259f9f763400f232a671d6aa0c64b8dec77b61fedddb7b789ef8bac3760f03`；
- 协议 SHA-256：
  `2e073812597b605edf80b9a40a69d4c46ab26773667b053f3fd2856d2143a3ce`。

冻结协议逐项绑定 v2 manifest、质量报告、initial set、membership events 和 daily membership 的精确
哈希，并原样转录 v1 的 Alpha158、标签、三 OOS 窗、Top10/n_drop2、10 日调仓、下一交易日开盘、
等权、成本、流动性、集中度、行业、重叠、风险及准入/拒绝门。首次推送遇到一次 SSH
`Permission denied (publickey)`，同一命令一次有界重试成功；没有更换远端、绕过权限或泄露凭据。

## 3. P2-1 月份域输入门

P2-1 没有沿用 v2 的“比较数量等于 72”捷径，而是在机器配置中显式枚举 2020-07~2026-06 的
72 个预期月份。实际门禁结果为：

| 检查 | 结果 |
|---|---:|
| 预期/实得月份 | 72 / 72 |
| 每月恰好一个快照 | 72 / 72 |
| 每月恰好 50 行、50 个唯一成员 | 72 / 72 |
| 与 official daily membership 精确一致 | 72 / 72 |
| 缺失/额外月份 | 0 / 0 |
| 双快照月份 | 0 |
| 重复快照主键 | 0 |
| 集合差异月份 | 0 |
| `.BJ` | 0 |

对抗 fixture 删除一个月份，同时在另一个月份增加第二个快照，使唯一快照日期总数仍与原输入相同；
门禁仍以“缺月 + 双快照月”失败。它证明缺月不能被另一月的重复快照抵消。Tushare 仍只作二级集合
对账，没有使用权重数值，也没有把月末 `trade_date` 当成官方生效日。

## 4. 真实独立数据集质量

official daily membership 是动态 instruments 的唯一真身。入口逐文件重哈希 v2 五项冻结证据，
读取项目原始账本中与 128 只历史成员及 `000688.SH` 有关的最新不可变批次；报告只记录脱敏批次
身份哈希、行数和覆盖，不记录原始路径、token 或请求凭据。

策略成员区间为 2020-07-23~2026-07-24；为 Alpha158 特征准备读取此前 100 个 SSE 交易日，
warm-up 起点为 2020-02-26，但没有生成策略起点前的 instruments、标签或效果。

| 检查 | 结果 |
|---|---:|
| official trade days / member rows | 1,456 / 72,800 |
| 每日成员最小/最大 | 50 / 50 |
| 历史唯一成员数 | 128 |
| 全 warm-up 市场行 | 170,343 |
| 成员日行情 bar | 72,719 |
| 无 bar 且由全天停牌解释 | 81 |
| 无法解释的缺 bar | 0 |
| 行情或全天停牌覆盖 | 100% |
| daily_basic 成员 bar 覆盖 | 100% |
| PIT 申万 L1 成员 bar 覆盖 | 100% |
| 上市前成员日 / 退市生效日及以后成员日 | 0 / 0 |
| 行情/复权/基本面重复主键 | 0 / 0 / 0 |
| 日内停牌解释缺 bar | 0 |
| `.BJ` | 0 |

ST 由时点有效名称计算；停牌、方向性涨跌停、复权、基本面和行业字段均进入隔离成员日数据集。没有
当前成分回填、未来公告回填、停牌价格前填或手工补数。

三个 Git 忽略的真实派生产物为：

| 产物 | 行数 | SHA-256 |
|---|---:|---|
| `dataset/market.parquet` | 170,343 | `a1e1d99a9de8cce0dada33389f3588d96ec6e1ecd5f5a1738e7105353901c289` |
| `dataset/member_days.parquet` | 72,800 | `a6fb10532bba9de9504fc4be0bfe6e45e50621a761ae29fbaa1cf9ba39356061` |
| `dataset/benchmark.parquet` | 1,556 | `e659bcbc042fb56bd50482428daa8eb88dfc8bb674d91d7b4551a07e8a945c42` |

## 5. 独立 qlib 与动态 instruments

真实 qlib 只写入
`data/research/star50/p2-star50-engineering-v1/qlib_bin`，没有覆盖 `data/qlib_bin`、前瞻 qlib 或
任何 CSI800 provider。`star50_official_pit_v1.txt` 只由 official daily membership 连续交易日压缩
得到；专项 fixture 锁定成员退出后再进入时必须保留两个区间。

qlib 使用同目录 staging、原子切换、协议/输入/代码 build identity 和整树内容哈希：

| 检查 | 结果 |
|---|---:|
| 文件数 | 1,293 |
| 字节数 | 6,908,091 |
| qlib 内容树 SHA-256 | `b8f736ef9bc9e31cc236a81ca281a23e904789fb5ec87caa9195b572c6b78729` |
| build identity SHA-256 | `dca65a090284de044346bcea7f6ff7364f9a23e3479c9f77c1832f45b2fd26e6` |
| 第二遍复用既有 provider | `true` |

真实 provider 只做字段、区间、覆盖、结构、哈希和复用检查；没有被 qlib handler、模型、预测器或
回测器读取。

## 6. synthetic 工程通路

模型与执行器只消费确定性 synthetic fixture：16 个与历史官方成员无碰撞的合成代码、520 个合成
工作日、8,320 行合成行情和合成基准。完整执行：

`dataset → qlib → Alpha158 → LightGBM → TopK=10/n_drop=2/10 日调仓 → backtest`。

六阶段全部 PASS；训练/验证/测试分别形成 3,680/1,280/1,920 行 Alpha158 观察，120 个合成回测
观察日中有 110 个非现金持仓观察，证明 TopK 执行器不只是返回空壳。预测、排名、选中名称、模型
效果和回测效果均只在内存中短暂存在，未写文件、账本或验收报告。

qlib 的第三方运行时输出了 Gym 维护提示、可选 CatBoost/XGBoost 缺失提示、未来日历回落及空均值
warning；这些提示不影响已完成的六阶段和 110 个非现金持仓观察。`pip check` 通过，且没有为消除
提示安装新依赖或改变冻结工程口径。

fixture SHA-256 为
`33824d58f59419657c7a0a2fc62cd19d177fd085ff23e1e9eb3852bb88f91220`；终版 smoke report
SHA-256 为
`7d30d9024ccdf20487cf432e8fda6f8449c522f1b4afc8ac1cfa649a730c19b1`。

## 7. 幂等、账本与不可变证据

终版闭环连续运行两遍，质量报告、真实 qlib 内容树和 synthetic smoke report 的首遍/次遍哈希逐项
相同；次遍复用真实 qlib，synthetic 报告逐字节相同。终版：

| 证据 | SHA-256 |
|---|---|
| 质量报告 | `3074bac232442f1e862c09d529a35f42fd2aa086422b337d1e72e780b569a990` |
| 工程报告 | `a4cfad049e36914fcec76f05c9dc6f5c24b55d85fe4213a37a3e8f7ae9909401` |
| 脱敏 tracked manifest | `4e946aa7d3e3c3da31ca8ad700bee2587a189dddfcf62b83054bc6804c163986` |
| P2 run ledger | `ed6a5e56f4bff83542a95e9ddf8b6cb2d511614219e92572406125ed815c896a` |
| P2 admission ledger | `9e79231fef8d4bbc51aea0d13f28b0413d8a014fee450552557e502eaf3a3bbc` |

两个 P2 专属 ledger 只通过项目统一 append-only/idempotent 写入口追加。施工中先后在格式化和
“必须形成非现金持仓”断言增强后产生新代码身份；旧的两次 GO 尝试未删除或重写，对应报告和 provider
保留在 Git 忽略的 provisional 目录。终端账本键以终版工程报告哈希前缀
`a4cfad049e36` 标识；tracked manifest 绑定包含三次尝试的完整 ledger 哈希。

原始/派生业务数据、provisional 产物和运行输出均留在项目目录且保持 Git 忽略。Git 只提交协议、
配置、工具、fixture、测试、脱敏 manifest、P2 专属账本和本文；manifest 不含绝对路径、URL、token、
cookie、代理、响应头或策略结果。

## 8. 测试、生产隔离与停工线

提交前验证：

- Docker P2 工具包专项：5 passed；
- Docker P2 + ledger 组合：16 passed；
- Docker 全仓：197 passed；
- Docker Ruff：All checks passed；
- Docker compileall：通过；
- Docker `pip check`：No broken requirements found；
- `git diff --check`、manifest 脱敏和 Git 忽略边界：通过；
- 生产 scheduler：`shaiwei:scheduler-current`，`Up 4 hours (healthy)`。

本任务没有修改生产 compose、scheduler 镜像、CSI800 数据集/配置/模型/信号/门禁、共享 qlib、
前瞻 qlib 或生产账本。P2-1 工程门完成后立即停在 P2-2 前；正式训练、回测、效果查看和生产评审均
需要主控另立授权。

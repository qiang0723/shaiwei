# Web 1.0 指标字典（v1.0）

> 只定义展示语义，不修改后台口径。`I`=已有只读查询可直接支持，`P`=需求提案，`H`=已有历史/后台证据但尚无页面查询。前端只能使用 `I`；`P/H` 在契约落地前只用于原型示例。
>
> 2026-07-25 更新：P3-0 已实现原子总览、逐仓投影、FORWARD 锚点、最新信号和次日对账。
> 本表原 `P` 标记保留设计来源；实际可用性以 `WEB_QUERY_CONTRACTS.md`、
> `P3_WEB_QUERY_ACCEPTANCE_20260725.md` 和 `P3_WEB_OPERATIONS_ACCEPTANCE_20260725.md` 为准。
> 数据质量与系统运行查询已实现但页面未施工；实验和因子工厂仍未实现。

## 1. 通用字段

| 机器名 | 展示名 | 定义 | 格式/空值 | 来源 | 状态 |
|---|---|---|---|---|---|
| `as_of` | 数据截至 | 当前响应所代表的最新业务日期，不等于生成时间 | `YYYY-MM-DD`；缺失即错误 | 所有已实现 paper 查询 | I |
| `generated_at` | 查询生成时间 | 查询响应生成的 UTC 时间，UI 转 Asia/Shanghai | 日期时间；不得冒充数据时点 | paper 三组查询 | I |
| `freshness_status` | 新鲜度 | 后台判定的 `PASS/STALE` | 文本+图标；前端不重算 | paper 三组查询 | I |
| `execution_policy_version` | 执行策略 | 运行产物固化的策略版本 | 原样显示；不可用当前配置代填历史值 | paper 三组查询 | I |
| `evidence_hashes` | 证据哈希 | 产物、内容、信号、对账、策略、代码、数据哈希集合 | 默认截断 8 位，抽屉显示完整值 | paper 查询 | I |
| `source_refs` | 来源引用 | 后台批准的可追溯来源引用 | 脱敏文本/复制；不可浏览任意路径 | paper 查询 | I |

## 2. 总览与行动

| 机器名 | 展示名 | 公式/业务定义 | 粒度/单位 | 空值与状态 | 来源 | 状态 |
|---|---|---|---|---|---|---|
| `overall_status` | 系统结论 | 同一 `as_of` 下必需证据按 `FAIL>STALE>WARN>NOT_READY>PASS` 聚合 | 每交易日/枚举 | 必需项缺失不得 PASS | `overview_snapshot` 提案 | P |
| `latest_complete_trade_date` | 最新有效交易日 | 完成日增量、门禁、信号链所覆盖的最近交易日 | 日 | 无证据=`NO_DATA` | `overview_snapshot` 提案 | P |
| `rebalance_due` | 今日是否调仓 | 冻结信号 manifest 的调仓判定 | 每信号/布尔 | 无信号=`NO_DATA` | `latest_signal` 提案 | P |
| `target_count` | 目标持仓数 | 当前信号目标证券数量，`.BJ` 必须为 0 | 每信号/只 | 无信号=`NO_DATA` | `latest_signal` 提案 | P |
| `planned_trade_leg_count` | 计划交易腿 | 信号时点目标权重与最近已完成实际权重不同的证券数 | 每信号/腿 | 非调仓可为 0；不得称为成交 | `latest_signal` 提案 | P |
| `executed_trade_leg_count` | 实际交易腿 | 执行日真实产生订单/成交处理的证券数，按冻结对账定义返回 | 每执行日/腿 | 执行证据未到=`NOT_DUE` | `shadow_reconciliation` 提案 | P |
| `next_execution_date` | 下一执行日 | 信号日后的首个官方开市日 | 每信号/日 | 尚未登记不得猜测 | `latest_signal` 提案 | P |

## 3. 模拟组合结果

| 机器名 | 展示名 | 公式/业务定义 | 粒度/单位 | 空值与状态 | 来源 | 状态 |
|---|---|---|---|---|---|---|
| `net_asset` | 净资产 | `cash + market_value` | 账户日/RMB | 账户恒等失败=`FAIL` | `paper_portfolio_snapshot.net_asset` | I |
| `cash` | 现金 | 已登记成交与公司行为重放后的现金 | 账户日/RMB | 不补零 | `paper_portfolio_snapshot.cash` | I |
| `market_value` | 持仓市值 | 后台按冻结估值规则计算的持仓市值 | 账户日/RMB | 陈旧估值由 freshness 表达 | `paper_portfolio_snapshot.market_value` | I |
| `normalized_nav` | 模拟仓净值 | `net_asset / initial_capital` | 账户日/倍数 | BACKFILL 可显示但不得作前瞻结论 | snapshot/nav | I |
| `benchmark_nav` | 中证800净值 | 同一起点归一化的 `000906.SH` 净值 | 账户日/倍数 | 不得独立换起点 | snapshot/nav | I |
| `net_excess` | 全账户累计净值差 | `normalized_nav - benchmark_nav`；包含账户已有 BACKFILL 状态，不等于 FORWARD 专属业绩 | 账户日/%pt | 只用于全账户审计；不得直接进入前瞻主结果卡 | snapshot/nav | I |
| `drawdown` | 当前回撤 | 当前净值相对历史高水位的跌幅 | 账户日/%≤0 | 不用绝对值展示 | snapshot/nav | I |
| `max_drawdown` | 最大回撤 | 选定范围 `min(drawdown)` | 范围/%≤0 | 可由同一响应 series 计算；长期建议后端返回 | `paper_nav_series.series` | I* |
| `turnover` | 实际换手 | 后台按实际成交计算的账户日换手 | 账户日/% | 无交易可为 0 | `paper_nav_series.turnover` | I |
| `cash_ratio` | 现金比例 | 后台产出的现金/净资产比例 | 账户日/% | 净资产无效则错误 | `paper_nav_series.cash_ratio` | I |
| `daily_fees` | 当日费用 | 当日实际成交产生的费用 | 账户日/RMB | 无成交可为 0 | `paper_nav_series.daily_fees` | I |
| `cumulative_fees` | 累计费用 | 账户创建以来实际成交费用累计 | 账户日/RMB | 不与回测成本混用 | snapshot | I |
| `cumulative_dividends` | 累计分红 | 已登记公司行为实际入账现金累计 | 账户日/RMB | 无事件可为 0 | snapshot | I |
| `forward_observation_count` | 前瞻账户日 | `mode=FORWARD` 的已通过账户日数 | 账户/日数 | 0 时业绩结论 `NOT_READY` | `paper_nav_series` | I |
| `forward_status` | 前瞻状态 | 有 FORWARD 则当前实现返回 PASS，否则 NOT_READY | 账户/枚举 | 不是策略有效性判决 | `paper_nav_series` | I |
| `forward_anchor_trade_date` | 前瞻锚点日 | 首个 FORWARD 前最后一个完成的 BACKFILL 账户日 | 账户/日 | 无连续锚点即失败 | FORWARD 业绩提案 | P |
| `forward_portfolio_nav` | 前瞻组合净值 | `normalized_nav_t / forward_anchor_portfolio_nav` | FORWARD 账户日/倍数 | 只在锚点和策略版本一致时返回 | FORWARD 业绩提案 | P |
| `forward_benchmark_nav` | 前瞻基准净值 | `benchmark_nav_t / forward_anchor_benchmark_nav` | FORWARD 账户日/倍数 | 与组合使用同一锚点日 | FORWARD 业绩提案 | P |
| `forward_net_excess` | 前瞻累计净值差 | `forward_portfolio_nav - forward_benchmark_nav` | FORWARD 账户日/%pt | 主结果；不等于收益率比值 | FORWARD 业绩提案 | P |
| `forward_coverage_ratio` | 前瞻覆盖率 | 完整 FORWARD 账户日 / 应有开市账户日 | 范围/% | 年化和风险调整门槛要求 ≥95% | FORWARD 业绩提案 | P |
| `forward_rebalance_count` | 前瞻调仓周期 | 已完成且有完整账户证据的调仓周期数 | 范围/次 | 非调仓日不累计 | FORWARD 业绩提案 | P |
| `performance_maturity` | 表现成熟度 | 后台按账户日、跨度、覆盖率、调仓周期和 G8 条件返回 `OBSERVING/ANNUALIZED_READY/RISK_ADJUSTED_READY/EVALUATION_READY` | 范围/枚举 | 不是 PASS/FAIL 判决 | FORWARD 业绩提案 | P |
| `forward_annualized_return` | 前瞻年化收益 | 后台在同一 FORWARD 锚点序列上按冻结公式计算 | 范围/% | ≥252 日、≥12 月且覆盖率≥95% 才允许；标早期描述 | FORWARD 业绩提案 | P |
| `forward_annualized_volatility` | 前瞻年化波动 | 后台在同一 FORWARD 锚点序列上按冻结公式计算 | 范围/% | 与年化收益相同门槛 | FORWARD 业绩提案 | P |
| `forward_sharpe` | 前瞻 Sharpe | 冻结无风险收益来源并对序列相关作后端修正的风险调整收益 | 范围/倍数 | ≥504 日、≥24 月、≥40 调仓周期且覆盖率≥95%；未冻结公式继续隐藏 | FORWARD 业绩提案 | P |
| `forward_information_ratio` | 前瞻信息比率 | 冻结主动收益定义并对序列相关作后端修正 | 范围/倍数 | 与 Sharpe 相同门槛；只标 `PROVISIONAL` | FORWARD 业绩提案 | P |

`I*` 只允许前端在单一 `paper_nav_series` 响应内做无歧义的显示聚合；不得跨响应或跨策略版本计算。

## 4. 模拟执行与持仓

| 机器名 | 展示名 | 公式/业务定义 | 粒度/单位 | 空值与状态 | 来源 | 状态 |
|---|---|---|---|---|---|---|
| `order_count` | 订单数 | 当前执行日登记订单数 | 账户日/笔 | 非调仓可为 0 | `len(paper_orders_fills.orders)` | I* |
| `fill_count` | 成交数 | 当前执行日登记成交数 | 账户日/笔 | 非调仓可为 0 | `len(paper_orders_fills.fills)` | I* |
| `fill_rate` | 实际成交率 | `fill_count / order_count`；只有实际交易腿进入分母 | 账户日/% | 分母 0=`NOT_APPLICABLE`，不是 0% | orders/fills | I* |
| `rejection_reason_count` | 未成交原因 | 未成交订单按冻结 reason 枚举计数 | 账户日/笔 | 无未成交显示 0 | orders | I* |
| `position_count` | 实际持仓数 | 数量大于 0 的重放持仓数，`.BJ` 必须为 0 | 账户日/只 | 查询异常不得沿用旧值 | snapshot.positions | I* |
| `actual_weight` | 实际权重 | 后端查询投影 `position_market_value / net_asset` | 证券×账户日/% | 净资产无效、账户恒等失败或字段缺失时不得计算 | snapshot 增量投影 | P |
| `target_weight` | 目标权重 | 不可变信号中的目标权重 | 证券×信号/% | 不得由实际持仓反推 | `latest_signal` 提案 | P |
| `weight_gap` | 权重偏差 | `actual_weight - target_weight`，两者同一可比时点 | 证券×账户日/%pt | 任一缺失=`NO_DATA` | 组合/信号聚合契约提案 | P |
| `realized_pnl` | 已实现盈亏 | 不可变账户日产物登记的逐仓累计已实现盈亏 | 证券×账户日/RMB | 直接展示原字段；不与未实现盈亏混加 | snapshot.positions | I |
| `unrealized_pnl` | 未实现盈亏 | 后端查询投影 `market_value - cost_basis` | 证券×账户日/RMB | 任一字段缺失不计算 | snapshot 增量投影 | P |
| `stale_trade_days` | 估值陈旧交易日 | 当前估值价格日期至账户日之间的官方开市日数 | 证券×账户日/日 | 直接复用不可变产物；不得另建定义 | snapshot.positions | I |
| `cash_drag` | 现金拖累 | 冻结归因方法下由现金未投资导致的相对结果影响 | 账户日/% | 当前查询只有 cash_ratio，不能冒充 cash_drag | nav 增量字段提案 | P |
| `open_gap` | 次日开盘偏差 | `official_next_open / signal_day_close - 1` | 证券×执行日/% | 非交易腿仍可作观察，但须标定义 | 对账查询提案 | P |

## 5. 因子工厂

| 机器名 | 展示名 | 定义 | 空值与状态 | 来源 | 状态 |
|---|---|---|---|---|---|
| `factor_lifecycle_status` | 因子阶段 | `CANDIDATE/TESTING/REJECTED/ADMITTED/RETIRED`，由后台状态机返回 | 未登记=`NO_DATA` | `factor_catalog` 提案 | H/P |
| `factor_direction` | 冻结方向 | 研究前冻结的预测方向 | 不得观察结果后翻转 | `factor_detail` 提案 | H/P |
| `experiment_attempt_n` | 研究尝试数 | 同研究家族总账全部尝试，含失败 | 缺总账不得计算 DSR | 实验总账聚合提案 | H/P |
| `coverage_ratio` | 因子覆盖率 | 有效因子值证券日 / 应评估证券日 | 必须显示分子、分母和范围 | `factor_detail` 提案 | H/P |
| `rank_ic` | RankIC | 因子值与冻结 forward return 的日频 Spearman 相关 | 方向、horizon、中性化常驻显示 | factor tear sheet 提案 | H/P |
| `rank_ic_mean` | 平均 RankIC | 选定冻结范围内日频 RankIC 均值 | 不跨范围比较 | factor tear sheet 提案 | H/P |
| `rank_icir` | RankICIR | 平均 RankIC / RankIC 标准差，年化规则由后台冻结 | 无冻结公式不展示 | factor tear sheet 提案 | H/P |
| `hac_t` | Newey-West t | 方向冻结后的日频 RankIC `Newey-West(10) t` | G1 要求 ≥3.0；前端不重算 | G1 判决查询提案 | H/P |
| `dsr` | DSR | 按研究家族全部实验 N 修正的 Deflated Sharpe Ratio | G1 要求 ≥0.95；缺 N=`FAIL` | G1 判决查询提案 | H/P |
| `quantile_spread` | 分位收益差 | 冻结 horizon 下最高与最低分位组合收益差 | 必须显示分位数、误差和中性化 | factor tear sheet 提案 | H/P |
| `factor_autocorrelation` | 因子自相关 | 相邻评估期因子排名相关 | 与换手共同解释 | factor tear sheet 提案 | H/P |
| `quantile_turnover` | 分位换手 | Top/Bottom 分位成员在冻结周期内的更替率 | 明确周期和分母 | factor tear sheet 提案 | H/P |
| `library_max_abs_corr` | 因子库最大相关 | 候选因子与既有正式库因子值的最大 `|ρ|` | G1 要求 <0.5；正式库空时 N/A | 因子相关查询提案 | H/P |
| `candidate_max_abs_corr` | 候选池最大相关 | 候选内部最大 `|ρ|` | >0.7 触发去重，不等于准入线 | 因子相关查询提案 | H/P |
| `oos_decay_ratio` | 样本外衰减 | OOS RankIC 相对发现期的衰减比例 | 必须标发现期/OOS；不得混窗 | G1 判决查询提案 | H/P |
| `incremental_net_icir` | 增量净 ICIR | 新因子加入基线后相对基线的净 ICIR 增量 | 未准入/未跑组合=`NOT_APPLICABLE` | 准入判决提案 | H/P |
| `incremental_net_excess` | 增量净超额 | 同成本同窗口下加入因子后的净超额变化 | 不用单因子收益替代 | 准入判决提案 | H/P |
| `gate_decision` | 准入判决 | 后台 G1 裁判的 PASS/REJECT/NOT_READY | 显示全部失败门 | `factor_admission_history` 提案 | H/P |

## 6. 模型、数据与运行

| 机器名 | 展示名 | 定义 | 空值与状态 | 来源 | 状态 |
|---|---|---|---|---|---|
| `window_net_excess` | 窗口扣费超额 | 每个预注册 OOS 窗口的扣费后超额 | 窗口缺失=`NO_DATA` | `experiment_summary` 提案 | H/P |
| `sentinel_status` | 哨兵状态 | S1-S10 后台报告结论 | 未适用与缺失分开；报告未历史哈希绑定时证据 WARN | `GET /api/v1/data-quality` | I |
| `bse_count` | 北交所计数 | 当前对象中的 `.BJ` 行/订单/持仓数 | 必须为 0；非 0=`FAIL` | 现有页面与数据质量查询 | I |
| `task_status` | 核心任务状态 | 调度周期的核心执行结论 | 不与通知合并；失败后恢复为 WARN | `GET /api/v1/system/runs` | I |
| `notification_status` | 通知状态 | 同一逻辑消息多次 attempt 的最终投递状态 | 失败保留；恢复不覆盖失败 | `GET /api/v1/notifications/{message_id}` | I |
| `registered_batch_count` | 登记批次 | 截止日运行完成时进入数据快照的批次数 | 只证明登记身份链；不等于原始文件重哈希 | `GET /api/v1/data-quality` | I |
| `raw_parquet_rehash_status` | 原始文件重验 | 查询时是否逐字重哈希原始 Parquet | P3-2A 固定 `NOT_EVALUATED` | `GET /api/v1/data-quality` | I |
| `sentinel_evidence_status` | 哨兵证据完整性 | 哨兵报告是否有历史时点哈希绑定 | 当前固定 WARN/`IDENTITY_MATCH_UNHASHED` | `GET /api/v1/data-quality` | I |
| `replay_status` | 账本重放 | 独立重放全部账户日的结论 | 非 PASS 禁止可信组合结论 | `verify_paper_replay.status` | I |
| `replay_run_count` | 重放账户日 | 重放覆盖的 PASS run 数 | 无 run=`NO_DATA` | `verify_paper_replay.run_count` | I |
| `replay_event_count` | 重放事件数 | 重放核对的事件总数 | 无事件=`NO_DATA` | `verify_paper_replay.event_count` | I |

## 7. 暂不展示

- 未达到 R5 分层门槛的年化收益、Sharpe、信息比率；达到天数但后台公式、无风险收益来源或序列相关修正未冻结时仍不展示；
- 胜率、预测准确率：没有冻结定义且容易误导中低频选股效果；
- “AI 置信度”与不可审计因子贡献：后台没有确定性契约；
- BACKFILL 四日排名、年化或策略结论：只可在工程验收上下文查看；
- 任何由前端扫描文件、自由 SQL 或跨快照拼接得到的数字。
- 因子单一综合分、星级、排行榜、“最佳因子”徽章或未经过多重检验校正的显著性标签。

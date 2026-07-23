# P1 主力资金流隔离增量实验协议 — p1-moneyflow-v1

冻结时间：2026-07-24（UTC+8），早于 2016—2026 全量资金流回填、候选面板生成和 W1—W6
增量结果读取。状态：**预注册、仅授权隔离研究**；不得接入生产模型、正式信号、scheduler 或模拟仓。

## 1. 唯一研究问题

在中证 800、Alpha158、次一开盘成交、Top30、每 10 个交易日调仓和既有费用口径全部不变时，
`tushare.moneyflow` 的滞后资金流信息能否在行业、规模、成交活跃度和 Alpha158 基线暴露之外，
带来跨窗口稳定、扣成本且通过 `g1-v1` 的增量结果。

成功采集、单窗口 IC 为正、原始因子收益为正或某个候选表现最好，都不构成目标通过。六个候选逐一接受
同预算裁决；普通 `REJECT` 是有效完成，不得看结果增加变体或修改门槛。

## 2. 数据与时钟

- 唯一正式主源：`tushare.moneyflow`；THS/DC 只保留数据质量诊断地位。
- 原始唯一键：`(ts_code, trade_date)`；`.BJ`、重复键、非有限值或可能截断均失败即停。
- `moneyflow-pit-v1`：原始 D 日资金流最早在下一官方交易日 D+1 使用；特征日 `t` 最多使用
  `t-1` 及以前的资金流。
- `daily.amount` 单位为千元，进入公式前除以 10 转为万元，与资金流金额字段对齐。
- 滚动窗必须由连续的官方开市日组成。任一成分日缺失时，该窗口为缺失；不得把“最近 N 条记录”
  冒充连续 N 个交易日，不前填、不后填、不以 0 填补。
- 全历史单日质量失败按 `moneyflow-quality-v2` 整日隔离：全期、发现期和每个 W1—W6 有效源日
  均须不低于 95%，压力期不低于 90%，连续隔离日不超过 10 日；单日质量门本身不放宽。
- 原始层不截尾、不猜测证券代码映射、不重算官方 `net_mf_amount`；正式派生值在完成 T+1 对齐后，
  仅按同一特征日横截面做 1%/99% winsorization。

## 3. 固定候选预算与公式

研究家族固定为 `p1-moneyflow-v1`，正式预算固定为六个候选。符号定义：

- `A_d = daily.amount_d / 10`，当日成交额，万元；
- `N_d = net_mf_amount_d`，供应商官方净流入，万元；
- `L_d = buy_lg_amount_d + buy_elg_amount_d - sell_lg_amount_d - sell_elg_amount_d`，
  大单与特大单有符号金额，万元；
- `sign(0)=0`。

| ID | 冻结公式（在原始日 d 计算，映射到下一交易日使用） | 研究含义 |
|---|---|---|
| `mf_net_intensity_1d` | `N_d / A_d` | 单日官方净流入强度 |
| `mf_large_intensity_1d` | `L_d / A_d` | 单日大/特大单失衡强度 |
| `mf_net_intensity_5d` | `sum(N,5) / sum(A,5)` | 一周量级的累计流入压力 |
| `mf_net_intensity_20d` | `sum(N,20) / sum(A,20)` | 一月量级的持续流入压力 |
| `mf_net_innovation_5_20` | `mf_net_intensity_5d - mf_net_intensity_20d` | 短期相对长期的流量创新 |
| `mf_net_persistence_10d` | `mean(sign(N),10)` | 流入方向的持续性，弱化金额极值 |

不加入更多窗口、阈值、平方项、分段项或候选组合。论文同时给出订单拆分导致的持续性、价格压力延续
以及流动性供给后的反转机制，因此六个候选不预设正负方向。候选方向只由发现期 RankIC 符号冻结，
样本外不得翻转。

## 4. 正式派生与残差化

每个候选在特征日横截面 winsorization 后分两层做 OLS 残差化：

1. 申万一级行业 PIT one-hot；
2. `log(total_mv)`；
3. `log(daily.amount)`；
4. `turnover_rate`；
5. W1—W6 评估日额外加入该窗口训练冻结的同日 Alpha158 基线预测分数。

第一层为 `candidate_core`，在发现期和 W1—W6 使用完全相同的行业/规模/成交活跃度处理；发现期
没有此前三年可训练的 Alpha158 基线，候选方向只由 `candidate_core` 冻结，禁止用样本外结果补方向。
第二层为 `candidate_incremental`，仅在 W1—W6 将同日 `candidate_core` 再投影到各窗已训练且冻结的
Alpha158 分数之外；只有该增量残差进入正式样本外 RankIC 和 `90% + 10%` 组合。这一分层避免用
不存在的发现期模型分数伪造同口径，也确保样本外组合真正检验 Alpha158 之外的信息。

连续暴露先在当日横截面 1%/99% winsorization，再标准化；缺少当层任一必要暴露的证券保持缺失。
每日有效横截面少于 30 或残差无变化时，该日不产生因子值。原始候选只作诊断，不参与正式裁决。

## 5. 发现、窗口与组合对照

- 请求发现期：2016-01-01 至 2018-12-31；因 qlib 100 日回溯约束，实际可评估起点与既有 G1
  流程一致，最早为 2016-06-01。该期间只冻结方向，不选择窗口、公式或权重。
- 样本外：冻结的 W1—W6，集合和日期完全复用 `config/settings.yaml`。
- 每个候选单独运行一次：`90% Alpha158 横截面排名 + 10% 方向冻结后的候选残差排名`。
- 基线和候选使用相同中证800 PIT 股票池、标签、Top30、调仓日、次一开盘、涨跌停/停牌语义、
  账户规模和费用。不得用更有利的成交样本或替代基准。
- 正常费用、费用 +100%、买卖各额外 10bp 三种情景全部重放；三段压力期沿用 `g1-v1`。

六个候选及任何系统失败都进入 `ledger/experiments.csv` 的同一研究家族，失败也计多重试验 N。
首轮禁止把表现较好的候选再拼成组合；如未来确有独立理由，必须另立家族和新预注册。

## 6. 裁决与停止规则

每个候选必须调用冻结的 `g1-v1` 十五门，完整核对 PIT/shift、复杂度、人工经济含义、相关性、
W1—W6 同向性、RankIC 保留、压力期回撤、换手、增量 ICIR、增量净超额、双倍成本、双倍滑点、
有效试验数、DSR 和 Newey-West(10) t 值。

- 至少一个候选十五门全部 PASS：结论为 `GO_REVIEW_ONLY`，只允许另立目标评审生产接入。
- 全部普通不达标：结论为 `REJECT`，保留证据并进入科创50主线；不调门槛、不追加变体。
- 数据修订、证据损坏、PIT/shift 失败或绑定不一致：结论为 `BLOCKED_EVIDENCE`，停止裁决并修复
  证据问题；不得把系统失败写成因子 REJECT。

无论 PASS 或 REJECT，只有不可变候选面板、逐日 IC/收益、实验总账、G1 决策、代码/数据/规则哈希
和幂等复跑全部可重算，目标才算完成。

## 7. 隔离与资源边界

- 新代码和测试只位于 `tools/p1_moneyflow/`；生产 `src/`、`tests/`、`config/`、模型、门禁、信号和
  scheduler 不变，生产代码快照不得因本实验漂移。
- 全量回填和实验使用一次性 Docker 任务；不新增常驻服务，不继承 Web 工作，不与 19:30 后的每日
  scheduler 争抢资源。窗口串行执行并记录峰值 RSS。
- 数据、日志和不可变研究产物留在本项目目录且不进 Git；Git 只提交脱敏代码、规格和结果摘要。

## 8. 方法依据（只约束假设，不替代本项目证据）

- Tushare 个股资金流字段与单位：<https://tushare.pro/document/2?doc_id=170>
- Chordia & Subrahmanyam (2004), *Order Imbalance and Individual Stock Returns: Theory and Evidence*：
  <https://doi.org/10.1016/S0304-405X(03)00175-2>
- Andrade, Chang & Seasholes (2008), *Trading Imbalances, Predictable Reversals, and Cross-stock
  Price Pressure*：<https://doi.org/10.1016/j.jfineco.2007.04.005>
- Tóth et al. (2015), *Why Is Equity Order Flow So Persistent?*：
  <https://doi.org/10.1016/j.jedc.2014.10.007>

上述文献使用的市场、样本和订单识别均不等同于 Tushare 的数据商分桶，因此只支持“延续与反转都应
事前允许、必须归一化并控制交易活跃度”的研究设计，不构成 A 股有效性结论。

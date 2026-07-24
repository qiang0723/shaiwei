# P2-2C 科创50历史效果综合方法纠错协议 v1（纠错结果前冻结）

冻结时间：2026-07-25 01:30（UTC+8）

状态：**FROZEN BEFORE ANY CORRECTED REAL HANDLER, TRAINING, PREDICTION, EXECUTION OR EFFECT RESULT**。

机器真身为 `config/p2_star50_effect_correction_v1.yaml`，冻结输入审计为
`config/p2_star50_effect_correction_input_audit_v1.json`（SHA-256
`c228943ca2247d93c0c6bf0921b308a87d79a277f5e8b13029b0b02d0d496f1a`）。本协议不是新策略变体或
盲预注册：原 P2-2 结果和主控 open-clock-only 敏感性已可见，当前仅对三项已确认方法错误做一次
综合纠错及一遍确定性复核。无论结果如何，`production_authorization=none`。

## 1. 不可变输入与旧证据

P2-2C 继续绑定 P2-1 终版 `ea225cdaf06b951932ca5155ede7b61676fe0847`、official-lineage-v2 五项
证据、market/member/benchmark 三份 Parquet、qlib 整树
`b8f736ef9bc9e31cc236a81ca281a23e904789fb5ec87caa9195b572c6b78729` 和 build identity
`dca65a090284de044346bcea7f6ff7364f9a23e3479c9f77c1832f45b2fd26e6`；精确哈希完整列在机器配置。

同时绑定原 P2-2 freeze/final commit、报告、manifest、专属账本、原 model/executor/run/metrics 代码、
model/prediction bundle 和原结果目录整树。旧证据不得改写、删除或重算覆盖。P2-2C 使用新的
dataset 外层身份、model/config/signal/result root、run ledger、admission ledger 和 tracked manifest；
不写 CSI800、共享/前瞻 qlib、生产模型/信号/账本、模拟仓或 scheduler。

真实纠错前必须同时满足：工作树干净、`HEAD=origin/main`、冻结提交已推送、全部输入逐哈希一致、
生产 scheduler healthy。任何漂移、额外同类方法冲突或资源异常均先停下回主控。

## 2. 唯一三项纠错

### A. train/valid 标签成熟 purge

标签和含义不变：`Ref($open,-11)/Ref($open,-1)-1`。每个 train/valid 原日历端点先落到不晚于端点的
最后官方交易日，再向前第 11 个官方交易日作为最后可入模 signal date；最后 11 个 signal date 被剔除，
原端点和 test 起点均不移动。处理器 `fit_end_time` 必须等于 purge 后 train 最后信号日。

冻结日期为：

| 窗口 | train 最后信号 | valid 最后信号 |
|---|---:|---:|
| STAR-W1 | 2022-06-15 | 2022-12-15 |
| STAR-W2 | 2023-06-13 | 2023-12-14 |
| STAR-W3 | 2024-06-13 | 2024-12-16 |

机器审计逐窗证明 purge 后最大标签成熟日不晚于原段末，valid 标签成熟严格早于首个 test 交易日；并
反证原未 purge train/valid 的标签成熟日分别越入后续段。early stopping 只读取 purge 后 valid，禁止
使用 test 标签、移动 test、调参、换 seed 或按纠错结果重训。

### B. 次日开盘时钟与前收估值

开盘可成交性只读执行日 `open/pre_close/factor/raw_volume`：

- `raw_open=open*factor`，`raw_pre_close=pre_close*factor`；
- `opening_change=raw_open/raw_pre_close-1`；
- `tolerance=0.01/raw_pre_close`；
- 买入阻断：`opening_change >= 0.195-tolerance`；
- 卖出阻断：`opening_change <= -0.195+tolerance`；
- open、pre_close、factor、raw_volume 任一无效或非正即不成交并保留持仓。

执行日 close、pct_chg 和旧 `limit_buy/limit_sell` 不得决定当日开盘成交。若持仓缺 open，`nav_open`
只能使用前一交易日最后有效 close；执行和收盘估值完成后才允许更新当日 `last_close`。首成员日前有效
bar 缓冲最少 74 个交易日，当前成员执行段不存在首发前五日问题；该断言运行前 fail closed。

### C. 买卖双向 5% 单次订单容量

每次买单和卖单都以信号日截至当日的 20 个交易日有效 amount 中位数的 5% 为单次 notional 上限。
卖出同样允许部分成交，未卖完持仓原样保留并在后续冻结调仓日继续尝试。为退出成员、ST 或其他硬
不合格持仓计算卖出容量时，流动性集合必须包含当前全部 holdings，不能只含当日 prediction 成员；
有效 amount 少于 15 日、median 缺失/非有限/非正时，卖出容量为零，禁止虚构流动性。

原基础场景审计基线固定为 893 笔：买 498、卖 395；买单 >5% 为 0，卖单 >5% 为 14，最大
11.3037996634%，按 W1/W2/W3 分别 7/4/3 笔。P2-2C 每笔 corrected buy/sell 的 capacity utilization
必须 `<=1`，否则失败。

## 3. 完全不变的模型、组合、成本和门槛

除上面三项外，原 P2-2 全部口径逐字段相等：Alpha158、LightGBM seed42 与超参数、W1/W2/W3 原始
窗口和 test 区间、三压力段模型映射、Top10/n_drop2、每 10 个官方交易日、次开盘、等权、1 亿元、
约束不足留现金、目标权重、行业/ST/成员约束、整数股、四成本场景、pooled 定义、三窗/成本/回撤/
分散化门及阈值。合法 CSI800 同口径真身仍缺失，禁止造代理；分散化继续按冻结合同
`NOT_EVALUABLE_AND_NO_GO`。

后复权交易数量/目标约束而非逐日实际权重等既有 caveat 不在本次纠错范围，不能趁纠错修改。若冻结
前同类边界审计再发现会改变结论的冲突，必须先上报；冻结后不允许边跑边补丁。

## 4. 唯一运行、确定性与机器结论

冻结推送成功后，只允许按上述 purge 训练一套 W1/W2/W3 模型，然后以相同输入/代码/seed 做一遍
确定性复核。两遍比较 model、prediction、daily NAV、trade、holding、pooled canonical hash，并逐文件
比较 54 份不含运行时间 metadata 的可比产物。真实产物只写 Git 忽略的独立 correction root；Git 只
提交脱敏汇总、哈希 manifest、专属账本、测试和验收文档。

终版至少输出：

- `original_p2_2_model_valid=false`；
- `original_p2_2_execution_valid=false`；
- 三项 `correction_scope`；
- `results_known_before_correction=true`；
- `model_retrained=true`、`predictions_recomputed=true`；
- corrected window/cost/drawdown/diversification/determinism gates；
- `authoritative_historical_effect_gate=GO/REJECT/NO_GO`；
- `strategy_effective=HISTORICAL_GO_FOR_FORWARD_ONLY/REJECT`；
- `production_authorization=none`。

只有原冻结全部硬门通过才是历史 GO，且最多允许主控另立前瞻观察；P2-2C 不生成生产信号、不改模拟仓、
不接 scheduler。若 standalone 门失败，可恢复权威 REJECT；若 standalone 通过但 comparator 仍缺，只能
NO_GO/NOT_EVALUABLE。任何结论下均不得自动进入前瞻或生产。

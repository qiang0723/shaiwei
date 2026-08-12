# TS-1A v3结果盲数据门验收

日期：2026-08-12（UTC+8）

## 1. 权威裁决

`MULTIPLE_BLOCKS`：`BLOCKED_MARKET_RULE` + `BLOCKED_DATA`。

这不是TS策略效果失败。TS-1A没有读取候选入场后的收益，没有生成股票推荐、模型、回测、模拟仓或
生产信号；当前只证明v1输入合同尚不足以形成无歧义候选漏斗。不得进入TS-1B、效果或Web施工。

机器报告和独立审计保存在项目内Git忽略目录：

- `data/research/trend_swing/ts-v3-data-gate-v1/input_manifest.json`，SHA-256
  `b62c77781f75518027452901fab7fafaf251e198d98d314a3b104de5fd9ab495`；
- `data/research/trend_swing/ts-v3-data-gate-v1/profile_report.json`，SHA-256
  `d606a3adb7357f29c89e77ae2989f9117e3b7d7bb44b9cb8845d878ed30f6664`；
- `data/research/trend_swing/ts-v3-data-gate-v1/audit.json`，SHA-256
  `bbeb4407d34757a095933fbd53cd05f4208877ededd0e9560a5f1ef3cd29e75b`。

真实运行代码身份为Git `41866ade6596e0f34dd0614b0bf78be0bd0ca901`，受控代码快照为
`0711171c230e77d773e4349490ac0788efbb3ccc32bdaa15266b9621e0d89a76`。

## 2. 真实读取边界

- 外网请求0，DeepSeek/Tushare/Baostock新调用0，密钥读取0；
- 策略效果尝试0，`strategy_results_inspected=false`；
- 生产授权`none`，未修改scheduler、模型、信号、模拟仓、Web或任何生产门槛；
- manifest重新核验44,195个不可变源批次、32,660,428行，独立audit全部PASS；
- 既有Alpha158 OOS缓存存在：1,164,697行、1,456日、1,239只，2019-01-02至2024-12-31；因上游
  数据门阻断，事件键覆盖保持`NOT_EVALUATED_UPSTREAM_BLOCKED`，未读取TS效果。

## 3. 阻断一：创业板官方指数缺失

冻结映射要求主板=`000906.SH`、创业板=`399006.SZ`、科创板=`000688.SH`且禁止互相替代。现有
`index_daily`中：

- 中证800有2,575个唯一交易日，2016-01-04至2026-08-11；
- 科创50有1,590个唯一交易日，2019-12-31至2026-07-24；
- 创业板指`399006.SZ`为0行。

因此`BLOCKED_MARKET_RULE`成立。恢复必须另立结果盲恢复协议，只补采`399006.SZ`在
2016-01-01至2026-08-11的官方日线并经不可变批次、主键、交易日和哈希门验证；不得用中证800、
当前指数或未来数据替代。

## 4. 阻断二：95个成员日未被v1合同解释

PIT中证800共2,060,800个成员日、2,576个交易日、1,514只历史证券和127个成分快照；`.BJ=0`、
重复键0、冲突键0，日线/复权/市值/成交额覆盖均通过，申万L1唯一归属覆盖99.2539%。日线或
Tushare全天停牌可解释覆盖为99.99539%，但冻结硬门要求未解释缺bar必须为0，实际为95。

结果盲键级诊断把95个缺口闭合为两类：

1. 90个落在7只退市/换股证券的`delist_date`及之后：`000748.SZ` 6日、`600005.SH` 10日、
   `600270.SH` 22日、`000418.SZ` 5日、`600068.SH` 11日、`600837.SH` 19日、`601989.SH` 17日。
   `DATA_SPEC.md`已冻结`delist_date`为存续区间右开，但v1 required sources漏列
   `tushare.stock_basic`，所以真实运行不能事后用它改判。
2. 余下5个单日缺口为`000413.SZ/601899.SH`的2019-11-19和
   `001979.SZ/002049.SZ/601969.SH`的2020-06-05。项目内既有不可变
   `baostock.history_k_data_plus`对5键均为`trade_status=0`，确认未交易；v1同样漏列该独立状态源，
   不能事后纳入权威报告。

所以这里暴露的是输入合同遗漏，不是已发现的行情坏账。v1报告和裁决永久保留，不静默改写。

## 5. 下一合法节点

下一节点应为`TS-1A-R1_RESULT_BLIND_DATA_CONTRACT_RECOVERY`，仍不读取任何收益，且只允许：

1. 在结果前把`stock_basic`右开退市区间和既有Baostock `trade_status=0`纳入required sources与独立
   audit；
2. 取得用户对一组固定Tushare `399006.SZ`请求的精确网络授权，采集后回到断网评价；
3. 重新核验指数、成员日、行业谱系、Alpha158事件键覆盖，并完成v1尚未执行的板块/个股结构、波动、
   放量、入场距离、空仓期和容量画像；
4. 只有R1全部通过才允许冻结TS-1B唯一业务口径。补完数据本身不等于策略有效，也不授权效果、模拟仓、
   Web或生产。

## 6. 工程验收

- 新增`shaiwei.research.trend_swing`按合同、源读取、数据质量、纯特征、编排、独立审计分层；最大模块
  256行，未新增大文件或反向依赖；
- 专项10 PASS，架构门13 PASS，全仓1,079 PASS；Ruff、compileall、pip check、diff-check均PASS；
- 报告写一次后相同scope禁止重跑，manifest/report/audit均不可覆盖；
- 自然跑批账本和两份无关平台校准产物未纳入本节点提交。

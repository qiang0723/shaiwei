# 数据口径卡（DATA_SPEC）— 违反任一条都会产生不报错的静默污染

来源：可行性报告 v0.5.4 第 5 章 + 枢衡施工避坑单。实现任何采集/转换代码前先对照本卡。

## 采集层
1. **6000 行硬顶（最高危）**：daily / adj_factor 单票单次最多返回 6000 行，长历史票早年整段静默截断，全市场约千只中招。→ 每票按 `list_date → 今` 日期窗分页拉取；完成后必须过「完整性对账」哨兵。
2. **namechange**：传日期区间会静默丢约一半行（丢的多为上古改名行）。→ 全量拉取、本地筛选。
3. **上古退市缺口**：2007 年前退市的 T 前缀代码 stock_basic 不返回。回测起点 2016 不受影响；起点前移必须重估。
4. **幽灵 bar**：个别历史日 is_open=0 但行情源有 bar。→ trade_cal 为权威轴，bar ∩ calendar，收益跨到前一日历交易日。
5. **北交所**：以 .BJ 后缀为唯一零漏网识别（数字段筛选漏 920 段约 98%）。全市场口径含不含北交所在 config 写死一次，全管线一致。
6. **频控与并发**：1 万积分常规接口官方上限 500 次/分钟；本地最多 8 路并发用于隐藏网络延迟，但所有线程共享 0.15 秒请求起点间隔（理论硬顶 400 次/分钟）。响应与写盘解耦，账本仍按冻结请求计划顺序串行提交。

## 口径层
7. **复权**：后复权 + 上市首日 factor=1（与 qlib 原生一致）。daily（不复权）+ adj_factor 本地自算；禁用 pro_bar qfq/hfq（历史时段异常、前复权基准漂移，GitHub #924/#1546/#1555）。
8. **量纲**：Tushare vol=手、amount=千元；AlphaGen/baostock 假设 股/元。→ 转换层强制 vol×100、amount×1000。VWAP=amount/volume 若量纲错会差 10-1000 倍且 IC 照常可算。
9. **财务 PIT**：只用 income/balancesheet/cashflow 三表自建；fields 显式请求 update_flag、report_type、f_ann_date。逐股常规接口默认只给 report_type=1，必须再按季度用 income_vip/balancesheet_vip/cashflow_vip 显式补采稀疏的 report_type=5；不能用同一公告日下的 update_flag=0 冒充“更正前时点”。PIT 对齐用 f_ann_date ≤ 交易日 D；模拟日落在更正区间取 report_type=5 / update_flag=0；直接取 report_type=1 最新行 = 前视偏差。fina_indicator 缺 f_ann_date/report_type，不得用于严谨 PIT。盘后公告保守算次日可用。
10. **ST 状态库**：namechange 存在 end_date=NULL 的历史 ST 行；按「含 ST 且 end 为空即 ST」会把摘帽票永久钉成 ST（约一成宇宙误判）。→ latest-effective-name 按时点取现行有效名做 PIT 判定；同日双名保守判 ST；「XX退」判非 ST（退市整理期限幅主板 10%、创业板/科创板 20%，首日不设限）。
11. **停牌**：停牌日 OHLCV=NaN，禁 0 或前值填充（零填充制造正自相关、统计量虚高，Kallunki 1997）；自算因子同样禁零填充，收益按 trade-to-trade 跨缺口口径；与 suspend_d 交叉核对。
12. **涨跌停**：主板 0.095；创业板 2020-08-24 前 0.095、之后 0.195（回测跨此日分段）；科创板 0.195；ST 0.045；退市整理期首日不设限。涨跌停价按分价位取整，比对留一分钱容差。
13. **成分股**：index_weight 为月度快照，向前填充对齐到日频。退市股保留在历史宇宙中（stock_basic delist_date）。
14. **北向资金**：2024-08-19 起无日度披露（监管变化），不作因子。
15. **行业中性化**：AlphaGen benchmark 禁用 stock_basic 当前行业覆盖历史；申万 L1 暴露来自 index_member_all 的 in_date/out_date 区间，逐交易日 PIT 对齐，未覆盖行留缺失并不得用未来行业回填。

## 转换层（→ qlib bin）
16. 代码映射 600000.SH → SH600000；停牌日各字段留 NaN；首日 factor=1；每股一文件。
17. 有除权的日子触发 dump_fix 重写该股全历史（后复权因子变化改写全序列）；常规日 dump_update 增量；新股上市注意 instruments 文件更新（dump_bin 已知不自动处理多时间段）。
18. 勿直接消费 chenditc/investment_data 预打包 bin 作研究底库（issue #1976 与 Tushare 原值差异大）。

## 工程纪律
19. **数据不可变**：data/raw 按批次只增分区永不改写，批次元数据（源、参数、时间戳、行数）入库；bin 为可重建派生缓存。
20. **数据时钟契约**（影子执行启动后生效）：数据完整性确认时间（哨兵全过）→ 信号生成截止 → 订单清单生成 → 缺数或哨兵未过则当期不交易，宁可跳过不带病出单。

# 阶段 0 施工手册（Day 1-7，全职口径；兼职按 2-2.5 倍拉长）

每日收工：更新 STATE.md 进度与待答点；实验/异常写入 ledger。

## Day 1-2 · 骨架与基础表
- 目录骨架：`config/ data/raw/ data/duckdb/ data/qlib_bin/ src/{ingest,transform,sentinel,backtest,shadow}/ ledger/ logs/`
- config：Tushare token（环境变量注入，不入 git）、北交所口径开关、回测窗口（2016-01-01 起）、板块涨跌停规则表
- 拉取并落 Parquet：trade_cal（权威日历轴）、stock_basic（list_status=L/D/P 全量，含 delist_date）、namechange（全量！不传日期区间）、index_weight（SH000906 全历史，月度）、suspend_d
- 构建：动态股票池（免幸存者偏差）、ST 状态库（latest-effective-name PIT 逻辑）→ 跑哨兵 S9
- fund_comparator.csv 填充并 commit（启动日冻结，见 templates/）

## Day 3-4 · 全量行情与哨兵
- daily + adj_factor 全市场：**每票按 list_date→今 日期窗分页**（6000 硬顶）；批次元数据入库
- 本地后复权（首日 factor=1）；量纲统一 vol×100 / amount×1000；派生 VWAP
- 跑哨兵 S1 完整性对账（全市场，逐票归因）→ S2 双算闸 → S3 复权反算（四类样本）→ S4 量纲 → S6 停牌 → S7 量价逻辑 → S8 交叉比对
- 退出标准：全部哨兵 PASS，零未归因异常

## Day 5 · 财务 PIT
- income/balancesheet/cashflow 三表全量（fields 显式含 update_flag/report_type/f_ann_date）
- PIT 快照逻辑（f_ann_date 对齐、更正前取 report_type=5）→ 跑哨兵 S5 京东方A 回归测试
- 本日产出只入库不入因子（财务因子属阶段 2），目的是把 PIT 层和回归测试建成

## Day 6 · qlib 基线 + 影子执行启动
- dump_bin 转换（代码映射/停牌 NaN/factor 列）→ qlib init → check_data_health
- Alpha158 + LightGBM，自定义双周版 TopkDropoutStrategy（topk=30, n_drop=3, deal_price=open, 成本参数见报告 4.5，含成本情景带三档输出）
- 覆盖三段压力期；输出 G0 三条件所需全部数字（6 滚动窗口超额、+50% 情景累计超额）
- **启动影子执行**：当日截面 → 信号清单哈希入 git → 次日对账可成交性与开盘偏离（此后每交易日例行）

## Day 7 · AlphaGen CPU benchmark（选型定案实验）
- clone alphagen（+ AlphaEval 作对照参考）；gp.py device 改 "cpu"
- fitness 改为：行业+对数市值中性化残差 RankIC，标签 = 双周 forward return（注意拆 MseAlphaPool 耦合层——它优化的是池组合 IC 非单因子 IC）
- CSI300 小样本先通量纲断言（S4），再跑单轮：记录 耗时 / 峰值内存 / 产出因子 RankIC 分布 → 写入 STATE.md 待答区
- 判读：单轮 <4h 且 RankIC>0.03 → 阶段 1 放大；>12h 或内存爆 → 降参/纯 numpy 向量化/评估短租 GPU；AlphaGen 改造 2-3 天不通 → fallback 自建轻量 GP

## 阶段 0 退出（对 G0）
① 哨兵全过零未归因 ② 6 窗口 ≥4 正超额 ③ +50% 成本情景合并超额 ≥0 ④ 两个动手验证（CPU 耗时、量纲）定案。全部达成 → 报告升 v1.0，进入阶段 1；任一未达 → 按 G0 触发动作执行，不进入 GP。

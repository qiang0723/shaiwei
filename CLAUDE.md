# 筛微系统 · Claude Code 施工守则

本仓库为「筛微」A 股中低频量化因子系统。规划基线：《筛微系统可行性技术报告 v0.5.4》（docs/ 存档）。施工依据以 docs/ 下蒸馏文档（DATA_SPEC/GATES/SENTINELS/DAY_PLAN）为准，日常不必通读报告全文；蒸馏文档与报告冲突时，停下向人上报，不自行裁决。本文件是每个 Claude Code 会话的第一优先级指令。

## 会话纪律（不可协商）

1. **每会话开工先读 `STATE.md`，收工必更新 `STATE.md`**。会话记忆一律视为草稿，git 为真身。改判任何既定口径时，必须在 STATE.md 显式作废旧结论并注明日期。
2. **不修改任何已冻结判据**（G0-G9、C0，见 docs/GATES.md）。发现判据有问题时：记录到 STATE.md 待答区，不擅自变通。
3. **数据不可变**：`data/raw/` 下 Parquet 按批次只增分区、永不改写；每批次记录（源接口、参数、时间戳、行数）。qlib bin 是派生缓存，可全量重建；dump_fix 只动 bin 层。
4. **实验必须记账**：任何因子候选、参数搜索、失败尝试，写入 `ledger/experiments.csv`（append-only）。不记账的实验视为未发生。
5. 一次只动一个变量。禁止在同一 commit 里同时改数据管线和因子逻辑。

## 本机约束（Mac Pro M5）

- 10 核（4P+6E）/ 24GB 统一内存 / 1TB SSD，macOS arm64。
- joblib 并行上限 6-8 进程，留 ≥8GB 系统余量。
- PyTorch 一律 `device="cpu"`；MPS 是阶段 1 之后的可选实验，阶段 0 禁用。
- RD-Agent 不在本机部署（需 Linux 原生，属阶段 2）。
- 代码不写死路径；所有路径、token、参数走 `config/`；假设未来会迁移到 Linux 生产机。

## 硬编码级数据口径（违反即产生静默错误，详见 docs/DATA_SPEC.md）

- Tushare `daily`/`adj_factor` 单票单次最多 6000 行 → 所有长历史拉取必须按日期窗分页。
- 量纲：Tushare vol 单位=手、amount=千元 → 入库统一 vol×100（股）、amount×1000（元）。
- 复权：统一后复权 + 上市首日 factor=1；禁用 pro_bar 的 qfq/hfq 参数；用 daily+adj_factor 本地自算。
- 财务 PIT：只从三大报表自建，显式请求 update_flag/report_type/f_ann_date；PIT 对齐用 f_ann_date；更正前取 report_type=5/update_flag=0；禁用 fina_indicator 做严谨 PIT。
- namechange 全量拉取后本地筛，禁止传日期区间；ST 判定按 latest-effective-name PIT 逻辑。
- 停牌日 OHLCV=NaN，禁止零填充/前值填充；收益按跨缺口口径。
- 交易日历以 trade_cal 为权威轴，bar ∩ calendar。
- 北交所以 .BJ 后缀识别；全市场口径是否含北交所在 config 里写死一次。
- 涨跌停分板块分时段：主板 0.095 / 创业板 2020-08-24 前 0.095 后 0.195 / 科创板 0.195 / ST 0.045 / 退市整理期首日不设限；贴板判定留一分钱容差。

## 机械约束（比文档纪律优先级更高）
- 依赖唯一来源 pyproject.toml；配置唯一入口 `shaiwei.config.load()`（pydantic 校验），禁止散落魔法数字；密钥只走 .env。
- 账本唯一写入口 `shaiwei.ledger.append_*`；禁止任何直接改写 ledger/*.csv 的代码；每次 commit 前 `make check-ledger` 必过。
- 每批数据采集必须调用 `append_ingest_batch`（行数+sha256 入 git 账本）——git 里的哈希就是数据未被篡改的存证。
- 操作动词只有六个：`make bootstrap / ingest / sentinel / test / backtest-baseline / check-ledger`。新流程先加 make 目标再写实现。

## 完成的定义

任何数据管线代码，只有对应哨兵断言（docs/SENTINELS.md）编写完成、全量跑过、零未归因异常，才算完成。跑通 ≠ 完成。

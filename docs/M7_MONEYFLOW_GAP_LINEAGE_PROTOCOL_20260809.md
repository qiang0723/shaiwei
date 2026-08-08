# M7-0R2 资金流早期缺口谱系协议（2026-08-09）

- 协议 ID：`m7-moneyflow-gap-lineage-v1`
- 机器真身：`config/m7_moneyflow_gap_lineage_v1.yaml`
- 机器真身 SHA-256：`bf5ebac79cb1b81699e5a8f4d1fae13b78dedb35e7ed19672e0c69ea8254ad9e`
- 阶段：`GAP_LINEAGE_PROTOCOL_ONLY`
- 结果披露：M7-0 的覆盖失败已知；本协议冻结前未查看任何缺口类别结果

## 1. 要回答的问题

本节点只回答：原 M7 全日期域中没有匹配到 `moneyflow` 的成员键，能否被现有不可变本地证据完整、
互斥地解释为整日隔离、确有交易但资金流源缺键、独立证据确认未交易，或仍然冲突/无法归因。

它不修改原 M7 的 `NO_GO`，不补数据、不删除分母、不计算“剔除停牌后覆盖率”，也不生成资金流公式、
候选、标签、收益、模型、回测或生产信号。即使谱系 GO，也只说明缺失原因可解释，不表示数据兼容门
恢复为 GO。

## 2. 防止针对已知结果定制

诊断域固定为原 M7 的 2021-01-04—2026-06-30 全部 feature 日、三池、11 个完整半年和全部成员行，
不是只读取已知失败的四个“池×半年”单元。四个失败单元只作为报告焦点，不是输入筛选条件。

原 99.5%/99%/95% 覆盖门、PIT 下一交易日时钟、隔离语义、三池身份和最低名称门均不变。R2 不输出
任何调整后覆盖率或反事实 PASS/FAIL，避免用已知缺口结果重新定义分母。

## 3. 只读输入

继承原 M7 内容寻址输入束，只读取：

- `moneyflow`：`ts_code, trade_date`；
- M3 成员：`trade_date, formation_date, universe_id, ts_code, segment`。

新增三类既有本地不可变证据：

- `tushare.daily`：只读 `ts_code, trade_date`，用于确认源日存在真实行情键；
- `tushare.suspend_d`：只读代码、日期和停牌时段/类型；`suspend_timing` 非空只能算日内停牌，不能
  解释整日无 bar；
- `baostock.history_k_data_plus`：只读代码、日期和 `trade_status`，作为独立交易状态证据。现有目录
  覆盖不完整，缺失必须如实进入未决类别，禁止前后填充或把主源停牌单独升级成独立确认。

新增源的 metadata inventory 只从追加式 ledger 选择冻结时点前每个规范请求的最新批次，核对普通
文件、非软链、行数、schema 和 SHA。真实 Parquet 语义行在精确批准前仍为 0；资金流、行情数值列
永不读取。

## 4. 互斥分类

每一条原分母中的缺失成员行必须恰好落入一个类别：

1. `QUARANTINED_SOURCE_DATE`：源日已被 P1 整日隔离；
2. `CONFLICTING_INDEPENDENT_TRADE_STATUS`：独立源同键同时出现交易与未交易状态；
3. `CONFIRMED_MONEYFLOW_GAP_DAILY_PRESENT`：同代码同源日存在 daily bar，但 moneyflow 键缺失；
4. `CONFIRMED_NONTRADING_INDEPENDENT`：daily 不存在且 Baostock 明确 `trade_status=0`；
5. `CONFLICT_DAILY_PRESENT_INDEPENDENT_NONTRADING`：daily 存在但独立源称未交易；
6. `CONFLICT_DAILY_ABSENT_INDEPENDENT_TRADING`：daily 不存在但独立源称交易；
7. `CONFLICTING_PRIMARY_SUSPENSION_ROWS`：主源同日同时给出整日与日内停牌语义；
8. `PRIMARY_FULL_DAY_SUSPENSION_ONLY_UNRESOLVED`：只有主源整日停牌，没有独立确认；
9. `INTRADAY_SUSPENSION_NOT_EXPLANATION`：只有日内停牌，不能解释整日无行情；
10. `UNRESOLVED_NO_TRADE_EVIDENCE`：既无行情，也无足够的交易状态证据。

分类只输出三池×11 半年和全期的聚合计数/比率，不保存或提交证券清单。`.BJ`、重复关键键、非法代码、
PIT 映射错误、类别重叠/漏分均失败关闭。

## 5. 裁决语义

只有全部输入身份和键门通过、每条缺失行恰好一类、冲突为 0、未决为 0、Pandas 主算与 DuckDB 独立
审计完全一致，才返回 `GO_M7_GAP_LINEAGE_COMPLETE_ONLY`；否则返回
`NO_GO_M7_GAP_LINEAGE_INCOMPLETE`。

两种结论都保持 `strategy_effective=NOT_EVALUATED`、研究尝试增量 0、生产授权 `none`。GO 只允许另立
恢复决策协议；NO-GO 只说明本地证据不足，不等于资金流策略 REJECT。

## 6. 一次性执行和停止线

实现必须把 R1 的 pre-read consumption 接入 runner/auditor 真实入口：完成协议/release/approval 纯
控制身份核验后先原子消费角色，再允许语义 loader。第一次后续失败也不得同 scope 重跑；第二次调用
必须在 Parquet loader 前停止。

本目标只授权协议、metadata inventory、合成工程、断网镜像和精确 release scope。形成新 scope 后停止。
只有用户再次逐字绑定完整 scope SHA 并批准动作 `M7_MONEYFLOW_GAP_LINEAGE_ONCE`，才可唯一运行一次
runner 和一次独立 auditor；不能复用 M7-0 approval，也不授权外网、资金流数值、候选或效果。

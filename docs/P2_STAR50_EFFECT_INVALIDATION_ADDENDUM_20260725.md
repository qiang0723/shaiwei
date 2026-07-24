# P2-2 原历史效果裁决失效附录（不可改旧证据）

日期：2026-07-25（UTC+8）

状态：**原 P2-2 数值仍可复算，但方法裁决不再具有权威性；旧提交、报告、产物和账本必须原样保留。**

本附录只纠正证据层级，不删除或重写 `ed5b1b0d59bd18186ef99c9844123af473897fcb`、
`13d219dee6ff305d71c8bc0243b9bf5740828f03` 或其任何产物。原 effect report SHA-256 为
`94c458ae908e77af7808e27a41de2b386e920ad910c05a24718de621896f5ce9`，tracked manifest 为
`c12b9404899b94873b7923e20920b02e1a795fc0d75b8fc60d863327f7bf64cd`；原结果目录 115 个文件、
1,551,575 bytes，canonical tree SHA-256
`98637864c9e341f1af413c300e922b9e80a02589c5fc91fec8eadb315bd5f3a6`。这些身份在 P2-2C 每次运行前
重哈希，任何漂移立即失败。

## 失效原因

原 P2-2 同时存在三项会改变模型或持仓路径的方法违约：

1. 标签 `Ref($open,-11)/Ref($open,-1)-1` 到信号日后第 11 个官方交易日才成熟，但原 train/valid
   未 purge。train 末 11 个信号的标签越入 valid；valid 末 11 个信号的标签直接使用 test 价格并
   参与 early stopping。原处理器 `fit_end_time` 也停在未 purge 的 train 端点。
2. 次日开盘成交判断读取由当日收盘 `pct_chg` 派生的 `limit_buy/limit_sell`，使用了开盘时不可知
   的收盘信息；日循环又在 `nav_open` 前写入当日 close，形成潜在同日收盘估值时钟污染。
3. 冻结口径要求所有订单不超过信号日 20 日中位成交额的 5%，原执行器只 cap 买单。独立复算原
   基础场景 893 笔交易：498 笔买单零违规；395 笔卖单有 14 笔超过 5%，最大 11.3037996634%。

因此机器语义永久补充为：

- `original_p2_2_model_valid=false`；
- `original_p2_2_execution_valid=false`；
- `original_p2_2_numeric_results_reproducible_but_not_authoritative=true`；
- 原 `historical_effect_gate=NO_GO` 和 `strategy_effective=REJECT` 只能描述旧方法输出，不能继续支持
  权威历史效果决策。

这不推翻 `p2-star50-protocol-v1` 的永久 NO-GO、official-lineage-v2 数据门 GO 或 P2-1 工程门 GO，
也不授权生产。原账本时间字段及值不修改；本附录和 Git 提交时点提供新的审计解释。

## 已知结果披露

P2-2C 不是盲预注册或新变体。原三窗/压力/成本结果已被主控与施工窗口查看；主控还用冻结预测做过
不落盘的 open-clock-only 敏感性检查，看到 W2 基础净超额由 -32.7332% 变为约 -32.3002%。该数值
只证明路径被改变，不能替代同时修复标签、开盘时钟和双向容量后的权威纠错结果。

P2-2C 只允许这三项确定性修复；其他模型参数、seed、窗口起点/test 区间、压力映射、Top10/n_drop2、
调仓、目标权重、成本和门槛均不得改变。权威结论只能来自结果前单独提交并推送的
`p2-star50-effect-correction-v1` 以及其终版证据。

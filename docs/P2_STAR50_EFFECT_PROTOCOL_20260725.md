# P2-2 科创50正式历史效果协议 v1（结果前冻结）

冻结时间：2026-07-25 00:50（UTC+8）

状态：**FROZEN BEFORE ANY REAL STAR50 HANDLER, MODEL, PREDICTION, BACKTEST OR EFFECT RESULT**。

本协议只授权 `p2-star50-effect-v1` 唯一一次预注册历史裁决和一遍确定性复核；机器真身为
`config/p2_star50_effect_v1.yaml`。历史 GO 最多允许主控另立前瞻观察目标，不授权生产；任何结果下
`production_authorization=none`。`p2-star50-protocol-v1` 的 NO-GO、v2 官方谱系 GO 和 P2-1 工程 GO
全部永久保留，且分别只代表其原有层级。

## 1. 冻结输入与身份

P2-2 只消费主控终验的 P2-1 终版 `ea225cdaf06b951932ca5155ede7b61676fe0847`。运行前及确定性复核前
逐文件重哈希：

| 输入 | SHA-256 |
|---|---|
| P2-1 tracked manifest | `4e946aa7d3e3c3da31ca8ad700bee2587a189dddfcf62b83054bc6804c163986` |
| P2-1 quality | `3074bac232442f1e862c09d529a35f42fd2aa086422b337d1e72e780b569a990` |
| P2-1 engineering report | `a4cfad049e36914fcec76f05c9dc6f5c24b55d85fe4213a37a3e8f7ae9909401` |
| market parquet | `a1e1d99a9de8cce0dada33389f3588d96ec6e1ecd5f5a1738e7105353901c289` |
| member-days parquet | `a6fb10532bba9de9504fc4be0bfe6e45e50621a761ae29fbaa1cf9ba39356061` |
| benchmark parquet | `e659bcbc042fb56bd50482428daa8eb88dfc8bb674d91d7b4551a07e8a945c42` |
| qlib 内容树 | `b8f736ef9bc9e31cc236a81ca281a23e904789fb5ec87caa9195b572c6b78729` |
| qlib build identity | `dca65a090284de044346bcea7f6ff7364f9a23e3479c9f77c1832f45b2fd26e6` |

同时绑定 official-lineage-v2 五项哈希：manifest
`387514f25d9f883c7ebe84e386ba6dbca4644bb204628004cee4991dc316e112`、quality
`51bfe33aa21162007961d9fb0fd8a6fe91d45ce7593bddac7c9ff0c2fda2df93`、initial
`fe960ccc0b86592c02d082a7f9fda18bb6032b4c263458850cc7deb709a95d4c`、events
`ee5b6ac2a3ee608067bcca51cc21da152b754ec2b96c52c2be4db184c55cdf6a`、daily
`91e9d48421d2a577176488d792c63f5d33bceee953a4532cdb8a8f6317d82644`。

独立身份为 dataset `star50-official-pit-engineering-v1`、model
`p2-star50-alpha158-lightgbm-effect-v1`、benchmark `000688.SH/SH000688`、signal namespace
`p2-star50-effect-v1-local-research-only`、专属 run/admission ledger 和 Git 忽略结果根目录。禁止写共享
`data/qlib_bin`、前瞻 qlib、CSI800 模型/信号/账本、模拟仓或 scheduler。

## 2. 模型、窗口与一次性纪律

三个窗口、Alpha158、标签 `Ref($open,-11)/Ref($open,-1)-1`、LightGBM seed 42 和全部超参数原样沿用
P2-1。线程固定为 1，并启用 LightGBM deterministic/force-col-wise；early stopping 只看冻结 valid。
不得调参、换 seed、按测试结果重训。正式执行恰好一遍；随后以相同代码/输入/seed 再训练一遍，比较
model、prediction、NAV/交易/持仓裁决 canonical 哈希。终版入口再调用只复用终版报告并幂等核账，
不构成新增运行。

压力期映射预先固定：`star_2023_drawdown→STAR-W1`、`microcap_2024→STAR-W2`、
`volume_price_2026h1→STAR-W3`。W3 压力段是 2025 test 后延伸 OOS，不重训。每个测试窗和压力期均
从 1 亿元现金独立开始，避免把其他窗口状态带入。

## 3. 组合与执行操作化

信号日为每个评估段首个官方交易日起每 10 个官方交易日，使用当日收盘可知特征/成员/ST/行业和
截至当日的 20 日成交额；下一官方交易日开盘执行。目标 Top10、n_drop2、每名目标 10%、不足 10 名
保留现金。首次建仓至少 200 股，之后按 1 股递增；卖出允许清理尾数。

候选按分数降序贪心，必须同时满足 PIT 成员、非 ST、有行情、行业有效、20 日中至少 15 日有效、
中位成交额至少 2,000 万元及单行业最多 3 名。新名字若 10% 目标订单超过其信号日中位成交额 5%，
跳过并继续下一名；已有名字的补仓在执行时最多部分成交到 5% 容量。硬不合格名字先移出目标；其后
排名变化最多 drop 2 名。该解释在结果前固定。

卖出先于买入。停牌、缺开盘、涨停买入或跌停卖出均不成交并保留真实仓位；停牌日仅为 NAV 估值沿用
最近真实收盘，不填充信号或成交价。持仓若没有未来价格且退市现金实现未建模则失败。基础费率买 6bp、
卖 16bp、每笔最低 5 元；另算 1.5x、2x 和基础费率上双边各加 10bp。所有场景都使用相同冻结模型和
规则。

## 4. 效果与回撤门

pooled 指标按时间顺序串联 2023/2024/2025 三段不重叠 OOS 日收益，分别复合策略净收益和
`000688.SH` 基准收益后相减；不使用超额 NAV 比值。每窗须至少 220 日、20 次调仓；至少 2/3 基础
成本净超额为正；pooled 基础成本必须大于 0，pooled 2x 与 extra-slippage 必须不小于 0。

最大回撤分别在三个测试窗和三个压力期各自的基础成本策略净 NAV 上以峰谷计算，任一超过 20% 即失败；
禁止以超额 NAV 回撤替代。RankIC、ICIR、换手、行业和容量只可诊断，不得事后增加门槛。

## 5. CSI800 分散化输入门

冻结前仅盘点文件存在性、schema 和哈希。脱敏清单
`config/p2_star50_csi800_comparator_inventory_v1.json` 的 SHA-256 为
`a1c940272bc94aeec9b85a9d35b4148fac3548f0da563a3d660b15ad8d825002`。盘点结论是：Stage0 文件只有
窗口汇总；P1 日表只有净超额且无持仓权重；P1 predictions 不是执行后组合；shadow/paper 只覆盖 2026
前瞻。没有任何现有产物同时提供 2023–2025 基础成本日净收益与逐日持仓权重，因此本协议
`bound_comparator=null`。

不允许临时重跑 CSI800、从预测造持仓或把净超额反推日收益冒充真身。最终必须把分散化组记为
`NOT_EVALUABLE`，并按冻结规则使 P2-2 `NO_GO`；STAR50 其他门仍照常唯一运行和报告，以保留诊断证据。
若未来取得合法真身，只能另立新协议，不能回写本次裁决。

若已有合法真身，本来应按共同日计算：最大 `sum(min(w_star,w_csi))<=0.35`；2023–2025 基础成本
日净收益 Pearson 相关至少 660 日且 `<=0.80`；75% CSI800 + 25% STAR50 协方差 Euler 方差贡献
`RC_star<=0.25`。缺日、非有限或非正分母均 fail closed。

## 6. 结论层级、证据与停工线

机器报告必须输出 `strategy_results_inspected=true`、`historical_effect_gate=GO/REJECT/NO_GO`、
`strategy_effective=HISTORICAL_GO_FOR_FORWARD_ONLY/REJECT`、`production_authorization=none`。本次因冻结
分散化输入缺失，最终最多是 `NO_GO/REJECT`，但仍须如实报告其他门；不得称为 P2 整体失败或据此修改
阈值追加变体。

真实 prediction、model、NAV、交易、持仓只留在 Git 忽略目录。Git 只提交脱敏汇总、哈希 manifest、
专属追加式 ledger、测试和验收文档。P2-1 时间字段问题按
`docs/P2_STAR50_P21_LEDGER_TIMESTAMP_ADDENDUM_20260725.md` 解释，新账本分列协议冻结与真实 UTC 运行/
裁决时间。冻结提交必须独立推送成功且 `HEAD=origin/main` 后，真实入口才允许执行。

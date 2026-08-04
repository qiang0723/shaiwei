# M4-1R 科创50残差因子效果执行纠错协议（2026-08-05）

## 裁决

2026-08-05 首次真实入口是一次无研究裁决的工程失败：运行在生成任何效果报告、不可变 Parquet 或
账本行之前，因 `daily_rank_ic` 输出的一维无名 `DatetimeIndex` 与 `_between` 对两级命名索引的假设
不一致而中止。该入口永久记为 `INVALID_ENGINEERING_ATTEMPT_NO_RESEARCH_DECISION`，不计作候选研究
尝试，也不得描述为通过、拒绝或效果未知以外的任何策略结论。

本协议在重试前冻结，只授权修复这一项索引契约，不授权改变候选、方向、样本、标签、中性化、
Alpha158 混合、组合、执行、成本、压力期、统计或门槛。原 M4-1 协议与第一次执行 release 均永久
保留，不覆盖、不改写。

机器真身见 `config/m4_star50_residual_effect_recovery_v1.yaml`。

## 已核验的失败边界

- 原协议 SHA-256：`a006f62d263249cbbfb33e18de8c18fc2757a80ed145ec273c21c65b46f5a8aa`。
- 原执行 release SHA-256：`1c051b36eec18e63dcdb0f69128092061649c0f3809a3e0290af252183deb661`。
- 原镜像内容 ID：`sha256:8d3b2d3788ef194918b02e8c11d8487f538eaaa4f5452c2ba68dc1b796530c03`。
- 失败类型：`KeyError: Requested level (datetime) does not match index name (None)`。
- 失败发生在 `evaluate_candidate` 汇集全 OOS RankIC 序列时；异常输出没有包含任何 RankIC、收益、
  排名、持仓或候选裁决数值，人工未查看效果值。
- 结果目录仍无文件；运行账本和决策账本仍均只有表头，SHA-256 分别保持
  `c2989a61...f293` 与 `dce03143...d52`。
- 因未产生 `effect_report.json`，原入口的幂等复用分支没有成立，不能直接用旧 release 再跑。

## 根因与唯一许可改动

`factor_portfolio.daily_rank_ic` 的合同是返回按交易日索引的一维 Series，当前实现没有给其
`DatetimeIndex` 命名；`_between` 同时被用于两级信号 Series 和这一维 RankIC Series，却无条件调用
`get_level_values("datetime")`。fixture 只覆盖了前一种形态，因而测试未触发真实路径。

唯一许可补丁为：

1. 两级索引只接受含 `datetime` 命名层的既有信号形态；
2. 一维索引按其值严格解析为日期，不依赖索引名称；
3. 其他层数、不可解析日期或混乱形态失败关闭；
4. 增加两种合法形态和非法形态的回归测试。

该补丁只修日期切片的表示契约，不改变任何输入值、计算公式或研究裁决。

## 重试门

纠错代码须先完成专项/全仓测试、静态检查、依赖和 Compose 检查，再独立提交并推送；随后另立并
推送新的执行 release，绑定新的实现提交与代码束。新镜像内测试、发布身份、空结果目录、表头账本、
Git 同步和 scheduler 身份全部通过后，才允许恰好一次恢复入口；恢复入口仍只含首遍与一次内部完整
确定性复跑。

恢复运行无论结果好坏都按原协议门槛裁决。若再次出现工程失败，立即停止，不继续修复或重跑，另行
复核；不得借纠错调整任何研究参数。

# M7-0R3-P1 真实目标投影协议

## 目标

从已经封存并完成独立审计的 R2 输入束，断网投影恢复轨 A/轨 B 的精确键计划。输出允许在 Git 忽略区
包含证券代码，但跟踪的报告、manifest、文档和账本只能保留计数、范围与哈希。

本节点不回收数据、不调用 Baostock/Tushare、不读资金流数值，也不计算调整后覆盖率。

## 日期口径纠正

目标成员粒度保留两个日期：

- `trade_date`：原 R2 的 feature date；
- `source_date`：PIT 映射后的前一交易日，也是后续 provider 请求日期。

后续 recovery 计算入口另做窄投影，将 `source_date` 映射为请求表的 `trade_date`。不得覆盖 feature date，
也不得把两者混成一个字段。该约束修正 release 工程合成阶段尚未接真实输入时暴露的歧义，不改变 R2
分类、908/541计数、任何门槛或既有证据。

## 主算与独立审计

- 主算直接复用冻结 R2 Pandas 分类器并先验证 core
  `df5de399...eeca`；
- auditor 使用冻结 R2 DuckDB `classified` 关系独立重建两个目标集合；
- 两边分别对规范排序后的五字段行计算内容哈希，成员数、唯一性、日期映射、分层计数和内容哈希必须
  完全相同。

## 一次性执行与输出

projector 和 auditor 各自在任何语义行读取前写入不可变 claim；同 scope 二次调用在 loader 前停止。
目标 Parquet、报告、manifest 和审计报告写入 `data/control/m7-recovery/` 忽略区，全部 write-once，记录
行数、schema 和物理 SHA-256。生产 data/raw、生产 ledger、scheduler、Web 均不挂载。

## 授权边界

用户“继续下一个任务”只授权施工并生成精确 release，不视为尚不存在的 scope 的执行批准。实现必须
先提交推送，再构建断网只读镜像并生成绑定 Git、代码束、镜像、R2 输入束、命令、挂载和资源的 scope。
用户逐字批准该 SHA 后，才能进行唯一一次真实 key-only 投影。

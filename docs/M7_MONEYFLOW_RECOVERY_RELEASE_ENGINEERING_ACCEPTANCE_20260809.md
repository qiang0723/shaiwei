# M7-0R3 真实恢复 release 前置工程验收

## 1. 裁决

`GO_M7_RECOVERY_RELEASE_ENGINEERING_ONLY`。

这只证明真实恢复链所需的目标投影、provider 适配、不可变批次、断网 evaluator、独立 auditor 与
四角色 release 合同已经具备可测试实现。它不是恢复数据 GO，不是执行批准，不改变原 M7/R2 NO-GO，
也不授权读取真实证券键、资金流数值、凭据或外网。

结果前构建合同已由提交 `e43bee4` 单独冻结并先推送；施工期间没有静默修改合同、原门槛或分母。

## 2. 架构与职责

在既有 `m7_moneyflow_recovery` 包中新增九个窄模块：

- `target_projection.py`：直接复用冻结 R2 分类器，投影两个精确恢复类别；
- `providers.py`：依赖注入的 Baostock/Tushare 适配器与先 claim 后调用入口；
- `batch_store.py`：隔离 Parquet 与 canonical receipt 的 write-once 写入；
- `batch_reader.py`：逐批校验 release、request、schema、行数和内容哈希；
- `evaluator.py`：断网主计算与内部双跑；
- `auditor.py`：DuckDB 独立复算；
- `release.py`：构建并校验不可执行的四角色 synthetic scope；
- `sealing.py`：报告、审计与 evaluator/auditor 语义读取前 claim；
- `release_fixture.py`：端到端断网合成验收。

新增模块最大 201 行；既有通用 S1、Baostock、P1 合同、R2 主/审分类和 recovery 主/审计算均未修改。
没有新增依赖、常驻服务、生产账本或公共 schema，不需要 ADR。

## 3. 四角色安全边界

1. `status_collector`：未来精确批准后才可访问 Baostock，只写自己的 status 批次/claim；
2. `moneyflow_collector`：未来精确批准后才可访问 Tushare 主 `moneyflow`，只写自己的批次/claim；
3. `evaluator`：网络为 none，只读 target/status/moneyflow，写独立 run 目录；
4. `auditor`：网络为 none，只读前三类证据与 run，写独立 audit 目录。

synthetic release 中四角色全部 `network_mode:none`、只读根、非 root、无生产挂载；各角色可写源唯一，
collector 没有共享写目录。真实 release、approval envelope 和 live CLI 均未生成。

## 4. 数据质量证据

- 目标投影使用冻结 R2 `compute_lineage_core/_normalize/_joined`，先校验 predecessor core，再精确选择
  `PRIMARY_FULL_DAY_SUSPENSION_ONLY_UNRESOLVED` 与
  `CONFIRMED_MONEYFLOW_GAP_DAILY_PRESENT`；
- 真实规模合成投影为 908/541 成员行，重复、非法键和 `.BJ` 失败关闭；投影摘要不含证券代码；
- 批次 receipt 绑定 release scope、request identity、源、形态、行数、schema 与内容 SHA-256；篡改和
  重复写入均被拒绝；
- evaluator 内部双跑完全一致；auditor 用既有独立 DuckDB 实现逐项重算，结果完全一致；
- 完整性、唯一性、有效性、跨源一致性、冲突和未决数继续分列，不把未知状态改写为已恢复。

端到端 synthetic release：

- release scope `cac367d088464ee933490b491b51fca677918aacf51842d94ae1125b5fa1421d`；
- evaluator report `87abea5510b4f5a901b37d35b47ca60384374b785fdc756c17da331d60e90d12`；
- auditor report `faea8b8fe8c72b631819e5b1ccc4a88abe92f62b71a5b5f9e4ff9bf813772878`；
- 实际 provider 调用 0、真实目标投影 0、真实 scope 0、生产写入 0。

## 5. 验证

- release 专项：11 PASS；
- 全仓：1,026 PASS；架构宪法：13 PASS；
- Ruff、compileall、pip check、Compose config、diff-check：PASS；
- Docker 断网、只读、非 root、无宿主挂载 fixture：PASS；
- 终版镜像 ID：`sha256:95fd788c995ceff6ce13d699a8a860475c79b9b1bdd6ad708f02d2702486f0fd`；
- scheduler 保持原容器 `183b8c6c5edd`、原镜像
  `sha256:722f63de15932cb2698e82db7c0140f02921f27f126e1c0235ca62e0a1213b76`、创建时间
  `2026-08-03 17:39:34 +0800`、healthy，未重启。

已知 warning 只有既有 Starlette 弃用提示和合成 R2 空值下的 pandas future warning；均不影响裁决，
且本节点不以修改冻结 R2 文件消除提示。

## 6. 下一停止点

下一合法动作不是联网，而是另行批准一次**断网、key-only 的真实目标投影**：只读已封存 R2 输入，
生成 Git 忽略区内 908/541 目标计划与聚合 manifest；不读资金流数值、不调用 provider。只有该 manifest、
最终推送提交和不可变 collector 镜像齐备后，才能生成另一个精确网络 scope，再由用户逐字批准采集。

旧 M7、R2 和此前任何批准都不可复用。真实数据回收即使 GO，也必须再过 successor M7 数据门，不能在
本链直接进入候选、效果、前瞻、模拟仓或生产。

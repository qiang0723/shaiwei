# M7-0R3 双轨证据恢复 synthetic 工程验收

## 1. 裁决

`GO_M7_EVIDENCE_RECOVERY_ENGINEERING_ONLY`。

这只证明已冻结的恢复规则具备可维护、确定、失败关闭的工程实现；不是恢复数据 GO，不改变原 M7
`NO_GO_M7_0_DATA_COMPATIBILITY` 或 R2 `NO_GO_M7_GAP_LINEAGE_INCOMPLETE`，不授权真实网络采集、
调整覆盖率、候选、效果、模型、前瞻、模拟仓或生产。

## 2. 架构边界

新增 `src/shaiwei/research_gates/m7_moneyflow_recovery/`，共 8 个职责文件、1,334 行，最大文件低于
400 行：

- `contract.py`：绑定 protocol 与 synthetic 工程权限；
- `inputs.py`：内存输入类型；
- `planning.py`：恢复专用精确键计划；
- `claims.py`：请求前不可变 claim 与有界传输尝试；
- `compute.py`：Pandas 主数据质量裁决；
- `audit_compute.py`：DuckDB 独立复算审计向量；
- `fixture.py`：真实规模合成正常/对抗样本；
- `__init__.py`：窄公开入口。

既有通用 S1 状态计划器、Baostock 采集器、581 行 P1 资金流合同及 R2 Pandas/DuckDB 实现均经
字节哈希锁定且未修改。没有新增常驻服务、外部依赖、账本、公共 schema 或跨层依赖；Docker 只增加
一次性 fixture，因此本节点无需 ADR。

## 3. 数据质量工程证据

合成输入严格采用冻结规模：

- 轨 A：908 个成员行/908 个唯一键，生成 908 个最坏情形状态请求；
- 轨 B：541 个成员行/541 个唯一键，生成 1 个按日全市场请求和 541 个按证券单日请求；
- 实际 provider 调用 0，真实证券键读取 0，真实资金流数值读取 0。

主计算和独立 DuckDB 审计逐项核对：目标成员行、唯一键、重复、非法/`.BJ`、轨间重叠、daily
存在性、状态缺失/交易冲突、双形态 schema/数值/重复/缺失/额外键/内容一致性、6,000 行饱和、批次
完整性和请求计划数。输出只含聚合计数，不含证券代码。

完全正常样本：

- 主/审向量完全一致；
- 两次规范运行完全一致；
- `clean_core_sha256=8250b2113a673363894eee56f8a0d97e7cfe52506aff263395931818746cf25f`；
- `scenario_bundle_sha256=8915a9e0cfedd2e29207fa57770e76ecdd4c3cb77a01bcc3a46009d32d64ca50`。

## 4. 13 个场景

1. 完整 GO；
2. 独立状态显示交易；
3. 独立状态缺失；
4. 一种 moneyflow 请求形态缺失；
5. 两种形态都缺失；
6. 两种形态内容冲突；
7. 目标成员键重复；
8. 非法/`.BJ` 键；
9. 全市场响应触及 6,000 行；
10. 不可变批次完整性失败；
11. 同请求重复 claim；
12. 可重试传输错误恰好止于 3 次；
13. 语义错误恰好调用 1 次且不重试。

除完整样本外，九类数据场景全部裁
`NO_GO_M7_EVIDENCE_RECOVERY_INCOMPLETE`；三个 claim/重试场景均按冻结次数停止。工程复核中还修正了
一个描述性字段：`recovered_unique_keys` 只统计两形态内容相同的键，内容冲突不能因“双方都有行”而
被显示为已恢复。

## 5. Docker 隔离

一次性 fixture 镜像采用固定 Python 基镜像、非 root UID/GID 65532、只读根、`network_mode:none`、
`cap_drop:ALL`、`no-new-privileges`、1 CPU/2 GiB、仅 `/tmp` tmpfs。无项目根、`.env`、Docker socket、
生产 data/ledger/logs 挂载。终版镜像 ID 为
`sha256:b42acd68f37cea1b153400a19f6adbf9cd81e1a7bdb053e1ffeca52cbf7d7f01`。构建与运行后生产 scheduler
仍为容器 `183b8c6c5edd`、镜像 `sha256:722f63de...13b76`、创建时间
`2026-08-03T09:39:34Z`，状态 running/healthy，未被替换或重启。

## 6. 工程验证

- M7 R3/旧 M7/R2 专项：44 PASS；
- 本机 13 场景 fixture：PASS；
- Docker 断网 fixture：PASS；
- 主/独立审计：完全一致；
- 双运行：完全一致；
- 全仓：1,015 PASS（1 条既有 Starlette 第三方弃用 warning）；架构宪法：13 PASS；
- Ruff、compileall、pip check、diff 与脱敏检查：PASS；
- `adjusted_or_counterfactual_coverage_computed=false`；
- `candidate_definition_count=0 / effect_test_count=0 / research_attempt_increment=0`；
- `strategy_effective=NOT_EVALUATED / production_authorization=none`。

## 7. 剩余边界和下一停止点

- 真实 908 行可能按证券/连续日期合并为少于 908 个请求；工程以最坏 908 请求验证预算。
- 真实 541 个成员行可能投影成更少唯一源键；工程以最坏 541 个唯一键验证双形态预算。
- 当前没有真实 reader、provider adapter、不可变输入 bundle、release builder、runner 或 auditor CLI；
  不得把 synthetic 包直接指向 `.env` 或生产 data。
- 下一步若继续，须另立 real-recovery release 目标，先施工并推送真实输入投影/适配/独立执行器，再生成
  不可复用旧批准的精确 scope；用户绑定 scope 批准前仍不得读取真实证券键、数值或调用外网。

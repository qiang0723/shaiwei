# g1-v2 与 g1-positive-control-v2 工程说明（结果前）

- 日期：2026-10-25；上位：`docs/G1_SPEC_V2.md`、`config/g1_v2_spec.yaml`、`docs/G1_POSITIVE_CONTROL_V2_PROTOCOL_20261025.md`（冻结于 c895de4）
- 性质：冻结之后、任何 g1-v2 统计量在真实或标定数据上计算之前的实现选择；只有合成测试

## 1. g1-v2 裁判（`src/shaiwei/research/g1_v2.py`）

- `research/g1.py` 一行未改。共享门把 v2 证据投影成 v1 视图后原样调用 `g1._evaluate_gates`，再移除四个被替换的门、加入四个新门；
  共享阈值来自 `settings.g1_admission`，因此 `load_spec` 逐项核对 v2 配置中同名阈值与之相等，不等即拒绝（防止两份配置漂移）。
- PIT 中性化：同一回归函数 `neutralized_factor_values`，以常数占位标签列，使支撑只取决于当日因子、行业、市值；标签只在算 IC 时使用。
- 逐日配对：只取两侧在同一日期都有有限值的观测，按日期排序；`incremental_icir_t`、`excess_noninferiority` 用 NW(10) t，
  `deflated_increment_ir` 用 Bailey & López de Prado 公式作用于配对 RankIC 差序列，试验方差取同家族有限 `selection_increment_ir`。
- 证据 schema 2：在 v1 字段外加四条带日期的逐日序列与 `neutralization: pit_support`；g1-v1 的证据模型只接受 schema 1，
  因此正式 v1 裁判读到 v2 证据即校验失败（有测试）。账本复算：证据配对序列须逐位复现总账 `selection_increment_ir`。
- 本模块不提供写正式准入账本的入口（规格 §3：须在历史候选重判协议中另行裁决）。

## 2. 标定框架（`research/g1_calibration/`，v1 行为不变）

- 协议加载按 `schema_version` 分派；v2 额外核对：g1-v2 配置 SHA、三层恰好划分 g1-v2 的 15 个门、PIT 中性化、N3 只按三个增量门判定、
  方向固定 +1、N3 种子不削减。v1 原有测试全部保持通过。
- v2 实验总账行同时记 `selection_sharpe`（共享门要求候选日收益复现它）与 `selection_increment_ir`；N3 行只有后者。
  同绑定复跑复用既有行前，两项指标都须一致。判定绑定本格试验集合哈希（v2 按 `selection_increment_ir`），复跑稳定。
- **N3 实现**：各窗口基线 OOS 分数拼接（六窗测试期不相交）后逐日截面 z 化，与按种子生成的截面 z 化噪声以权重 √½ 合成，
  PIT 中性化后以方向 +1 做 90/10 混合，只算混合分数与基线分数的逐日 RankIC；不回测、不落面板，证据 schema
  `g1-calibration-increment-v1`。三个增量门全过即“放行”，汇总把任何放行计入阴性对照通过（→ `G1_PERMISSIVE`），并单独报告上界。
- 授权/执行/审计/试跑均带 `--protocol`（默认 v1）；控制、数据、报告、审计目录随协议家族；标定账本基线只计本协议的行
  （v1 已有 93 行不计入 v2）。审计对 N3 增量证据只核标记与重判，不查面板。
- compose 以变量注入协议、家族、报告目录与协议文档，默认值即 v1；新增 `g1-calibration-devset` 服务。make 目标统一用
  `G1_PROTOCOL=v1|v2`。容器合同测试在 v1、v2 两种取值下逐项核对读写边界。

## 3. 开发集工具（`devset.py`，执行另需授权）

在 v1 正式执行（`g1cal-17f5ae756cdb-20261024T153149Z`）的 93 份面板上计算 g1-v2 新统计量，只报告每单元数值与各格分布，
报告中不出现通过/不通过与终态。两点限制如实写入报告：面板按 v1 中性化构建；v1 证据的候选日净超额未存日期，只在与基线日序列
等长时按日期顺序配对，否则记 `excess_alignment` 而不计算。

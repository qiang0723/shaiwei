# g1-v2 历史候选重判 · 工程说明（协议 v2 §5 第 2 步）

- 协议：`g1-v2-rejudge-v2`（`docs/G1_V2_HISTORICAL_REJUDGE_PROTOCOL_V2_20261025.md`，配置 `config/g1_v2_rejudge_v2.yaml`，abd0e5a 冻结推送）
- 本步只有工程与合成测试；未读取任何重判结果，未在任何历史候选上计算 g1-v2 统计量，未运行复现预检
- 下一步（各自单独授权）：第 3 步复现预检（只读，只算复现差值）；第 4 步断网镜像 → 精确 scope → 逐字批准 → 单次执行 → 独立审计

## 1. 模块（`src/shaiwei/research/g1_v2_rejudge/`）

| 模块 | 行 | 职责 |
|---|---|---|
| `protocol.py` | 178 | 严格载入冻结配置：规格 SHA、家族与顺序、4/6/6/5 共 21 个唯一定义、8 条被取代裁决不入单位、家族内公式不重复、多重检验家族合法；可选核对 P1 原始面板与 11 个原代码文件、每个 v1 证据与复现目标的哈希 |
| `sources.py` | 229 | 四家族原始因子重建与复现门（键集合一致 + 逐键最大绝对差 ≤1e-6） |
| `evaluate.py` | 185 | PIT 中性化 → 与标定相同的组合证据与逐日配对序列 → 实验总账 → 逐家族全部记账后判定 → `summary.json` |
| `judge.py` | 98 | g1-v2 判定（轻量，不载入 qlib/torch）；正式执行与独立审计共用 |
| `release.py` | 274 | 复现预检、精确 scope、逐字批准转录、一次性认领、单次执行 |
| `audit.py` | 98 | 独立审计：只读证据/报告/账本，逐个重判并复核两本账本与汇总计数 |

账本：新建 `ledger/factor_admissions_v2.csv`（表头与 v1 相同，纳入 append-only 测试）；报告 `logs/g1-v2/<执行>/`；
`rejudge_roots` 拒绝任何指向 `ledger/factor_admissions.csv` 或 `logs/g1/` 的输出。

## 2. 实现层面的解释选择（协议未逐字写明处，均不改判读规则）

1. **复现口径与 v2 口径分离**：复现门按各家族 v1 口径重算（GP：v1 中性化残差面板；P1/F1/F2：v1 正式残差在 v1 标签上的日频 RankIC，
   `series_type=factor`、`window=ALL`）。复现通过后交给 g1-v2 的是**原始候选值**，走标准 PIT 中性化；各家族的截尾、标准化与基线正交化只属于
   v1 评估口径（协议 §3.2），不带入 g1-v2。
2. **F/P1 复现的基线正交化**用 v1 时期缓存的 Alpha158 OOS 预测（`p1-moneyflow-alpha158-predictions-v1-46a24aad…`，哈希已绑定在 F1 冻结配置中，
   载入时复核）；OOS 区间 20190101–20241231 与原代码相同。
3. **P1 直接调用原代码的纯计算函数**（`_liquidity_exposures`、`_universe_features`、`residualize_moneyflow_candidates`、`formalize_core_with_oos`、
   `_factor_series`），不经原 `main()`：原入口会拒绝已增长的数据采集总账快照。新增批次日期均晚于 v1 面板，按设计不进入连接结果——
   **是否成立由第 3 步复现门实测**，不过即整家族 `NOT_REEVALUATED`。
4. **候选身份映射**：实验总账存的是冻结公式文本；F 家族按家族协议、P1 按原代码 `CANDIDATE_SPECS` 把公式唯一映射回候选名，非唯一即失败。
5. **沿用 v1 的不变量**：经济含义、复杂度（表达式 token/AST 节点）与 PIT/shift 哨兵结果取自 v1 证据与测试报告（定义未变）；新测试报告记
   `rejudge_of`、v1 证据哈希与复现结果。GP 占位经济含义（15 字 < 20）照常判定，按第②项如实 REJECT。
6. **实验总账**：每个定义一行，`g1_research_family` 为真实家族（计入 N），`parent_experiment_id` 为 v1 候选，`attempt_stage=g1_v2_rejudge`，
   实验 ID = sha256(协议|家族|v1 候选|代码|数据)[:12]；同绑定复跑只复用，内容不同即失败关闭。
7. **N 与方差**：按 `family_order` 逐家族先全部记账再判定；`judge_unit` 在完整前缀快照上统计，F2 按 v1 声明的 F1+F2。历史行没有
   `selection_increment_ir`，故方差只取本次写入的增量 IR（协议 §3.3 原文）。
8. **证据错误**：中性化/组合/流水线错误（含空因子——共用中性化对空输入会抛裸 `ValueError`，重判在调用前拦下）记为失败尝试并计入 N，
   单元状态 `EVIDENCE_ERROR`；判定期的 G1/g1-v2 证据错误与标定一致，失败关闭（中止执行，须新 scope）。

## 3. 架构登记：`src → tools` 依赖债（冻结身份冲突）

`sources.py` 导入 `tools.p1_moneyflow.{experiment,features,residual_builder}`。架构宪法禁止 `src` 依赖 `tools`，唯一例外是冻结身份冲突的历史重放
（先例：M4-1 重放复用 P2-2C 执行器）。本处同类：用户批准的冻结协议裁决 `p1_reconstruction: original_tools_p1_moneyflow_code_and_raw_panel_with_reproduction_gate`，
并以提交 7046985 与 11 个文件哈希绑定原代码；迁入 `src` 会改变被绑定的身份，动态导入则是隐藏依赖。故在
`config/codebase_consolidation_v1.yaml` 登记三条 `A1_1A_DEFERRED_FROZEN_IDENTITY_CONFLICT`，退出条件：版本化的重判后继协议或 P1 历史重建归档 ADR 获批。
导入均为函数内延迟导入，审计与判定路径不触达 `tools`。

## 4. 容器与操作

- `compose.g1-v2-rejudge.yaml`（登记为组件 `g1-v2-rejudge`，资产总数 100→101）：三服务全部断网、只读根、`cap_drop ALL`、无密钥；只读挂 qlib_bin、
  原始数据、研究产物、账本、AlphaGen vendor、`tools/__init__.py` 与 `tools/p1_moneyflow`、冻结协议文档。
  - precheck：唯一可写 `logs/g1-v2/precheck`；
  - run：root + 调度命名卷锁；可写 `ledger/experiments.csv`、`ledger/factor_admissions_v2.csv`、`data/research/g1-v2-rejudge`、`logs/g1-v2`；
  - audit：被审对象全部只读，唯一可写 `logs/g1-v2-audit`。
- 镜像复用 `make docker-g1-calibration-build`（`shaiwei:g1-calibration-<快照12位>`），须从推送后的 HEAD 重新构建。
- Make 目标：`docker-g1-v2-rejudge-precheck IMAGE=…`、`g1-v2-rejudge-scope-prepare IMAGE=… PRECHECK=…`、
  `g1-v2-rejudge-record-approval SCOPE=… TEXT="…"`、`docker-g1-v2-rejudge-run SCOPE=…`、`docker-g1-v2-rejudge-audit SCOPE=… EXECUTION=…`。
- scope 绑定：协议配置/文档/规格哈希、HEAD、镜像与镜像 ID、代码/数据快照、qlib_bin 指纹、21 单位、预检报告哈希、账本状态（重判行 0、v2 账本 0 行、
  v1 准入账本哈希）。逐字批准文本由工具生成，工具从不自造批准。

## 5. 合成测试

`tests/test_g1_v2_rejudge.py`（10 项）与 `tests/test_g1_v2_rejudge_docker_contract.py`（3 项），不读真实研究数据、不写真实账本：
冻结配置载入与篡改拒绝；复现门键集合/容差；GP 重建复现与扰动失败；输出隔离；逐字批准与前置漂移拒绝；端到端执行（P1 一个复现不过 → 整家族
`NOT_REEVALUATED` 且不记账；其余家族真实家族记账；真实账本字节不变）；家族 N（GP 3+2、F1 2+2、F2 (2+2)+(1+2)=7，方差条数 F2=4）；GP 第②项 REJECT；
一次性认领拒绝重跑；独立审计 PASS 并捕获 v1 账本变动与 v2 准入行篡改；空因子记为证据错误；容器合同。

## 6. 第 3 步预检需实测的风险

- P1：原代码标签精度（float32）与排名并列处理能否在 1e-6 内复现日频 IC；采集总账增长是否确实不进入连接结果；
- F1/F2：`fundamental_effect.metrics.load_labels` 的标签与 v1 落盘 IC 是否同源；
- GP：AlphaGen 表达式路径与 v1 中性化残差面板逐键一致。
预检只可修正重建实现的工程错误；任何修正都在第 4 步 scope 之前提交并重建镜像。

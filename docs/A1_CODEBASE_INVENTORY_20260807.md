# A1-0 代码库只读审计与首批架构整理建议

- 审计日期：2026-08-07（UTC+8）
- 审计代码：`8e2c5d4399e5705c7bd570c1e208f6394f8db668`
- 状态：`A1_0_COMPLETE_A1_1A_DEFERRED`
- 权限边界：只读检查代码、Git 入口和依赖；未删除、拆分或修改生产代码，未运行研究、数据或生产任务
- 上位规则：`docs/ARCHITECTURE_CONSTITUTION.md`、`docs/CODEBASE_CONSOLIDATION_PLAN_20260807.md`
- 机器清单：`config/codebase_inventory_a1_0_20260807.yaml`

## 1. 结论先行

筛微当前规模已经进入必须依靠架构治理、不能依靠个人记忆维护的阶段，但尚未失控。Git 已跟踪代码为
121,353 行；核心 Python 62,747 行，Web UI 14,860 行，研究/验收工具 17,137 行，Python 测试
23,654 行。测试与证据占比仍然健康，主要风险是近期 M6 在同一天形成大量一次性 release、runner、
auditor 和恢复入口，以及少数高中心度模块继续承担过多职责。

本轮没有找到满足全部删除门的生产文件，所以“可安全直接删除”是 **0 个**。这不是审计失败：静态零引用
项全部是历史 release、CLI 或唯一复算入口；前端唯一不可由 `main.tsx` 到达的 `vite-env.d.ts` 是编译器
声明。为了减少行数删除它们，会损害复算、失败解释或构建能力。

当前最值得处理的不是批量删代码，而是三项边界裁决：

1. 科创50纠错执行内核经 A1-1A 前置检查确认被 P2/M4 双重冻结身份锁定，暂缓迁移并继续机器隔离；
2. 拆开 DeepSeek 传输与 `llm_factor.py` 之间的循环依赖；
3. 把 M3 发现输入身份移入独立合同模块，拆开 data/release 循环依赖。

三项必须分别施工、分别回滚。它们不改变模型、因子、执行参数、研究结论或生产授权，也不以净减行数
作为完成条件。完成后再按“下一次真实需求触碰哪个热点，就先抽离哪个职责”的棘轮方式治理 Web 与 D1，
不启动全仓重写。

## 2. 规模与增长事实

计数口径为 Git 已跟踪文件的物理行；代码扩展名包括 Python、TypeScript/TSX、CSS、JavaScript、Shell，
并包括 Makefile、Dockerfile。数据、日志、忽略产物和第三方依赖不计入。

| 范围 | 当前文件数 | 当前行数 | 2026-08-07 早间基线 | 变化 |
|---|---:|---:|---:|---:|
| Git 已跟踪文件 | 1,068 | — | 977 | +91 文件 |
| 已跟踪代码 | 583 | 121,353 | 522 / 约 113,500 | +61 文件 / +7,853 行 |
| `src/shaiwei` Python | 283 | 62,747 | 243 / 56,703 | +40 文件 / +6,044 行 |
| `web-ui/src` | 64 | 14,860 | 现行窄口径无同口径旧值 | 本阶段未增长 |
| `tools` Python | 87 | 17,137 | 87 / 17,137 | 0 |
| `tests` Python | 129 | 23,654 | 119 / 21,940 | +10 文件 / +1,714 行 |
| Dockerfile | 11 | 281 | — | — |
| Compose | 12 | 3,221 | — | — |

从冻结基线提交 `ec34a02f342723ef450b44471def6aa729ffad2d` 到本次审计提交，按同一代码扩展名
逐文件差分为 `+8,365/-2`，净增 8,363 行，其中核心 `src` 净增 6,044 行、测试新增 1,633 行、
构建/Compose 等新增约 686 行。主要增长完全来自 M6：

| 新职责族 | 文件数 | Python 行数 | 裁决 |
|---|---:|---:|---|
| `research/model_attribution` | 23 | 4,477 | 已完成研究证据；冻结、不得继续泛化 |
| `research/topk_conversion` | 16 | 2,880 | 已完成研究证据；冻结、不得继续追加 TopK 变体 |
| `research/top30_diagnostic` | 14 | 2,041 | 含失败恢复历史；保护复算与失败解释 |
| `research/top30_provenance` | 10 | 1,122 | 零新回测谱系证据；保护审计入口 |

这说明代码增长能对应到真实的确定性、独立审计和失败证据，不是纯粹无效代码；但 M6 已关闭，以上四个
包应转为 **frozen/no-growth evidence islands**。未来新研究不得复制其整条 release/scope/audit 框架，
必须先复用稳定合同或证明不能复用。

## 3. 复杂度与爆炸半径

### 3.1 文件与函数

- 核心 Python 超过 400 行：26 个；超过 600 行：12 个。
- 加上 Web UI，机器清单冻结的 `>600` 生产/Web 热点仍为 13 个，未越过既有上限。
- `src + web-ui + tools` 中超过 600 行的文件共 18 个。
- 核心 Python 中物理跨度超过 60 行的函数 200 个，超过 100 行的函数 74 个。

最高风险不等于单纯最长文件，而是“文件大 + 被很多模块依赖 + 仍会继续变化”。当前优先级如下：

| 模块 | 行数 | `src` 内静态入边 | 风险与棘轮 |
|---|---:|---:|---|
| `shaiwei.config` | 408 | 96 | 爆炸半径最高；保留现有 loader，未来新增配置放入领域子配置 |
| `shaiwei.ledger` | 363 | 60 | 追加式真身；只扩显式 schema/append API，不做通用存储层 |
| `shaiwei.provenance` | 194 | 40 | 发布身份核心；修改须独立回归发布清单与回滚 |
| `research_gates.m5_dynamic.contract` | 391 | 40 | 冻结合同中心；M5 暂停时不得泛化 |
| `research.model_attribution.contract` | 246 | 35 | M6 共享合同；转入 no-growth |
| `research.llm_factor` | 1,254 | 32 | 最大的“体积 + 中心度”组合；先拆传输合同和 fixture/lifecycle 边界 |

最长函数中，`llm_factor.execute_completed_attempt` 为 410 行，`web.query._build_from_cut` 为 349 行，
`web.api.create_app` 为 324 行，`paper_cycle.run_once` 为 238 行，`paper.engine.execute_day` 为 233 行。
不在 A1-1 一次性重写这些函数；只有在对应业务再次变化时，先用 characterization test 固定公共行为，
再抽离一个可命名、可独立测试的职责。

### 3.2 依赖方向

机器与 AST 双重扫描确认：

- 唯一 `src -> tools` 反向依赖是
  `src/shaiwei/research/star50_residual_effect/metrics.py:16` 导入
  `tools.p2_star50_effect_correction.executor`。
- 该 executor 又导入 `tools.p2_star50_effect.metrics` 和
  `tools.p2_star50_effect_correction.contract`，因此不能只改一行 import；必须把执行类型、开盘/容量语义和
  最小收益计算作为一个稳定领域内核迁移，并让历史工具反向成为兼容适配器。
- AST 图存在两个强连通分量：
  `deepseek_client <-> llm_factor`，以及 `m3_multi_pool_data <-> m3_multi_pool_release`。
- 未发现核心领域反向依赖 Web 的新增违规；现有 `make architecture-check` 仍是最终机器门。

### 3.3 前端可达性

从 `web-ui/src/main.tsx` 解析相对静态 import，59 个非测试 TypeScript/TSX/CSS 文件中 58 个可达；唯一
不可达项为 `vite-env.d.ts`，它是 Vite/TypeScript 编译声明，不是运行时模块，必须保留。
`styles/60-responsive-legacy.css` 虽名称含 legacy，但由 `styles.css` 明确导入且有模块化测试，不能删除。

## 4. 候选清单与逐项裁决

| ID | 文件/职责族 | 引用与入口证据 | 动态/历史风险 | 替代目标 | 保护等级 | 收益 | 回滚点 |
|---|---|---|---|---|---|---|---|
| A1-C01 | P2-2C corrected execution → M4-1 | M4 `metrics.py:16` 直接导入 tools；P2 run/tests 也直接调用 | executor 路径/物理SHA、M4 code bundle和P2纠错身份三重绑定 | v1保持字节不变；未来只在版本化 successor 建新 `src` 内核 | `DEFERRED_FROZEN_IDENTITY_CONFLICT` | 不以架构整齐破坏合法复算；禁止第二处反向依赖 | 现状即回滚点；裁决见A1-1A文档 |
| A1-C02 | `llm_factor` / `deepseek_client` | transport 从 `llm_factor` 导入 6 个合同/规划符号；fixture 又反向导入 transport | 真实 API、计费、恢复账本与旧 D1 STOP 证据 | 抽出 transport 所需 typed contract/planning seam；原 API re-export | `SPLIT_NO_BEHAVIOR_CHANGE` | 消除循环；缩小 1,254 行热点和 secret 边界 | 独立提交；mock transport、40 响应恢复与语义门 characterization |
| A1-C03 | M3 data/release | release 导入 `M3DiscoveryIdentity`；data 的 CLI main 反向导入 release | M3-2/M3-3 冻结输入与 release 身份 | 将 identity 移到 `m3_multi_pool_contract` 或独立 identity 模块 | `SPLIT_NO_BEHAVIOR_CHANGE` | 消除循环；data 不再知道 release 实现 | 独立提交；原 CLI 输出和 release SHA 校验回归 |
| A1-C04 | Web evidence read primitives | `operations.py` 与 `query_evidence.py` 有相同 `_normalize_as_of`、`_read`、JSON 文档逻辑 | 原子 snapshot、mtime/hash 双读和错误码不能漂移 | 下次 Web 查询变化时抽 `web/evidence_reader.py` 窄端口 | `DEFER_UNTIL_TOUCHED` | 避免两套 fail-closed 文件读取语义 | 保留旧函数包装；真实只读 E2E 与 snapshot 哈希 |
| A1-C05 | 两套 SQLite schema fingerprint | 两个 `schema_descriptor` 物理跨度 42/43 行且主体相同 | fingerprint 常量、错误类型和迁移域不同 | 下次 schema 变化时抽无状态 descriptor，领域层保留 fingerprint/error | `DEFER_UNTIL_SCHEMA_CHANGE` | 减少迁移审计重复 | 两套 schema fixture 和旧 fingerprint 精确不变 |
| A1-C06 | Top30 三个 release 生成入口 | 静态业务入边 0；均有 `__main__`，来自 R1/R2/R3 独立提交 | 失败 scope、恢复 scope、镜像与数值谱系复现 | 无当前替代；未来仅可经 archive ADR 固化命令/镜像后退出 | `HISTORICAL_REPLAY_PROTECTED` | 现在删除收益小、审计损失大 | 保留原 Git 提交和路径 |
| A1-C07 | M5 四个 inventory/release CLI | 静态业务入边 0；均是显式 CLI，来自 v1/R2 release 构建 | 绑定 registry、真实 NO-GO 与输入束身份 | 无当前替代；M5 暂停期间冻结/no-growth | `HISTORICAL_RELEASE_PROTECTED` | 防止误把手工入口当死代码 | 保留原 Git 提交和路径 |
| A1-C08 | Star50 residual `run.py` / `audit.py` | 静态业务入边 0；均有 `__main__`，是 M4-0 数据门入口 | 唯一历史复算/审计职责 | 暂无替代 | `HISTORICAL_REPLAY_PROTECTED` | 保留 M4 数据门可复核性 | 保留原 Git 提交和路径 |
| A1-C09 | 前端 `vite-env.d.ts`、legacy responsive CSS | 前者不在运行时 import 图；后者被 `styles.css` 与测试引用 | 编译声明与 320/390px 响应式行为 | 不替代 | `BUILD_AND_UI_PROTECTED` | 避免错误清理 | Git revert |
| A1-C10 | Web/D1/config 高风险热点 | 13 个 grandfathered 文件由机器清单限额；当前均有真实调用 | 大改可能同时改变口径、错误和历史证据 | 新能力外置，旧文件只留薄编排；按触碰触发拆分 | `RATCHET_NO_GROWTH` | 防止继续形成单文件代码山 | 每个业务族独立提交和旧接口回归 |
| A1-C11 | canonical JSON/hash/cost 等小重复 | AST 找到多组 3—11 行相同函数 | 跨域合并会创造无边界 common，并可能改变哈希序列化 | 保持局部；仅在同一领域出现第三个活跃调用方时评审 | `KEEP_LOCAL` | 避免为少量行数引入更强耦合 | 不施工 |

### 删除裁决

- `SAFE_DELETE_NOW = []`。
- 静态零引用不等于可删除；本轮零引用项全部命中 CLI、release、历史复算或构建保护条件。
- release/recovery/audit 入口是否最终归档，必须另立 ADR，至少固化镜像、命令、输入 manifest、预期输出
  哈希与可执行 Git tag；在此之前不删除。

## 5. 目标架构

```text
领域合同 / typed identity / error semantics
                    ↓
纯领域内核（PIT、执行、指标、门禁、裁决）
                    ↓
应用编排（run、release、recovery、audit coordinator）
                    ↓
窄适配器（Tushare、DeepSeek、文件、SQLite、飞书）
                    ↓
只读证据投影 / HTTP query
                    ↓
Web / CLI / 告警

冻结研究与失败入口 ──兼容适配──> 稳定领域内核
```

落地约束：

1. 不建全局 `common/utils/helpers`；共享能力必须归属具体领域，如 `star50_execution`、
   `llm_factor_transport_contract`、`web.evidence_reader`。
2. 研究 release、recovery 和 audit 是应用入口，不得拥有第二套执行或指标算法；冻结历史入口通过兼容层
   调用稳定内核。
3. 新文件默认不超过 400 行；A1-C01 的 536 行 executor 迁移时必须按 contract/selection/execution/
   metrics 职责拆开，不能把大文件原样搬进 `src`。
4. 公共 import 路径在兼容期内保留；旧路径退出必须有调用清单、迁移完成证据和单独 ADR。
5. 配置与 Web 大热点采取“下一次触碰先抽职责”的方式，不为了目录整齐预先大拆。
6. 每个重大阶段继续记录代码规模、热点数、循环依赖和 `src -> tools` 数；下一次完整复核按既有约定在
   新增约 20,000 行、三个新超 400 行文件、同热点连续两目标被触碰或重大阶段关闭时触发。

## 6. 建议的 A1-1 首批施工包

以下顺序是建议，不构成自动施工授权。每包必须独立提交、可单独回滚；前一包完成不自动授权后一包。

### A1-1A · 科创50执行内核提升（已裁定暂缓）

- 前置检查确认无法在不破坏冻结执行路径、物理SHA和M4 release bundle的前提下原地迁移。
- v1旧实现转为历史复算隔离项，保持字节不变；机器门继续要求全仓只有这一处登记债务。
- 未来另立M4/P2版本化successor时，新版本必须直接建设`src`领域内核；不得让新能力继续消费旧tools。
- 完整裁决见`docs/A1_STAR50_EXECUTION_MIGRATION_DECISION_20260807.md`。

### A1-1B · D1 传输依赖解环

- 抽出 DeepSeek transport 真正需要的 D1 typed contract、request planning 和敏感输出规则；
  `deepseek_client` 不再导入 1,254 行 `llm_factor.py`。
- 原公共符号从旧模块 re-export，旧 CLI、mock transport、恢复账本、费用与“未授权不读 secret”行为不变。
- 验收：循环依赖减少为 1 个；D1 preexecution、mock transport、语义门和恢复 characterization 通过。

### A1-1C · M3 输入身份依赖解环

- 将 `M3DiscoveryIdentity` 移到既有 contract 或独立 identity 模块；data 和 release 只共同依赖该合同。
- 不改 discovery 数据读取、release 内容、候选、费用、已封存结果或 CLI 输出。
- 验收：循环依赖为 0；M3 input snapshot、release 校验和相关测试不变。

Web projection、`types.ts`、SQLite descriptor 和大函数拆分暂不进入首批，避免一次整理同时影响研究、
Web、数据库和生产。它们继续由热点上限和“触碰即拆一项职责”约束。

## 7. A1-1 每包统一门禁

1. 开工前记录 `HEAD/origin/main`、工作树和 scheduler 非敏感身份；七个自然账本改动不得暂存。
2. 先加 characterization，再迁移；禁止趁整理修改模型、因子、成本、门槛、Schema、默认值或错误语义。
3. 运行专项测试、`make architecture-check`、全仓测试、Ruff、compileall、依赖、Compose、
   `git diff --check` 和脱敏检查。
4. 验证 `src -> tools` 数、循环依赖数、热点行数均只降不升；未达成则回滚该包，不用新增例外掩盖。
5. scheduler 容器、镜像、创建时间和健康状态不变；不读取 `.env`，不启动研究，不修改数据/日志/账本。
6. 更新本清单与 STATE，记录净行数变化，但不设必须删行 KPI。

## 8. 最终判断

项目不需要“大扫除式重构”，需要的是可验证的架构棘轮。12.1 万行本身不是失败；真正应被压住的是
新增反向依赖、循环依赖、热点继续长大和一次性研究框架复制。A1-1A说明有些结构债就是历史证据的一部分，
不能假装可以无损抹去；下一步应先做A1-1B/C两个解环包，再在后续真实功能中逐步拆Web、D1与配置热点。
这条路线比一次性追求十万行以下更稳，也更符合筛微“拿到可信结果”的目标。

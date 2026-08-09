# M7-0R2 资金流缺口谱系执行验收（2026-08-09）

## 1. 权威结论

`NO_GO_M7_GAP_LINEAGE_INCOMPLETE`。

本结论只说明：现有本地不可变证据不能把原 M7 的每一条资金流缺口完整确认为隔离、真实交易缺键或
独立确认的非交易。它不表示资金流机制或策略无效；`strategy_effective=NOT_EVALUATED`、候选定义 0、
效果检验 0、研究尝试增量 0、生产授权 `none`。

原 M7 权威 `NO_GO_M7_0_DATA_COMPATIBILITY` 继续有效，本次 lineage scope 已消费并永久停止。不得以
同 scope 重跑、补证、重分类、计算调整后覆盖率或进入候选/效果阶段。

## 2. 授权、身份与一次性执行

- 用户批准 scope：`9b5e40ec772df4a179fd3b57449304f32bf45f673a0627b1b2e1787e595c0cae`；
- action：`M7_MONEYFLOW_GAP_LINEAGE_ONCE`；
- live proposal 完整性复算 PASS；批准时仍为 `REVIEW_REQUIRED`、seq 2、head
  `da38d05a...b1f0a`，且未过期；
- approval canonical / physical SHA：`46863131...50e03` / `c3ab54c8...13565`；
- 输入束：10,927 文件，bundle manifest SHA `3f4a6cc3...005eb`；物化时语义行读取为 false、资金流
  数值列读取为 0；
- 镜像：`sha256:3f827cc8...4cda6`，`linux/arm64`；网络 none、根只读、输入只读、UID/GID 65532；
- run ID：`1e78e7c61760ea9dd3d8f5b2747d483a67d292420ecfa6efae20d60092154ea4`；
- runner 与 auditor 各留下恰好一个 pre-read claim，均声明
  `same_identity_retry_authorized=false`；没有第三个 claim。

输入包首次物化调用因使用相对 `project-root` 在控制路径规范检查处失败；工具已自动清除临时目录，
当时 approval 已生成，但输入束、输出、audit 和 claim 均不存在。随后仅将同一调用改为绝对项目路径，
物化成功。该问题发生在业务语义读取和一次性角色消费之前，不改变 scope、输入身份或最终裁决；真实
runner 和 auditor 均只调用一次。

## 3. 数据集、粒度与允许读取

- 粒度：`feature_date × universe_id × ts_code`；
- 诊断域：三池 × 11 个完整半年，共 33 个唯一分层单元；
- 成员行：757,636；原始缺口行：2,615；十类合计 2,615，`partition_delta=0`；
- `moneyflow` 只投影代码/日期，`daily` 只投影代码/日期，`suspend_d` 只投影代码/日期/停牌时段/
  类型，Baostock 只投影代码/日期/`trade_status`；
- daily 选择 8,225 批、suspend_d 1,328 批、Baostock 16 批；资金流和 daily 数值列读取均为 0；
- 成员/资金流重复键、非法源行、非法独立状态、`.BJ`、PIT/成员异常均为 0。

报告没有持久化证券代码、原始或派生业务行、绝对路径、凭据或调整后覆盖率。

## 4. 全域分类结果

| 类别 | 行数 | 缺口内占比 | 解释 |
|---|---:|---:|---|
| `QUARANTINED_SOURCE_DATE` | 1,157 | 44.2447% | 源日已在 P1 整日隔离 |
| `CONFIRMED_MONEYFLOW_GAP_DAILY_PRESENT` | 541 | 20.6883% | 同键存在 daily 行情，但 moneyflow 缺键 |
| `CONFIRMED_NONTRADING_INDEPENDENT` | 9 | 0.3442% | 独立源明确确认未交易 |
| `PRIMARY_FULL_DAY_SUSPENSION_ONLY_UNRESOLVED` | 908 | 34.7228% | 只有主源全天停牌，缺少独立确认 |
| 其余六类冲突/日内停牌/无证据类别 | 0 | 0% | 本次未出现 |

冲突行总数为 0，但未决行仍有 908，因此“冲突门”通过并不能替代“谱系完整门”。六个硬门中前五项
PASS，唯一失败项为 `unresolved_row_count_zero`（观察值 908，阈值 0），独立形成 NO-GO。

## 5. 股票池与时间分层

同一证券日期可能同时属于多个池，因此以下统计沿冻结粒度按成员行计数，不能相加后解释为唯一证券数。

| 研究池 | 缺口 | 隔离日 | daily 存在但资金流缺键 | 独立确认未交易 | 主源单边未决 |
|---|---:|---:|---:|---:|---:|
| 全科创板自建 PIT 池 | 1,772 | 695 | 541 | 9 | 527 |
| 科创中盘自建 PIT 池 | 439 | 233 | 0 | 0 | 206 |
| 科创小盘自建 PIT 池 | 404 | 229 | 0 | 0 | 175 |

| 半年 | 缺口 | 隔离日 | daily 存在但资金流缺键 | 独立确认未交易 | 主源单边未决 |
|---|---:|---:|---:|---:|---:|
| 2021H1 | 11 | 0 | 0 | 0 | 11 |
| 2021H2 | 301 | 238 | 45 | 0 | 18 |
| 2022H1 | 437 | 301 | 116 | 0 | 20 |
| 2022H2 | 151 | 0 | 125 | 0 | 26 |
| 2023H1 | 749 | 618 | 117 | 0 | 14 |
| 2023H2 | 137 | 0 | 124 | 0 | 13 |
| 2024H1 | 52 | 0 | 14 | 0 | 38 |
| 2024H2 | 136 | 0 | 0 | 0 | 136 |
| 2025H1 | 246 | 0 | 0 | 0 | 246 |
| 2025H2 | 214 | 0 | 0 | 8 | 206 |
| 2026H1 | 181 | 0 | 0 | 1 | 180 |

908 条主源单边未决中，2024H2—2026H1 占 768 条（84.58%）。这与当前 Baostock 独立证据仅有
16 个批次、覆盖不完整的已知边界一致；这是证据缺口的时间集中，不得推断为真实停牌比例变化。

## 6. 确定性、独立审计与生产隔离

- runner 内部 first-pass/replay 完全一致，core SHA `df5de399...eeca`；
- 独立 DuckDB auditor PASS，重新读取同一只读输入并逐字段复算六门、33 单元与十类分区，独立 core
  SHA 与报告 core SHA 同为 `df5de399...eeca`；
- lineage report SHA：`223b23ff...7e3b`；run manifest SHA：`43e5600d...4731`；audit report SHA：
  `2c088db6...6afe`；
- tracked aggregate manifest：`config/m7_moneyflow_gap_lineage_execution_manifest_v1.json`；
- tracked aggregate manifest SHA：`03ef40e7...b0de8`；M7-0R2 专项 14 PASS、架构宪法 13 PASS、
  全仓 988 PASS（仅 1 条既有第三方弃用 warning），Ruff 与 diff-check PASS；
- 真实执行 provider 调用 0、费用 `$0.00`；标签/收益、效果、模型、回测均未读取或运行；
- scheduler 执行前后保持同一容器 `183b8c6c5edd`、同一镜像 `722f63de...13b76` 且 healthy；未被
  Compose 的 orphan 提示处理，未删除、重启或改动。一次性 runner/auditor 容器均已按 `--rm` 清理。

## 7. 影响与下一合法动作

当前证据支持两个并列事实：一是 541 条成员行在 daily 存在时仍缺 moneyflow 键，属于已确认的源键缺口；
二是 908 条只有主源停牌描述，现有独立证据不足以确认是否非交易。它不支持把 908 条直接从分母剔除，
也不支持以 541 条推断因子效果。

因此 M7 继续停在候选阶段之前。若未来恢复，只能另立新版本协议和新 scope，先补足可审计的独立交易
状态证据，并对 541 条已确认交易缺键制定不改旧门槛的源数据恢复方案；补证后也不得复用本次 approval
或重跑本 scope。若不新增外部证据，当前 M7 路线应保持停止。

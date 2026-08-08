# M7 三自建科创池资金流键级数据门执行验收（2026-08-08）

## 1. 权威结论

`NO_GO_M7_0_DATA_COMPATIBILITY`。

本结论只否决当前冻结的“P1 moneyflow 源键能否直接作为 M3 三自建科创池资金流候选的输入”数据门；
它不表示资金流机制或策略无效。`strategy_effective=NOT_EVALUATED`、候选定义 0、效果检验 0、研究尝试
增量 0、生产授权 `none`。

本 scope 已消费并永久停止。不得重跑、调阈值、补数据、生成候选或进入效果评价。

## 2. 授权与运行身份

- 用户批准 scope：`f47100687eabe09959a6a1746e742a274e8e77ba3c9e6e90c58a43542b4b24e1`；
- action：`M7_STAR_CUSTOM_POOL_MONEYFLOW_DATA_GATE_ONCE`；
- live proposal 完整性复算：PASS；批准时仍为 `REVIEW_REQUIRED`、seq 2、head
  `da38d05a...b1f0a`，且未过期；
- approval canonical / physical SHA：`d5394732...e0e9` / `2545ba4e...1e76`；
- 输入束：1,342 文件，bundle manifest SHA `3e49ce01...5757`；
- 镜像：`sha256:893e90f4...c616`，`linux/arm64`，UID/GID 65532；
- runner 于 UTC+8 21:58 后启动，避开 15:45—20:00 scheduler 窗口；网络为 none、根只读、输入只读；
- run ID：`54529f2c5822c638c8bfd83ce26dd3c475b7eb5c483772ec2e42a487ac3c032d`。

## 3. 数据集与粒度

- 粒度：`feature_date × universe_id × ts_code`；
- feature 日期：1,328；非隔离 eligible 日期：每池 1,325；隔离映射日期 3，最长连续 1；
- M3 范围内成员行：757,636；moneyflow 源键行：6,495,149；
- PIT：源日 D 只映射下一官方 SSE feature 日；missing mapping、同日/未来映射、request date mismatch 均 0；
- membership/source 主键重复均 0，`.BJ` 0，未来 formation 0，未知池 0；
- 只读取 raw `ts_code, trade_date` 和 M3 五列成员键，资金流数值列读取 0。

## 4. 14 个硬门

12 PASS，2 FAIL。

### FAIL 1：半年成员键覆盖

冻结阈值为每个“池×完整半年”均不低于 99%。四个单元失败：

| 池 | 半年 | 覆盖率 |
|---|---:|---:|
| 全科创板自建 PIT 池 | 2021H2 | 98.8451% |
| 全科创板自建 PIT 池 | 2022H1 | 98.5452% |
| 全科创板自建 PIT 池 | 2023H1 | 98.7130% |
| 科创中盘自建 PIT 池 | 2022H1 | 98.9970% |

最低为全池 2022H1 的 98.5452%，低于 99%。该门独立足以形成 NO-GO。

三池全期总体覆盖率分别为 99.6105%、99.7107%、99.7325%，均高于 99.5%；最差 eligible 单日覆盖
分别为 98.4375%、97.5460%、96.0000%，均高于 95%；最少匹配名称为 63/21/21，也通过 60/20/20。
因此问题是特定早期半年段的累计缺口，不是全局目录崩坏或单日硬断裂。

### FAIL 2：required keys valid

报告记录 `source_malformed_key_count=3,620,544`。复核实现发现主计算与独立审计都把 source code 格式
写成仅允许 `[0-9]{6}.SH`，而冻结 P1 source catalog 是全 A 股 moneyflow 目录；合法非 `.SH` 源行因此
会被错误归为 malformed。这个计数不能作为可信的数据域诊断。

这是共享规范误读：两套实现代码独立，但复制了同一个过窄正则，所以逐字段一致的独立 audit 无法发现。
严重度为 `HIGH_DIAGNOSTIC_FIDELITY`。它不改变本次 NO-GO，因为半年覆盖门在完全独立的指标上已失败。
当前 scope 不得重跑；只能在未来另立版本化 successor 时先修正并增加合法 `.SZ`/拒绝 `.BJ` 对抗 fixture。

### 执行控制缺口：write-once 不是 pre-read one-shot

复核还发现 runner/auditor 会先读取并复算输入，之后才由 write-once sealing 发现已有目标。它可以防止
覆盖既有报告，但不能在语义读取前机器阻止同 scope 再调用。本次 runner 和 auditor 各自严格只调用
一次，现有结果未受影响；但 `same_scope_retry_authorized=false` 尚未完全机器落实，严重度为
`HIGH_EXECUTION_CONTROL`。

本 scope 不通过重跑测试验证该缺口。任何 successor release 前必须以 scope/run identity 为键增加
pre-read consumption gate，并用纯合成输入证明第二次调用在读取 Parquet 前失败。

## 5. 独立审计与不可变证据

- runner 内部 first-pass/replay：PASS；core SHA `42fd4de1...ab31`；
- independent DuckDB auditor：PASS，14 门逐字段一致；
- data gate report SHA：`6f16fe95...5d07`；
- run manifest SHA：`dede740b...9877b`；
- audit report SHA：`d0abc5d1...dac7`；
- tracked aggregate manifest：`config/m7_star_custom_pool_moneyflow_data_manifest_v1.json`；
- 报告和 tracked manifest 均不含证券清单、绝对路径、凭据或资金流数值。

## 6. 风险解释与下一合法动作

当前证据支持：“现有 P1 moneyflow 键在冻结三池/半年门下不能直接进入 M7 候选研究”。它不支持：

- “资金流因子无效”；
- “科创中小盘没有可研究价值”；
- “降低 99% 门槛即可继续”；
- “用别名、前后日、当前成分或填充补齐”；
- “修正 `.SZ` 正则后本门会 GO”。

M7-0 到此关闭，不进入八候选。若未来继续，先在新版本中修复 source 合法后缀域和 pre-read consumption
gate，再另立只面向早期半年缺口谱系的只读恢复协议：保持 PIT、覆盖阈值和三池身份不变，区分上市前/
当日源无记录/源采集缺口/隔离日等原因；必须使用新 scope 和新批准，不能复用本次 approval，也不能把
已知结果包装成盲预注册。

生产 scheduler、信号、模型、模拟仓、Web、自然账本和 M5 proposal 控制面均未修改。

# M7-0R3-P2 精确网络恢复 release 施工协议

## 冻结结论

本节点只授权离线生成精确请求计划、实现四角色隔离执行壳、构建不可变 Docker 镜像并生成精确
release scope。当前用户指令不是网络、凭据或 provider 执行批准；在新的 scope SHA 被逐字批准前，
Baostock、Tushare、`.env` 与 token 的实际访问次数必须保持为 0。

协议真身为 `config/m7_moneyflow_evidence_recovery_network_release_v1.yaml`，SHA-256：
`3b487b9a58ae7a376cc640899277885897372cac643118290ab59057cf0cf9d3`。

## 输入身份与已知边界

- 权威 lineage core：`df5de3990428e630eb2f56380601f3bee12fee2d2220a99c48c286e3701beeca`；
- P1 execution manifest：`7abf0889a9dd94364f68df08bb99d9e090e0f5b982000e604fbca50fc686ed5d`；
- 轨 A：908 个成员行、527 个去重源键，目标 Parquet SHA
  `71aded70452d4837b6beb0979b03b750db17aaec1208edb6e08cc4497f0a1237`；
- 轨 B：541 个成员行、541 个去重源键，目标 Parquet SHA
  `fbf2f704c9f5c6d5958f7356953ac34675fd39895eae4dd77b435097376f5dc8`。

旧 `m7-moneyflow-evidence-recovery-v1` 原样保留，其中 predecessor core 的 `d915...` 是已留痕的转录
错误；本协议只按已执行 P1 v2 的 `0428...` 权威身份纠正引用，不改旧文件、不改恢复语义、不改原
M7/R2 NO-GO。

## 请求计划

请求粒度固定为 `source_date × ts_code`，只允许从封存目标读取 `source_date` 与 `ts_code`，先去重，
再把 `source_date` 映射为 provider 的交易日期。证券代码只能留在 Git 忽略、owner-only 的控制目录；
Git 中只保留计数、日期范围和哈希。

轨 A 只调用 Baostock `history_k_data_plus` 的 `date,code,tradestatus`，按证券和连续官方交易日合并
为有界窗口，每个目标键恰好覆盖一次。轨 B 对每个目标键同时要求 Tushare `moneyflow` 的“按日全市场”
和“单证券单日”两种形态，逐键内容哈希必须一致；全市场调用按去重源日期合并。

## 隔离和失败关闭

四个角色使用同一不可变镜像但窄挂载：两类 collector 不共享可写目录；仅 Tushare collector 在未来
获批运行时可挂载一个 token 文件，禁止挂 `.env`；evaluator 与 auditor 永久断网。所有角色非 root、
只读根、drop capabilities、禁止 Docker socket、开发工作树及生产 raw/ledger/logs 挂载。

每个请求必须先原子 claim 后调用，最多 3 次仅传输层尝试；语义空响应不重试，已 claim 失败不得在同
release 重试，同 scope 不得重跑。达到行数上限、重复键、字段不符、非有限资金流数值、双形态缺失或
不一致均失败关闭。

## 下一停止点

协议提交并推送后才可读取封存键并施工。最终实现也必须先提交、推送，再由最终代码、镜像、精确请求
身份、命令、挂载、资源、网络与 secret 角色生成唯一 scope。到此必须停止，等待用户按 action 与 scope
SHA 逐字批准；release ready 不等于恢复成功，也不授权调整覆盖率、候选、效果、模型、回测、前瞻、
模拟仓或生产。


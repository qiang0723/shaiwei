# M7-0R1 资金流数据恢复前工程协议（2026-08-08）

- 协议 ID：`m7-moneyflow-recovery-engineering-v1`
- 机器真身：`config/m7_moneyflow_recovery_engineering_v1.yaml`
- 机器真身 SHA-256：`bad3ea9907eaf23258ed54b4b144cab0e86d8b0b1a8c10b0f3afeab9588788e4`
- 阶段：`SYNTHETIC_RECOVERY_ENGINEERING_PROTOCOL_ONLY`
- 结果已知：是；本节点不是盲预注册，也不得被描述为新的数据门运行

## 1. 结果目标

本节点只修复 M7-0 执行验收暴露的两个工程可信度问题：

1. 科创成员键只能是 `.SH`，但 P1 资金流源是全 A 股目录，源代码域必须允许 `.SH/.SZ` 并继续拒绝
   `.BJ`；
2. runner 和 auditor 必须在任何 Parquet 语义读取前原子消费各自的 scope/role 身份，第二次调用必须在
   loader 被调用前失败，不能只依靠结果写入阶段的 write-once 冲突。

交付只使用合成键。它不读取真实证券键或资金流数值，不调查四个失败半年段，不改变 v1 裁决，也不
授权新的 data gate、候选、标签、收益、模型、回测、外网、前瞻、模拟仓或生产。

## 2. v1 永久边界

M7-0 scope `f4710068...b24e1` 的权威结论继续是
`NO_GO_M7_0_DATA_COMPATIBILITY`，同 scope 永久关闭，不得用于二次调用测试。v1 的四个半年覆盖失败、
报告、manifest 和独立 audit 均不改写。

已知 `source_malformed_key_count=3,620,544` 由 SH-only 校验器误用于全 A 源目录造成，不能作为数据域
诊断；但最低半年覆盖 98.5452% 的独立失败不依赖该计数，所以工程修复不会自动把 v1 改判为 GO。

v1 的覆盖分母、99.5%/99%/95% 阈值、隔离日、PIT 时钟、三池身份和最低名称门全部冻结不变。禁止借
“修正实现”删除年份、删池、降低门槛、填充或改写旧结果。

## 3. 版本化代码域

| 数据角色 | 合法域 | 原因 |
|---|---|---|
| M3 科创成员 | `^[0-9]{6}\.SH$` | 三个研究池均为科创板成员 |
| P1 moneyflow 源 | `^[0-9]{6}\.(SH\|SZ)$` | 冻结 catalog 是全 A 股源目录 |
| 北交所 | `.BJ` 一律失败关闭 | 继承项目不可协商边界 |

Pandas 主路径和 DuckDB 独立审计必须分别实现并在合成 `.SH/.SZ/.BJ/非法格式` fixture 上一致；不得让
auditor 导入主路径的判断函数。现有 v1 公共入口默认行为保持不变，历史 fixture 的规范哈希不得漂移；
successor 通过显式新入口选择全 A 源域。

## 4. pre-read consumption 合同

successor runner/auditor 在完成协议、release、approval 等纯控制身份核验后，必须以
`protocol_sha256 + release_scope_sha256 + approval_sha256 + role + run_id` 原子独占创建消费凭证，随后
才允许调用语义 loader。

- `runner` 与 `auditor` 各有独立角色凭证；
- 凭证创建成功即视为该角色已消费，即使后续计算失败也不得同 scope 重跑；
- 凭证已存在、格式损坏或身份不一致，均须在 loader 调用前失败；
- 合成测试须用计数 loader 证明第二次调用的语义读取增量为 0；
- 当前 v1 正式 scope 不得拿来做这个二次调用测试。

这是一项执行控制原语，不替代后续 report/audit 的不可变 sealing。

## 5. 架构与验收

新职责仍位于 M7 研究门包内：代码域属于纯领域校验；消费凭证属于一次性编排控制。不得引入常驻服务、
数据库、队列、外部依赖或共享万能工具，也不得让 scheduler/Web/生产路径依赖研究 runner。

完成必须同时证明：

- v1 合成 clean/duplicate/sparse 结果与规范哈希不变；
- successor 主/审路径接受 `.SH/.SZ` 源，拒绝 `.BJ` 和非法格式，成员仍只接受 `.SH`；
- 第二次同身份调用在 loader 前失败，第一次失败后的凭证也不回滚；
- M7 专项、全仓、架构、Ruff、compileall、diff-check 与脱敏检查通过；
- 真实证券键、资金流数值、候选和研究尝试增量均为 0。

## 6. 下一停止线

R1 工程 GO 也不表示数据恢复。其后若继续，只能另立 `M7_MONEYFLOW_GAP_LINEAGE_RELEASE_ONLY`：保持
v1 门槛和池身份不变，只调查早期半年缺口属于上市前、合法无交易、隔离日、源采集缺口或其他已冻结
原因。必须生成新 release scope，并由用户精确批准后才能读取缺失键谱系；不得复用 v1 approval，不能
读取资金流数值或进入八候选。

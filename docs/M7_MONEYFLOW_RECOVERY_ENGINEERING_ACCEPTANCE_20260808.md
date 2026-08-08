# M7-0R1 资金流数据恢复前工程验收（2026-08-08）

## 1. 裁决

`GO_ENGINEERING_PREREQUISITES_ONLY`。

本结论只说明 successor 的证券代码域和 pre-read consumption 原语已通过纯合成验收。它不改变 M7-0
权威 `NO_GO_M7_0_DATA_COMPATIBILITY`，不表示缺口已经恢复、数据已经 GO 或资金流策略有效。

真实证券键、资金流数值、缺失证券清单、候选、标签、收益、模型、回测、外网、前瞻、模拟仓和生产
均未读取或运行；研究尝试增量 0，生产授权 `none`。

## 2. 协议先行证据

- 协议：`m7-moneyflow-recovery-engineering-v1`；
- 机器合同 SHA-256：`bad3ea9907eaf23258ed54b4b144cab0e86d8b0b1a8c10b0f3afeab9588788e4`；
- 协议冻结提交：`cdcb0c0`，已先于实现推送 `origin/main`；
- 协议显式声明 `result_blind=false`，没有把已知失败包装为新盲测；
- v1 scope `f4710068...b24e1` 继续关闭且未重跑，旧报告、manifest、audit 和门槛均未改写。

## 3. 代码域修复

Pandas 主路径新增显式 successor 入口，源代码域允许 `.SH/.SZ`；DuckDB 独立路径使用自己的固定正则
复算。M3 科创成员仍只允许 `.SH`，`.BJ` 继续同时触发格式与北交所失败门。

现有 `compute_quality_core` / `recompute_quality_core` 保留 v1 SH-only 默认行为。三组冻结 fixture 的
规范哈希保持：

- clean：`fba879c2...9209`；
- duplicate：`4578ae15...094`；
- sparse：`4c3a04d4...e120`。

successor fixture 证明：合法 `.SZ` 源不再污染 `source_malformed_key_count`；`.BJ`、`.XX`、非法代码
失败关闭；把 `.SZ` 放进科创成员仍失败。主/审报告及规范 SHA 完全一致。

代码身份：

- `compute.py` SHA-256：`bae329d8583a116533d3d88dfceea6938a6380ee01b2fb6b98eabee80bad1f98`；
- `audit_compute.py` SHA-256：`a40485923b6cdc1b780947ff830aa5d18bb88d0bbef6946d9e89d557bc2d95d1`；
- `consumption.py` SHA-256：`721ab9b4e6d764a35cc18c75cd2a1905063f6eef4b2338a20ace857188a687f7`。

## 4. pre-read consumption

新增 `consumption.py` 纯编排原语。它只接受固定五字段身份，以 `runner/auditor` 角色和 run ID 形成独立
文件名，使用 `xb + fsync` 原子独占创建凭证，然后才调用语义 loader。

合成对抗证明：

- 同角色/同 run ID 第二次调用在 loader 前失败；
- 第一次 loader 即使抛错，凭证仍保留，第二次 loader 调用增量为 0；
- runner 和 auditor 角色各自只可消费一次；
- 不依赖最终报告 write-once 才发现重复调用。

该原语尚未被包装成真实 successor runner；这是有意停止线。未来 release 必须在入口级测试中证明先
claim 后 read，不能因为原语存在就声称真实一次性门已完成。

## 5. 架构与验证

- 新/变更生产模块行数：315 / 277 / 75，均低于 400 行软上限；
- M7 恢复专项：20 PASS；
- 全仓：974 PASS，只有既有 `StarletteDeprecationWarning`；
- 架构宪法：13 PASS；
- 全仓 Ruff、compileall、pip check、`git diff --check`：PASS；
- 无新依赖、服务、数据库、队列、secret、网络或生产挂载；
- scheduler 保持既有不可变容器 healthy，未重启。

## 6. 下一合法动作

另立 `M7_MONEYFLOW_GAP_LINEAGE_RELEASE_ONLY` 协议与新 scope，把上述 successor 代码域和 pre-read
原语真正接入窄 runner/auditor，只读取解释早期半年缺口所需的键级谱系。必须保持 v1 的 PIT、池身份、
分母和阈值，不读取资金流数值，不生成八候选；形成精确 release scope 后再次由用户批准，不能复用
v1 approval。

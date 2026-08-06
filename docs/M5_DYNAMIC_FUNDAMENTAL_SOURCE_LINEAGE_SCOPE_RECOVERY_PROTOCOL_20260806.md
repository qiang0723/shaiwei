# M5-2B-R2-R1 锚定行域恢复协议（结果前冻结）

- 恢复 build：`m5-dynamic-fundamental-source-lineage-build-v4`
- 机器真身：`config/m5_dynamic_fundamental_source_lineage_scope_recovery_v4.yaml`
- 当前目标：`SOURCE_LINEAGE_RELEASE_READY_NOT_APPROVED`
- 策略结论：`NOT_EVALUATED`
- 生产授权：`none`

## 1. 为什么必须另立恢复

已批准的 R2 release `b01058b5…f155` 只运行一次，并以 event 6 `STOPPED` 结束。runner 在读取 anchor
财报行后发现冲突身份范围与冻结的 23 组基线不一致，零输出、零 audit。旧 release 已消费且不允许
重跑或原地修补；恢复必须使用新实现提交、新镜像、新 protocol scope、新 case 和新 release scope。

## 2. 唯一允许的语义修复

R1 冲突基线在构造来源身份前固定筛选：`end_date` 以 `1231` 结束，且 `report_type` 属于字符串
`{"1","5"}`。R2 reader 必须在 anchor conflict keys、history allowlist 和 Observation 构造之前应用
完全相同的行域。

季度行或其他 report type 从一开始就不属于被冻结的年报研究域；排除它们是恢复同一数据合同，不是
删除冲突样本。符合年报行域的缺失身份、不同值和来源冲突继续 fail closed，不允许 latest、VIP/普通
优先、update flag、非空率、多数值、数值容差或按效果选源。

## 3. 对抗测试

新 fixture 必须同时包含：

- 年报 report type 1 的既有 23 组冲突，数量和分表计数保持不变；
- 年报 report type 5 的合法冲突，证明不会被误删；
- 标准/VIP 值不同的季度行，证明不会污染 anchor 计数；
- 非法 report type 与带连字符日期，证明过滤和日期规范化与 R1 一致。

不得通过把 fixture 继续限制为“只有年报”来绕过本次故障。

## 4. 不变项

原 R2 v3 协议的三时钟、E0—E3 证据等级、六种处置、历史链门槛、脱敏输出、独立 auditor 和 verdict
全部不变；八候选、三池、24 单元、公式、方向、PIT、覆盖门、未来窗、尝试 `N=14/20` 与效果测试 0
不变。此次施工不构成新的因子尝试。

## 5. 施工与停止线

本阶段只允许修改 lineage reader 的冻结行域适配、增加纯 predicate 与合成对抗测试，并更新新
build/scope/case/release 控制身份。允许用 metadata/哈希生成新输入清单和构建断网镜像。

禁止读取真实财务语义、初始化正式 registry、运行真实 lineage、启动 auditor、联网、采集权威证据、
读取凭据、PIT、候选、标签、效果、模型、回测、Web、scheduler 或生产。实现提交必须先推送；新
release scope 形成后立即停止，只有用户针对新完整 SHA 再次明确批准才可运行一次真实 feasibility。

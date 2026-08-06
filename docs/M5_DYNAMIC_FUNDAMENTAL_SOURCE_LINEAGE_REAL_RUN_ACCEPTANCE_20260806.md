# M5-2B-R2 财报版本谱系断网真实运行验收

- 验收时间：2026-08-06（UTC+8）
- 批准的 release scope：
  `b01058b55ff3dd6c06cf0722541214ecbb793de92a3115410c073daab26cf155`
- 运行终态：`STOPPED`
- 谱系裁决：`NOT_EVALUATED`
- 策略结论：`NOT_EVALUATED`
- 生产授权：`none`

## 1. 结论

用户对上述完整 scope 明确批准恰好一次断网真实 `LINEAGE_FEASIBILITY`。批准不包含外网、权威证据
采集、PIT、候选、标签、效果、模型、回测或生产。

唯一真实 runner 在读取清单绑定的 anchor 财报行后，以 exit code 2 失败关闭：
`M5 lineage anchor conflict identity changed`。输出目录和 audit 目录均为 0 文件；auditor 未启动，
registry 未登记 `LINEAGE_GATE_RECORDED`。因此本次不是 lineage NO-GO、不是数据门新裁决，也不是策略
REJECT；权威状态只能是 `STOPPED / NOT_EVALUATED / production none`。

## 2. 执行前门禁

- 提案仍为 `REVIEW_REQUIRED`、event 2，head event SHA-256 为
  `2d6ff1aace167fa6299414773e031adab9ceac09eadd0b789fbb170c41570f5f`，到期时间
  `2026-08-12T10:48:16+00:00`。
- `HEAD=origin/main=e2700f69e06341444bd275485c120298d6766d22`；release 绑定的实现提交
  `f2e5483f55278010cde4ea5ff5f8e3b56c09ae37` 已先推送，后续提交仅含 release 验收文档。
- 本地镜像与 scope 完全一致：
  `sha256:fe9101f11a54d0b2111c0000ffff5a21d7d72fd86f4300aa30ae7b934119b606`，
  `linux/arm64`。
- 上一权威 registry 在只读、断网、只读根容器中完整性 PASS；其逻辑 dump SHA-256 为
  `bd8153ba14f0c4d57b645e34209831c2b451fdaaf460bbf71d2905571142a78d`。
- 四个 release 专属路径在执行前均不存在，未复用任何半成品。

## 3. 批准、输入束与正式事件链

新的 release-bound registry 从上一权威 registry 的 SQLite 一致性备份初始化，先保持原两条 case
逻辑内容不变，再追加独立 R2 case
`6b6c849f4ded89f631e1af8127f0e7321898aa7f4ce0c2630806fc8c8ef7be16`：

| event | seq | event SHA-256 | 状态 |
|---|---:|---|---|
| `IMPORT` | 1 | `9506e73317833204759744ac9ca6aa3ad24eec11db919e354dff1a31fe7df893` | `IMPORTED` |
| `PROTOCOL_FROZEN` | 2 | `655464742de0633b0b223f744b4f5118447c0be5b191c4d1cabfe73f11d30dee` | `PROTOCOL_FROZEN` |
| `LINEAGE_GATE_RELEASE_READY` | 3 | `19a34e34139f7d93c39520195778b1e1a46099def29d30115066ea84c8209ba8` | `LINEAGE_GATE_RELEASE_READY` |
| `LINEAGE_GATE_APPROVED` | 4 | `aea546bce6b4255d389bdb9bc27f3d331d6f30469cee5e25b12c8e7e1fe9fcef` | `LINEAGE_GATE_APPROVED` |
| `LINEAGE_GATE_STARTED` | 5 | `75a68bc9b1a3ba33673f5aac173d35dbdef218808e5f771b32ce5d1e76ed6a6c` | `LINEAGE_GATE_RUNNING` |
| `STOPPED` | 6 | `2dc732c8ed42a494b09bec6766f9896f6be73f82fced28bb48654f3481374e27` | `STOPPED` |

批准 envelope 的规范逻辑 SHA-256 为
`b72b73fedb0abf1019d2ee41d41ca273010569740f7f0d24ae3a10bcea74353b`，物理 SHA-256 为
`e9313d014daba93936cb222614822863f9349c6a7b3a5ca9b010af55dbd671ff`。

批准后物化的输入束包含 16,853 个文件，bundle manifest SHA-256 为
`033dca44482a478e613214302b5f07b59b3571b381d8f0f62180147f37fa42b2`；物化阶段保持
`semantic_rows_read=false`。runner 固定断网、非 root、只读根、drop ALL capabilities、
no-new-privileges、128 pids，只挂载 scope 中的只读输入和专属输出。

## 4. 实现级阻断根因

R1 的 23 组权威冲突基线是在 `source_conflicts._prepare` 中先限定
`end_date` 为 12 月 31 日且 `report_type` 属于 `{1,5}` 后计算。R2 的 `lineage_reader` 在锚定校验前
直接读取清单内所有财报行并计算 conflict keys，没有应用同一冻结过滤口径；合成 fixture 只包含年报，
因此此前工程测试没有暴露该范围差异。

这使 runner 把一个更宽的行域与冻结的 23 组年报基线比较，并在任何谱系构造、公开报告或 auditor
之前失败关闭。该根因来自静态代码路径对照；本轮没有为获得额外诊断数字而第二次读取真实语义数据。

## 5. 完整性、幂等与隔离

- 新 registry：3 cases、22 events、22 receipts、22 outbox，pending outbox 为 0；完整性 PASS。
- `STOPPED` 同命令重放返回同一 event 6；事件数不增加；outbox 第二次发布 0。
- 原 v3 case 仍为 event 10 `STOPPED`，head SHA
  `e0ca4594e03639212ba6ed5ebe75f651a0d3664da7cad86e232e3cefc0b9b3bd`。
- R1 case 仍为 event 6 `BLOCKED_DATA`，head SHA
  `7c2615a0f9d271b8b898bc8fa2a332edabfac92d48c58f31918c49bffa80917e`。
- 上一权威 registry DB 和 gate ledger 物理 SHA-256 仍分别为
  `1e5c0096b0ab1370956770c5c95d27440cc93bc961417640b7d503463b5f6bc8`、
  `77f85f1462af9970500435926c79405b8cd8cb900545f3ca098787358901012a`。
- R2 输出 0 文件、audit 0 文件；没有临时 M5 容器遗留。
- scheduler 仍为容器 `183b8c6c5edd`、镜像
  `sha256:722f63de15932cb2698e82db7c0140f02921f27f126e1c0235ca62e0a1213b76`、创建时间
  `2026-08-03 17:39:34 +0800`，healthy 且未重启。

## 6. 验证

- 谱系 release/source-conflict 专项：15 PASS。
- 全仓：804 PASS；仅 1 条既有 Starlette 第三方弃用 warning。
- 架构宪法：6 PASS。
- Ruff、compileall、pip check、git diff check：PASS。
- 正式 registry 在冻结断网镜像中完整性 PASS；event 6 与 outbox 幂等 PASS。

## 7. 停止线与下一合法动作

本 release 已消费且没有重试授权，不得原地修补、重建镜像或重跑。若继续，应另立 superseding
恢复提交与新 release：让 lineage reader 复用与 R1 基线完全相同的冻结行域，并增加包含季度行的对抗
fixture；实现、镜像和新 scope 推送后，仍须用户针对新完整 SHA 再次明确授权。即使未来 lineage GO，
也只允许另立数据门协议/release，不自动授权外网补证、PIT、候选、效果、模型、回测或生产。

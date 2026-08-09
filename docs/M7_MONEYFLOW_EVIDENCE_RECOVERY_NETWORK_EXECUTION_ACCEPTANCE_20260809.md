# M7-0R3-P2 资金流网络证据恢复执行验收（2026-08-09）

## 1. 权威结论

`NO_GO_M7_EVIDENCE_RECOVERY_INCOMPLETE`。

本次精确恢复把轨 A 的 527 个独立状态缺口全部闭合为未交易，但轨 B 的 541 个资金流目标键在
“按日全市场”和“按票单日”两种冻结请求形态下都没有取回。因此现有证据仍不能满足 M7 数据门，
不得计算调整后覆盖率、生成候选、读取效果、训练模型、回测、进入前瞻/模拟仓或生产。

这不是资金流因子或策略效果的 REJECT：候选定义 0、效果检验 0、研究尝试增量 0，
`strategy_effective=NOT_EVALUATED`、生产授权 `none`。原 M7-0 与 M7-0R2 的两个 NO-GO 继续有效。

## 2. 授权、身份与一次性消费

- 用户批准 action `M7_MONEYFLOW_EVIDENCE_RECOVERY_ONCE`，精确绑定 scope
  `a701e9ceb9bb77634a4feaa62fc640c3447555ef089bc7448577d48e5d68cb73`；
- release 文件物理 SHA `8d3e237c...f1af`，请求计划 manifest SHA `dcc2a78d...f43`；
- approval canonical / physical SHA 分别为 `99811b25...4b80` / `45cf767c...80c0`，明确
  `same_scope_rerun_authorized=false`；
- 执行镜像 `sha256:5b15e23f...b3da`，`linux/arm64`；四角色均非 root、只读根、
  `cap_drop=ALL`、`no-new-privileges`，不挂载项目根、Docker socket 或生产目录；
- status collector、moneyflow collector、evaluator、auditor 各只启动一次；共 1,157 个请求 claim、
  1,157 个不可变 receipt，没有语义重试或第二次角色调用；
- 专用 token 文件只在 moneyflow collector 中只读挂载，采集完成后立即删除；`.env` 未挂载、未修改，
  token 未输出、未写入 tracked manifest 或 Git。

本 scope 已完整消费并关闭，不得重跑、补跑已 claim 请求、重分类后覆盖本次报告或复用 approval。

## 3. 网络采集结果

| 角色/形态 | 冻结请求 | 传输尝试 | receipt | 结果 |
|---|---:|---:|---:|---|
| Baostock 独立交易状态 | 75 | 75 | 75 | PASS |
| Tushare 按日全市场 moneyflow | 541 | 541 | 541 | PASS |
| Tushare 按票单日 moneyflow | 541 | 541 | 541 | PASS |
| 合计 | 1,157 | 1,157 | 1,157 | PASS |

状态采集返回 527 行，恰好覆盖 527 个唯一目标键；没有重复、非法状态、冲突、额外键或缺键。
moneyflow 全市场响应合计 2,621,361 行，每次 4,517—5,166 行，未触发 6,000 行饱和门；但其中没有
541 个目标键。541 次单票单日响应也全部为空。两种独立形态共同确认这些资金流键在当前 Tushare
`moneyflow` 源中不可恢复，而不是某一种请求参数或分页方式漏取。

collection manifest：status `44f1eb4b...b45cc`，moneyflow `24c18fc9...03ddb`；合并 batch manifest
`2e2f42ef...f3f4a`。所有响应 schema、数值有限性、重复键、额外键、`.BJ`、内容完整性和 write-once
校验均通过。

## 4. 断网 evaluator 与独立 audit

- evaluator 在 `network=none` 下完成内部双算，first-pass/replay core SHA 同为
  `56afd43a...d8ff`；
- 轨 A：908 个成员行对应 527 个唯一键，527/527 独立确认为不交易，冲突 0、未决 0；
- 轨 B：541 个唯一键恢复 0；全市场缺 541、单票缺 541，`missing_shape_key_count=1082`，内容冲突 0；
- 10 个门中 7 PASS、3 FAIL；轨 B 两个硬门分别以观察值 1,082、阈值 0 独立失败；
- evaluator report / manifest SHA 为 `94a3b093...7e3a` / `161c4c65...2c5f`；
- 独立 auditor 重新读取全部 1,157 个 receipt 并复算 10 门，状态 PASS，裁决相同；audit SHA
  `f870534a...6604`，独立向量 SHA `7d71abfb...98a1`。

真实产物共 3,480 个文件、237,604,601 bytes，保留在 Git 忽略的项目内控制目录；tracked 聚合 manifest
为 `config/m7_moneyflow_evidence_recovery_network_execution_manifest_v1.json`，SHA
`573e52f7...9da`。聚合真身不含证券代码、原始/派生业务行、绝对路径或凭据。

## 5. 非改判诊断发现

附加的 `key_validity_and_bj_zero_pass` 观察值为 1,449。代码审查确认原因不是证券代码或 `.BJ`：
`m7_moneyflow_recovery.compute` 的目标行校验仍要求旧的 `YYYYH1/H2` segment 格式，而冻结目标投影使用
`large_unregistered/midcap/smallcap` 三种规模标签，故 908 + 541 个目标成员行全部被重复标为非法。

该缺陷不影响本次权威 NO-GO：轨 B 的两种源查询都对 541 个目标键返回缺失，两个独立硬门在去除此
诊断噪声后仍失败。为遵守同 scope 不得重跑和不得结果后修门，本次不修改 evaluator、不重算报告、
不覆盖 audit；缺陷仅作为后续代码清单项保留。

## 6. 验证与生产隔离

- 执行前 M7 网络 release/request-plan/mount-recovery 专项 23 PASS；
- 终版架构宪法 13 PASS，全仓 1,066 PASS（17 条既有第三方/兼容性 warning）；
- Ruff、compileall、pip check、git diff-check 和 tracked manifest 脱敏扫描 PASS；
- release、approval、计划、collection、evaluation 与 audit 哈希复算一致；1,157 个 receipt 与四角色
  claim 数量精确闭合，专用 token 副本不存在。

scheduler 执行前后保持容器 `183b8c6c5edd...3dd3b`、镜像 `sha256:722f63de...13b76` 且 healthy，
没有重启或挂载本次研究目录；自然 ledger 没有被本次任务暂存或写入。一次性容器均以 `--rm` 清理。

## 7. 停止点

按照 2026-08-09 路线复盘的硬停止规则，本次证据仍不完整后不再建立 M7 R4/R5，不追加数据源、不放宽
99.5%/99%/95% 门槛，也不进入八候选。M7 在候选前终止；下一主线转为只读 A1-2 活跃/归档/删除候选
清单，任何实际删除或重构仍须另立目标并由用户复核。

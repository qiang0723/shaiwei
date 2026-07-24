# P2-0 科创50官方成员谱系数据门验收（protocol-v2，2026-07-24，UTC+8）

## 1. 裁决

`p2-star50-protocol-v2` 机器裁决：**GO**，范围严格限定为
`official_membership_lineage_data_gate_only`。

分层状态为：

| 层级 | 结论 |
|---|---|
| `official_lineage_complete` | `true` |
| `tushare_crosscheck_pass` | `true` |
| `pit_constructible` | `true` |
| `engineering_complete` | `false` |
| `strategy_results_inspected` | `false` |
| `production_authorization` | `none` |

该 GO 只证明可从官方首批名单和官方调整公告构建 `000688.SH` 的逐日 PIT 成员集合。没有构建
qlib、训练模型、运行回测、计算 IC/收益/排名或生成信号，也不证明科创50策略有效。中证800仍是唯一
生产主策略，P2-1 必须由主控另立目标后才能开始。

`p2-star50-protocol-v1` 的 NO-GO 永久保留：它正确证明 Tushare `index_weight` 不能作为唯一 PIT
真身。v2 没有删除、覆盖或改写 v1，只以结果前冻结的官方一级来源协议建立另一条证据链。

## 2. 结果前冻结与来源纪律

官方材料查询前已提交并推送：

- 冻结提交：`3013710`（`docs: freeze P2 Star50 official lineage v2`）；
- 协议：`docs/P2_STAR50_OFFICIAL_LINEAGE_PROTOCOL_V2_20260724.md`；
- 配置：`config/p2_star50_v2.yaml`；
- 配置 SHA-256：
  `54e9d49d295c26c19898e716873a333d85f581d02c914c2d4affaa23072c4183`。

一级来源只使用上交所官方发布页、公告归档页及其官方附件；未用第三方网页补证。Tushare
`index_weight` 只对账成员集合，`weight` 数值没有进入官方谱系，月末 `trade_date` 没有被解释为
官方生效日。

官方查询按串行、至少 1 秒间隔、最多 3 次有界重试、重定向域名白名单、单文件 50 MiB 上限执行。
Docker 容器访问上交所材料收到 HTTP 403，因此下载器在项目宿主环境以同一冻结策略调用 `curl`；
解析、质量门和测试仍在开发 Docker 镜像内执行。没有绕过到第三方来源，也没有进入生产 scheduler
镜像。原文件按内容 SHA-256 寻址、只增不改，保存在 Git 忽略的
`data/research/star50/p2-star50-v2/official_sources/`。

脱敏 manifest 共列出 57 份官方材料：10 页公告归档、25 个候选发布/调整页面和 22 个附件。
它只含官方 URL、内容哈希、字节数、媒体类型、检索时间、用途和父页面，不含本机绝对路径、响应头、
cookie、token 或代理信息。

## 3. 初始集合与最早可用日

2020-06-19 官方发布页所附 `000688` 样本股 XLSX 可完整解析为 50 个唯一代码，`.BJ=0`：

| 证据 | SHA-256 |
|---|---|
| 首批样本名单 XLSX | `7cf6a9ea64f5d2c32210339c0d9838d1c3d26fc2e905361ebf6f6f00e1571557` |
| 官方发布页 | `c8c5ad2a9a9833a931888f0710a4d0424d0a604b6bd6d752a9deaab562b5a1f4` |
| 官方编制方案 PDF | `5e42b0297057fae5f09d392f21f183b9b9846523263377322da6a50695ef0aa7` |
| 初始集合 canonical | `39a5a9d292c4aa6ffe3f30a9402f7e54ed0176e4c5357e1e5b0d3ae5cbeea271` |

发布页同时证明：历史行情在 2020-07-22 收盘后发布，实时行情于 2020-07-23 正式发布。名单在
正式发布前已公开且文件哈希可固定，因此 v2 允许的最早策略可用日为 **2020-07-23**；这合法解除
v1 的 7 个交易日 Tushare 月末快照缺口，但不改变 v1 的裁决。

编制方案文本校验通过三项规则：样本原则上每季度调整一次、定期调整在审核月第二个星期五的下一
交易日生效、存在临时调整机制。

## 4. 官方成员事件与 PIT 重建

归档页从当前页串行扫描至第 10 页；第 10 页最新公告日为 2020-02-28，早于科创50首发，因而形成
可审计的历史扫描边界。首发后共识别 24 期相关官方调整公告：

- 23 期包含成员替换，共 82 对 `out_code/in_code`；
- 2024-11-29 一期官方明确“科创50指数样本无变动”；
- 官方归档内没有发现临时调整成员对，`temporary_adjustment_pair_count=0`；编制方案的临时调整机制
  仍被纳入发现与 fail-closed 规则，且 72 期集合对账没有暴露未解释的临时变动。

每条事件至少绑定
`announcement_date/effective_date/out_code/in_code/source_url/source_file_sha256/retrieved_at/parser_version`，
另保留 `official_reference_date/effective_timing/event_type`。公告写“收市/收盘后生效”时，以官方
参考日后的首个 SSE 开市日作为逐日集合生效日；写“于某日调整/起”时保留该开市日。未来公告不得
用于过去日期。

解析器支持官方 HTML、XLSX、可抽取文本 PDF 和 WPS/DOCX OOXML。2025-08-29 的官方 `.wps`
附件实际为 Word 2007+ 容器，由 XML 解析后纳入谱系；初次漏取该附件的失败结果与派生产物保留在
Git 忽略的 provisional 目录，没有手工补数或覆盖失败证据。对 28 页 PDF 做了渲染抽查，表格和
成员代码可读且没有裁切；机器解析仍以原文件哈希和双路径/声明数量核验为准。

从初始 50 只依次应用 82 对事件后，每个生效批次成员数均严格为 50，调出代码必须已在集合、调入
代码不得已在集合，重复、未知成员、`.BJ` 和公告日晚于生效日的情况均为 0。形成的逐日集合为：

| 指标 | 结果 |
|---|---:|
| 范围 | 2020-07-23~2026-07-24 |
| SSE 交易日 | 1,456 |
| 成员行 | 72,800 |
| 每日成员数最小/最大 | 50 / 50 |
| daily canonical SHA-256 | `67c519c312e83e74f85ada938b48d3a2f98f51be2b4f9775c95c82c63c3c3d74` |

## 5. Tushare 二级集合对账

冻结的 2020-07-31~2026-06-30 共 72 个已完成月度快照全部参与对账。对每个快照日只取
`con_code` 集合，与官方谱系当日已生效集合做精确比较：

| 检查 | 结果 |
|---|---:|
| 预期/实得快照 | 72 / 72 |
| 完全集合一致 | 72 / 72 |
| 集合差异 | 0 |
| 每期官方/Tushare 成员数 | 50 / 50 |
| Tushare 重复成员行 | 0 |
| `.BJ` | 0 |
| 使用 Tushare `weight` 数值 | 否 |
| 把月末 `trade_date` 当官方生效日 | 否 |

这项结果只说明官方事件重建与 Tushare 月度集合相互吻合；PIT 真身仍是官方 `initial_set +
membership_events`。

## 6. 不可变产物与哈希

| 产物 | SHA-256 |
|---|---|
| 脱敏官方来源 manifest | `387514f25d9f883c7ebe84e386ba6dbca4644bb204628004cee4991dc316e112` |
| 官方发现报告 canonical | `9b6e968379125128d42b6308133c2d112cb8c870dca76e690ef51bed0d402cb3` |
| 终版质量报告 | `51bfe33aa21162007961d9fb0fd8a6fe91d45ce7593bddac7c9ff0c2fda2df93` |
| `initial_set.parquet` | `fe960ccc0b86592c02d082a7f9fda18bb6032b4c263458850cc7deb709a95d4c` |
| `membership_events.parquet` | `ee5b6ac2a3ee608067bcca51cc21da152b754ec2b96c52c2be4db184c55cdf6a` |
| `daily_membership.parquet` | `91e9d48421d2a577176488d792c63f5d33bceee953a4532cdb8a8f6317d82644` |
| event canonical | `ad608741042a7d8fc0b06a24ce0436226c8df7b9a37f84580c8ced1851381db3` |
| v2 工具快照 | `37cf932453bbe971ab67eb4e0a086f7890e6a000f80b73ab098015c3191def59` |

原附件、检索状态、逐日集合和质量报告全部留在项目数据目录并保持 Git 忽略；Git 只提交脱敏
manifest、解析器、依赖锁、测试和本验收文档。官方抓取和谱系构建的相同输入复跑均复用既有内容，
不新增或覆盖不可变文件。

## 7. 测试、隔离与停工边界

专项测试覆盖公告发现筛选、附件 URL 去重、WPS 发现与解析、HTML 排除其他指数、首批 50 只唯一性、
盘后生效日归一化和开市日直接生效。提交前验证结果：

- Docker 全仓 pytest：196 passed；
- Docker Ruff：All checks passed；
- Docker compileall：通过；
- Docker `pip check`：No broken requirements found；
- 官方发现入口缓存复跑仍为 10 个归档页、25 个候选页面、22 个附件，发现报告路径与哈希不变；
- Docker 谱系入口以同一发现报告复跑仍为三门 `true`、`verdict=GO`，不可变产物未改变；
- `git diff --check` 和 manifest 脱敏扫描通过。

本任务没有修改 `src/`、生产 compose 配置、scheduler 镜像、CSI800 配置/模型/信号/门禁或任何
生产账本。v2 数据门完成即停；不自行进入 P2-1。

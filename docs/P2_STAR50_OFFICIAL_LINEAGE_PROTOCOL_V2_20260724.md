# P2 科创50官方成员谱系协议 v2（结果前冻结）

冻结时间：2026-07-24 23:05（UTC+8）

状态：**FROZEN BEFORE OFFICIAL SOURCE RETRIEVAL AND BEFORE ANY STRATEGY RESULT**。

本协议永久保留 `p2-star50-protocol-v1` 的 NO-GO，不覆盖、不删除，也不把它表述成 P2 整体失败。
v2 只回答“能否以官方材料重建 `000688.SH` 的 PIT 成员谱系”，不授权 qlib、模型、回测、IC、
收益、排名或信号。机器真身为 `config/p2_star50_v2.yaml`。

## 1. 一、二级来源

一级真身只允许上海证券交易所和中证指数有限公司官方域名及官方附件：`sse.com.cn`、
`csindex.com.cn`、`oss-ch.csindex.com.cn`。第三方网页、基金公司材料、行情软件和 Tushare 均不能替代
官方成员事件。

Tushare `index_weight` 降为二级交叉核验：只比较每个 `trade_date` 的成分集合；`weight` 数值不进入
v2，月末 `trade_date` 不解释为官方生效日。

## 2. 官方材料与不可变证据

首发页固定为：
`https://www.sse.com.cn/market/sseindex/diclosure/c/c_20200619_5130634.shtml`。

施工时须取得并保存：

1. 2020-06-19 发布页所附首批样本股名单；
2. 截止 2026-07-24 的全部定期调整公告及附件；
3. 同期全部临时调整公告及附件；
4. 能证明公告日期、实施日期和调入/调出代码的官方页面或文件。

下载必须串行、请求间隔至少 1 秒、最多 3 次有界重试，重定向不得离开官方域名，单文件不超过
50 MiB。原文件按内容 SHA-256 寻址保存在
`data/research/star50/p2-star50-v2/official_sources/`，只增不改且保持 Git 忽略。

Git 只提交 `config/p2_star50_official_sources_v2.json` 的脱敏 manifest、文件哈希、解析器、fixture、
测试和验收文档；manifest 禁止绝对本机路径、cookie、token、响应头或其他凭据。

## 3. 初始集合

`initial_set` 必须从官方首批名单解析，正好 50 个唯一代码，`.BJ=0`。每个成员必须绑定
`source_url/source_file_sha256/retrieved_at/parser_version`。

若名单完整可读、哈希可固定，且官方发布日期不晚于 2020-07-22，最早策略可用日允许为
2020-07-23；这只解除 v1 的 7 日 Tushare 快照缺口，不改写 v1。若证据不完整，最早日自动退回
2020-08-03并使 v2 当前门禁 NO-GO。

## 4. 事件账本与 PIT 重建

`membership_events` 一行表示一对调出/调入，字段至少为：

`announcement_date,effective_date,out_code,in_code,source_url,source_file_sha256,retrieved_at,parser_version`。

- `announcement_date > effective_date`、缺少调入/调出配对、代码重复或 `.BJ` 均 FAIL。
- 定期和临时调整都必须进入；无法解析、公告/生效日歧义或公告缺口均 FAIL。
- 事件只从 `effective_date` 改变集合；不得用未来公告改写过去日期。
- 每批事件后成员必须仍为 50 个；任何差异只追溯官方公告，不允许手工改数。
- `initial_set + membership_events` 是唯一成员真身；当前成分或 Tushare 月末快照不能向历史回填。

## 5. 完整性发现与停止条件

在官方站内/官方索引中串行检索精确名称、`000688`、定期“调整样本”和“临时调整”。停止条件不是
“搜索不到更多”，而是同时满足：首批附件取得；官方定期与临时公告材料均可解析；事件按生效日连续；
逐事件成员数恒为 50；与全部 72 份已完成 Tushare 月度集合逐期完全一致；不存在只能靠手工补齐的
差异。任一条件不成立即 fail closed。

## 6. 二级集合核验

冻结范围为 2020-07-31~2026-06-30 的 72 个 Tushare 月度快照。对每个快照日，取官方谱系在该日
生效后的成员集合，与 Tushare `con_code` 做精确集合比较。缺快照、集合差异、成员数异常、`.BJ`、
把 `weight` 或月末日期当官方事实，任一项 FAIL。差异必须回到官方页面/附件调查，不得修正 Tushare
或官方派生数据来追求一致。

## 7. v2 数据门

终版报告必须独立输出：

- `official_lineage_complete`；
- `tushare_crosscheck_pass`；
- `pit_constructible`；
- `engineering_complete=false`；
- `strategy_results_inspected=false`；
- `production_authorization=none`；
- `verdict=GO/NO_GO`。

只有前三项全部为 true 才允许 v2 数据门 GO。GO 只代表可另立 P2-1 目标，不代表工程完成、策略
有效或生产授权。

## 8. 隔离与停工点

所有数据、原附件和派生产物只留在本项目目录。不得修改 CSI800 生产代码、配置、模型、信号、门禁、
scheduler 镜像或发布状态。v2 GO/NO-GO、测试、脱敏、Git 同步和工作树干净后立即停工并回传主控；
不得自行进入 P2-1。

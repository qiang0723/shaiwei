# M7-0 三自建科创池资金流数据兼容性协议

> 协议 ID：`m7-star-custom-pool-moneyflow-data-compatibility-v1`
>
> 冻结时间：2026-08-08 12:20:03（UTC+8）
>
> 当前状态：`RESULT_BEFORE_PROTOCOL_FROZEN / REAL_DATA_NOT_AUTHORIZED`
>
> 唯一允许的未来数据裁决：`GO_M7_0_DATA_COMPATIBILITY_ONLY` 或
> `NO_GO_M7_0_DATA_COMPATIBILITY`

## 1. 结论与本批目的

本批只回答一个问题：既有、已审计的 `tushare.moneyflow` 历史键，能否按冻结的下一交易日可用时钟，
与 M3 三个自建科创 PIT 研究池形成覆盖稳定、无时间穿越、可重复审计的数据连接。

它不回答哪些资金流公式有效，不生成 8 个候选，不读取资金流数值列、标签、收益或封存效果，也不
训练模型、回测、开模拟仓或接生产。数据门 GO 只允许另立有界候选协议；NO-GO 则在数据层停止。

选择先做键级兼容性门有三个原因：

1. P1 已证明 A 股全市场资金流源总体可用，但六个中证800简单候选最终 REJECT；数据可用与因子有效
   必须继续分层。
2. M3 已证明三个规则型科创池的成员 PIT 可构造，但 M3-2 使用的是量价输入；资金流对这些池的覆盖
   尚未被独立验证。
3. 若先定义公式再发现源与成员无法稳定连接，会无谓消耗 8 次研究尝试；本门只读取键，不允许据数值
   分布选择公式，因此不会把数据可行性检查变成隐性因子筛选。

完整机器合同为
`config/m7_star_custom_pool_moneyflow_data_v1.yaml`，当前 SHA-256 为
`b629ba917744c43247d301fa59cc1bb0ef5340587c6947b0d2f737cc023e164e`。

## 2. M5-1B 提案绑定

本协议只继承以下 `REVIEW_REQUIRED` 非权威提案：

- proposal ID：`4d3007db221e9d63e9d0be742f3e64493085dac48c7a9c5ca37de7bd6d589a65`；
- request SHA-256：`05caa719c15a7d60030aca650078827aa82821fa2b61cfd04de98ef65beba88c`；
- canonical proposal SHA-256：`67e1674835f2077a0d59e8ec6968ded2729f48bde7c296e11ea8519bb42faeb8`；
- 事件序号：2；事件链头：`da38d05a...b1f0a`；
- 到期时间：2026-08-15 12:05:02（UTC+8）；
- 内容寻址导出：`config/m7_star_custom_pool_moneyflow_proposal_export_v1.json`，SHA-256
`99368c40d5dcbb9888659a2fb84445aec31eaafc957ad000dcd8630aeb9cf582`。

未来 real-data release 获批时，提案必须仍为 `REVIEW_REQUIRED`、事件序号仍为 2、链头不变且未
到期；任一项变化都使 release 失效，不能迁移旧授权或续签原提案。

## 3. 研究对象与尝试计数

股票池身份固定为：

| 角色 | 股票池 | 身份 |
|---|---|---|
| HOME | `star-board-all-pit-v1` | 科创板全市场自建 PIT 研究池 |
| TRANSFER | `star-board-midcap-pit-v1` | 科创板中盘自建 PIT 研究池 |
| TRANSFER | `star-board-smallcap-pit-v1` | 科创板小盘自建 PIT 研究池 |

三个池都必须显示为 `CUSTOM_RULE_BASED`，不得包装为科创50、科创100、科创200或其他官方指数。

本协议冻结时：

- 候选定义数：0；
- 评价单元数：0；
- 效果读取数：0；
- 本批生成尝试增量：0；
- 资金流家族既有历史背景：`N=18`；
- M5-1B 只登记未来最多 8 次，计划背景为 `N=26`，尚未发生。

若数据门 GO，未来候选协议必须恰好从 `N=18` 起累计、最多增加 8 次；不能因为三个股票池而把同一
公式记成三次独立生成，也不能把 P1 REJECT 的六式改名、翻向或轻微改窗后当作全新零历史家族。

## 4. 冻结输入

### 4.1 M3 成员 PIT 真身

- 协议：`config/m3_star_custom_pit_v1.yaml`，SHA-256 `e400f6f1...ddd058`；
- manifest：`config/m3_star_custom_pit_manifest_v1.json`，SHA-256 `cf8cb88e...1c2638`；
- 质量报告：`data/research/m3/star-custom-pit-v1/quality_report.json`，SHA-256 `f25d8e60...ace02`；
- 日成员：`data/research/m3/star-custom-pit-v1/daily_members.parquet`，779,271 行，SHA-256
  `1983169e...75101`；
- 唯一键：`(trade_date, universe_id, ts_code)`；
- 必需列：`trade_date, formation_date, universe_id, ts_code, segment`。

运行前必须再次验证物理哈希、上游裁决 `GO_CUSTOM_PIT_DATA_RULE_GATE_ONLY`、策略仍
`NOT_EVALUATED`、三池集合关系及 `.BJ=0`。不得用当前成员或其他池替换。

### 4.2 P1 资金流质量真身

- 数据规范：`docs/MONEYFLOW_DATA_SPEC.md`，SHA-256 `91f42a3f...6f25a`；
- 特征准备验收：`docs/P1_MONEYFLOW_FEATURE_ACCEPTANCE_20260724.md`，SHA-256 `79dfccf8...1568`；
- 权威效果验收：`docs/P1_MONEYFLOW_EXPERIMENT_ACCEPTANCE_20260724.md`，SHA-256 `5256ed73...80a`；
- 全量复采后质量报告：`logs/moneyflow/p1_full_quality_post_refresh_20160104_20260723_20260724.json`，
  SHA-256 `f451cc8d...e4b5`；
- 失败日复采报告：`logs/moneyflow/p1_failed_dates_refresh_20260724.json`，SHA-256 `403937bf...e883`；
- 整日隔离报告：`logs/moneyflow/p1_quarantine_v2_20160104_20260723_20260724.json`，SHA-256
  `e841f813...4d24`；
- 冻结 catalog SHA-256：`04ffd1f5...0890`；2,563 个源日、10,614,438 行、46 个隔离日、修订0、
  饱和响应0。

未来 metadata inventory 必须从追加式 ingest ledger 选择冻结日期域内每个规范请求的最新已提交批，
核对文件、行数、内容哈希与上述 catalog。它可以构建内容寻址输入束，但不得读取证券键或任何数值列；
该 inventory 及实现提交必须先行推送，形成新的精确 release scope 后再请求真实读取授权。

## 5. 粒度与 PIT 时钟

正式兼容性粒度为一个 `feature_date × universe_id × ts_code` 成员行。

- feature 日期域：2021-01-04 至 2026-06-30，均为完整历史区间；
- source 日期域：2020-12-31 至 2026-06-29；
- D 日 `moneyflow` 只能映射到下一 SSE 官方开市日 D+1；
- 同日使用、未来源日使用、多源日映射一个 feature 日或一个源日映射非下一开市日均为硬失败；
- 46 个 `moneyflow-quality-v2` 隔离源日映射出的 feature 日整日隔离，不填0、不前填、不后填；
- 非隔离日只允许 `ts_code` 精确连接，不按简称、现代码、收益轨迹或模糊别名补映射；
- 原始 Parquet 只投影 `ts_code, trade_date` 两列，数值资金流字段禁止读取。

这一定义使数据门只知道“某成员在事前可用源日是否存在键”，不知道任何资金流大小、方向、分布、
标签或收益。

## 6. 固定质量门

### 6.1 完整性、唯一性与合法性

以下计数必须全部为0：

- 成员主键重复；
- 资金流 `(trade_date, ts_code)` 重复；
- 空键、非法日期或非法代码；
- `.BJ`；
- 未登记股票池；
- 无唯一前一源日的 feature 日期；
- 同日或未来源日连接；
- 历史修订或源端饱和。

任一物理哈希、schema、行数、上游裁决或 proposal 身份不一致，必须在读取键前失败关闭。

### 6.2 覆盖分母

覆盖不能通过静默删除坏日美化：

- 总分母：日期域内、存在冻结前一源日的全部 M3 成员行；
- 分子：前一源日非隔离且 `ts_code` 精确存在的成员行；
- 隔离源日对应成员行单列报告，不与证券级缺失混在一起；
- 必须分别输出三池总体、11个完整半年段及逐 feature 日覆盖；
- tracked 报告只保存聚合计数、比率、日期和哈希，不保存证券清单。

硬门固定为：

1. 可用源日 feature 日期率每池不低于95%；
2. 非隔离精确键总体覆盖每池不低于99.5%；
3. 每个完整半年段精确键覆盖每池不低于99%；
4. 任一 feature 日覆盖每池不低于95%；
5. 连续隔离源日不超过10个；
6. 每个 feature 日匹配证券数最低为全市场60、中盘20、小盘20。

阈值在任何真实键读取前冻结。结果后不得放宽、删除年份、删池、造别名或把隔离日重新标 PASS。

## 7. 输出与裁决

主报告 schema 固定为 `m7-moneyflow-data-compatibility-report-v1`，至少包括：输入身份、数据集与粒度、
PIT 映射、完整性、唯一性、合法性、连接完整性、半年段、门结果和 authority。独立 auditor 使用
`m7-moneyflow-data-compatibility-audit-v1`，不得导入主 runner 的门裁决函数。

未来 runner 必须在一次调用内完成 first-pass 和 replay，物理/规范输出一致；随后独立 auditor 从同一
只读输入重算。输出 write-once，失败证据保留，不得用第二次 release 追成功。

裁决只有两种：

- 全部硬门 PASS：`GO_M7_0_DATA_COMPATIBILITY_ONLY`；
- 任一硬门 FAIL：`NO_GO_M7_0_DATA_COMPATIBILITY`。

禁止 partial-pool GO。GO 仍是数据层结论，`strategy_effective=NOT_EVALUATED`、正式因子库不变、生产
授权 `none`；NO-GO 也不是资金流策略失败。

## 8. 架构、资源与安全边界

本批继承 M5 的四维身份、proposal、内容寻址、隔离 Worker 和独立审计能力；不新增常驻服务、队列、
Web 写动作、M5-1 schema/API或第二套账本。未来实现应放在独立窄模块，复用现有 catalog 哈希验证和
M3成员合同，不把新职责堆入 P1、M3、M5 热点文件。

真实门只能在一次性 Docker 中运行：`network_mode:none`、非root、只读根、无宿主端口、无Docker
socket、无`.env`，只读挂载内容寻址输入束/协议/scope，窄写正式输出；最多2 CPU/4 GiB，避开
UTC+8 15:45—20:00 scheduler窗口。生产 scheduler、信号、模型、模拟仓、Web和自然账本不得改变。

## 9. 授权分段与停止线

1. 本节点只冻结 proposal export、协议、config和机器测试，提交并推送；真实数据读取0。
2. 下一节点可在协议推送后施工 metadata-only inventory、runner/auditor、合成fixture、Docker镜像和
   release scope；仍不得读取真实证券键。
3. 只有用户明确批准完整 release scope SHA，且 proposal 仍合法，才能唯一运行一次断网真实数据门。
4. 数据 GO 后才能另立 8 候选协议；公式、方向、窗口、选择、多重检验和未来效果授权均须再次冻结。

出现提案过期/取消/事件漂移、输入哈希或 schema 漂移、`.BJ`、修订、重复键、非法时钟、读到数值列、
触碰标签/收益/模型/回测/外网/生产，立即停止。不得把本次“继续下一步”解释为真实读取或后续研究的
无限授权。

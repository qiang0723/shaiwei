# M2-0R2 科创200数据恢复验收

> 执行日期：2026-08-04（Asia/Shanghai）
>
> 恢复 ID：`m2-star200-data-recovery-v2`
>
> 实现提交：`061e17baf98c3a44c800b3ac7b8d99d38ab597b8`
>
> 权威裁决：`NO_GO_M2_STAR200_DATA_GATE`

## 1. 结论

本次恢复解决了 Tushare 2026-07 二级月度快照缺失，但没有解决官方历史成员谱系缺失：

- `000699.SH` 的 2026-07 `index_weight` 即时双查均返回 200 行，canonical SHA-256一致；
- 2024-08至2026-07共24个月的二级快照已经齐全，Tushare源采集门由不完整变为PASS；
- 截至2026-08-04重新扫描的上交所公开归档，与旧恢复证据相比没有新增URL、删除URL或内容哈希变化；
- 仍未解析出任何科创200历史调入/调出成员对，官方谱系事件为0；
- 24个月中只有1个月与“首批200只且从未调整”的错误假设集合一致，其余23个月不一致，因此不能
  用月末集合反推历史PIT成员。

机器终态为：`tushare_source_collection_pass=true`、`official_adjustment_lineage_complete=false`、
`tushare_crosscheck_pass=false`、`pit_constructible=false`、
`strategy_results_inspected=false`、`production_authorization=none`。这不是策略REJECT；科创200因子、
IC、收益、模型、回测、信号和持仓仍未运行或查看。

## 2. 结果前冻结与执行身份

- 恢复协议/配置先行提交并推送：`48ffc4ac80b07e1c74ab9d7754a3632e221def13`；
- 恢复schema、薄编排和fixture先行提交并推送：
  `548eb64d498e5d539552d4bcdb03cf21f6e09693`；
- 生产scheduler镜像没有官方抓取所需`curl`，因此另加不进入生产release链的一次性研究运行时；
  最终执行提交为`061e17baf98c3a44c800b3ac7b8d99d38ab597b8`；
- effective protocol SHA-256：
  `ea2295c215510c8b4acdd6c373d799060d697255cb358bcc97ed9fd314843ae1`；
- 恢复协议文档 SHA-256：
  `d715266c8567a201379d2332a4f66dbcdf5eb98258f125fb85275016986da84b`；
- 工具快照 SHA-256：
  `c73f5b0b9d7cde3eb9854eb5af1f8db0cdc44f6b607404cd8a88b52714bd8211`。

运行容器非root、只读根、无端口、无Docker socket，只注入`TUSHARE_TOKEN`；飞书和DeepSeek凭据未
注入。写入面只限本项目`data/`、`ledger/`和最终manifest所在`config/`。生产scheduler未构建、未
promote、未重启，验收后仍为原`shaiwei:scheduler-current`且healthy。

## 3. 唯一 Tushare 刷新

冻结请求为：

```text
api=index_weight
index_code=000699.SH
start_date=20260701
end_date=20260731
fields=index_code,con_code,trade_date,weight
```

执行事实：

- 外部查询数恰好2，未重查其他26个分区；两响应 canonical SHA-256 均为
  `b402785b38c8b19c69e277a119c3d24577dde0644be2cdcc6a04e2ad34547307`；
- 新批次`3419fcd0ccf1`追加200行，文件 SHA-256
  `46e8a67d4444cc9c9c0deb3fcc3b7ad45ee0607e2948c6fd5171dc39daf8863b`；
- 快照日期唯一为`20260731`，200个唯一成员，`.BJ=0`；
- 原0行批次`33aa80a00744`及其文件永久保留，目标请求现在共有2个不可变批次；
- 其余26项旧文件逐项重哈希一致。24个月均恰好一个日期、200行、200个唯一成员；缺月、多快照、
  重复键、未知代码和`.BJ`均为0，权重和范围99.989%至100.008%。

collection report SHA-256：
`f9ace7ab789992de3bb0d555530086344a2e64ffef7f7ff8118967818243183e`；target probe SHA-256：
`3637054fc6317d935764d82ca5de0f99f66aca42b5f5c02e67e34cac6ed0c6d1`。

## 4. 官方全量重扫

使用全新的内容寻址目录从当前归档页扫描至越过2024-07-21首发边界：

- 归档页4页、候选公告12个、附件13个；
- 与旧`official-discovery-85daceb5fba7`相比，URL新增0、删除0、同URL内容哈希变化0；
- 首批200只、V1.0/V1.1规则材料仍可验证；事件解析错误0、成员状态机错误0；
- 但科创200调入/调出成员对仍为0，无法解释二级月度集合的历史变化；
- discovery report SHA-256：
  `93c80f5e7096fc4e2b6611473442c4d52365726700886a602807fa245765dbc3`。

因此公开官方归档路线本轮没有新增信息，继续盲扫同一来源的预期收益已经很低。

## 5. 裁决、幂等与验证

质量报告 SHA-256：
`141584501c5b70fabad58ef70269bbde25441fb52afff750079e21fd0e9f5c2e`；脱敏tracked manifest
SHA-256：`86210d161114af90ce6366e13779af8b3a34951098b7691b22f6d94f6a24bd31`；初始集Parquet
SHA-256：`1692bca7d3ea6ddd885888d94ff108c04d60873985e121bf0a045d11cd8d9449`。

同一完成入口随后在`network_mode=none`、无任何密钥、`data/config/ledger`全只读条件下复跑，返回
`REUSED_COMPLETED_COLLECTION`与`refresh_query_count=0`。collection、probe、discovery、quality、
manifest、初始集和ingest账本七项物理SHA-256全部不变，账本仍仅新增1行。

验证：

- 宿主全仓：572 PASS（1条既有第三方弃用warning）；
- 恢复与官方谱系专项：27 PASS；
- 一次性断网Docker专项：27 PASS（只读pytest cache warning）；
- Ruff、compileall、pip check、`git diff --check`：PASS；
- 本次新增证据不含凭据、绝对本地路径、原始成员行或官方原文；新增ledger行使用项目相对路径，
  tracked manifest只含URL、相对路径、哈希、行数和公开元数据。

## 6. 后续边界

M2公开数据恢复路线在此停止，不按天继续重复扫描同一归档。科创200若继续，只允许两种路径：

1. 获得带公告日/生效日/版本/修订语义的授权历史成分产品，并另立结果前数据恢复协议；
2. 把等待期研究资源转向已有合法PIT成员真身的科创50或三类`CUSTOM_RULE_BASED`科创池，新因子仍
   须独立结果前冻结和验证，不能冒充科创200结论。

不得用当前成分、ETF PCF、基金持仓、Tushare月末集合反推、第三方无版本列表或人工成员表补造
科创200历史。取得新的一手/授权数据身份前，M2不进入因子、qlib、模型、回测、信号或生产。

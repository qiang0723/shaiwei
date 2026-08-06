# M6-1 中证800模型归因结果盲工程门验收

日期：2026-08-06（UTC+8）

## 1. 裁决

`m6-csi800-model-attribution-engineering-v1` 的终态为 **`GO_ENGINEERING_ONLY`**。

| 状态 | 结论 |
|---|---|
| 工程合同、时钟、模型工厂与裁决器 | PASS |
| 五种互斥终态合成预演 | 5 / 5 PASS |
| 失败关闭矩阵 | 12 / 12 PASS |
| 正式报告双跑 | 同 SHA，第二遍复用 |
| 独立审计双跑 | PASS、同 SHA，第二遍复用 |
| 真实模型拟合 / 预测 / 标签或效果读取 / 回测 | 0 / 0 / 0 / 0 |
| 策略有效性 | `NOT_EVALUATED` |
| 生产授权 | `none` |

这只证明 M6-0 冻结的 LightGBM 控制、`Ridge(alpha=1.0)` 和日排名 50/50 融合可以在同一合同下
确定性运行、统计裁决和独立复核；没有回答哪一臂在中证800真实数据上更好，也不授权真实训练、
回测、前瞻、模拟仓或生产。

## 2. 结果前冻结和实现身份

- M6-0 协议提交：`262d941baa97c4aae4ddf57ed2950529d307dca3`；
- M6-1 工程协议提交：`64fe39d8c1ab183bd367f5e6866f8ea3735ae10f`，先于实现推送；
- 初始实现提交：`5290a174c23349a120b3acb9c4b774252733fe56`；
- 发布身份修复提交：`c6bf7d6dee3c427e48374aa6ebd5c9886602eaf8`，先于终版镜像和正式报告推送。

冻结身份为：

| 证据 | SHA-256 |
|---|---|
| M6-0 config | `6c170d991df1ef75f18208837301b545fe50518c028a65c814d425fc36d7a22a` |
| M6-0 协议 | `647682250aff54861dc4888340e88d4e82ac009ec53999e3eddea29fb5a52b0c` |
| M6-1 config | `af6801f72f145e3f0599c26fb03e1ad88998217f218b544bb24c6b31f97a5680` |
| M6-1 协议 | `89bd9da4cd92342fdb7304bb57bce1cc9b6acd7da92101c3d7e5b5964233d555` |

终版镜像为 `shaiwei:m6-model-attribution-engineering-v1`，内容 ID
`sha256:1a9ba6b7697780ec92cce007405b7c93e6399c99ec99963d61a586f850fc1ebd`。镜像内发布清单独立校验
输出代码快照 `a99ceb508a68d4cff3b2e21f63ccb729e25da53342b338bc4e8c54ed2ded9eec`，报告又绑定同一快照和
完整 Git 提交；独立 auditor 在相同边界内重新校验，`release_identity=true`。

## 3. 发现并关闭的发布身份问题

第一版正式候选运行的业务工程门和审计均通过，但额外发布复核发现：两个只读输入原先挂载到
`/workspace/config`，使发布清单把运行输入误判成镜像受控代码新增文件，发布身份验证失败。该候选不得
作为正式证据。

修复只做两件事：把 Qlib manifest 和交易日历移到代码树之外的 `/inputs`；正式 runner 和独立 auditor
都把嵌入式发布清单、Git 提交和代码快照加入机器证据。模型、窗口、合成 seed、统计、裁决、门槛和
生产边界未改变。

旧候选没有删除或覆盖，保存在 Git 忽略目录
`data/research/m6_csi800_model_attribution_v1/engineering/provisional_docker_unverified_release_54be350a`：

- report SHA：`54be350a3e30e90150e81284ae5545b0b7d3f6b94c81d88772995feb66f38da0`；
- audit SHA：`949a8f599af5c2e4b172a4f4ded693bfb01dafc1006966560f92f6b9cd4b001a`；
- 权威性：`formal=false`。

## 4. 冻结输入和结果盲边界

容器只读两个真实元数据文件：Qlib manifest 与交易日历。manifest SHA 为
`62cae2f46b57020db202bee1748f072e7859e209663046747f76aaa008f605a9`，绑定 54,464 个文件和内容树
`0532f6cd7c2c78f0936f92a986aef83a848175fe6f332274e06c7ed6e8c11778`；交易日历 2,557 行，SHA 为
`80ddefd8e3cce5137bb99f6b53dbe090de1b1bd234db1a19f31ef3ddb2bd8bdb`。

没有挂载或读取 Qlib features、prices、instruments、真实标签、旧效果、账本、`.env`、模型、信号或
持仓。报告机器字段为：`semantic_market_rows_read=false`、`real_model_fit_count=0`、
`real_prediction_count=0`、`real_label_or_effect_read=false`、`real_backtest_count=0`、
`external_call_count=0`。

## 5. 工程通路与失败关闭

新增 `shaiwei.research.model_attribution` 包按合同、时钟、模型适配、评分、统计裁决、合成预演和独立
审计拆分，8 个模块均不超过 400 行。Qlib 的 `LGBModel` 与 `LinearModel(estimator=ridge,
alpha=1.0)` 被真实实例化，但 `fit_called=false`；未来真实运行通过可注入窄适配器接入，不把 I/O
混入领域裁决。

合成 fixture 使用固定 seed `20260806`，W1—W6 每窗 210 个评分日、每天 40 个纯合成名称，共
50,400 个成员日；不含真实证券代码。三臂成员日键、每日 50/50 百分位排名融合、RankIC、复利、回撤、
换手、成本差、单边 NW(10)、恰好两个假设的 Holm 校正均可复算。

五个终态全部命中且互斥：`MODEL_STRUCTURE_SUPPORTED`、
`PORTFOLIO_CONVERSION_BOTTLENECK_INDICATED`、`FEATURE_INFORMATION_BOTTLENECK_INDICATED`、
`MIXED_NOT_CONCLUSIVE`、`BLOCKED`。十二类失败关闭覆盖上游哈希漂移、第三/替换臂、模型或组合参数
变化、标签成熟日错误、成员日键错位、非有限值、覆盖不足、Holm 家族错误、裁决歧义、输出越界、
write-once 冲突及审计重建/哈希不一致；独立篡改测试证明 auditor 会拒绝错误裁决。

## 6. 正式产物、幂等与独立审计

| 产物 | 字节数 | SHA-256 |
|---|---:|---|
| `engineering/report.json` | 6,999 | `43c0716bcc4b1f595c242897189b7bf9a4cfd879d34a4dfbce6f9ee8a8be1cc2` |
| `engineering/audit.json` | 721 | `7fb095a339b066112eccca86fa44f17ac930d0573a2bf7100cdb45f9f5163a33` |

正式报告连续两遍 SHA 相同，第一遍 `reused=false`、第二遍 `reused=true`；独立审计同样连续两遍 SHA
相同并在第二遍复用。auditor 不导入主 `inference`，独立重建六窗口成熟边界、Holm 两假设校正、五种
终态、代码束和发布身份，终态 `independent_audit=PASS`。

Git 只提交脱敏 manifest、代码、测试、协议、状态和本文；正式/临时报告、原始或派生业务数据仍在
项目内 Git 忽略区。tracked manifest 不含绝对路径、URL、token、cookie、代理、证券清单、行情值、
模型效果或持仓。

## 7. Docker、生产隔离与验证

M6 容器运行时 `network_mode=none`、非 root、只读根、`cap_drop=ALL`、no-new-privileges，无端口、
无 `.env`、无 Docker socket、无整仓/业务账本挂载；两个 `/inputs` 挂载只读，唯一可写路径为 M6
engineering 输出目录。所有一次性容器已删除。

施工前后 scheduler 均为容器 `183b8c6c5edd`、镜像内容
`sha256:722f63de15932cb2698e82db7c0140f02921f27f126e1c0235ca62e0a1213b76`、创建时间
`2026-08-03 17:39:34 +0800 CST`、release revision
`210af4dab33c85b38c05b28f56c176b7970c41db`，状态始终 `healthy`，未重建或重启。

终版交付门：

- 全仓 `838 passed`，另有 1 条既有 Starlette 弃用 warning；
- M6 专项 `23 passed`；架构门 `6 passed`；
- Ruff、`pip check`、Compose config、`git diff --check`、tracked secret 模式扫描均 PASS；
- compileall PASS，保留一条既有测试正则转义 `SyntaxWarning`，不涉及 M6 代码或运行语义。

## 8. 停止线

M6-1 到此完成并停止。下一合法节点是另立 **M6-2 真实 release**：必须绑定本 manifest、冻结输入、
已推送实现和一次性运行 scope，并由用户明确授权后，才可读取真实特征/标签、拟合两种模型、生成三臂
预测和运行固定回测。M6-0/M6-1 的既有授权不自动迁移；未获授权前策略保持 `NOT_EVALUATED`，中证800
生产基线和每日自然前瞻继续原样运行。

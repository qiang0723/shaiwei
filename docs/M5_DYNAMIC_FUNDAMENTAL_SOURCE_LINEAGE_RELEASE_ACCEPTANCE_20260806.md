# M5-2B-R2 财报版本谱系断网 release 验收

- 验收时间：2026-08-06（UTC+8）
- 当前状态：`SOURCE_LINEAGE_RELEASE_READY_NOT_APPROVED`
- 权威边界：纯合成工程 GO；真实谱系结果 `NOT_EXECUTED`
- 策略结论：`NOT_EVALUATED`
- 生产授权：`none`

## 1. 结论

M5-2B-R2 已完成版本 commitment、历史链构造、脱敏投影、write-once 封存、独立复算 auditor、registry
v1 新 case 状态投影、批准后输入束物化器和短命断网 Docker release。实现提交
`f2e5483f55278010cde4ea5ff5f8e3b56c09ae37` 已先推送至 `origin/main`，随后才生成精确 release scope。

本结论只证明实现和 release 可被审计，不代表 23 个真实冲突组已恢复。当前元数据清单中的
`authoritative_evidence=[]`，真实运行若获批只能按规则给出可复算的 GO/NO-GO；不得以本地抓取先后、
普通/VIP优先或 latest wins 代替 E2/E3 权威历史证据。

## 2. 实现边界

- 三个时钟严格分离：财报 `f_ann_date`、权威修订生效时点、本地不可变批次观察时点。
- 相同五字段身份和 `update_flag` 不给不同值排序；仅 E2/E3 可构成历史版本链。
- 六种互斥处置、缺时点、同刻歧义、缺中间版本、未来版本和未解释 A→B→A 回滚均 fail closed。
- 主执行器与 auditor 分别实现数值规范化、commitment、区间链和 verdict；auditor 不导入主
  commitment、lineage builder 或 report projection。
- 对外只输出表级计数、处置、证据等级和链 commitment；证券、报告日期、原值、规范化值、请求参数、
  绝对路径均禁止输出。
- 输入束只有在精确 approval envelope 校验通过后才能物化；已有 bundle 必须字节一致，半成品、路径
  漂移和哈希漂移全部失败关闭。
- 新增生产模块最大 340 行，未增长既有热点；未修改 R1 `source_conflicts.py` 的六类语义。

## 3. 合成工程门

断网 fixture 覆盖完全重复、本地观察、相同 update flag 不同值、唯一权威链、同刻版本、缺中间版本、
未来版本、未解释回滚、write-once 双跑、独立 audit、禁止字段注入和临时 registry 完整性。最终两遍
Docker 输出逐字段相同：

- fixture canonical SHA-256：
  `1b4b0008834e187be752ec99257f34dde49c66d5b3fae6c27c107648ba1e9a62`
- `case_count=8`
- `deterministic_double_run=true`
- `independent_audit_pass=true`
- `forbidden_field_tamper_rejected=true`
- `semantic_rows_read=false`
- `external_call_count=0`

首次容器冒烟在进入任何数据逻辑前因 fixture 将镜像工作目录误写为 `/app` 而退出；修正为镜像实际
工作目录后重建，最终两遍均 PASS。该失败未挂载项目数据、未读取真实财务内容、未写正式 registry。

## 4. 元数据清单

只读取 ingest ledger、Parquet metadata、文件大小和内容哈希，不读取财务列值：

- 逻辑 SHA-256：`b9b7c7fb4b4f87ee931cbbc202134d7faf8bc4c891fe252267f3e777b6bfe5d7`
- 物理 SHA-256：`0576de1f5fa4c6be123de2a97cbf406801292fb9072813d46b052c8d45ab6780`
- 文件大小：27,755,333 bytes
- R1 锚定批次：16,841
- 截止清单时点的历史批次：16,841
- 权威版本证据：0
- `semantic_rows_read=false`

锚定批次与历史批次当前相同，说明本地没有新增可证明历史有效时点的版本材料；这不是实际冲突诊断，
也不授权联网补证。

## 5. 内容寻址 release

- release scope SHA-256：
  `b01058b55ff3dd6c06cf0722541214ecbb793de92a3115410c073daab26cf155`
- release 文件物理 SHA-256：
  `a60df7e220277249fb7eae2e06304f9d5adddb85597da2422eb6868ffe00ee46`
- code bundle SHA-256：
  `41183685b42058bd67273f974492c70a05cc2ccaac1288b89a38e2c0d666925f`
- 独立 lineage audit 代码 SHA-256：
  `1a8ec7fe6b1b6abd832f1497212a3aff85a1ff8f4ec052128dd162348dcb6358`
- 镜像：
  `sha256:fe9101f11a54d0b2111c0000ffff5a21d7d72fd86f4300aa30ae7b934119b606`
- 平台：`linux/arm64`
- 提案到期：`2026-08-12T10:48:16+00:00`

容器固定 `network_mode=none`、非 root、只读根、drop ALL capabilities、no-new-privileges、128 pids；
只允许 `/lineage-input:ro`、`/lineage-output:rw`、`/lineage-audit:rw`、`/registry:rw` 四个窄挂载，
不挂项目根、`.env`、Docker socket、标签、效果或模型目录。

scope 中只有 `lineage_release_ready=true`；approval、execution、正式 registry 写、真实读取、冲突诊断、
外部调用、凭据、PIT、候选、标签、效果、训练和回测授权均为 false，生产为 `none`。

## 6. 验证

- 全仓：804 PASS；仅 1 条既有 Starlette 第三方弃用 warning。
- 架构宪法：6 PASS。
- 谱系/发布/registry/Docker 专项：24 PASS。
- Ruff、compileall、pip check、Compose config、diff check：PASS。
- 最终镜像两遍断网 fixture：PASS，canonical 输出相同。
- 生产 scheduler：原容器 `183b8c6c5edd`、原镜像
  `sha256:722f63de15932cb2698e82db7c0140f02921f27f126e1c0235ca62e0a1213b76`、创建时间
  `2026-08-03 17:39:34 +0800`，仍 healthy，未重启。
- 七个自然跑批 ledger 变更未进入实现提交。

## 7. 停止线与下一授权

当前没有 approval envelope、正式 lineage registry、内容输入束、真实 runner/auditor 产物或结果。
必须由用户明确批准完整 scope
`b01058b55ff3dd6c06cf0722541214ecbb793de92a3115410c073daab26cf155`，才可物化输入束并运行恰好一次
断网 `LINEAGE_FEASIBILITY`。该批准不授权外网、权威材料采集、PIT/候选、M5-2C、效果、模型、回测或
生产；scope 任一字段漂移都使批准失效。

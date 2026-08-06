# M5-2B-R1 release v4 真实数据门验收

- 验收日期：2026-08-06（UTC+8）
- release scope：`8858912f14577a8911e47f0ec338cde82208fe818b4c7a921578e42aeeed6f65`
- case：`a2539149d588a0c19f9cb73331f19a66df63e301df03f56fbb2c8e5c74672068`
- run：`2df49bc1a6efcd82339d99a4446b1dc4edda6688a7861471d04987808c52a92a`
- 权威数据门裁决：`NO_GO_M5_2_DATA_PREEXECUTION`
- registry 终态：`BLOCKED_DATA`
- 策略有效性：`NOT_EVALUATED`
- 生产授权：`none`

## 1. 结论

用户批准的唯一一次 release v4 断网真实 DATA_GATE 已完成。冻结财报输入存在 23 个来源身份冲突组：
资产负债表 8 个，现金流量表 15 个，利润表 0 个。恢复协议按结果前冻结规则不选源、不覆盖、不修数，
在 PIT、候选公式和 feature panel 之前全局失败关闭；8 个候选 × 3 个股票池共 24 个单元全部记为
`FAIL / GLOBAL_SOURCE_IDENTITY_CONFLICT / NOT_COMPUTED_GLOBAL_FAILURE`。

独立 auditor 未复用 runner 的分类和投影实现，重读同一输入后逐项复现冲突类别、字段计数、全局
commitment、24 单元矩阵与裁决，终态 `PASS`。因此本轮是有审计证据的 DATA NO-GO，不是运行异常，
也不是因子或策略 REJECT；M5-2C、标签、效果、模型、回测、前瞻和生产均未获授权、未运行。

## 2. 关键发现

| 严重度 | 发现 | 证据 | 影响 |
| --- | --- | --- | --- |
| P0 | 资产负债表存在 8 个冲突身份组：普通源内部 7 个、VIP 源内部 1 个 | `accounts_receiv` 冲突字段计数 4，`inventories` 计数 8 | 禁止为动态基本面候选选择单一版本 |
| P0 | 现金流量表存在 15 个 VIP 源内部冲突身份组 | `free_cashflow` 冲突字段计数 15 | 自由现金流候选不能合法计算 |
| P1 | 利润表无冲突身份组；三表普通/VIP 交叉冲突均为 0 | 利润表一致交叉重叠 64,281，VIP 完全重复 14 | 仅说明该表身份可无损折叠，不足以解除全局失败 |
| P1 | 全局完整性门失败 | 23 个冲突身份组；global conflict set SHA `007724ca...fc9c4` | 24 单元全部失败，eligible 候选为 0 |
| P3 | 读取阶段出现 pandas concat FutureWarning | runner/auditor 均出现相同提示，未改变退出码、产物或审计结论 | 后续依赖升级前应单独消除兼容性风险，不在本轮夹带修改 |

冲突报告只保留表级分类计数、字段计数和 canonical commitment；没有证券代码、公告日、报告期、
原始值、候选值或绝对路径，`row_level_export=false`。

## 3. 范围与方法

### 3.1 授权与执行边界

- 用户只授权本 scope 一次断网真实 DATA_GATE。
- 镜像为 `sha256:acb7c6c2828dd3b8a40f599f934f3059904ec27835c19e3847bbb416897d1ea7`，
  平台 `linux/arm64`，code bundle 为
  `afdc4f2b402fedba8a91969d5a03c86a50f124c74fe2ff2c1d82803fc182093f`。
- runner、auditor 与 registrar 均使用 `network_mode:none`、非 root 用户 `65532:65532`、只读根、
  `cap_drop:ALL`、`no-new-privileges` 和冻结资源上限。
- 输入只读挂载；output、audit 与 registry 分别写入 release 绑定的项目内隔离目录。
- 未读取标签或效果，未训练模型、未回测、未调用 provider；调用数 0、费用 `$0.00`。

### 3.2 输入与批准证据

- metadata-only input manifest 绑定 7 类 API、16,843 个不可变批次和 3 份成员证据；逻辑 SHA
  `f4aeb411af00ea2f5ad096983859f50a587ed9ad6cee1f384268e14d1ef9399b`。
- 批准信封绑定 registry event 4，event SHA
  `acb799c99f5478d96135384add9ed61919895a8a9e4bbef036474f2a699318df`；信封逻辑/物理 SHA 为
  `76d92df9...a3b4` / `83dd4e59...c56a`。
- 只读 input bundle 共 16,856 个文件，物化阶段 `semantic_rows_read=false`；bundle manifest 物理
  SHA `03886c6d...25fd`。
- 真正语义读取只发生在用户批准后的唯一 runner 和随后独立 auditor 中。

### 3.3 运行与审计步骤

1. 复核提案仍为 `REVIEW_REQUIRED`、event seq 2、head SHA `2d6ff1aa...70f5f`，且未到期。
2. 在新 release-bound registry 中原样重放旧 case 的 10 个命令。旧事件、case 投影和末端
   `STOPPED` SHA `e0ca4594...b9b3bd` 与原库逐字段一致；旧库未改写。
3. 新 case 依次登记 `IMPORT → PROTOCOL_FROZEN → DATA_GATE_RELEASE_READY → DATA_GATE_APPROVED →
   DATA_GATE_STARTED`。
4. runner 只运行一次，以预期 exit 3 封存 DATA NO-GO；输出恰为冲突报告、data gate report 和
   run manifest 三件，无 feature panel。
5. 独立 auditor 只运行一次并返回 `PASS`，随后才登记 `DATA_GATE_RECORDED`。
6. 同一登记命令重放返回同一 event 6，未增加事件；outbox 首次发布 16 行，第二次发布 0 行。

首次尝试重放旧命令时，Compose 在配置解析阶段把未加绝对前缀的项目内路径误判为命名卷并拒绝启动；
当时没有容器、数据库、事件或语义读取。随后只把同一 release-bound 宿主目录改为绝对路径传给
Compose，挂载内容与冻结 scope 未变。

## 4. 结果与证据身份

### 4.1 数据门投影

- `candidate_count=8`
- `universe_count=3`
- `evaluation_unit_count=24`
- 24/24 单元 `FAIL`
- `eligible_candidate_ids=[]`
- 8/8 候选进入 rejected 投影
- `coverage_status=NOT_COMPUTED_GLOBAL_FAILURE`
- `effect_test_count=0`
- `strategy_effective=NOT_EVALUATED`

### 4.2 不可变产物

| 产物 | SHA-256 |
| --- | --- |
| `run_manifest.json` | `70cc008b802bd59eaa833a56916623047fa13c92ecaf783cebf8b74fd56edc57` |
| `data_gate_report.json` | `1c6220884f0cb7394a49f40c623b5e7e4a4d6c02b39259a61dc9634864190db3` |
| `source_conflict_report.json` | `dbd89549a83b32a68dee54be59d3260d10362730c9ade8e24a89f584613c6428` |
| `audit_report.json` | `647ac34e2d0ac6ce621c69a02da1ddbb5b4934180d8b0ccce4bcbb5f103f5677` |
| `gate_registry.sqlite3` | `1e5c0096b0ab1370956770c5c95d27440cc93bc961417640b7d503463b5f6bc8` |
| `gate_events.csv` | `77f85f1462af9970500435926c79405b8cd8cb900545f3ca098787358901012a` |

审计还分别核对冲突报告 canonical SHA `cc5bd7a8...54b48` 与物理 SHA `dbd89549...c6428`，防止
序列化层与语义层混淆。

### 4.3 registry 与幂等

- 全库完整性：`PASS`；case 2、event 16、receipt 16、outbox 16，未发布 outbox 0。
- 旧 case 保持 event 10 `STOPPED`，末端 SHA `e0ca4594...b9b3bd`。
- 新 case 保持 event 6 `DATA_GATE_RECORDED → BLOCKED_DATA`，末端 SHA
  `7c2615a0f9d271b8b898bc8fa2a332edabfac92d48c58f31918c49bffa80917e`。
- 新 ledger 前 10 行与旧 ledger 逐字段一致；旧历史没有被重写。

## 5. 隔离与未发生事项

- 没有外网、DeepSeek、Tushare 或任何 provider 调用。
- 没有标签/效果读取，没有候选值导出，没有模型、回测、信号、模拟仓或生产写入。
- 没有修改 `src`、配置门槛、模型、股票池、生产数据、scheduler 或 Web。
- M5 短命容器全部退出。生产 scheduler 前后均为容器
  `183b8c6c5eddac951d9d9b3cfa58c0d38e351d5b94ee1b1d52b9b8059c23dd3b`、镜像
  `sha256:722f63de15932cb2698e82db7c0140f02921f27f126e1c0235ca62e0a1213b76`、创建时间
  `2026-08-03T09:39:34.800579793Z`，状态 `running/healthy`。
- 日常 scheduler 自然追加的账本保留在工作树中，本次不暂存、不提交。

## 6. 限制与下一合法动作

本轮只能回答“冻结输入是否足以合法构造动态基本面候选”，答案是否定的。它不能回答八个候选是否有
预测能力，也不能证明科创50、中盘或小盘策略无效。

当前禁止进入 M5-2C、标签/效果、模型和回测。若继续，必须另立 M5-2B-R2 结果前数据恢复协议，先处理
普通/VIP 源内部版本冲突的公告时间、修订状态和保留规则，并以新 case、新实现、新 release scope 和
再次精确授权运行；不得根据候选效果选源、静默覆盖或回写本轮 23 个冲突组。本次结果与全部失败证据
永久保留。

## 7. 交付验证

- registry 全库断网完整性：`PASS`，case count 2。
- 全仓 `make test`：761 PASS；仅 1 条既有 Starlette/httpx 弃用提示。
- 架构宪法：6 PASS。
- Ruff、`git diff --check`：PASS；diff-check 只提示自然账本既有 CRLF 归一化警告，本次未暂存该账本。
- 本次拟提交三份文档的凭据模式扫描：PASS。

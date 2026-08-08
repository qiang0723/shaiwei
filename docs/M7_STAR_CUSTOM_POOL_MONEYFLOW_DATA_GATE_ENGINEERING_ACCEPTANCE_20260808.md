# M7 三自建科创池资金流键级数据门工程验收（2026-08-08）

## 1. 裁决

`GO_ENGINEERING_PREREQUISITES_ONLY`。

本裁决只说明 M7-0 的元数据清单、键级门计算、独立审计、不可变输出和隔离容器已经具备生成精确
release scope 的工程条件。它不是数据兼容性 GO，不是候选协议，不是资金流因子有效，也不授权读取真实
证券键、资金流数值、标签、收益、模型、回测、前瞻或生产。

精确 release scope 必须在本实现提交并推送后，以该 Git 提交重建镜像并单独生成；本次施工期镜像只作
provisional 合成验证，不得作为真实运行身份。

## 2. 冻结继承与架构边界

- 继承 protocol scope canonical SHA
  `3b137d0b84e557c4fa38ea5072fe22241802f7a714f5890fc365705f2b71d59b`，不改写已冻结协议。
- 新能力位于 `src/shaiwei/research_gates/m7_moneyflow/`，共 15 个窄模块、2,359 行；最大单模块 300
  行，低于 400 行软上限。
- 不复用 M5 动态基本面专用状态机和八候选语义；只复用内容寻址、精确批准、一次性 Docker 与独立审计
  模式。未新增常驻服务、队列、数据库、公共 registry schema 或第二套账本。
- `compute.py` 是 Pandas 权威实现；`audit_compute.py` 是 DuckDB 独立复算，不导入主计算函数。
- runner 在一次调用内双算；runner 与 auditor 均只接受冻结 manifest、release 和 approval 的精确身份。
- 输出为 canonical JSON、write-once、aggregate-only；报告不包含逐证券缺失清单。

## 3. 元数据清单证据

元数据入口只读取 ingest ledger 索引、JSON 质量证据、文件大小/SHA-256 和 Parquet footer，没有读取
Parquet 语义行。生成的本地忽略区 manifest：

- canonical SHA-256：
  `8a1333888c3abd20d1a4c003018ec81dc22ccf8629372266e6833a8cc750e27a`；
- physical SHA-256：
  `6522e5802b3d51f16c7ed48aac5afb4f10368716dc38201121a8417a170673ee`；
- P1 完整目录：2,563 个 latest canonical batch、10,614,438 行，目录 SHA 与冻结审计
  `04ffd1f5...50890`一致；
- M7 选择范围：2020-12-31—2026-06-29 共 1,328 个源交易日，对应 2021-01-04—2026-06-30
  共 1,328 个 feature 交易日；
- M3 成员真身：779,271 行，内容 SHA `1983169e...75101`；
- M7 范围内隔离源日 3 个，继续执行整日隔离、不填充；完整 P1 的 46 个隔离日事实不变；
- `semantic_rows_read=false`，证券键读取 0，资金流数值列读取 0。

## 4. 计算语义与 fail-closed 门

真实获批后，reader 只能从 raw moneyflow 投影 `ts_code, trade_date`，成员只读冻结的五列；以源日 D 映射
下一官方 SSE feature 日。覆盖率分母保留全部成员行，隔离源日的匹配分子为 0；逐日最低与最少名称门
只在非隔离 eligible 日计算，隔离风险由 eligible rate 与最长连续隔离门另行约束。

合成 fixture 覆盖 11 个完整半年段和三池 60/20/20 最少名称边界：

- clean：`GO_M7_0_DATA_COMPATIBILITY_ONLY`，core SHA
  `fba879c245988e427abc9d4d4b71a2a541c29edf2cceb84fd2811b0a689a9209`；
- duplicate source key：`NO_GO_M7_0_DATA_COMPATIBILITY`，core SHA
  `4578ae15911dfedb608f5d66bb341764e006578243e99c3e5aef9dc29a113094`；
- sparse source coverage：`NO_GO_M7_0_DATA_COMPATIBILITY`，core SHA
  `4c3a04d4a33fdeb7f85b4bf53a1f7e1f32e111eb024cdcf1da8d58dd3afee120`；
- 主实现内部 replay 一致，独立 DuckDB audit 逐字段及规范 SHA 一致；partial-pool GO 不存在。

## 5. 容器与发布停止线

- Dockerfile 只复制 M7 包、冻结控制文件和已锁依赖，不复制整个项目；非 root UID/GID 65532。
- Compose 固定 `network_mode:none`、只读根、`cap_drop:ALL`、no-new-privileges、pids 128、无宿主端口；
  runner 2 CPU/4 GiB，auditor 1 CPU/2 GiB。
- 只允许内容寻址输入束 `/inputs:ro`、运行输出和独立审计输出；禁止项目根、`.env`、`.git`、Docker
  socket、模型、标签、效果或生产目录挂载。
- 输入束只能在 exact approval 通过后硬链接物化；物化前再次核验每份文件大小、footer 与 SHA。
- release envelope 只可声明 `release_ready=true`；执行、真实键读取、网络、候选、效果、模型、回测、
  前瞻、scheduler/Web 变更均保持 false/none。approval 必须绑定 action、完整 scope SHA、proposal 状态、
  event seq、head SHA 和有效期；独立 host-side approval builder 必须先对 live proposal SQLite 做完整
  证据图复算，并证明当前状态/序号/head 未漂移，不能由手填字段冒充。

## 6. 验证

- M7 专项：12 PASS；
- 全仓：959 PASS，只有既有 StarletteDeprecationWarning；
- 架构宪法/整理/Web 模块门：13 PASS；
- Ruff、compileall、Compose config、`git diff --check`：PASS；
- 本地断网非 root 镜像合成 fixture：PASS；未挂载真实数据；
- scheduler 保持原容器 `183b8c6c5edd`、原镜像内容 ID `722f63de...13b76`、healthy，未重启；
- 七个自然账本的日常追加保持未暂存，本节点没有写入或改写自然账本。

## 7. 下一合法动作

1. 仅提交并推送本工程实现、测试、文档与状态，不提交自然账本或忽略区 manifest。
2. 从已推送提交重建一次性镜像，记录不可变 image ID/platform。
3. 以已推送 Git、代码 bundle、依赖、Docker/Compose、auditor、镜像和 metadata-only manifest 生成并
   推送精确 `m7-moneyflow-data-gate-release-scope-v1`。
4. 到此停止。只有用户逐字绑定完整 scope SHA 并批准动作
   `M7_STAR_CUSTOM_POOL_MONEYFLOW_DATA_GATE_ONCE`，且 proposal 未过期/漂移，才可物化输入束并唯一运行
   一次断网真实键级门；同 scope 不得重跑。

# A1-4B 组件构建身份注册与 release 门验收

## 裁决

裁决为 `GO_ENGINEERING_ONLY`。

A1-4B 已建立中央构建资产注册表和通用组件 release 身份门。仓库内 91 个被 Git 跟踪的 Dockerfile、
`compose*.yaml` 与专属 ignore 已全部且仅登记一次；生产全局、组件 release、纯 fixture 和归档候选四类
边界明确。身份门能够对活跃组件机械核对构建文件、源码 bundle 身份、Git 提交、镜像 ID 与三项镜像
标签，并在任何漂移时失败关闭。

本裁决不等于真实组件已发布。当前没有生成真实 Web attestation、没有检查新镜像、没有重建或重启
Web，也没有改变 scheduler。验证成功仍固定返回 `execution_authorized=false`、
`production_authorization=none`。

机器真身：`docs/BUILD_IDENTITY_COMPONENT_GATE_ACCEPTANCE_20260821.artifact.json`。

## 注册结果

| 类别 | 组件数 | 构建资产数 | 当前语义 |
| --- | ---: | ---: | --- |
| `GLOBAL` | 1 | 49 | 继续由生产全局代码快照约束 |
| `COMPONENT_RELEASE` | 7 | 39 | 活跃组件可另立新 release；关闭组件不可复用旧 scope |
| `FIXTURE_ONLY` | 1 | 1 | 只允许合成工程 fixture |
| `ARCHIVE_CANDIDATE` | 1 | 2 | 只登记复核候选，不删除、不发布 |
| 合计 | 10 | 91 | 与 Git 跟踪集合精确相等 |

注册表同时锁定：

- `GLOBAL` 49 项与 `CONTROLLED_FILES` 中被跟踪构建资产精确相等；
- 基础 Dockerfile 实际复制的现存根级文件仍与 `CONTROLLED_FILES` 反向闭合；
- 活跃本地 Web 独立包含 `Dockerfile.control`、`Dockerfile.web`、`compose.web.yaml`；
- M7 网络恢复专属 ignore 与其 Dockerfile/compose 位于同一组件；
- 消费者路径全部存在且已由 Git 跟踪；路径穿越、符号链接、重复/多归属、未知字段和不相容状态全部
  失败关闭。

注册表文件 SHA-256 为 `006e4f46...94af`，规范化注册身份为 `39462db2...cda9`。注册表本身进入
`config/` 受控树，因此本次开发代码快照从 A1-4A 的 1,209 项变为 1,214 项、SHA-256 为
`b00264fa...65c`；这是新合同和实现的预期变化，不是扩大 `CONTROLLED_FILES` 集合，也没有提升到
运行 scheduler。

## release 门

`shaiwei-component-release-attestation-v1` 采用严格字段合同，绑定：

- 注册表 ID、Schema 与规范化内容哈希；
- 组件全部且仅有的构建资产路径、文件 SHA-256 和路径+内容组件快照；
- 源码 bundle SHA-256 与正文件数；
- 相等的 40 位 Git commit / `origin/main`；
- 不可变镜像 reference、内容寻址 image ID；
- Git revision、组件构建快照、源码 bundle 三项身份标签；
- 固定 `production_authorization: none`。

纯校验器不访问 Docker daemon、Git 远端、网络、`.env` 或业务数据。真实发布适配器未来负责收集实际
镜像与仓库事实，再调用这一个权威校验器；不能在各组件复制另一套身份公式。attestation 自身也以
canonical SHA-256 内容寻址，因此任一字段改变后复用旧身份会被拒绝。

合成活跃 Web attestation 正向通过；21 个对抗场景覆盖缺失/额外/篡改资产、路径/Schema 漂移、Git
未同步、源码或标签漂移、非内容寻址镜像、越权生产状态，以及全局/关闭/fixture/归档组件冒充活跃
release。成功结果仍没有执行权限。

## 代码结构与验证

新能力按职责拆为：

- `build_identity/registry.py`：244 行，只负责注册 Schema、所有权和路径/状态校验；
- `build_identity/release.py`：229 行，只负责内容寻址和 attestation 校验；
- `build_identity/__init__.py`：窄公共出口；
- 单一专项测试文件：25 项。

没有把能力堆入 `provenance.py`、scheduler、Web 或研究 runner，也没有新增 Docker/网络依赖。验证结果：

- A1-4B 专项：25 PASS；
- 架构门：13 PASS；
- 全仓：1,719 PASS、17 条既有第三方/未来弃用 warning；
- Ruff、compileall、pip check、`git diff --check`：PASS。

## 运行隔离

只读复核确认：

- scheduler 仍为容器 `183b8c6c5edd...`、镜像
  `sha256:722f63de...13b76`、快照标签 `4e5244b6...2708`，状态 `healthy`；
- research-control 仍使用 `sha256:95c00fb5...2e2`；Web query/UI 仍使用
  `sha256:30ee550b...b421`，三项均 `healthy`；
- 没有构建、重启、提升、删除镜像/容器，没有读取环境变量或凭据。

## 后续边界

下一次需要重建 Web 时，应另立 A1-4C（或等价的独立 Web release 节点）：先由真实适配器生成源码
bundle manifest、构建新镜像并读取实际标签/image ID，再用本门核验，通过后才允许本机只读部署。
本次不能被解释为已经补齐现有旧 Web 镜像的源码谱系。

runner 的 canonical ledger 原子写入和 M6-5C 退市处置仍是两个独立节点；不得与组件发布施工混做。

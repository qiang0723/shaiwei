# A1-4B 组件构建身份注册与 release 门协议

- 协议 ID：`a1-4b-component-build-identity-gate-v1`
- 状态：`FROZEN_BEFORE_IMPLEMENTATION`
- 冻结日期：2026-08-21（UTC+8）
- 上游审计：`a1-4a-build-identity-coverage-audit-20260821`
- 上游机器证据 SHA-256：`695ecec3efc8bd31bf621f74519da4385efc65ee8daa58d03de69192f00ec102`

## 1. 结果目标与裁决边界

本节点只建设组件构建资产的中央注册表和纯身份 release 门。目标是让仓库内每个被 Git 跟踪的
Dockerfile、`compose*.yaml` 和 Dockerfile 专属 ignore 恰好归属一个身份域，并使未来组件镜像在
执行或提升前能够机械证明“构建定义、源码 bundle、Git 提交、镜像 ID 与镜像标签”一致。

本节点不重建、重启、提升或删除任何镜像/容器，不修改 scheduler 发布身份，不授权 Web 或研究
组件运行，不读取运行效果，也不改变研究裁决。工程门通过只代表身份合同可用，
`production_authorization` 固定为 `none`。

以下事项明确不在本节点内：

- 不把 A1-4A 识别的 42 个组件资产机械加入 `provenance.CONTROLLED_FILES`；
- 不修改生产/研究 runner、尝试计数或 canonical ledger 写入路径；
- 不设计或实现退市处置规则，不恢复 M6-5B/M6-5C；
- 不修改模型、因子、股票池、回测、信号、模拟仓、Web 页面或生产数据；
- 不读取 `.env`、secret、行情、持仓、收益或其他业务数据。

## 2. 权威事实与冻结输入

A1-4A 已确认：仓库共有 91 个被跟踪构建资产，其中全局生产快照内 49 个、组件级 42 个；基础
Dockerfile 显式复制的 57 个现存根级 `CONTROLLED_FILES` 与受控根文件精确相等。生产全局身份当前
闭合，故本节点不得以“补齐覆盖”为由扩大它。

组件注册的权威输入只包括：Git 跟踪的构建资产集合、`CONTROLLED_FILES`、各构建资产当前内容、
显式消费者路径和本协议。历史 release scope、旧镜像或旧结果只作为冻结证据，不因新注册表而回写、
改判或伪装成已经具备新合同。

## 3. 架构决策记录

### 3.1 备选方案

1. **全部并入全局快照。** 实现简单，但会把 Web 和已关闭研究支线耦合到 scheduler 身份，任何无关
   组件变动都触发生产快照漂移；拒绝。
2. **各组件继续自建 manifest。** 保持局部自由，但无法证明 91 个资产恰好一次归属，历史上已经出现
   多种不一致实现；拒绝。
3. **中央资产注册表 + 通用纯身份门。** 全局快照保持原边界；组件按统一合同生成和验证 release
   attestation；选择本方案。

### 3.2 依赖与职责

中央注册表属于配置/公共合同层；注册加载与 release 验证属于 release 应用能力。核心校验不得访问
Docker daemon、网络、`.env`、生产配置或业务数据，不得依赖 Web、研究 runner 或 scheduler 编排。
Docker/CI/人工发布入口未来只负责收集实际镜像字段并调用同一纯校验器，不能复制身份公式。

### 3.3 代价与回滚

注册表本身位于受控 `config/` 树，因此首次合入会改变开发代码快照；本节点不据此发布 scheduler。
组件资产内容继续留在各自身份域，不进入全局生产快照。若实现门有缺陷，回滚本节点代码和注册表即可；
既有不可变镜像、历史 scope、账本和结果不受影响。任何旧组件未来复用都必须创建新 release，不得把
新注册登记追溯解释为旧 release 已通过。

## 4. 注册合同 v1

注册表必须使用版本化、严格 Schema，并满足：

1. 所有 Git 跟踪的 Dockerfile、`compose*.yaml` 和 Dockerfile 专属 ignore 恰好登记一次；缺失、重复、
   多归属、陈旧条目、绝对路径、路径穿越、符号链接或不存在文件均失败关闭。
2. 每个组件只属于下列四类之一：
   - `GLOBAL`：属于生产全局代码快照；
   - `COMPONENT_RELEASE`：未来运行前必须通过独立组件 release 身份门；
   - `FIXTURE_ONLY`：只允许合成/工程 fixture，不允许真实 release；
   - `ARCHIVE_CANDIDATE`：只登记待复核，不删除、不运行、不发布。
3. `GLOBAL` 构建资产集合必须与 `CONTROLLED_FILES` 中实际受控的构建资产精确相等；基础 Dockerfile
   的现存根级 COPY 集合继续与 `CONTROLLED_FILES` 精确相等。
4. 每个非归档组件必须声明至少一个被 Git 跟踪且存在的消费者；归档候选可没有消费者，但必须声明
   `REVIEW_BEFORE_DELETE`，不得由注册表触发删除。
5. 资产列表、组件列表和消费者列表采用确定性排序；未知字段、未知枚举或类/状态/复用政策不相容均
   失败关闭。
6. 活跃本地 Web 必须独立登记 `Dockerfile.web`、`Dockerfile.control`、`compose.web.yaml`；M7 网络
   恢复组件必须把专属 ignore 纳入同一身份域。

## 5. 组件 release attestation v1

`COMPONENT_RELEASE` 的新 release attestation 必须以严格 Schema 绑定：

- 注册组件 ID 和注册表版本；
- 该组件全部且仅有的构建资产相对路径及当前 SHA-256；
- 基于“路径 + NUL + 内容摘要”的确定性组件构建快照 SHA-256；
- 源码 bundle SHA-256 与正文件数；
- 40 位 Git commit 与同一时刻的 `origin/main`，二者必须相等；
- 不可变镜像 reference 与 `sha256:<64 hex>` 镜像 ID；
- 镜像标签：
  - `org.opencontainers.image.revision` = Git commit；
  - `io.shaiwei.component_build_snapshot_sha256` = 组件构建快照；
  - `io.shaiwei.source_bundle_sha256` = 源码 bundle SHA-256；
- `production_authorization: none`。

门禁只验证调用方提供的事实，不访问 Git 远端或 Docker daemon。缺字段、额外字段、资产增减/篡改、
旧 scope 复用、Git 身份不一致、源码 bundle 不一致、镜像 ID 非内容寻址、标签缺失/漂移、关闭组件、
fixture 或归档候选尝试 release，均失败关闭。验证成功返回内容寻址的 canonical release identity，
但不授予运行、生产、Web 重建或研究效果读取权限。

## 6. 迁移顺序

1. 先提交并推送本协议，确保实现前边界固定；
2. 建立 91/91 恰好一次注册及独立校验；
3. 建设通用 attestation 校验器和完全合成的成功/对抗 fixture；
4. 全量验证并记录工程裁决；
5. 工程 GO 后停止。下一次真实 Web 重建须另立 release 动作，先生成 attestation/标签，再构建和部署；
   scheduler 保持不动；
6. runner 原子记账和退市方法分别走独立版本化节点，不得借本合同夹带。

## 7. 验收门

A1-4B 只有同时满足以下条件才可记 `GO_ENGINEERING_ONLY`：

- 91 个被跟踪构建资产全部且恰好一次注册，集合与 Git 真身相等；
- 四类均有实际登记，类/状态/复用政策和消费者合同全部通过；
- `GLOBAL` 与当前 `CONTROLLED_FILES` 构建资产集合相等，基础 Dockerfile COPY 反向闭合；
- Web 三项和 M7 专属 ignore 边界由测试明确锁定；
- 合成 Web attestation 成功，缺失/额外/篡改资产、路径穿越、身份或标签漂移、关闭/fixture/归档越权
  等对抗用例全部失败关闭；
- 新生产模块不超过 400 行、函数职责单一，不新建无边界工具模块；
- `make architecture-check`、`make test`、Ruff、`git diff --check` 和脱敏检查通过；
- 只提交本节点文件，scheduler/Web 容器身份和服务状态未被改变。

若任一门失败，状态为 `BLOCKED_ENGINEERING`；不得删除资产、扩大 `CONTROLLED_FILES`、放宽 Schema、
重建服务或转入 runner/退市施工来绕过。

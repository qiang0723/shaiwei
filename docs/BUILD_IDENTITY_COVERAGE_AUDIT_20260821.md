# A1-4A 构建身份覆盖只读审计

## 结论

裁决为 `PASS_PRODUCTION_GLOBAL_WITH_COMPONENT_FINDINGS`。

生产 scheduler 的全局快照边界当前闭合：`CONTROLLED_FILES` 中 57 个现存根文件与基础
`Dockerfile` 的显式 COPY 集合精确相等，`src/config/templates/tests` 全树继续受控；运行中的
scheduler 仍是不可变镜像、带代码快照和 Git revision 标签且 `healthy`。因此本节点不改
`CONTROLLED_FILES`、不重建或提升 scheduler。

仓库级构建资产治理尚未闭合：91 个被跟踪构建资产中，49 个属于全局快照，42 个位于组件边界；
其中 27 个能在 Git 跟踪证据中找到当前内容 SHA-256，15 个没有精确的当前内容哈希引用。缺的是
“每个构建资产恰好归属一个身份域”的中央注册与机器门，不等于 42 个文件都应进入生产快照。

机器真身：`docs/BUILD_IDENTITY_COVERAGE_AUDIT_20260821.artifact.json`。

## 盘点口径

| 项目 | 数量 | 说明 |
| --- | ---: | --- |
| Git 跟踪 Dockerfile | 36 | 不含专属 ignore |
| Git 跟踪 compose | 54 | `compose*.yaml` |
| Dockerfile 专属 ignore | 1 | M7 网络恢复镜像 |
| 构建资产合计 | 91 | 集合 SHA `c384b8f1...63dea` |
| 全局快照内构建资产 | 49 | 16 Dockerfile + 33 compose |
| 组件级构建资产 | 42 | 不应机械并入 scheduler 身份 |
| 组件级当前哈希有跟踪引用 | 27 | release scope、manifest 或验收证据中精确出现 |
| 组件级当前哈希无跟踪引用 | 15 | 须分层处理，不据此改写旧结果 |

“当前哈希有引用”只是机械可证下界：它证明当前文件内容在跟踪证据中有精确身份，不单独证明旧
release 的完整语义闭环；“无引用”也不推翻旧封存结果，旧执行可能绑定了当时版本、镜像 ID 或忽略区
证据。本审计不追溯改判历史研究。

## 全局生产快照

- 当前工作树代码快照为 `acbc94c1...d6f59`，受控树 1,209 个文件；本审计新增文档不在代码快照域。
- 57 个根级 `CONTROLLED_FILES` 全部由基础 `Dockerfile` 显式复制，反向也没有额外根文件。
- 若把全部 42 个组件资产机械加入全局快照，受控树会变为 1,251 个文件，快照变为
  `30a6d497...657e`；基础 Dockerfile 必须同步 COPY，并需要完整 scheduler 发布流程。
- 这会让 Web、已关闭 M5/M6/M7/TS 支线的构建文件变化影响 scheduler 身份，扩大无关耦合，故
  `NO_GO_BLANKET_CONTROLLED_FILES_EXPANSION`。
- 运行 scheduler 镜像 ID 为 `sha256:722f63de...13b76`，标签快照 `4e5244b6...2708`、Git revision
  `210af4d...41db`，健康状态 `healthy`；与当前开发 HEAD 不同是不可变发布隔离的预期结果。

## 组件级 Findings

### P1：活跃本地 Web 缺少可重建源码谱系

`Dockerfile.web`、`Dockerfile.control`、`compose.web.yaml` 不在全局快照，也没有当前文件 SHA 的跟踪
引用。当前 Web/query 镜像 ID `sha256:30ee550b...b421`、control 镜像 ID
`sha256:95c00fb5...2e2`已在验收文档留痕，三个容器均健康；但镜像没有
`io.shaiwei.code_snapshot_sha256`或`org.opencontainers.image.revision`标签，无法从运行容器机械闭合到
源码提交和构建定义。

风险受本机边界限制：UI 仅监听 `127.0.0.1:8080`，query/control 不暴露宿主端口，服务只读；不影响
scheduler 裁决。但下一次 Web 重建前必须先补组件级 release manifest、Git revision、Dockerfile /
compose SHA 与镜像标签，不应继续只靠文档记 image ID。

### P2：已关闭研究资产只有不统一的历史绑定

10 个 M6/M7/TS 构建资产没有当前内容 SHA 的跟踪引用。多数已有历史 release scope、旧镜像或测试
边界，但当前内容与当时执行身份不能用一条统一机器入口复核。它们保持冻结，不重写旧 scope、不并入
生产快照；若未来复用，必须新建组件 release 并绑定当次 Dockerfile、compose、专属 ignore、源码
bundle、镜像 ID 和 Git commit。

### P2：两个整理候选

`Dockerfile.star200-recovery`当前只见历史 STATE 引用，`Dockerfile.web-test`未发现消费者。二者只进入
A1整理候选，不在本节点删除；须按既有 A1 清理纪律先复核冻结证据与恢复价值。

## Docker context 复核

根 `.dockerignore` 放行 19 篇构建文档，唯一专属
`Dockerfile.m7-moneyflow-recovery-network.dockerignore`放行 2 篇；合并各自实际 Dockerfile COPY 图后，
20 篇唯一文档全部可达，缺失 0。此前把专属 ignore 忽略后得到的“根白名单漏 1 篇”不是有效缺陷。

## 对外部反馈的校准

“构建白名单不能依靠人工记忆”的方向正确；但将所有 Dockerfile/compose 直接加入
`CONTROLLED_FILES`会混淆生产全局身份与组件 release 身份。M6-3C 的相关 release scope 已单独记录
Dockerfile/compose SHA，因此“浮点取证问题由它们不在全局快照导致”只能列为假设，不能由本审计
证明。

## 下一节点建议

另立 A1-4B 组件构建身份工程门，仍不先扩大 `CONTROLLED_FILES`：

1. 建立 `GLOBAL / COMPONENT_RELEASE / FIXTURE_ONLY / ARCHIVE_CANDIDATE` 四类恰好一次注册；
2. 机器断言所有被跟踪 Dockerfile、compose 和专属 ignore 均登记且消费者存在；
3. `GLOBAL` 与 `CONTROLLED_FILES`、基础 Dockerfile COPY 精确相等；
4. `COMPONENT_RELEASE` 在每次运行前绑定 Dockerfile/compose/ignore SHA、源码 bundle、Git commit、
   镜像 ID，并拒绝旧 scope 复用；
5. 先为活跃 Web 落组件 release manifest 与镜像标签，再安排下一次 Web 重建，不触碰 scheduler；
6. 已关闭研究资产只登记归档状态，未来复用时再新建 release，不为补清单回写历史。

A1-4B 需要修改测试和组件发布合同，必须另立施工目标；本节点不授权实施、镜像重建、容器重启或生产
发布。旧 runner 原子记账与 M6-5C 退市方法继续是独立问题，不夹带在构建身份治理中。

## 验证与施工边界

- 机器清单从 Git 跟踪集合重新计算，资产计数、三类集合哈希、当前/假设快照、基础 Dockerfile COPY、
  当前 SHA 引用分层和 Docker context 可达性全部一致；
- 全仓 1,694 PASS，架构门 13 PASS，Ruff 与 `git diff --check` PASS；
- 只读检查了 scheduler 与 Web 容器的定向非敏感身份字段，没有读取环境变量或凭据；
- 未修改 `src/config/tests`、Dockerfile、compose、`.dockerignore`、模型、账本、数据、Web 服务或
  scheduler；未构建、重启、提升或删除任何镜像/容器。

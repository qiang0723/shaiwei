# A1-4C 真实 Web 组件 release 与本机只读部署协议

- 协议 ID：`a1-4c-web-component-release-v1`
- 状态：`FROZEN_BEFORE_IMPLEMENTATION_AND_BUILD`
- 冻结日期：2026-08-23（UTC+8）
- 上游工程提交：`780a4c7ee1aafd4f652a9cf018c7633170f7e079`
- 上游裁决：A1-4B `GO_ENGINEERING_ONLY`

## 1. 结果目标与唯一变化

本节点只闭合活跃本地 Web 的真实组件 release 身份，并在候选镜像验证通过后受控替换现有本机只读
Web。唯一变化是“旧 Web 镜像无统一源码谱系”变为“新 Web 双镜像 release 可从 Git 提交、源码
bundle、构建定义、镜像标签和运行容器机械复核”。

不修改 Web 页面、查询口径、研究控制语义、模型、因子、信号、账本、数据或 scheduler；不施工
runner 原子记账或退市规则。发布后仍仅监听 `127.0.0.1:8080`，query/control 无宿主端口，所有既有
只读挂载、权限、网络和资源限制保持不变。

## 2. 开工复核与合同修正

A1-4B v1 attestation 只表达一个镜像，但 `web-local` 实际由两个不可互换的镜像构成：

- `web-runtime`：由 `Dockerfile.web` 构建，供 `web-query` 与 `web-ui` 共用；
- `research-control`：由 `Dockerfile.control` 构建，只供 `research-control` 使用。

因此不能用 v1 单镜像文档只证明其中一半。A1-4C 新增
`shaiwei-component-release-attestation-v2`，保留 v1 代码和历史语义不变；v2 使用确定性、角色唯一的
`images` 列表。该修正是结果前发现的公共合同缺口，不回写 A1-4B 验收，也不声称旧镜像已通过新门。

## 3. 权威输入与源码 bundle

release 只允许来自已推送的 `origin/main`，且以下构建域必须与 HEAD 一致、无未跟踪文件：

- Git 跟踪的 `src/` 与 `web-ui/` 全部文件；
- `pyproject.toml`、`requirements.web.lock`；
- Web 镜像实际复制的三份运行配置；
- A1-4C 的版本化 Web release 配置；
- 注册表中 `web-local` 的 `Dockerfile.web`、`Dockerfile.control`、`compose.web.yaml`。

源码 bundle manifest 按路径排序，逐项记录相对路径与 SHA-256，并以“路径 + NUL + 内容摘要”生成
总 SHA-256。manifest 生成到 Git 忽略、但位于项目内的专用构建目录；两个 Dockerfile 都将同一份
manifest 复制到镜像内。缺文件、额外未跟踪文件、内容漂移、HEAD 未推送或 manifest 自身不一致均
失败关闭。

## 4. 双镜像 attestation v2

v2 必须继承 A1-4B 的注册表、全部三项构建资产、组件构建快照、源码 bundle、Git commit /
`origin/main` 和 `production_authorization: none`，并恰好包含两个按角色排序的镜像记录。每个记录绑定：

- 唯一角色、对应 Dockerfile 和服务集合；
- 内容寻址 image ID 与本地候选 reference；
- `org.opencontainers.image.revision`；
- `io.shaiwei.component_build_snapshot_sha256`；
- `io.shaiwei.source_bundle_sha256`；
- `io.shaiwei.component_image_role`。

候选验证必须同时检查 Docker daemon 的定向非敏感字段、镜像内嵌 manifest、只读一次性容器可读取
身份、两镜像角色/服务覆盖和 attestation 自哈希。不得读取镜像环境变量、容器环境变量、secret 或
完整 inspect 文档。v2 验证成功仍只表示身份闭合，不自动授予生产或研究执行权限。

## 5. 构建、提升与回滚

1. 协议先作为独立提交推送；
2. 实现、合成/对抗测试、全仓验证再作为独立提交推送；
3. 只有 HEAD 与 `origin/main` 相等且构建域干净后，才允许各构建一次候选镜像；
4. 两镜像验证通过后生成真实 v2 attestation 和本地内容寻址 release 状态；
5. 记录现有三容器与两个旧镜像的精确 ID，给旧基线创建仅供回滚的内容标签；
6. 使用 `--no-build` 只替换 `web-query / research-control / web-ui`，验证镜像 ID、健康、端口、只读根、
   挂载/网络边界和核心只读页面；
7. 演练“新 release → 精确旧基线 → 同一新 release”，每步均须健康。最终停在新 release；
8. 状态与动作写入项目内 Git 忽略的原子状态和哈希链审计，旧镜像不删除。

旧 Web 镜像缺 A1-4C 标签，故只允许作为本次迁移的精确 legacy rollback baseline：必须绑定 A1-4A
已记录的 image ID 与本次提升前实际容器 ID；不得把它标为通过 v2，也不得在未来新 release 后继续
作为普通候选。首个 v2 release 稳定后，后续 previous 必须同样是已验 v2 release。

若候选身份、构建、健康、端口、权限、查询或回滚任一失败，立即停止；若已替换则回到精确旧基线，
保留失败镜像、manifest、attestation 和审计，不修改数据或用重建 scheduler 代替恢复。

## 6. 实现结构

- A1-4B v1 loader/verifier 保持兼容，不把 daemon、Compose 或文件写入塞入纯校验模块；
- 新增窄模块分别负责源码 manifest、v2 纯合同、Docker/Compose release 编排；
- Dockerfile 只增加身份参数、标签和内嵌 manifest；compose 只增加候选镜像 reference 参数，不改变
  服务权限、挂载、端口、网络或业务 command；
- Makefile 入口转为调用统一 release 编排，避免继续绕过身份门直接 build/up；
- 新生产模块各自不超过 400 行，函数职责单一；不得新增无边界工具模块。

## 7. 验收门

A1-4C 只有同时满足以下条件才可记 `GO_LOCAL_READ_ONLY_RELEASED`：

- v1 行为回归不变，v2 双镜像正向和缺角色/重复角色/错 Dockerfile/错服务/错标签/错 manifest/旧镜像
  冒充等对抗全部失败关闭；
- 源码 manifest 与已推送 HEAD 的冻结构建域逐文件一致，候选两镜像只构建一次且各自 image ID
  内容寻址；
- 真实 v2 attestation、内嵌 manifest、daemon 标签和运行容器 image ID 全部一致；
- promote、legacy rollback、同 release re-promote 三步均通过，最终三个 Web 服务 healthy；
- UI 仅 `127.0.0.1:8080`，query/control 无宿主端口；根文件系统只读、无 Docker socket、无整仓挂载，
  数据/账本/证据挂载权限与原 compose 一致；
- 关键只读 API/UI、CSP/同源、前端单元与现有 Web 回归通过；
- scheduler 容器 ID、image ID、代码快照标签和健康状态与施工前相同；
- `make architecture-check`、`make test`、Ruff、compileall、pip check、Compose 校验、差异与脱敏检查通过；
- Git 只提交 A1-4C 文件，运行账本和用户已有校准文档保持未暂存。

工程或候选构建通过但尚未部署时只能记 `GO_RELEASE_READY_NOT_DEPLOYED`；不得提前声称现有 Web 已
完成身份闭环。

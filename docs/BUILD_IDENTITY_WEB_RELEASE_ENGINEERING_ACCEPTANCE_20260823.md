# A1-4C Web 双镜像 release 工程验收

- 节点：`a1-4c-web-component-release-v1`
- 日期：2026-08-23（UTC+8）
- 工程裁决：`GO_RELEASE_READY_NOT_DEPLOYED`
- 策略效果：`NOT_EVALUATED`
- 生产授权：`none`

## 1. 本节点解决的问题

A1-4B 的单镜像 attestation 无法完整表达本机 Web 实际使用的两个镜像。本节点在不改变 v1 历史语义
的前提下新增 v2 双镜像合同，把同一 release 中的 `web-runtime` 与 `research-control` 同时绑定到：

- 已推送 Git revision；
- 精确源码 bundle 与逐文件 SHA-256 manifest；
- `Dockerfile.web`、`Dockerfile.control`、`compose.web.yaml` 三项注册构建资产；
- 每个镜像的角色、服务集合、内容寻址 image ID、四项非敏感标签及镜像内 manifest；
- `production_authorization=none`。

Web 构建、启动和状态入口统一经过 release CLI；不再允许 Makefile 对单个 Web 镜像直接 build，或绕过
身份门直接 up。

## 2. 实现边界

- `source_bundle.py`：纯源码 manifest 构造与校验；
- `multi_image_release.py`：纯 v2 双镜像 attestation 合同；
- `web_release_config.py`：严格、版本化 Web release 配置；
- `web_release_build.py`：已推送源码域、候选构建、daemon 标签与内嵌 manifest 适配；
- `web_release_runtime.py`：定向容器身份、只读根、能力、挂载、网络和端口核验；
- `web_release_deploy.py`：提升、旧版回滚演练、重新提升、状态与哈希链审计；
- `web_release.py`：统一 CLI。

新生产模块均不超过 400 行。Dockerfile 只增加身份参数、四项标签和同一 manifest 的复制；Compose 只
把两个镜像 reference 参数化，业务 command、挂载、权限、网络、资源与端口合同未改变。

## 3. 失败关闭与回滚

- 缺/重角色、错 Dockerfile、错服务覆盖、错标签、错 manifest、非内容寻址 ID、未推送 revision、
  源码增删或漂移、生产授权越界全部失败关闭；
- 候选标签已存在时不重建；同一候选已有完整本地证据时只验证并复用；
- 发布前精确记录并标记两个旧镜像；候选替换发生后的任何异常，包括 Compose 部分完成、HTTP/CSP、
  scheduler 身份或本地状态写入失败，均尝试恢复精确旧镜像；
- 首次迁移必须完成“新 release → 旧基线 → 同一新 release”三段健康演练，最终才写入本地状态；
- UI 只允许 `127.0.0.1:8080`，query/control 不得发布宿主端口；禁止整仓挂载和 Docker socket。

## 4. 工程验证

- 双镜像/运行时专项与 A1-4B 回归：57 PASS；
- 架构门：13 PASS；
- 全仓：1,751 PASS，只有 17 条既有第三方/旧研究 warning；
- Ruff、compileall、pip check、`git diff --check`：PASS；
- `docker compose -f compose.web.yaml --profile web config --quiet`：PASS；
- 发布前运行基线：scheduler、web-query、research-control、web-ui 均 healthy；UI 仍仅监听
  `127.0.0.1:8080`。

本阶段没有构建新镜像、生成真实 attestation、重启服务或修改 scheduler。因此当前只可裁
`GO_RELEASE_READY_NOT_DEPLOYED`，不得提前声称 Web 已完成真实身份闭环。

## 5. 下一步唯一合法动作

先把本实现提交并推送，使 release 输入与 `origin/main` 精确同步；随后只允许统一 CLI 各构建一次
两个候选镜像、验证真实 v2 attestation，再执行一次受控提升和旧版回滚演练。真实验收完成前，旧
Web 镜像保留且不得删除。

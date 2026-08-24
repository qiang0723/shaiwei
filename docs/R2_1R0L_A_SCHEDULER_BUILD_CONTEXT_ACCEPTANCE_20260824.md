# R2-1R0L-A Scheduler 隔离构建上下文工程验收

- 日期：2026-08-24（UTC+8）
- 合同：`r2-1r0l-scheduler-timeline-release-v1`
- 节点：`R2-1R0L-A`
- 裁决：`GO_ENGINEERING_COMPLETE`
- 实现提交：`d2c499289b4815f4fb4c206f247fd2238ac2721d`
- 生产授权：无

## 1. 结果

Scheduler 发布构建源已从 live worktree 改为已推送 Git 提交的隔离受控上下文。发布入口现在要求
`HEAD == origin/main`，并在任何 Docker build 之前检查全部 tracked、staged 和 untracked 受控输入；
自然账本、运行证据和非受控用户草稿可以继续留在工作树，但不会进入候选镜像来源。

新增 `release_build_context.py` 单独负责：

1. 校验已推送提交与受控输入；
2. 从精确 revision 只归档 `CONTROLLED_ROOTS` / `CONTROLLED_FILES`；
3. 拒绝路径穿越、符号链接、硬链接和其他非普通文件；
4. 在 Git 忽略的 `.release/scheduler-build-contexts/` 安全解包；
5. 从该上下文生成 release manifest 和代码快照；
6. 归档前后重新核对 HEAD、origin/main 和受控工作树，最后自动删除临时目录。

原 `release.py` 只把 Docker build 的最后一个参数从 `.` 改为上述上下文路径，并继续复用既有 label、
runtime manifest、audit、promote 和 rollback。它由施工前 581 行降为 579 行；新模块为 219 行，没有把
新职责堆入发布热点。

## 2. 真实项目 smoke

实现提交先推送到 `origin/main`，随后在 live worktree 保留七份自然增长账本和三份用户草稿的状态下，
执行一次零 Docker 的真实上下文 smoke：

- Git revision：`d2c499289b4815f4fb4c206f247fd2238ac2721d`；
- 代码快照：`ccf4aa05bc3e07ffc2f62fcf09f79a7cd9aa339e7a80999d3e0c7f049a823d34`；
- 受控文件：1,287；
- `.env`、`data`、`ledger`、`logs`：全部不存在于上下文；
- 上下文位于项目内 Git 忽略目录；退出后临时 run root 已删除。

在提交前，同一真实发布入口也已验证会在 Docker build 前拒绝四个本节点受控改动；错误清单没有包含
自然账本或三份用户草稿。这证明门没有退化为“整个工作树必须干净”，也没有放宽受控输入身份。

## 3. 测试与失败关闭

- 发布上下文与发布专项：20 PASS；
- provenance、构建身份、架构和整理联合专项：66 PASS；
- 架构门：13 PASS；
- 全仓：1,876 PASS，17 条既有第三方/兼容性 warning；
- Ruff、compileall、`pip check`、`git diff --check`：PASS。

专项覆盖自然账本和用户草稿共存、受控 tracked dirty、受控 untracked、未推送 HEAD、非忽略/项目外
上下文根、受控符号链接、归档期间代码漂移、自动清理、archive snapshot 复算和 Docker build 只接受
归档路径。没有读取 `.env` 内容，也没有构建或运行镜像。

## 4. 生产与停止点

本节点的 Docker build、timeline fixture、promote、restart 和真实业务运行均为 0。生产 scheduler
仍为原容器 `183b8c6c5edd...23dd3b`、原镜像 `sha256:722f63de...13b76`、原创建时间，状态
`running/healthy`，RestartPolicy 为 `unless-stopped`。

下一合法节点是 `R2-1R0L-B`：在用户另行批准后，从最终已推送 HEAD 恰好构建一个候选镜像并运行一次
断网 synthetic timeline fixture。L-B 仍不授权 promote 或 restart；生产提升必须另行绑定候选镜像、
代码快照和 Git revision 精确批准。

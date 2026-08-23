# M6-5C-C-R1 Docker context 恢复协议

- 日期：2026-08-23（UTC+8）
- 状态：`FROZEN_BEFORE_RECOVERY_IMPLEMENTATION`
- 生产授权：`none`

## 失败事实

原实现提交 `aac357d` 与断网镜像构建均成功，但唯一 synthetic daemon fixture 在
`ReleaseProtocol.load()` 校验 `method_acceptance` 前序文档时失败。根因是全局 `.dockerignore` 默认
排除 `docs/*`，独立 Dockerfile 又未配置专用 context 例外；因此镜像缺三份合同要求的只读验收文档。
fixture 尚未进入合成领域计算，真实 R2/raw/effect 未读，approval/claim/canonical ledger 写入均为 0。
失败镜像 `faf2ac66...c963cbf` 永久保留身份，同镜像不得重跑 fixture。

## 唯一恢复变量

只新增 `Dockerfile.m6-head30-delisting-risk-release.dockerignore`，允许构建上下文带入三份已跟踪的前序
验收文档，并在独立 Dockerfile 中显式只读 COPY。不得修改风险计算、runner、auditor、claim、门槛、
Compose 挂载、真实输入或全局 `.dockerignore`。successor 使用新镜像名
`shaiwei:m6-head30-delisting-risk-release-r1-v1`，只允许一次断网构建和一次 synthetic fixture。

恢复实现须先推送，再从已推送 revision 形成 source manifest；fixture PASS 后方可生成 metadata-only
scope。scope 推送后停止，真实运行仍须用户绑定精确 SHA 与原冻结动作另行授权。

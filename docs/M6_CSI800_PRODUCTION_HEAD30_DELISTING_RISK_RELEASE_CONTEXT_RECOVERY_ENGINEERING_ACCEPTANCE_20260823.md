# M6-5C-C-R1 Docker context 恢复工程验收

- 日期：2026-08-23（UTC+8）
- 裁决：`GO_SUCCESSOR_BUILD_READY`
- 生产授权：`none`

## 变更与边界

恢复严格只增加一个专用 Docker ignore 文件，并在原独立 Dockerfile 中显式 COPY 三份协议前序验收
文档；successor 镜像名改为 `shaiwei:m6-head30-delisting-risk-release-r1-v1`。全局 `.dockerignore`、
领域计算、runner、auditor、claim、门槛和 Compose 挂载集合均未改变。专用 ignore 只开放 `src/`、
`config/`、单一 source manifest 和三份指定文档，不把其余 docs、data、ledger、logs 或 secret 带入
构建上下文。

release 合同同时绑定 R1 协议与首次 fixture 失败证据；metadata scope 必须包含 base protocol 与 R1
protocol 双身份。首次失败镜像永久关闭，不允许复用或重跑。

## 验证

- R1/M6-5C/build/claim 专项：35 PASS；
- 全仓：1,815 PASS，17 条既有弃用提示；
- architecture-check：13 PASS；
- Ruff、compileall、Compose、pip check、`git diff --check`：PASS；
- 构建资产：94/94 唯一登记；全局 `CONTROLLED_FILES` 未扩大。

## 下一步

本恢复实现推送后，基于远端相同 revision 生成新的 source manifest；只允许一次 successor 断网构建
和一次 synthetic fixture。PASS 后仅生成 metadata-only scope 并停止，不创建真实 approval，不读取真实
R2/raw/effect，不写 canonical ledger。

# M6-3C-R3 数值谱系取证 release 验收

- 冻结时间：2026-08-07 18:34（UTC+8）
- 实现提交：`ad969dcadae3a68e7d5a1ec7fed25c5bee67bde3`
- release scope：`70ae0cc5ab00e3ca0972d013d6898defbc2399861ca33f70e96952a1de1b5b87`
- 当前状态：`READ_ONLY_EXECUTION_READY`

## 1. Release 边界

本 release 只允许原 M6/失败 M6-3C 两套镜像各执行一次无业务数据的包与运行时探针、一次 collector
读取既有 Top30 证据、一次无 Qlib auditor 独立复算。固定 Top30/Top20 新回测 0、模型拟合 0、新预测
0、研究尝试增量 0、外网 0、生产授权 none，同 scope 不重跑。

两套薄镜像均只在冻结 base 上复制版本化的 provenance 包和既有 Top30 精确证据包；不安装依赖、不
拉取镜像。scope 同时绑定 base/thin image ID、24 文件代码 bundle、内嵌发布清单、实现 Git、协议、
Dockerfile、Compose、规范日报与 R2 证据整树。

## 2. 内容身份

- protocol SHA-256：`a129ea9f708e4013fc56b1e09fb7c7f11f04e34e567c31cb31194d1a04514071`；
- scope document SHA-256：`6797e69904210e64501b9d615a5c035b3d22de657bb62655521b6de89e165476`；
- code bundle：24 文件，`5507cbf6...b233`；
- Dockerfile / Compose：`94f2e3ce...398d` / `10f77a9b...1520`；
- original thin image：`sha256:7e5fe6fc...8b867`，base `sha256:3c40c9c...cd40e`；
- failed thin image：`sha256:f6b95c2f...17b43b`，base `sha256:69c1a497...afa17`；
- original/failed image manifest：`b575af7c...d903` / `ffa216e9...596e`；
- 规范日报：8,137 字节，`c705c067...1262`；
- R2 证据：7 文件/310,131 字节，整树`5c58f796...750c`。

## 3. 结果盲验证

- 单元与篡改失败路径：5 PASS；Top30 系列联合定向：16 PASS；
- 架构宪法：10 PASS；全仓：934 PASS（1 条既有第三方弃用 warning）；
- Ruff、compileall、pip check、Compose 展开、安全挂载检查、diff-check、脱敏扫描：PASS；
- 两套最终镜像的断网合成分类/ULP fixture：均 PASS；
- 正式输出根在 scope 生成时不存在，未读取规范日报或 R2 rows 的语义结果。

首次镜像构建曾在 image manifest 阶段因历史 base 不含后置的`top30_diagnostic`共享包而失败；该失败
发生在镜像导出、scope 和正式容器之前，未读取业务输入。修复仅把已测试共享包纳入薄镜像，并把它
纳入 24 文件内容身份；未改变取证矩阵或权限。

## 4. 正式执行顺序

协议与 scope 推送后，严格串行执行 original probe → failed probe → collector → independent auditor。
任何一步失败都关闭 scope，不得原地重跑。成功也只给出工程谱系分类，不自动恢复 Top20、前瞻、
模拟仓或生产。

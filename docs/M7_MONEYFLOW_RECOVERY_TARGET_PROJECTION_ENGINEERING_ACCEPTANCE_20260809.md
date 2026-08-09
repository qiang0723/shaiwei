# M7-0R3-P1 断网目标投影工程验收

## 裁决

`GO_M7_RECOVERY_TARGET_PROJECTION_ENGINEERING_ONLY`。

该裁决仅说明 projector、独立 auditor、一次性 claim、不可变输出与专用 Docker 角色已经在真实规模
合成数据上通过；它不是 908/541 真实目标投影结果，也不授权读取真实证券键、资金流数值、外网、
provider、调整覆盖率、候选、效果、模型、回测、前瞻、模拟仓或生产。

## 冻结身份纠错

施工测试在任何真实语义行读取前发现 v1 把 R2 core 转录为 `df5de399d915...eeca`，与封存 report、
DuckDB audit 和 tracked execution manifest 一致记录的 `df5de3990428...eeca` 不符。v1 原文永久保留、
未执行；v2 `34531647...c1fd` 仅修正该身份，已在实现提交前独立推送。实现和未来 release 只接受 v2。

## 工程真身

- 主算复用冻结 R2 Pandas 分类器，先重算并绑定 lineage core；
- 独立审计从冻结 DuckDB `classified` 关系重新投影，不读取主算内存结果；
- 成员输出保留 feature `trade_date` 与 PIT `source_date`，provider 请求视图只在窄适配函数中把
  `source_date` 映射为请求日期，不覆盖 feature date；
- 目标 Parquet、报告、manifest、audit 与 projector/auditor claim 全部 write-once；
- tracked 报告只含计数、分层和哈希，不含证券代码；
- release 必须精确绑定已推送实现、代码束、镜像、R2 输入束、命令、挂载和资源，且初始
  `execution_authorized=false`；批准 envelope 必须另行逐 scope 绑定。

新增模块均位于 `src/shaiwei/research_gates/m7_moneyflow_recovery/`，职责拆为 contract、release、runner、
auditor、sealing 和 fixture，最大文件 259 行，低于 400 行软上限；未新增依赖、服务、公共 schema 或账本。

## 合成验收

- 真实规模轨 A 908 行、轨 B 541 行；成员粒度、来源键粒度、日期映射、唯一性和 `.BJ=0` 全部通过；
- 主算内部重放哈希一致，DuckDB 独立目标集合与两份 Parquet 逐内容一致；
- 同 scope 第二次 projector 在 loader 前停止，语义读取次数保持 1；
- release 对网络、挂载、资源或权限扩张 fail closed，approval 对错误 scope fail closed；
- 专用容器 `network_mode=none`、只读根、`65532:65532`、drop all capabilities、无项目/数据/账本/
  日志/`.env`/Docker socket 挂载；容器裁决同为 engineering-only GO。

## 验证

- M7 投影/兼容专项：17 PASS；
- 架构宪法：13 PASS；
- 全仓终版：1,039 PASS；
- Ruff、compileall、pip check、Compose config、diff-check、仓库凭据门：PASS；
- 仅有既存 Starlette 弃用提示和冻结 lineage Pandas downcast future warning，不影响裁决；
- 最终合成镜像内容 ID：`sha256:ea77e1716ae14774f2eb98e33fcab58136b62aa8be3fd567155fcbddf82ed007`；
- scheduler 仍为容器 `183b8c6c5edd`、镜像 `sha256:722f63de...13b76`、创建时间
  `2026-08-03 17:39:34 +0800`，healthy，未重启。

## 下一停止点

先提交并推送本实现，再从该提交重建镜像并生成唯一精确 release scope。用户绑定该 SHA 明确批准前，
不得启动真实 projector 或 auditor；本阶段真实证券键、数值、provider、网络和研究尝试均为 0。

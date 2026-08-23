# M6-5C-C-R2 scope 运行时恢复 release 验收

- 日期：2026-08-23（UTC+8）
- 裁决：`GO_RELEASE_READY_NOT_EXECUTION_APPROVAL`
- 生产授权：`none`

## 发布身份

- R2 协议 SHA-256：`a65e9ac7c6e9aed86966cf8821c37ce7794ec958ada0153df5033860b950f66e`；
- 实现提交 / `origin/main`：`68f1192c982c897c97dbd3b6e738fdd6b481e1d6`；
- source manifest 文件 SHA-256：`5e6d01fde9411953df04af97fa95d1c7f9eac6c0be85f85dcffd62f4096128d3`；
- source bundle SHA-256：`82e5cda8083b3f5f3796ad9913f636504ce0ca4895685440697fbc045377ca1c`；
- 组件构建快照 SHA-256：`0bb3e0bb58cdd5fb5c514cbdf224100201b29bda499d640e4f9d69480cbf5a34`；
- successor 镜像：`shaiwei:m6-head30-delisting-risk-release-r2-v1`，内容 ID
  `sha256:e423a6cdf634b3e0c5a72c523fcd80b356a4ebcd5522fac50ad3b85bce23ad79`；
- 新 release scope：`config/m6_csi800_production_head30_delisting_risk_release_scope_r2_v1.json`，
  scope SHA-256 `94a4560553cd67899988276f336cc103de052b2088a2d4adbb63e5ff2d2e9829`。

镜像的 revision、source bundle、组件快照三项标签与 scope 逐项一致。镜像只执行了一次
`network=none` 构建；没有拉取基础镜像或访问外部网络。

## 唯一 daemon fixture

在全新的 Git 忽略目录执行恰好一次断网 synthetic fixture，证据 SHA-256 为
`c94c1b6c2412a47a88680ce44e5a438244bdb55732827cfcdfb245d55806d7b8`，结果：

- `release_scope_loader_pass=true`，组件镜像内真实穿过 `ReleaseScope.load()`；
- runner/auditor CLI 参数映射 PASS；
- canonical claim 先于 effect reader，重复 scope 被拒绝；
- 六个合成窗口共 6 次锁存退出，内部重放与独立重建 PASS；
- `network_used=false`、真实目标/行情/效果读取为 0、真实 canonical ledger 写入为 0；
- fixture `reused=false`，没有第二次运行。

## 边界复核

R2 approval、claim、effect、audit 四类隔离路径均不存在；canonical experiment ledger 中该真实尝试
家族仍为 0。原 R1 scope `2afe815f...ec85c`、approval 和镜像继续永久关闭。生产 scheduler 仍运行
`shaiwei:scheduler-current` 原容器，创建于两周前且 healthy，未重启、未换镜像。

工程门延续为：专项 34 PASS、architecture-check 13 PASS、全仓 1,817 PASS；Ruff、compileall、
pip check、Compose config 和 diff-check 均 PASS。没有读取 `.env`，没有新增 secret、外网、模型拟合、
新预测、前瞻、模拟仓、Web、scheduler 或生产权限。

## 停止条件

本节点到此停止。不得创建 approval 或启动 runner/auditor。若要运行唯一真实退市风险历史诊断，用户
必须重新逐字绑定 scope
`94a4560553cd67899988276f336cc103de052b2088a2d4adbb63e5ff2d2e9829` 与冻结动作；原 scope、原
approval 和本 R2 scope 均不得自动重跑。

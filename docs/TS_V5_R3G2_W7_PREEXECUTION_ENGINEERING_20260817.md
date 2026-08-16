# TS-v5 R3G-2 W7分数谱系预执行工程

日期：2026-08-17（UTC+8）

裁决：`READY_FOR_IMMUTABLE_IMAGE_BUILD_NOT_EXECUTION`

策略效果：`NOT_EVALUATED`
生产授权：`none`

## 结果

R3G-2效果协议要求2025只能使用与M6干净控制同配方的新W7，且必须在任何TS收益读取前单独闭合谱系。
当前已完成训练合同、write-once产物、内部双跑、精确批准、失败封存及无Qlib独立审计入口；真实W7
训练和分数仍未生成，RankIC、收益、H00906、组合和三次策略效果尝试均未读取或消耗。

release准备协议为`config/ts_v5_r3g2_w7_release_v1.yaml`，SHA-256
`4fef44db711081a41ef19ea32cadd883e1fa7efe87c63ea4708c5ff1670a98f0`。容器合同为
`compose.ts-v5-r3g2-w7.yaml`，SHA-256
`fa258ea45f5fa76d07debca92b3a9c48e821fe5aa2726dd5af79ea2bc4345c54`。

## 工程边界

- W7窗口逐字段投影为训练2022-01-01—2024-06-30、验证2024-07-01—2024-12-31、测试2025全年；
  train/valid末端11个信号日剔除，handler只拟合到2024-06-13。
- 真实入口只拟合M6的`clean_lgbm_control_v1`；测试期只持久化`datetime/instrument/score`和模型文本，
  不准备测试标签、不计算RankIC、收益或组合指标。
- first pass与replay必须模型和分数物理哈希全等；失败也封存且同scope不可重跑。模型谱系失败不会伪计
  策略失败，效果尝试数始终为0。
- auditor是独立入口，不挂Qlib，只读release、approval与W7产物；它重算文件集合、哈希、Schema、日期、
  非有限值、`.BJ=0`、双跑一致性及授权链。
- release scope必须绑定已推送Git、受控代码快照、不可变镜像、Qlib树/日历和空输出目录；用户批准必须
  精确匹配action与scope哈希。
- Docker全程`network=none`、只读根、非root、无`.env`、无secret、无账本、无Docker socket；runner
  只挂Qlib和专用输出，auditor不挂Qlib。scheduler不构建、不重启、不改变。

## 架构与验证

R3G-2新代码按`contract / evidence / lineage / control / run / audit / release`职责拆分，生产模块最大
227行，没有增长既有大文件或建立万能工具。合成fixture覆盖确定性双跑、write-once、`.BJ`与非有限
分数、额外标签文件、漂移、重复执行、运行中失败、批准错配和独立审计。

本机专项23项、全仓1348项与架构门13项均PASS；Ruff、Compose解析和`git diff --check`也通过。
既有17条warning均来自已登记的第三方弃用提示或M7数据构造路径，本次没有新增warning。

首个镜像候选在host/image受控文件集合核验时被拒绝：通用Dockerfile此前没有复制12个已经登记的
Dockerfile、Compose与LLM锁文件。该候选没有进入release scope或真实W7；修复后必须以新提交重建，
并重新通过同一集合与逐文件哈希门。

## 下一步

先提交并推送当前实现，再用精确提交构建不可变镜像，在最终镜像内只运行合成fixture。镜像通过后才
允许生成`config/ts_v5_r3g2_w7_release_scope_v1.json`；该文件本身仍是“准备完成、执行未授权”。只有
用户逐字批准唯一scope，才运行一次真实W7双跑和一次独立审计。W7数据GO也不自动授权TS效果读取。

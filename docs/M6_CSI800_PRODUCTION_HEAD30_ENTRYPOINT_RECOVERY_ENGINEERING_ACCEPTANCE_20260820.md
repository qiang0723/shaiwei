# M6-4B-R1 生产 Head30 编排入口恢复工程验收

## 结论

`GO_RECOVERY_RELEASE_READY_NOT_EXECUTION_APPROVAL`。原scope入口失败证据已冻结且永久禁止重跑；
恢复实现只修复Compose tmpfs序列化，并增加必须由Docker daemon实际创建容器的合成fixture。
新不可变镜像和精确recovery scope均已完成；真实Qlib、封存预测、控制报告内容和策略效果均未读取，
组合转换尝试仍为0，生产授权为`none`。

## 实现边界

- 新恢复协议显式继承原协议、失败scope和机器失败证据，且机械锁定唯一变量为tmpfs序列化。
- 原release协议与scope仍可独立加载；恢复scope使用新协议ID、批准动作、镜像和批准文件路径。
- runner/auditor通过显式`--protocol`选择恢复协议，禁止任意协议路径。
- recovery Compose展开后，runner/auditor tmpfs分别为单个4g/1g挂载项；断网、只读根、非root、
  cap-drop、无env、无Docker socket、无生产账本和无整仓挂载边界不变。
- daemon级fixture服务不挂载Qlib、M6 effect、批准文件或真实输出，只运行既有纯合成双跑门。
- 恢复前置校验单独放入`recovery_validation.py`；核心`real_contract.py`保持354行，未因恢复路径增长为
  超过400行的热点文件。

## 不可变发布身份

- 恢复实现提交：`313e711aac232e428a7c685bda29b6996bbd01eb`，构建时与`origin/main`一致。
- 最终镜像：`shaiwei:m6-production-head30-recovery-v1`，ID
  `sha256:19587417b6db6eb338f51ffe9bdaae51dc5fe10dd218019af519b69b4bec63c3`，平台
  `linux/arm64`，代码快照`1d85deadb0d702a231019d9f8c038cae302cbb25f907023df084ca831d01658e`。
- 新recovery scope：`ea648bda49b185cb698f11f78f01d8ce16df217e50c4d12542dfac4318783d2c`；
  文档SHA-256 `d1f6038731a35acde664f8e0f388dfe879d3b46585a3e675da76085db7ab9406`。
- 最终镜像daemon fixture实际创建容器并PASS；first/replay均为
  `269ce579532e8115dd55f17d4d65313e5976765a3e624f12e20126a9552ca301`，独立重建PASS，
  report SHA-256 `e6b097ff777025fafa40cae23050733d17061f1c9ce12abae1042b23525121af`。
- 首轮恢复镜像因人工转录完整Git SHA错误被身份门拒绝进入scope；未读取真实效果、未消费尝试。
  最终镜像已由Git直接返回的完整SHA重建并复核一致。

## 验证

- M6 Head30原协议、发布与恢复专项：20 PASS。
- 架构宪法：13 PASS。
- 全仓：1518 PASS，17条既有第三方/兼容性warning。
- Ruff、compileall、pip check、Compose展开/语法与`git diff --check`：PASS。

## 待完成

真实恢复运行尚未发生。必须停止在用户绑定上述新scope SHA-256的批准前；新scope失败后同样不得
重跑。任何策略有效、模拟仓可用或生产可用结论仍未形成。

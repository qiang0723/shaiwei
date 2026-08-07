# M6-3C-R2 Top30 兼容诊断编排恢复协议（结果盲冻结）

- 冻结时间：2026-08-07 15:36:03（UTC+8）
- 协议 ID：`m6-csi800-top30-compatibility-diagnostic-recovery-v2`
- 机器真身：`config/m6_csi800_top30_compatibility_diagnostic_recovery_v2.yaml`
- 当前阶段：`RESULT_BLIND_ORCHESTRATION_RECOVERY_PROTOCOL_FREEZE_ONLY`

## 1. 结果目标

R1 获精确批准后的唯一 original 编排调用，在 Docker 创建容器前因 tmpfs YAML 被拆分而失败；真实
Top30 诊断仍为 0/6。R2 只恢复这一编排门，使未来新 scope 能真正启动同一三路诊断，不解释或读取
任何策略效果。

## 2. 唯一变化

旧 `compose.m6-top30-diagnostic.yaml`、旧 scope 和旧 approval 永久保留，不修补、不复用。R2 新建
独立 Compose、Dockerfile、镜像名、approval 路径和输出根。三项 tmpfs 都必须是 YAML 列表中的一个
带引号字符串，并且经 `docker compose config`展开后仍恰好为一个完整挂载字符串。

除此之外，R1 的 W1 控制臂、Top30、两种执行器、两个镜像环境、每路双回放、6 次回测、IEEE-754
逐位比较、六类分类、资源和安全边界全部继承，不得改变。

## 3. 架构边界

R2 只新增版本化的恢复合同、运行身份和编排层；现有 Top30 runner、输入验证、精确编码、分类器和
auditor 继续作为唯一领域实现，通过显式 loader/runtime verifier 注入复用。不得复制回测、日报编码
或分类逻辑形成第二套口径。

新 Compose 增加无真实挂载的 fixture 服务，分别证明 original/current 镜像以及 auditor 的非 root、
断网、只读根、drop ALL、no-new-privileges 与 tmpfs 声明可以由当前 Docker 创建和运行。fixture 不挂
Qlib、封存 effect、approval、账本、`.env`、Docker socket 或项目根。

## 4. 授权与停止线

用户“继续下一步”只授权本协议、结果盲实现、合成/Compose fixture、镜像构建和新 scope 生成，不
授权真实数据或诊断执行。新 scope 生成后必须停止。

未来只有用户逐字批准动作
`M6_TOP30_COMPATIBILITY_DIAGNOSTIC_MATRIX_RECOVERY_ONCE`并绑定新完整 scope SHA，才可各调用一次
original runner、current runner 和独立 auditor。任何阶段失败仍不得在同 scope 重跑；诊断结论仍不
自动恢复 Top20、模拟仓、前瞻或生产。

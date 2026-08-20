# M6-4B-R4 生产 Head30 独立审计入口恢复协议

## 冻结结论

R4 只修复 R3 在容器内传入旧协议路径的入口错误。R3 已被唯一调用且永久关闭；它在读取 R2
效果语义前失败，R2 五份封存产物未变化，家族组合转换尝试仍累计 2 次。

R4 不改变研究问题、G0、组合、成本、效果、审计统计或容差，也不增加模型、预测、回测和组合
转换尝试。继承 R3 的独立审计语义：主结果身份精确核验，独立重算按冻结的 `1e-12` 数值容差
比较，并要求主判与独立判决完全一致。

## 唯一变量

- 禁止继续挂载或传入 `/inputs/original-protocol.yaml`。
- 冻结 loader 及其 allowlist 不修改。
- R4 只把原协议路径改为基础镜像已包含且 allowlist 接受的
  `/workspace/config/m6_csi800_production_head30_price_recovery_v1.yaml`。
- 该镜像内文件必须与仓库协议 SHA-256
  `6e4fc89c5c02db862681866e96d1e8063e6b6bc2a6bb58c3cfc08819ba327a6e` 一致；不得复制、改写或
  以另一个路径替代。

## 发布硬门

协议必须先于实现提交并推送。实现提交并推送后，必须用最终镜像和 Compose 服务由 Docker daemon
真实创建断网容器，证明上述精确路径可被冻结 `ReleaseProtocol.load` 加载。仅进程内单元测试或
`docker run --self-test` 不足以放行。

发布 scope 只能绑定镜像、实现、R3 失败证据、R2 五份封存产物的文件身份，以及新的空审计目录；
生成 scope 不得读取效果语义。scope 推送后必须停止，等待用户精确批准，才允许唯一一次 auditor-only
执行。

## 边界

容器断网、非 root、只读根、丢弃全部 capabilities，不挂载 Qlib、项目根、`.env`、Docker socket、
生产账本、模型、预测或其他项目。R2 effect 只读，新 R4 audit 目录可写。R4 不授权生产、Web、模拟仓、
前瞻或 scheduler 重启。

机器真身：
`config/m6_csi800_production_head30_audit_entrypoint_recovery_v1.yaml`。

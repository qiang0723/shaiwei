# M6-5C-C-R2 组件 scope 运行时恢复协议

- 日期：2026-08-23（UTC+8）
- 状态：`FROZEN_BEFORE_RECOVERY_IMPLEMENTATION`
- 生产授权：`none`

## 失败事实

用户批准 scope `2afe815f...ec85c` 后，唯一 runner 容器在 `ReleaseScope.load()` 阶段失败。组件镜像只
包含自身源码、配置和三份合同文档，但共享 `load_build_registry()` 默认要求全仓 94 个构建资产都在
当前文件系统存在，因此在无关的 `Dockerfile.star200-recovery` 处阻断。该错误发生在
`execute_loaded()` 与 claim 之前：真实目标/行情/效果读取 0，canonical ledger 与 receipt 写入 0，
attempt 家族仍为 0，auditor 未启动。原 scope、approval 和镜像运行入口永久关闭，不得重跑。

## 唯一恢复变量

1. build registry loader 新增显式 metadata-only 模式，默认严格文件存在性验证保持不变；
2. M6-5C scope runtime 只在该显式模式读取组件所有权，并要求 registry 中组件路径与 scope 的构建资产
   路径完全相等，再从 scope 的哈希记录独立重算组件 snapshot；
3. successor synthetic fixture 必须实际穿过 `ReleaseScope.load()`，不能只测 Protocol loader 和 CLI
   参数映射。

不修改退市风险状态机、paper-v2执行、指标、独立统计、claim次序、输入、门槛或容器挂载。successor
镜像改用 `shaiwei:m6-head30-delisting-risk-release-r2-v1`，只允许构建和 fixture 各一次。

## 停止点

R2 实现、镜像、fixture 和 metadata-only 新 scope 推送后停止。由于原失败发生在 claim 前，新 scope
仍使用同一新家族 ordinal 1；但必须由用户绑定新 scope 与新恢复动作重新授权，不得复用原 approval。

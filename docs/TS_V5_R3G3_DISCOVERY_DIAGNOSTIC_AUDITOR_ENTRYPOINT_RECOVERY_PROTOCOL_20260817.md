# TS-v5 R3G-3 独立审计入口恢复协议（2026-08-17）

## 事实与裁决

R2 runner 已唯一完成，内部 first/replay 一致，报告 SHA-256 为
`118a528ca0ff4a3877d8a3c28e5fd61dcbe05f1b8d0a8380e68e1b42384ca919`，manifest SHA-256 为
`7ea41562e29b32388bd4a85fae9bc837c9e65b322bcb01abe49f21da9832c96c`。父 R3G-2 `REJECT` 未变，
效果尝试增量0，生产授权none。

原 auditor 容器已唯一创建，但 CLI `protocol` 在调用审计函数前没有映射为 `protocol_path`，触发
`TypeError`。审计函数未进入、诊断明细未读、audit-r2 输出根为空。原 auditor 入口关闭且不得重跑；
runner 结果也不得重跑或改写。

本 scope 只允许修复 auditor CLI 的显式参数映射，并绑定 R2 authorization/report/manifest 哈希，在
独立 audit-r3 根运行一次审计。不得更改诊断算法、指标、父裁决或产物；仍禁止外网、留出期/2026、
模型、回测、搜索、DeepSeek、模拟仓、Web和生产。恢复 auditor 同 scope 不得重跑。

机器 scope：`config/ts_v5_r3g3_discovery_diagnostic_auditor_entrypoint_recovery_v1.yaml`。

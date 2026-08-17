# TS-v5 R3G-3 发现期失败诊断入口恢复协议（2026-08-17）

## 裁决

原 R3G-3 runner 容器已唯一创建，但 CLI 参数 `protocol` 在调用诊断函数前没有映射为
`protocol_path`，触发 `TypeError`。当时尚未进入诊断函数：专用输出根仍为空，未写授权文件，未读取
封存 discovery 数据，未增加策略效果尝试。原入口调用已关闭，不直接重跑。

本恢复 scope 只允许修正公开 CLI 参数到内部 `Path` 参数的显式映射，并以新发布快照运行一次恢复
runner、一次内部确定性 replay 和一次独立 auditor。原协议、四个诊断问题、三点、时间、分母、输入
哈希、输出根与停止条件全部不变。

## 固定边界

- 原协议 SHA-256：`dba4200576168a39c50fc419c938e076299ded7f4c0005bf0a1d2e07a00256aa`。
- 原调用失败于 `argparse_dispatch_before_run_function`；sealed input read、authorization write、output
  write 与 effect attempt increment 均为 0。
- 恢复动作：
  `TS_R3G3_DISCOVERY_FAILURE_DIAGNOSTIC_ENTRYPOINT_RECOVERY_ONCE_WITH_REPLAY_AND_INDEPENDENT_AUDIT`。
- 恢复仍为断网、只读输入、零模型、零回测、零参数搜索、零 DeepSeek、零留出期/2026、零生产权限。
- 原入口与本恢复入口均不得重跑；恢复失败时只能留痕并另裁，不得静默重试。

机器 scope：`config/ts_v5_r3g3_discovery_diagnostic_entrypoint_recovery_v1.yaml`。

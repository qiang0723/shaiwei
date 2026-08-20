# M6-5B 50万元历史回放入口失败留痕

## 权威状态

scope `62f88802a8812a8ce87facd4a149c99b26fc0329497983d62cfc27d215c7570d` 已唯一调用，
容器启动后在 Python CLI 参数映射处失败关闭。该 scope 永久不得重跑。

- 错误为 `TypeError: run() got an unexpected keyword argument 'release'`。
- `argparse` 生成 `release`、`approval` 等键，却被直接展开给要求 `release_path`、
  `approval_path` 等参数的 `run()`；独立 auditor 的 CLI 也存在相同但尚未调用的映射缺陷。
- 异常发生在进入 `run()` 之前，`effect` 与 `effect-audit` 均为 0 个文件；封存 R2 目标、原始价格、
  收益和效果均未读取，独立 auditor 未启动。
- 新语义尝试消费 0，家族累计仍为 1（此前 schema 检查意外目标读取）；但一次性 scope 的调用权已
  消耗，不能因“未读结果”而静默重试。
- scheduler 保持原容器 healthy，未重启；模拟仓、Web、账本和生产均未修改，生产授权仍为 `none`。

机器证据为 `config/m6_csi800_production_head30_500k_entrypoint_failure_v1.json`。后续只能另立
M6-5B-R1 结果盲入口恢复协议：只修 runner/auditor 的 CLI 到领域函数显式映射，并要求最终镜像用
合成输入真实穿过两个 CLI 入口；新输出根、新镜像和新 scope 完成后再次请求精确授权。

# M6-5B-R1 50万元历史回放入口恢复协议（结果盲）

## 目标

只修复 M6-5B runner 与独立 auditor 的 CLI 参数名到领域函数参数名的映射缺陷，构建新镜像、新输出根
和新精确 scope。原 scope `62f88802...7570d`永久关闭，不修改、不重跑。

## 唯一改动

- runner 将 `--release` 显式传给 `release_path`、`--approval` 显式传给 `approval_path`，其余参数也
  逐项显式映射，禁止再次使用无检查的 `**vars(args)`。
- auditor 使用同样的显式映射。该缺陷在本次 runner 失败复核中被提前发现，尚未实际调用 auditor。
- 最终不可变镜像的 daemon 断网 fixture 必须用合成输入真正穿过 runner CLI、内部 replay、auditor
  CLI 和独立重算，不能只直接调用 Python 函数。

`run()`、`audit()`、50万元、Head30目标、paper-v1费用/整手/现金/容量、封存输入身份、评价门和生产
授权均不得改变。恢复工程期间不得读取封存目标、价格、收益或效果。

## 尝试与授权边界

失败发生在进入 `run()` 之前，新增语义尝试为0，家族累计仍为1；但原一次性 scope 已被调用，所以
不得重试。恢复工程完成后必须停止在新的精确 scope：只有用户绑定新 SHA 和动作
`M6_HEAD30_500K_FEASIBILITY_ENTRYPOINT_RECOVERY_ONCE_WITH_REPLAY_AND_INDEPENDENT_AUDIT`批准后，
才可运行一次真实 first/replay 与一次独立 audit，届时新增尝试1、家族累计2。外网、拟合、新预测、
实验账本、前瞻、模拟仓写入、Web、scheduler和生产均不授权。

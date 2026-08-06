# M6-2R 独立审计入口恢复协议（结果后、结论披露前冻结）

- 冻结时间：2026-08-06 23:08（UTC+8）
- 机器协议：`config/m6_csi800_model_attribution_audit_entrypoint_recovery_v1.yaml`
- 当前阶段：`FROZEN_AFTER_RUNNER_BEFORE_AUDIT_RECOVERY_IMPLEMENTATION`

## 1. 为什么需要恢复 release

获批的 M6-2 唯一 runner 已正常完成。它在同一进程内串行完成 `first_pass/replay`，两遍完整产物通过
runner 自身确定性门并写出 report；真实读取已消费恰好两个替代尝试，原 release 永久禁止重跑。

随后唯一 auditor 容器在进入 `audit()` 之前失败：argparse 生成的是 `release/approval`，入口却把
`vars(args)` 直接展开给要求 `release_path/approval_path` 的函数，因而抛出 `TypeError`。审计函数没有
执行、没有读取封存效果语义，audit 目录仍为空。此时 runner 的结论只能是
`PENDING_INDEPENDENT_AUDIT`，不得作为权威结果披露或进入实验账本。

## 2. 已封存且不可改变的事实

- 原 scope：`9b609f0764240ff3930a4aeaaf16cef9deb82579d2a5875f1be9e8c4ffb0b139`；
- 原 approval SHA：`4fce180e98f6058816a56b29fc0622ca86b5e50a726f2c96b9e59b1f5e41168d`；
- 原镜像：`sha256:3c40c9c74bbbda926433f2d49cd78128c665cbb84e071ab3d44d187ecc2cd40e`；
- effect：199 文件、84,957,571 字节，整树 SHA
  `dfbc0b52f40250b7151d74d9a45f3fdc17a69ca1f7b9c853267c1071b4b0d5cb`；
- report SHA：`65e7b7ae2a8c4844f11d855f978d13c58eb082547f76a92ce92c8d6dc94b29f3`；
- 首遍/replay manifest 物理 SHA 均为
  `efa87bfdbfcf83d1b964bc68601a0c9031c5bf276eb04e8fc97fe0d8847cb32f`；
- `failure.json` 不存在，audit 输出文件为 0。

恢复不得修改、删除、规范化或重新生成上述任何文件，也不得重开 runner。

## 3. 唯一允许的改动

第一，修正未来 `effect_audit.main()` 的显式参数映射，并补足真实 CLI 入口测试。第二，建立一个窄的
auditor-only 恢复控制层：恢复镜像必须以原 M6 镜像为不可变 base，只把新入口复制到 `/workspace`
之外；原独立审计函数、统计实现、reader 和原发布清单保持逐字节不变。

恢复入口先验证新 recovery scope/approval、原 scope/approval、原镜像运行身份及完整 effect 树，
再以正确的显式关键字调用原 `audit()`。审计结束后再次核对 effect 树，并在空 audit 目录中保留原
`audit.json` 和一份只含恢复身份与前后哈希的 receipt。任何漂移均失败关闭。

不允许改变模型、窗口、特征、标签、组合、成本、压力期、指标、NW/Holm、门槛或五类终态；不允许
重新计算 runner、打开 Qlib、写实验账本，或根据已出现的暂定标签修改审计语义。

## 4. 权限与隔离

新 release 只能有一个断网短命 auditor：无 Qlib、无 `.env`、无 Docker socket、无整仓、无生产账本；
effect 只读、audit 唯一可写；非 root、只读根、drop ALL capabilities、no-new-privileges，资源上限
2 CPU / 4 GiB / 256 pids。scheduler、Web、模拟仓和其他项目均不触碰。

scope 种类固定为 `AUDITOR_ENTRYPOINT_RECOVERY_READY_NOT_EXECUTION_APPROVAL`，批准动作固定为
`M6_INDEPENDENT_AUDIT_ENTRYPOINT_RECOVERY_ONCE`。实现、镜像和完整 effect 身份内容寻址并提交推送后
必须停止；只有用户针对新的完整 scope SHA 明确批准，才允许启动一次恢复 auditor。

## 5. 完成与停止条件

恢复 auditor 只有在以下条件全部满足后才能披露原结果：新旧权限与身份通过、原 audit 独立重算
PASS、首遍/replay 全量一致、effect 前后整树 SHA 不变、audit/receipt write-once、生产 scheduler
身份不变。失败时保留全部证据并停止，不得再调用第二次、换命令或放宽校验。

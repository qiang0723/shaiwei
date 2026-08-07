# M6-3C 中证800 Top20 组合转换真实 release 协议（结果前冻结）

- 冻结时间：2026-08-07 11:15:44（UTC+8）
- 协议 ID：`m6-csi800-topk20-conversion-real-release-v1`
- 机器真身：`config/m6_csi800_topk20_conversion_real_release_v1.yaml`
- 当前阶段：`RESULT_BLIND_REAL_TOPK20_RELEASE_PREPARATION_ONLY`

## 1. 本节点的结果目标

把 M6-3A 冻结的唯一变量`TopK 30→20`和 M6-3B 已通过的纯合成执行/裁决能力，做成一个可精确授权、
只能运行一次、可独立复核的真实效果 release。本节点只允许实现、合成验证、构建不可变镜像和生成
release scope；完整 scope SHA 获得用户明确批准前，不读取封存预测或组合效果，不挂载 Qlib，不运行
Top20 回测，不写效果产物和实验账本。

## 2. 冻结输入与唯一变量

输入只能来自 M6-2 已封存且经 M6-2R 独立审计 PASS 的 effect 树：199 文件、84,957,571 字节、整树
SHA-256 `dfbc0b52...d5cb`，first-pass/replay bundle 均为`424e3ff9...a27e`，独立 audit SHA 为
`8788bddc...0fd6`。运行时先核对整树、report、两遍 bundle、独立 audit 和 Qlib 身份，任一漂移均在
效果读取前失败关闭。

唯一变化仍是`portfolio.topk: 30→20`。三条分数、W1—W6、中证800 PIT 成员、1亿元账户、
`n_drop=3`、10日调仓、次日开盘、可交易性、基准、费用和三个成本档全部不变。禁止重新训练、重新
预测、改排名、增加 Top10/15/25、第三臂、seed、因子、调仓周期、权重或门槛。

## 3. 先复现 Top30，再允许查看 Top20

正式 runner 必须先从封存输入逐内容复现 M6-2 Top30 组合日报；成员日、预测值、基准、毛收益、费用、
换手和全部日报不能使用 inner join、数值容差或降级路径。只要 Top30 复现不一致，终态只能是
`BLOCKED_PRE_EFFECT`，不得继续生成或裁决 Top20。

通过兼容门后，runner 才使用同一封存预测运行 Top20。主要统计仍为两个既有替代分数臂的配对日频
差分中的差分，固定 NW(10)+Holm(2)，并复用 M6-3A 的 Top20 直接组合门。四种终态和门槛均不改变。

## 4. 一次性、尝试与独立审计

获批后只允许一次 runner 调用，内部串行完成`first_pass/replay`；首次读取 Top20 效果即消费恰好两个
组合转换尝试。即使后续执行或审计失败，也不允许同 release 重跑、递补其他 TopK 或增加假设。

独立 auditor 是第二个断网进程，不导入主指标或执行模块，从两遍 write-once 产物重新计算日报身份、
差分中的差分、NW(10)、Holm、直接组合门和终态。只有独立 audit PASS 后才能形成权威 M6-3C 结论；
所有终态的策略有效性仍为`NOT_EVALUATED_FOR_PRODUCTION`，生产授权始终为`none`。

## 5. Docker 与安全边界

使用独立一次性 Compose。runner/auditor 均断网、非 root、只读根、drop ALL、
no-new-privileges，不挂`.env`、Docker socket、整仓或生产账本。runner 只读挂 Qlib、封存 M6 effect、
M6 audit、release 和 approval，唯一写 Top20 effect；auditor 不挂 Qlib 或旧 M6 effect，只读 Top20
effect 并写独立 audit。W1—W6 串行，生产 scheduler 保护窗口内不启动，也不修改或重启 scheduler。

## 6. release 与批准语义

实现必须提交并推送后再构建不可变镜像。release scope 必须绑定协议、M6-3B manifest、实现 Git、代码
快照、镜像 ID、发布清单、Qlib、封存 effect/audit、命令、挂载、资源和输出路径。

批准动作固定为：

`M6_TOPK20_CONVERSION_EFFECT_ONCE_WITH_INTERNAL_REPLAY_AND_INDEPENDENT_AUDIT`

用户批准必须逐字绑定最终完整 release scope SHA。此前任何“继续”、M6-3A/M6-3B 权限或旧 M6 授权
均不能继承；scope 任一字段漂移都使批准失效。

## 7. 当前停止线

本次冻结提交不读取真实效果。下一步只施工结果盲 runner/auditor、合成测试、不可变镜像和精确 scope；
完成后必须停止并向用户报告完整 scope SHA。在用户明确批准前，真实效果读取、Qlib 挂载、Top20 回测、
实验账本、前瞻、模拟仓、Web 和生产均保持未授权。

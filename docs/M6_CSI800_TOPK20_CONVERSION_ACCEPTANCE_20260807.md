# M6-3C 中证800 Top20 真实转换运行验收

- 运行时间：2026-08-07 12:11（UTC+8）
- 机器裁决：`BLOCKED_PRE_EFFECT`
- 策略有效性：`NOT_EVALUATED_FOR_PRODUCTION`
- 生产授权：`none`

## 1. 结果

用户逐字批准动作
`M6_TOPK20_CONVERSION_EFFECT_ONCE_WITH_INTERNAL_REPLAY_AND_INDEPENDENT_AUDIT`并绑定 scope
`ba4d03be675e63fd94211271e5dc6d4812bc12954fbf8f77ef0eea85c5065fd9`后，唯一断网 runner 已启动一次。
冻结输入、scope、approval、镜像运行身份、Qlib 和封存 M6 effect/audit 身份均通过；W1 控制臂的
Top30 计划名单也先通过兼容检查。

runner 在重新生成第一个 `W1/clean_lgbm_control_v1` Top30 日报后，与封存规范日报的逐内容比较失败，
以 `ConversionError: M6-3C Top30 canonical report differs: W1/clean_lgbm_control_v1` 退出。按结果前协议，
该状态只能是 `BLOCKED_PRE_EFFECT`，不能继续查看 Top20 效果。

## 2. 尝试与停止线

- runner 调用：1 次；退出码 2；同 release 永久不得重跑；
- `top20_effect_started.json`：不存在；Top20 组合尝试消费 0/2；
- Top20 回测、first-pass/replay bundle、正式 report：均未生成；
- 独立 auditor：未启动，因为 runner 成功是其前置条件；audit 目录文件数 0；
- 模型拟合、新预测、第三臂、其他 TopK、外网、实验账本、前瞻、模拟仓和生产写入：均为 0；
- 策略仍为 `NOT_EVALUATED_FOR_PRODUCTION`，不能从本次失败推断 Top20 有效或无效。

## 3. 不可变失败证据

- approval SHA-256：`374f049c4ff591c4332d78691866b2e4c8307198bd9e007e3a5ea714fb06db09`；
- authorization SHA-256：`67a6d98c2b906f3da41008efd71c29aff8b950bff5fef70c3f6792a173edbf02`；
- failure SHA-256：`0b837144676a3b3dfbd33e4da9835b43439f9a56f6ac2dd8edd26acc1f7d7537`；
- effect 树：2 文件、896 字节、SHA-256
  `d2c22e1738eec49294c814355d29bf76e9b6d9e36c5b8db82ced119c34b3615a`；
- 跟踪清单：`config/m6_csi800_topk20_conversion_manifest_v1.json`。

失败实现只持久化了兼容对象名，没有在失败前保存新生成日报或逐单元差异。因此现有证据足以确认
“输入/名单之后、Top20 之前的 Top30 日报逐内容不一致”，但不足以裁定具体日期、字段和值；不得把
可能的运行时复现差异或合同接线错误写成已证实根因。

## 4. 隔离与生产

runner 使用正式镜像 `sha256:69c1a497...afa17`，断网、非 root、只读根，不挂 `.env`、Docker socket、
整仓或生产账本；退出后无一次性容器残留。scheduler 保持容器 `183b8c6c...23dd3b`、镜像
`722f63de...13b76`、`healthy`、重启次数 0，未被修改或重启。现有 scheduler 产生的 7 个账本改动继续
保留且未暂存。

## 5. 下一合法节点

如继续，须另立结果盲的 `M6-3C-R1` 兼容诊断/恢复协议：只能解释并持久化 Top30 逐字段差异，先证明
是否为可复现性或接线问题，不读 Top20、不放宽逐内容门、不引入数值容差、不改参数。任何新的真实
执行仍须新镜像、完整 scope 和用户精确授权；本 scope 不得以修代码、换命令或手工补产物方式重开。

## 6. 归档质量门

- 全仓测试：918 PASS，只有 1 条既有 Starlette 第三方弃用提示；
- M6 Top20 专项：28 PASS；架构门：10 PASS；
- Ruff、compileall、pip check、JSON 解析、`git diff --check`和跟踪文件凭据门：PASS。

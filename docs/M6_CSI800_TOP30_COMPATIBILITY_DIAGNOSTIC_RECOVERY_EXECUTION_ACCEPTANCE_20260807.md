# M6-3C-R2 Top30 兼容诊断运行验收

- 运行时间：2026-08-07 17:46—17:51（UTC+8）
- 独立审计：`PASS`
- 权威分类：`MIXED_UNRESOLVED`
- 策略有效性：`NOT_EVALUATED_FOR_PRODUCTION`
- 生产授权：`none`

## 1. 结果

用户逐字批准动作`M6_TOP30_COMPATIBILITY_DIAGNOSTIC_MATRIX_RECOVERY_ONCE`并绑定 scope
`f4ade91b9cd93f4bc248138eb3b06f5283361c7642c4b497bcfc70414422d13e`后，R2 original、current 和无
Qlib 独立 auditor 各调用一次并全部正常退出。

固定矩阵的 6 次 W1 控制臂 Top30 回放全部完成；Top20 回测、模型拟合、新预测、研究尝试、实验账本
写入、外网、前瞻、模拟仓和生产写入均为 0。同 scope 已关闭，不得重跑。

## 2. 独立分类事实

三路每路内部双回放均逐位一致，因此不是`RUNTIME_NONDETERMINISM`：

- 原 M6 镜像 + 原执行器：两遍 rows SHA 均为`0fd9f0a5...89a7`；
- 失败 M6-3C 镜像 + 原执行器：两遍均为`20b1f718...f394`；
- 失败 M6-3C 镜像 + 新执行器：两遍也均为`20b1f718...f394`。

失败镜像内原/新执行器完全一致，排除“仅新适配器差异”；但原 M6 镜像的重建结果也不等于封存规范
日报，且不等于失败镜像结果，所以同时不满足“仅失败镜像环境差异”或“三路统一历史复现缺口”的
冻结定义。独立 auditor 因而只能裁定`MIXED_UNRESOLVED`，不能越权强行归入某个单因标签。

## 3. 差异规模

三路与规范日报均为相同 244 行，日期和行数未缺失；差异集中在 IEEE-754 末端：

- 原 M6 镜像相对规范日报：245 个差异单元，首个差异在位置 12 的`gross_return`，最大绝对差
  `7.528699885739343e-16`；
- 失败镜像的原/新执行器相对规范日报：各 217 个差异单元，首个差异在位置 20 的`gross_return`，
  最大绝对差`6.175615574477433e-16`。

绝对差很小只能作为诊断事实，不能反向加入容差、舍入或放宽逐内容门。当前证据说明问题是可重复的
数值/历史环境复现混合差异，但还不能从现有六路矩阵唯一识别具体依赖、BLAS、序列化或历史生成路径。

## 4. 不可变证据

- approval SHA-256：`9c92e86d3ab4aaa96d9530034fe47da02c89682a1191dcaa84bfb347c7b5ae5f`；
- original bundle / tree：`9a4eaee1...3322` / `f2a79d75...f876`；
- current bundle / tree：`e0283a9c...a576` / `dfcad43b...6596`；
- audit / audit tree：`db03a7e5...8c75` / `28376602...741`；
- 全部 7 件正式产物：310,131 字节，整树 SHA-256 `5c58f796...750c`；
- 脱敏机器清单：`config/m6_csi800_top30_compatibility_diagnostic_recovery_manifest_v2.json`。

独立 audit 的 scope、approval、规范日报、执行次数、零 Top20、零尝试增量和非生产七项检查全部为
true；`top20_remains_prohibited=true`。

## 5. 隔离与生产

两个 runner 均断网、非 root、只读根，仅挂冻结 Qlib/effect 和专属输出；auditor 不挂 Qlib。退出后
没有一次性容器残留。scheduler 保持原容器`183b8c6c...23dd3b`、原镜像`722f63de...13b76`、状态
`healthy`、重启次数 0；7 个 scheduler 自然账本改动继续保留且不纳入本次提交。

## 6. 下一合法节点

本诊断没有恢复 M6-3C 或 Top20。若继续，须另立结果盲的`M6-3C-R3`数值谱系复原协议，只读比对：

1. 封存规范日报的生成提交、镜像、Python/NumPy/Pandas/Qlib、BLAS 和序列化版本；
2. 原 M6 与失败 M6-3C 两个 base 镜像对应依赖和计算路径；
3. 既有三路 rows 的逐字段分布与首差，不新增回测。

R3 不得读取 Top20、不增加容差、不改日报、不重跑本 scope；只有能还原规范生成环境并形成新完整
release 时，才可再讨论一次新的 Top30 复现验证。否则 M6-3C 保持`BLOCKED_PRE_EFFECT`并关闭本路线。

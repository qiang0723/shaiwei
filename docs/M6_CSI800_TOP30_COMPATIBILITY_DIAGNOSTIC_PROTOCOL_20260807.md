# M6-3C-R1 Top30 兼容差异诊断协议（结果盲冻结）

- 冻结时间：2026-08-07 12:26:41（UTC+8）
- 协议 ID：`m6-csi800-top30-compatibility-diagnostic-v1`
- 机器真身：`config/m6_csi800_top30_compatibility_diagnostic_v1.yaml`
- 当前阶段：`RESULT_BLIND_DIAGNOSTIC_PROTOCOL_FREEZE_ONLY`

## 1. 目的

M6-3C 唯一 runner 已在首个 `W1/clean_lgbm_control_v1` Top30 日报逐内容门失败；Top20 尚未开始、
组合尝试消费 0。现有失败证据没有保存新生成日报，因此不能判断是新适配器、镜像环境、历史复现缺口
还是运行内不确定性。本协议只补齐诊断证据，不评价策略，不恢复 Top20。

## 2. 唯一诊断对象

只允许同一个 W1 控制臂、同一封存 test prediction、Top30、`n_drop=3`、10日调仓、1亿元账户、
SH000906、次日开盘和原成本参数。禁止 W2—W6、压力期、替代臂、Top20、其他 TopK、模型拟合、
新预测、参数或门槛变化。

诊断矩阵在未来获批后固定为三路：

1. 原 M6 正式镜像 + 原执行器，内部精确双跑；
2. 失败 M6-3C 镜像 + 原执行器，内部精确双跑；
3. 失败 M6-3C 镜像 + 新 TopK 执行器，内部精确双跑。

合计恰好 6 次相同 Top30 诊断回测，研究尝试增量 0；三路串行，不能增加第四路或临时换参数。

## 3. 精确比较与分类

日期、行序、四列和每个浮点数都用 IEEE-754 `float.hex()`逐位比较；不允许 inner join、删行、舍入、
容差或“足够接近”。每次重建日报、规范身份、首个差异单元和差异总数都写入忽略区，独立 auditor
不挂 Qlib，只从产物和封存规范日报二次分类。

分类固定为：全部复现、`NEW_ADAPTER_DIVERGENCE`、`FAILED_IMAGE_ENVIRONMENT_DIVERGENCE`、
`HISTORICAL_REPRODUCIBILITY_GAP`、`RUNTIME_NONDETERMINISM`或`MIXED_UNRESOLVED`。这些标签只回答工程
复现问题，不改变 M6-3C 的 `BLOCKED_PRE_EFFECT`，也不自动授权 Top20。

## 4. 安全与发布边界

两类 runner 和 auditor 都必须是断网、非 root、只读根、drop ALL、no-new-privileges；不挂 `.env`、
Docker socket、整仓或生产账本。runner 只读 Qlib、封存 M6 effect 和原 M6-3C 失败证据，专属目录
唯一可写；auditor 无 Qlib。scheduler、Web、模拟仓、实验账本和生产均不触碰。

实现必须在本协议提交推送后开始；先做完全合成矩阵和篡改测试，再以原 M6 与失败 M6-3C 正式镜像为
不可变 base 构建两套薄诊断镜像。最终 scope 必须绑定协议、实现 Git、两个 base/image ID、代码与发布
清单、Qlib、三份封存输入、命令、挂载和资源。

## 5. 停止线

本次“继续下一任务”只授权协议、结果盲实现、合成验证、镜像和精确 scope，不授权真实 Qlib/封存日报
读取或 6 次 Top30 诊断。完整 scope 生成后必须停止；只有用户逐字批准动作
`M6_TOP30_COMPATIBILITY_DIAGNOSTIC_MATRIX_ONCE`并绑定完整 SHA，才可各启动一次 runner 和 auditor。
任何失败都不得在同 scope 重跑；即使诊断成功，Top20 仍须另立新 release 和再次授权。

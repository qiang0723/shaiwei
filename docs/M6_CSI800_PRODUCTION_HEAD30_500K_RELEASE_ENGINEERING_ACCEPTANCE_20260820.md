# M6-5B 生产 Head30 50 万元历史回放发布工程验收

## 裁决

`GO_RELEASE_READY_NOT_EXECUTION_AUTHORIZED`。

真实 runner、内部 first/replay、独立 artifact-only auditor、精确原始批次 manifest、隔离 Docker profile 和恢复版 release scope 已完成。真实 50 万元历史回放没有运行，价格/收益/效果指标仍未读取，生产授权为 `none`。

## 结果盲事件与恢复

工程检查期间，一次 schema 探针意外打印了 W1 第一调仓点的交易日、信号日和 30 个目标代码；没有读取价格、收益、成本、NAV、回撤或裁决。冻结 v1 明确把真实目标读取也计为尝试，因此：

- 原 v1 永久保留但不再具备执行资格；
- 该读取计为家族第 1 次尝试；
- 恢复协议提交 `d65ec19` 先行冻结并推送；
- 未来若获一次真实运行授权，该运行计第 2 次家族尝试；同 scope 不得重跑。

完整事件见 `docs/M6_CSI800_PRODUCTION_HEAD30_500K_TARGET_READ_INCIDENT_20260820.md`。

## 工程边界

- 真实账户路径直接复用 `shaiwei.paper.engine.execute_day`，没有复制第二套会计引擎。
- 初始资金每窗口人民币 500,000 元；六窗口分别重置。
- 目标顺序、30 只等权、调仓日和信号日只来自封存 R2 first/replay。
- 原始证据固定为 7 类 Tushare API 的 21,815 个不可变批次；scope 固定每个批次路径、SHA-256、行数和采集时间。正式 runner 在语义读取前逐文件复核哈希和 Parquet 行数，scope 外新增批次自动忽略。
- 容量只使用信号日前 20 个有效成交额，至少 15 个观察，订单金额不得超过中位成交额 5%；执行日成交额禁止参与。
- runner 断网、只读根、非 root；只给 R2、R7 audit、raw manifest 和 `data/raw` 只读挂载，effect 为唯一写根。
- auditor 不挂载 R2、raw 或其他生产输入，不导入主 runner/主指标模块；只读五份封存 effect，以 `1e-12` 容差独立重算并要求裁决精确一致。
- 不训练模型、不生成预测、不写实验账本、模拟仓、Web、scheduler 或生产路径。

## 身份与证据

- 最终实现提交：`8fb0c84cbe730d758281f34e87520acf0af8483d`，生成 scope 时与 `origin/main` 一致。
- 镜像：`shaiwei:m6-head30-500k-release-v1`，`linux/arm64`，内容 ID `sha256:1f2a6daf35a432881d3999e1befd9ad7f5e133a1f672cc1c6c995ffc36459b86`。
- 镜像代码快照：`748b51eeba098dbf001c6e91b574cd65364bb4116c48859bad80df30fea111e8`，1190 个受控文件。
- 镜像 manifest SHA-256：`a7e0b48a861ee5284a7cddf67becc2d3dd056e1697b377e40db84b91d0ef51fd`。
- 合成 fixture SHA-256：`7b8ac052af3057fc9012f089cd633bc013d8216a082fece2895949c899e6cf17`。
- 原始批次 manifest SHA-256：`96d798f1bf6b6ef846e1e288a0e2ca40560241942dce8a42360b64ca11fae892`。
- release scope 文档 SHA-256：`697169f05c4df78a08fcd07722ff40bc176874d9738e734271cfd44038c933c9`。
- 精确 release scope SHA-256：`62f88802a8812a8ce87facd4a149c99b26fc0329497983d62cfc27d215c7570d`。

## 验证

- 纯合成 Docker daemon fixture：PASS；实际创建容器，断网、只读根、非 root，`execute_day`、内部双跑和独立重算全部通过。
- fixture 明确记录 `real_target_read=false`、`real_price_or_effect_read=false`、`model_fit_count=0`、`production_authorization=none`。
- 专项测试、Ruff、compileall、Compose config、架构宪法、敏感模式与 diff 检查通过。
- 终版全仓回归 1,619 PASS（17 条既有第三方/未来弃用 warning）。
- scheduler 仍为原容器，已运行两周且 `healthy`，未重启。

## 下一步唯一合法动作

只有用户逐字绑定下列 scope 与动作，才可运行一次真实 runner；成功后才运行一次独立 auditor：

- scope：`62f88802a8812a8ce87facd4a149c99b26fc0329497983d62cfc27d215c7570d`
- action：`M6_HEAD30_500K_FEASIBILITY_TARGET_READ_RECOVERY_ONCE_WITH_REPLAY_AND_INDEPENDENT_AUDIT`

该授权只允许一次断网真实 50 万元历史回放、完整 first/replay 和一次独立审计；新增尝试 1、家族累计 2。不授权外网、模型拟合、新预测、实验账本、前瞻、模拟仓写入、Web、scheduler 或生产。

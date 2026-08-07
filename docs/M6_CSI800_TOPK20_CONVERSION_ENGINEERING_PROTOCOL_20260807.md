# M6-3B Top20组合转换结果盲工程协议

- 冻结时间：2026-08-07 10:08:13（UTC+8）
- 协议 ID：`m6-csi800-topk20-conversion-engineering-v1`
- 机器真身：`config/m6_csi800_topk20_conversion_engineering_v1.yaml`
- 阶段：`RESULT_BLIND_SYNTHETIC_ENGINEERING_ONLY`

## 1. 结果目标

本节点只证明 M6-3A 可以被一套职责清晰、确定性、失败关闭且可独立复核的组合专用工程实现承载。
工程 GO 不回答 Top20 是否有效，也不读取任何真实 Top20 或 M6-2 效果。

实现必须覆盖：TopK 单变量合同、Top30 逐内容兼容门、Top20 组合计算、两个既有替代分数臂的差分中的
差分、Top20 直接组合门、NW(10)+Holm(2)、四个互斥终态、write-once 双跑和独立 auditor。

## 2. 继承和架构边界

M6-3A 提交 `931d6334...005c`、机器合同及文档按物理哈希绑定并保持不变。新增独立
`shaiwei.research.topk_conversion` 包，不扩大现有 M6 模型归因模块，也不触碰基线策略和共享交易类。

- `execution` 只接受已存在的分数/报告端口，不能导入模型工厂、训练、特征或评分模块；
- `metrics` 负责正式差分中的差分和终态；
- `artifacts` 负责规范化、write-once 和双跑身份；
- `audit_statistics` 物理独立重写关键公式；`audit` 不得导入主 `metrics`、`execution` 或 `synthetic`；
- 每个新增生产模块常态不超过400行，不新增运行依赖，不把逻辑堆入既有热点。

本节点不需要 ADR：它是一次性断网研究包，沿用既有合同、回测端口和权限，不新增服务、公共写接口、
账本Schema或跨层依赖。

## 3. 合成门与失败矩阵

固定 seed `20260807`，生成 W1—W6、三组虚构分数臂、Top30/Top20及每窗40个虚构账户日。证券标识
必须是不能对应真实A股的 `SYN...`，不含真实证券代码、行情或封存效果。

合成 fixture 必须覆盖四类终态：`TOPK20_CONVERSION_SUPPORTED`、
`TOPK20_CONVERSION_NOT_SUPPORTED`、`MIXED_NOT_CONCLUSIVE`、`BLOCKED`。还要对抗前置哈希漂移、
第二变量、模型导入、Top30不一致、成员日错位、`.BJ`、非有限/不可复利收益、错误Holm家族、双跑漂移、
路径逃逸、覆盖写入和audit篡改。

## 4. Docker隔离与证据

使用独立 `compose.m6-topk-conversion.yaml`，不继续增长1600行以上的 `compose.research.yaml`。runner 与
auditor 都是一次性、断网、非root、只读根、cap drop all、no-new-privileges；不挂 `.env`、Docker
socket、整仓、Qlib、M6 effect、账本或生产目录。

runner 只有自己的合成输出目录可写；auditor 只读 runner 输出，只能写独立 audit 目录。镜像内代码
来自已提交快照。`first_pass/replay` 物理SHA一致，第二次同身份调用只能复用；独立audit必须重算并
PASS。Git只提交代码、合同、测试、脱敏manifest和验收文档，不提交合成运行目录。

## 5. 当前权限和停止点

允许工程代码、合成数据和不可变工程镜像；依赖构建网络仅用于镜像构建，运行时必须断网。禁止读取
M6 effect、Qlib manifest/日历/特征/价格、真实标签或效果，禁止模型拟合、预测、真实回测、实验账本、
前瞻、模拟仓、Web、scheduler和生产变更；不读取 `.env`，Tushare/DeepSeek 调用均为0。

若工程门全部通过，终态只能是 `GO_ENGINEERING_ONLY`，策略仍
`NOT_EVALUATED_FOR_PRODUCTION`、生产授权`none`，随后停止。真实效果必须另立目标、构建完整不可变
release scope，并由用户对精确scope再次授权；本节点权限不得继承。

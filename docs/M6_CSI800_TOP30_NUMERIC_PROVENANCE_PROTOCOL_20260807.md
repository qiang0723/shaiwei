# M6-3C-R3 Top30 数值谱系复原协议（零新回测冻结）

- 冻结时间：2026-08-07 18:12:39（UTC+8）
- 协议 ID：`m6-csi800-top30-numeric-provenance-v1`
- 机器真身：`config/m6_csi800_top30_numeric_provenance_v1.yaml`
- 当前阶段：`FROZEN_READ_ONLY_NUMERIC_PROVENANCE_RECONSTRUCTION`

## 1. 结果目标

R2 已证明三路各自确定、失败镜像内新旧适配器完全一致，但原 M6 镜像、失败镜像和封存规范日报
三者不等，权威只能记为`MIXED_UNRESOLVED`。R3 不再制造第四路回测，而是复原规范日报与两套历史
镜像的生产谱系，回答差异是否能被运行时、依赖、BLAS、代码路径或 Parquet 序列化唯一解释。

这是一项工程取证，不评价策略，也不恢复 Top20。

## 2. 固定输入与唯一变化

只读输入固定为：封存 W1 控制臂 Top30 规范日报、R2 的 7 件正式诊断产物、两套已存在的历史镜像、
三个冻结 release/scope、仓库内对应 Git 对象和依赖锁。开始前必须逐项核对 SHA、整树身份、镜像 ID
与 Git 对象；任一身份不符即失败关闭。

R3 的唯一变化是增加“数值生产谱系证据”。禁止挂载或读取 Qlib provider、预测、Top20、其他窗口、
其他策略臂或生产账本；禁止训练、回测、调参、容差、舍入、改写旧 Parquet 或增加研究尝试。

## 3. 取证矩阵

一次 collector 只收集并规范化五类既有事实：

1. 两套镜像的 Python、平台、libc、关键发行包版本、NumPy 构建配置、镜像层与发布清单身份；
2. 规范 Parquet 的 producer、format、schema、row group、压缩和文件身份；
3. 规范生成提交、原镜像提交、失败镜像提交中授权执行模块的内容哈希与窄范围源码差异；
4. 现有三路 rows 的逐列差异、首末位置、IEEE-754 ULP 距离和方向分布；
5. 哪些身份完整、哪些生产信息从未被封存，形成明确证据缺口。

包探针只允许在现有镜像中断网运行，不挂项目根、`.env`、Qlib、Docker socket 或账本；环境变量只准
记录与 BLAS/线程有关的变量名，不得记录值。一次独立 auditor 不依赖 collector 的裁决代码，重新核对
输入身份、统计和分类。

## 4. 冻结分类

- `ROOT_CAUSE_IDENTIFIED`：存在唯一且无竞争解释的谱系差异，并与现有三路输出关系逐项一致；仅发现
  版本不同或统计相关不能满足。
- `PRODUCER_ENVIRONMENT_IDENTIFIED_NOT_CAUSALLY_PROVEN`：规范日报生产环境已完整内容寻址，但零新
  回测证据不足以证明具体差异的因果性。
- `PROVENANCE_GAP_CONFIRMED`：规范日报缺少不可替代的生产身份，现有镜像、提交和元数据无法闭合。
- `MIXED_UNRESOLVED`：其他证据模式。

不允许为了得到更具体标签而新增回测、扩大读取范围、试装依赖或调整比较方式。分类只决定工程复现
路线是否还能继续，不改变策略有效性与生产授权。

## 5. 安全、架构与完成定义

collector 与 auditor 必须职责分离：前者规范化既有证据，后者独立复算身份、ULP统计和裁决；不得复制
回测实现。二者均为一次性、断网、非 root、只读根，只有专属忽略目录可写。正式执行固定为 collector
一次、auditor 一次、Top30/Top20 回测 0、研究尝试增量 0，同 scope 不重跑。

完成需要：协议提交先行推送；合成 fixture 覆盖四种分类和篡改失败；正式取证一次完成；独立 audit
PASS；产物逐哈希归档；scheduler 身份与自然账本不变。即便裁到`ROOT_CAUSE_IDENTIFIED`，也不自动
授权新的 Top30 验证或 Top20，后续动作仍须另立协议。

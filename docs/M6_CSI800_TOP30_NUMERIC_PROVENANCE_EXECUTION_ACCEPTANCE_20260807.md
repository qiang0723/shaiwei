# M6-3C-R3 Top30 数值谱系复原执行验收

- 执行时间：2026-08-07 18:35—18:36（UTC+8）
- 独立审计：`PASS`
- 权威分类：`PRODUCER_ENVIRONMENT_IDENTIFIED_NOT_CAUSALLY_PROVEN`
- 策略有效性：`NOT_EVALUATED_FOR_PRODUCTION`
- 生产授权：`none`

## 1. 结论

规范 Top30 日报的生产身份已经闭合：原始镜像、Git、代码快照、发布清单、Qlib 内容树、运行 Compose
和 Parquet producer 均有内容地址，不能再称为“历史环境丢失”。但现有零新回测证据中同时存在运行
线程/资源、入口进程和后续镜像代码边界等多个差异，无法证明其中任何一个是唯一因果来源。

因此本次不能裁`ROOT_CAUSE_IDENTIFIED`，也不能继续沿用 R2 的笼统`MIXED_UNRESOLVED`；冻结合同下
最窄且诚实的结论是：生产环境已识别，因果未证。

## 2. 已排除与仍存在的解释

已排除：

- 规范日报和 original 诊断使用同一个 M6 base image `sha256:3c40c9c...cd40e`；
- 两套历史镜像的 Python 3.11.15、glibc 2.41、NumPy 1.26.4、Pandas 2.3.3、PyArrow 24.0.0、
  Qlib 0.9.7、SciPy 1.17.1、LightGBM 4.6.0 与 OpenBLAS 构建身份全部相同；
- 原执行器、策略和 artifact 写入模块的文件身份相同；失败镜像新增的 TopK 转换执行器存在性不同，
  但 R2 已证明失败镜像内新旧执行器输出完全一致，所以它不能解释该镜像内差异。

仍有竞争解释：

- 规范 runner 使用 6 CPU、12 GiB、四类线程变量均为 6；R2 诊断使用 2 CPU、4 GiB、线程均为 1；
- 规范日报由完整`effect_run`流程产生，诊断由只重建单臂日报的 runner 产生，进程状态与调用路径不同；
- original 与 failed 两套 base image 的整体内容地址仍不同，即使关键包版本相同。

仅靠现有三路 rows 不能在这些差异间建立唯一因果关系；不得把“最像线程差异”写成已证明根因。

## 3. 数值拓扑

规范日报为 244 行，Parquet 2.6、ZSTD、单 row group，producer 为
`parquet-cpp-arrow version 24.0.0`。差异只出现在`gross_return`、`recorded_cost`与`turnover`，基准
收益未变：

- original image/original adapter：245 个单元，ULP 中位数 130、最大 66,559，最大绝对差
  `7.528699885739343e-16`；
- failed image/original adapter：217 个单元，ULP 中位数 131、最大 26,595，最大绝对差
  `6.175615574477433e-16`；
- failed image/new adapter：与上一条逐位相同。

ULP 统计说明差异是稳定的末端浮点路径差异，不说明业务结果显著，也不构成添加容差的理由。

## 4. 执行与证据

严格串行唯一执行：original probe 1、failed probe 1、collector 1、independent auditor 1；Top30/Top20
新回测、训练、预测、研究尝试、Qlib 读取、外网和生产写入均为 0。同 scope
`70ae0cc5...5b87`已关闭，不得重跑。

- probes：`6c193269...250af` / `9f02d8ea...db4c`；
- collector report：`c8b29c6a...393e`；
- independent audit：`15d360f4...c1cd`；
- 5 件正式产物：19,923 字节，整树`9888eb8e...dcae`；
- 脱敏机器清单：`config/m6_csi800_top30_numeric_provenance_manifest_v1.json`。

独立 audit 八项检查全 PASS：scope、冻结输入、collector 输入、ULP 拓扑、分类、因果不过度声称、零
新回测和非生产。一次性容器已退出；scheduler 保持原容器/镜像、healthy、重启 0；7 个自然账本未
纳入本次提交。

## 5. 后续裁决

M6-3C 继续保持`BLOCKED_PRE_EFFECT`，Top20 不恢复。若未来一定要验证因果，必须另立新的结果盲
R4，只改变一个运行变量并重新执行 Top30；本次结论不自动授权该动作。

当前更合理的主线是关闭 M6-3C 连续诊断，进入已排期的 A1-0 代码库只读整理清单，再决定下一项重大
策略池或研究能力，避免为了约`1e-16`的非业务级差异继续消耗主线。

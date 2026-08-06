# M6-1 中证800模型归因结果盲工程协议

- 冻结时间：2026-08-06 19:19:08（UTC+8）
- 协议 ID：`m6-csi800-model-attribution-engineering-v1`
- 机器真身：`config/m6_csi800_model_attribution_engineering_v1.yaml`
- 阶段：`RESULT_BLIND_ENGINEERING_ONLY`

## 1. 目标与权限

M6-1 只证明 M6-0 的三臂比较可以按冻结合同确定性运行、裁决和复核，不回答哪一臂真实更好。允许编写
工程代码、读取 Qlib manifest 与交易日历、实例化但不拟合真实 Qlib 模型，并使用完全合成数据运行。

不允许读取 Qlib 特征/价格、真实标签或效果，不允许真实训练、预测、回测、实验账本写入、前瞻、模拟
仓或生产。运行时断网，不读取 `.env`，Tushare/DeepSeek 调用均为 0。依赖构建可使用现有 Docker 缓存
和冻结依赖源，但运行容器必须 `network_mode=none`。

## 2. 架构边界

新增 `shaiwei.research.model_attribution` 独立包，按职责拆分：

- `contract`：冻结协议、哈希与项目内路径；
- `clock`：11交易日标签成熟和六窗口边界；
- `models`：LightGBM/Ridge 工厂及可注入训练适配器；
- `scoring`：成员日键、RankIC、50/50排名融合和组合转换指标；
- `inference`：NW(10)、Holm、成本/回撤门与唯一终态；
- `synthetic`：确定性合成预演、write-once 报告；
- `audit`：不导入 `inference` 的独立复算。

不得继续扩大 `backtest/baseline.py`、`research/g1.py` 或科创50效果模块。每个新增生产模块常态不超过
400 行，禁止新增依赖和万能工具文件。真实效果 runner 只留窄接口，不在 M6-1 读取真实输入。

## 3. 合成工程门

固定 seed `20260806`，每个 W1—W6 生成 210 个成熟评分日、每日 40 个纯合成 instrument；不得包含
真实证券代码、行情值或封存效果。预演必须覆盖五个互斥终态：

1. `MODEL_STRUCTURE_SUPPORTED`；
2. `PORTFOLIO_CONVERSION_BOTTLENECK_INDICATED`；
3. `FEATURE_INFORMATION_BOTTLENECK_INDICATED`；
4. `MIXED_NOT_CONCLUSIVE`；
5. `BLOCKED`。

还必须证明：恰好两个替代假设、三臂成员日键完全一致、非有限值和覆盖不足失败关闭、标签成熟日逐窗
精确、单边 NW(10)+Holm 两假设可复算、裁决优先级唯一、输出路径不能逃逸、同身份不同内容禁止覆盖。

## 4. Docker 和证据

新增一次性 `m6-model-attribution-engineering` research profile。镜像内含已提交代码，宿主只挂载：

- Qlib manifest（只读）；
- Qlib 交易日历（只读）；
- M6 engineering 输出目录（唯一可写）。

禁止挂载整仓、`.env`、Docker socket、业务账本或行情/特征目录。容器须非 root、只读根、cap drop all、
no-new-privileges、断网。正式合成报告无运行时间字段；首遍与复跑物理 SHA 必须相同，第二遍只能复用；
独立 auditor 重建后 PASS。Git 只提交脱敏 manifest、代码、测试、协议、状态和验收文档。

## 5. 终态和停止条件

只有合同、时钟、三臂工厂、统计、五类终态、失败路径、双跑哈希和独立审计全部通过，M6-1 才能
`GO_ENGINEERING_ONLY`。任何缺项都是 `BLOCKED`，不能降级成 GO。

无论工程门结果如何，策略始终 `NOT_EVALUATED`，生产授权始终 `none`。GO 后立即停在 M6-2 真实
release 前；M6-0/M6-1 授权不得继承，真实训练、标签/效果读取和回测必须由新的完整 scope 与用户明确
授权开启。

# M6-2 中证800模型归因真实 release 协议（结果前冻结）

- 冻结时间：2026-08-06 21:09:12（UTC+8）
- 协议 ID：`m6-csi800-model-attribution-real-release-v1`
- 机器真身：`config/m6_csi800_model_attribution_real_release_v1.yaml`
- 当前阶段：`RESULT_BLIND_REAL_RELEASE_PREPARATION_ONLY`

## 1. 本节点做什么

M6-2 先把 M6-0 的真实比较做成一个可精确授权、只能运行一次、可独立复核的 release。本节点允许
实现 runner/auditor、纯合成测试、构建不可变镜像和生成 release scope；在完整 scope SHA 获得用户
明确批准前，不读取 Qlib 特征、价格、真实标签或任何 M6 效果，不拟合模型、不预测、不回测、不写
正式效果产物或实验账本。

M6-0 的研究问题和所有门槛不变；M6-1 的工程 GO 只作为上游能力证据，不自动授权效果运行。真实结果
仍只是模型结构、组合转换或特征信息瓶颈的资源排序证据，不是因果证明或生产替换授权。

## 2. 三臂和唯一变化量

三个臂仍为清洗后原参数 LightGBM 控制、固定 `Ridge(alpha=1.0, fit_intercept=false,
include_valid=false)` 和两者每日横截面百分位排名 50/50 融合。每窗只拟合 LightGBM 与 Ridge 两个
模型，融合不训练第三个模型；禁止网格、多 seed、第三臂、权重搜索、新因子或组合参数变体。

W1—W6、Alpha158、`t+1` 开盘进入/`t+11` 开盘退出标签、train/valid 末 11 个信号日 purge、
Top30/`n_drop=3`/10 交易日、1 亿元研究账户、中证800基准、开平仓费率和最低费用逐项继承 M6-0。
每窗三个臂共享同一个已拟合 Alpha158 handler 和完全相同的成员日键。

## 3. 真实指标的操作化

- RankIC 只使用不晚于冻结 test 末日完成 `t+11` 退出开盘的信号日；每天至少 30 个有效截面。
- 三臂 prediction member-day 键必须完全相等；禁止 inner join 静默缩样本。
- 日净策略收益为 Qlib `return - multiplier × recorded_cost`；日净主动收益为
  `(1+净策略收益)/(1+benchmark)-1`，主要配对差为替代臂减控制臂。
- 1.5x/2.0x 沿用旧 Stage0 的可归因口径：在同一组 base 交易上缩放 Qlib 已记录的每日成本，不另跑
  交易路径；这避免成本场景意外改变持仓，也明确意味着最低费用包含在被缩放的 recorded cost 中。
- 累计净超额分别复利策略与基准后相除；换手取 base report 的 `turnover` 或 `total_turnover` 逐日和；
  回撤取净策略 NAV，不取主动 NAV。
- “Top30 重合”只表示每 10 个交易步的信号 Top30 集合交集比例，不冒充实际成交或持仓重合。

主要检验仍是 W1—W6 按时间拼接后的日净主动收益差，单边 Newey-West(10)，且只对 Ridge 与固定融合
两个假设做 Holm 0.05。六窗口、三个成本档和压力期不是新增尝试。

## 4. 压力期

2017 继续显示 `NOT_EVALUABLE_NO_PRE_2017_FROZEN_MODEL`。2024-01~02 从 W6 base backtest 截取；
2026H1 使用冻结的 W6 模型作一次额外预测和 base-cost 回测，并明确标注 stale-model diagnostic。
压力结果不参与新增假设计数，只进入冻结的最大回撤门。

## 5. 两遍、产物与独立复核

获批后 runner 只调用一次，但内部必须串行完成 `first_pass` 和 `replay` 两个完整 pass。每个 pass 独立
重建 handler、拟合两个模型、生成三臂预测和固定回测；模型规范文本/系数、预测和标签、base backtest
日报、信号 Top30、2026H1 压力产物及 summary 全部 write-once。两遍规范 bundle、数值数组和模型身份
必须一致。

独立 auditor 是第二个进程，不导入主 `inference`，从两遍产物重算成员日键、RankIC、分数相关、
成本、主动收益、换手、回撤、NW(10)、Holm 和唯一终态，并核对 release/approval。只有 audit PASS 后
才可把两个替代假设写入 `ledger/experiments.csv`；第一次真实效果读取即消耗恰好 2 次尝试，之后即使
工程失败也不得递补第三臂或以同一 release 重跑。

## 6. Docker 与资源边界

专属 `compose.m6-attribution.yaml` 只定义一次性 runner/auditor。运行时断网、非 root、只读根、drop
ALL capabilities、no-new-privileges、无 `.env`、无 Docker socket、无整仓和生产账本挂载；runner
只读挂载完整 Qlib provider、release scope 和 approval，唯一写入 M6 effect 目录。auditor 不挂载
Qlib，只读 effect、单独写 audit。

资源上限为 6 CPU、12 GiB、256 pids，W1—W6 串行；不得在 scheduler 保护窗口内启动，也不得重建、
重启或修改生产 scheduler。镜像构建可使用冻结依赖源，真实运行外部调用为 0。

## 7. release 与批准语义

实现必须先提交并推送，再构建不可变镜像。release scope 至少绑定：协议/M6-1 哈希、实现 Git、代码
bundle、镜像 ID/发布快照、Qlib manifest/tree、交易日历、命令、挂载、资源和输出路径。scope 的种类
固定为 `REAL_EFFECT_RELEASE_READY_NOT_EXECUTION_APPROVAL`。

批准文件保存在项目内 Git 忽略控制目录，必须逐字绑定完整 release scope SHA 和动作
`M6_REAL_EFFECT_ONCE_WITH_INTERNAL_REPLAY_AND_INDEPENDENT_AUDIT`。旧授权、M6-0/M6-1 权限或仅说
“继续”都不能替代对最终完整 SHA 的明确批准；任一 scope 漂移使批准失效。

## 8. 当前停止线

当前只授权协议、实现、合成验证、镜像与 scope 生成。完成 release readiness 后必须停下并报告完整
scope SHA；在用户明确批准前，策略保持 `NOT_EVALUATED`，生产授权为 `none`。

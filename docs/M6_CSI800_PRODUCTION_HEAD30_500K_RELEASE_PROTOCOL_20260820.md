# M6-5B：生产 Head30 的 50 万元账户 release 工程协议

日期：2026-08-20（UTC+8）

状态：`RESULT_BLIND_RELEASE_ENGINEERING_ONLY`

## 结果目标

把 M6-5A 已冻结的 50 万元账户口径建设成一次性、可审计的真实历史回放入口。最终用于回答：经过
整数股、最低佣金、公司行为、开盘可成交性、现金和容量限制后，已经通过研究尺度审计的生产 Head30，
在个人账户尺度是否仍可执行并保持历史效果。

本节点不读取结果，也不允许为了得到正收益修改策略。真实回放前仍必须停下，由用户绑定精确 scope
SHA 和冻结动作另行批准。

## 权威事实与复用边界

1. 目标证券、顺序和调仓日期只取自 R2 五件封存效果；first-pass 与 replay 必须完全一致。
2. 账务、费用、整数股、公司行为和开盘合法性只调用既有 `paper-v1` 的 `execute_day`，禁止复制第二套。
3. 原始批次仅提供 `daily/index_daily/stock_basic/namechange/suspend_d/dividend/trade_cal`；release scope
   固定精确批次 manifest，后续新增账本行不得改变本次输入。
4. 容量只使用信号日前 20 个有效成交额，不得读取执行日成交额决定当日能否成交。
5. 独立 auditor 只挂载最终输出，不挂 R2、原始批次或主 runner，独立复算会计、统计门和裁决。

## 一次性运行

- runner 恰好一次，内部完整执行 `first_pass` 和 `replay`。
- 首次读取真实目标、价格或效果时消费本家族恰好 1 个尝试；失败也消费，不得同 scope 重跑。
- first-pass/replay 必须物理内容一致，随后才允许唯一独立 auditor。
- 结果只允许 `BLOCKED / CAPITAL_FEASIBLE_RESEARCH_ONLY / CAPITAL_INFEASIBLE`，三者均不授权生产。

## 隔离与失败关闭

- 镜像固定为 `shaiwei:m6-head30-500k-release-v1`，运行时断网、只读根、非 root、无 Docker socket。
- 不读取 `.env`，不调用外网，不写实验账本、模拟仓、Web 或 scheduler。
- 原始数据、R2 和 manifest 只读；effect/audit 使用新的 Git 忽略、预先存在、不可覆盖目录。
- 输入哈希、文件集合、目标身份、交易日、会计、确定性或独立审计任一不完整即 `BLOCKED`。

## 工程完成定义

- 协议 loader、release/scope/approval 合同、原始批次窄读取器、runner、内部 replay、独立 auditor 完成。
- 纯合成 fixture 覆盖可行、资金不可行、容量失败、身份篡改、重复运行和 auditor 对抗路径。
- Docker daemon 真实创建断网 fixture，且不挂载任何真实 R2 或原始批次。
- `make architecture-check`、全仓测试、Ruff、compileall、pip check、Compose 与脱敏检查通过。
- 精确 scope 推送后停止，等待用户按下述动作授权：
  `M6_HEAD30_500K_FEASIBILITY_ONCE_WITH_REPLAY_AND_INDEPENDENT_AUDIT`。

# M3-3 三自建池机械 Top2 独立审查终版验收

日期：2026-08-02（UTC+8）

裁决：`STOP_M3_3_REVIEW_CONTRACT`

策略有效性：`NOT_EVALUATED`

M3-4 验证/G1 协议授权：`false`

生产授权：`none`

## 结论

M3-3 没有完成结果盲委员会审查，不能进入 M3-4，也不能解封 2023—2025 验证、压力期或 G1。
用户批准的固定批次原计划为两条机械 Top2 × 四个固定角色、恰好 8 个响应；第 1 个
`deepseek-v4-pro` 响应完成传输后，机器门检出 `provider_finish_reason_invalid`，在 schema 和自由文本
语义检查前按结果前协议立即停止。

该响应没有有效角色结论，机器报告的 `candidate_decisions` 为空。不能据此表述第一条候选已被经济
拒绝或通过，第二条候选也没有被审查；权威结论仅到“本批审查合同失败、停止”。按冻结规则，这一
完成响应计数，不补发、不续跑剩余 7 份、不换角色、不改提示、不递补其他候选。两条原公式与方向
均未改变。

## 调用与费用

- 用户明确批准向 DeepSeek 发送固定两条公式、非权威假设与公开知识摘要、三池定义和四角色问题；
  不发送发现指标、行情原始数据、证券清单、封存结果、持仓或其他凭据。
- 实际完成响应 `1/8`；传输为 1 个 STARTED + 1 个 HTTP 200 COMPLETED，执行器没有补发或重试。
- 实际估算费用 `0.003200730000 USD`，低于 `0.25 USD` 本批硬上限；停止后没有继续消耗额度。
- 2023—2025 封存验证、压力期、G1、模型、回测、组合、信号和生产均未读取或运行。

## 结果前与运行隔离

- 结果前协议、预执行实现和 live release 分别先行提交；live release 固定候选、角色、顺序、载荷、
  价格、8 响应上限和 0.25 USD 熔断。
- 正式调用前的无网络、无密钥 Docker 预检为 PASS：候选 2、请求 8、两份专属账本 0 数据行、
  `provider_calls=0`、`api_key_read=false`、未解析发现指标、未读取封存结果。
- live 容器只接收项目 `.env` 中的 `DEEPSEEK_API_KEY`，不接收 Tushare、飞书或其他变量；请求正文
  只来自已冻结的脱敏载荷。断网复核容器没有密钥，也没有外部网络。

## 证据与幂等

- 终态报告 SHA-256：`257e50d88fa3ecdc93a9fc35626a5e7c97c89977b921cbdf616b752d0e6123a8`。
- 专属 review/transport 账本 SHA-256：`0352eec4...7db8` / `e533e5fe...4888`。
- 4 个不可变请求/响应/原始/审查 manifest 证据的规范 bundle SHA-256：
  `bd5dafce4c32d1a6cd5b698bf66a2871ab51e16f5d2dc89f4b0df11f3830a3b9`。
- M3-2 manifest 与尝试账本哈希仍为 `1a22bef6...98198` / `84d65566...e344`；原 24 次发现与机械
  Top2 没有被改写。
- 两次无密钥断网复核均返回 `idempotent_reuse=true / external_api_calls_this_run=0`；终态报告、
  两份账本和 M3-2 尝试账本哈希保持不变。

## 范围、秘密与生产

- `sealed_validation_read=false`、`stress_or_g1_run=false`、
  `model_backtest_portfolio_or_signal_run=false`、`new_candidates_generated=false`，生产授权仍为 `none`。
- 主控没有查看响应叙事，只使用机器状态、计数、哈希与空候选裁决归档终态。
- DeepSeek key 没有进入镜像、Git、请求正文、响应证据、账本、报告或日志；断网复核没有接收密钥。
- scheduler 始终保持原容器 `fd8e96152b53`、原镜像 `sha256:de87ec74...0261`、原创建时间和
  running/healthy，未重启。

## 验证与下一步

执行前已通过 M3 专项 37 PASS、全仓 486 PASS、Ruff、compileall、pip check、Compose、diff-check、
账本追加约束、凭据卫生和断网预检。终态追加后 M3 审查专项 14 PASS、全仓 488 PASS，Ruff、
compileall、pip check、diff-check、JSON、凭据卫生再次通过；结果以终版 manifest 与 Git 提交为准。

本批没有通过，因此**不允许另立 M3-4 验证/G1 协议**。若未来重新研究，只能由用户另行决定并建立
新的结果前研究批次；不得补发本批第 1 份、从第 2 份续跑、修改输出长度或提示后回救、替换候选，
也不得使用剩余额度静默重启。M3-0 数据与规则门 GO、M3-2 发现期 Top2 锁定均保持原结论；本批只
阻断这次结果盲审查通路。

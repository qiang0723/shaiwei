# P0 前瞻影子当前版本完整验收

> 裁定时间：2026-07-22（Asia/Shanghai）
>
> 受控代码快照：`c5c5ce55826edfc0d6fa816fa85c3aeb8cdaa8a6be504fdbd9edb5db1a140cc9`
>
> 结论：**核心任务 PASS；通知通道 WARN；P0 3/3 完成。**

## 验收边界

- `20260716` 信号使用锁竞争修复前代码快照，只作为先导证据，不计正式次数。
- 正式计数固定为 `20260717 → 20260720`、`20260720 → 20260721`、`20260721 → 20260722`。
- 只认追加式 ledger、不可变信号/对账产物及其 SHA-256；`forward_report.json` 的 `trial_ready` 不单独构成验收依据。
- 飞书告警通道故障按冻结语义不得改变核心任务退出码；原始失败必须保留，并以之后真实 PASS 事件证明通道恢复。

## 三次正式闭环

| 信号 → 对账 | 日增量 | 信号 | 对账 | 代码快照 | 信号关联 | 通知 |
|---|---|---|---|---|---|---|
| `20260717 → 20260720` | PASS | PASS | PASS | 一致 | SHA-256 一致 | 5 PASS |
| `20260720 → 20260721` | PASS | PASS | PASS | 一致 | SHA-256 一致 | 4 PASS / 1 FAIL，后续恢复 |
| `20260721 → 20260722` | PASS | PASS | PASS | 一致 | SHA-256 一致 | 4 PASS / 1 FAIL，后续恢复 |

三次日增量、信号和对账账本的 `operator` 均为 `docker-scheduler`，没有人工补账或修数。

## 第三次闭环实证

- 日增量：`20260722`，5 个市场批次、15,615 行，状态 PASS，数据快照 `ecc1677e18248ca32d38c84a09064cf4daafaa30d03bc0cfff04dbd39f9791c6`。
- 当日新增：8 个原始批次、21,150 行；逐文件行数和 SHA-256 重算一致，`.BJ` 行数为 0。
- 门禁：S1-S9 PASS，S10 NOT_APPLICABLE，`required_failures=[]`。
- 对账：`20260721 → 20260722` PASS；信号哈希 `c84a80351f1e7b22a5f5f7f6a56b3429edf191b5d541b5f874bbd7fffeddc064` 与上期影子运行账本一致。
- 对账产物：`data/shadow/reconciliations/20260721-20260722-c84a80351f1e.json`，SHA-256 `05704819a7e437a8cdd96f6d23a92413fe8b198c87a32ad2304ab577985a118d`。
- 本日非调仓：30 个目标持仓观察行，实际交易腿 0，换手 0，预计成本 0；平均绝对开盘偏差 1.7414%。`executable_count=0` 的分母为实际交易腿，不代表行情缺失。
- 新信号：`20260722` 状态 PASS、`on_time=true`、`rebalance_due=false`；信号 SHA-256 `3eef24f0d52ce08a220ea2be20ec37df9d8b0f2a577f322c607660851f7fd512`，manifest 自校验通过。

## 幂等与恢复

完成后受控执行一次 `docker compose run --rm shaiwei python -m shaiwei.pipeline.scheduler --once`，返回：

```json
{"generated_signal": false, "reconciled_trade_days": [], "signal_trade_date": "20260722", "status": "NOOP"}
```

重复运行前后保持不变：

- `ingest_batches.csv` 66,364 行（含表头），SHA-256 `40cdf5805193421fd84d0e6e0ba3fea9808a28b1d2d69a49d487f0c195ce38fe`
- `daily_runs.csv` 6 行，SHA-256 `beb34c045a1d092eda339978d21dcbec8a2c8889f08d10ef42e57b7164edc1b9`
- `shadow_runs.csv` 6 行，SHA-256 `f22b59cf18b6ab216e73b29c8490fb9ac1d078fe700ac2fe2faf9582b96da2c6`
- `shadow_reconciliations.csv` 5 行，SHA-256 `82de4dee0fcad7c842f0e5b0553c51cf3459396b2d9d75960e813054ab3abb02`
- `experiments.csv` 719 行，SHA-256 `48ffa2dbf2434dab09689f73276ada7023ad8e96e664abaab58c072240f0b47a`
- 信号 5 份、对账产物 4 份、`feishu_20260722.jsonl` 5 行，数量和内容不变。

`logs/shadow/forward_report.json` 是可再生汇总，重复运行只刷新 `generated_at`，不属于不可变验收产物。

## 通知 WARN 与后续动作

- 2026-07-21：`daily_catchup_started` 一次 `NETWORK_TimeoutError`；随后 4 个通知事件 PASS。
- 2026-07-22：`daily_catchup_passed` 一次 `NETWORK_TimeoutError`；随后对账、信号开始和信号完成 3 个事件 PASS。
- 两次失败均未改变核心任务结果，也未人工补发或覆盖原记录；后续真实 PASS 证明通道恢复。
- 连续两个交易日出现网络超时，已从“单次外部抖动”升级为验收后健壮性欠账。下一步先评估并实现有界重试、幂等消息身份、重复消息风险控制和恢复状态留痕；回归通过后再启动 P0.5 模拟组合。
